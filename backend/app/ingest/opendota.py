"""Асинхронный клиент OpenDota с учётом лимитов и файловым кэшем матчей.

Бесплатный тариф: 60 запросов/мин и 2000/день. Тело разобранного матча весит
1–3 МБ и никогда не меняется после парсинга, поэтому матчи кэшируются на диск —
повторный прогон аналитики не тратит ни одного запроса.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any, Self

import httpx

log = logging.getLogger(__name__)

BASE_URL = "https://api.opendota.com/api"
DEFAULT_RATE_LIMIT_PER_MINUTE = 50  # с запасом от заявленных 60
DEFAULT_TIMEOUT = 60.0

# Ошибки сети и 5xx: их немного и они обычно разовые.
MAX_RETRIES = 4

# 429 — отдельный бюджет и он больше. Практика показала: OpenDota считает лимит
# по-своему, и даже при 50 запросах/мин прилетает серия 429 подряд. Тратить на
# них тот же бюджет, что и на сетевые сбои, — значит ронять часовой ingest из-за
# временного троттлинга.
MAX_RATE_LIMIT_RETRIES = 8
MAX_RATE_LIMIT_BACKOFF = 120.0


class RateLimiter:
    """Скользящее окно: не более `limit` запросов за `period` секунд."""

    def __init__(self, limit: int, period: float = 60.0) -> None:
        self.limit = limit
        self.period = period
        self._timestamps: list[float] = []
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            while True:
                now = time.monotonic()
                self._timestamps = [t for t in self._timestamps if now - t < self.period]
                if len(self._timestamps) < self.limit:
                    self._timestamps.append(now)
                    return
                sleep_for = self.period - (now - self._timestamps[0]) + 0.01
                log.debug("rate limit: ждём %.2fs", sleep_for)
                await asyncio.sleep(sleep_for)


class OpenDotaClient:
    """Тонкая обёртка над публичным API OpenDota.

    Использовать как асинхронный контекстный менеджер:

        async with OpenDotaClient(cache_dir=...) as client:
            match = await client.match(8922016200)
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        cache_dir: Path | str | None = None,
        rate_limit_per_minute: int = DEFAULT_RATE_LIMIT_PER_MINUTE,
        timeout: float = DEFAULT_TIMEOUT,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.api_key = api_key
        self.cache_dir = Path(cache_dir) if cache_dir else None
        if self.cache_dir:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._limiter = RateLimiter(rate_limit_per_minute)
        self._client = client or httpx.AsyncClient(
            base_url=BASE_URL,
            timeout=timeout,
            headers={"User-Agent": "dota2-compendium-analyzer/0.1"},
        )
        self._owns_client = client is None
        self.requests_made = 0
        self.cache_hits = 0
        self.throttle_events = 0

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    # --- низкий уровень -------------------------------------------------------

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        params = dict(params or {})
        if self.api_key:
            params["api_key"] = self.api_key

        last_error: Exception | None = None
        throttled = 0
        attempt = 0
        while attempt < MAX_RETRIES and throttled < MAX_RATE_LIMIT_RETRIES:
            await self._limiter.acquire()
            try:
                response = await self._client.get(path, params=params)
                self.requests_made += 1
                if response.status_code == 429:
                    # 429 не расходует бюджет обычных ретраев: это не сбой, а
                    # просьба подождать. Ждём дольше с каждым разом.
                    delay = min(
                        float(response.headers.get("retry-after", 2 ** (throttled + 1))),
                        MAX_RATE_LIMIT_BACKOFF,
                    )
                    throttled += 1
                    self.throttle_events += 1
                    log.warning(
                        "429 от OpenDota (%d/%d), пауза %.1fs",
                        throttled,
                        MAX_RATE_LIMIT_RETRIES,
                        delay,
                    )
                    await asyncio.sleep(delay)
                    continue
                if response.status_code >= 500:
                    last_error = httpx.HTTPStatusError(
                        f"server error {response.status_code}",
                        request=response.request,
                        response=response,
                    )
                    attempt += 1
                    await asyncio.sleep(2**attempt)
                    continue
                response.raise_for_status()
                return response.json()
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_error = exc
                attempt += 1
                log.warning("сетевая ошибка %s (попытка %d)", exc, attempt)
                await asyncio.sleep(2**attempt)

        reason = "троттлинг" if throttled >= MAX_RATE_LIMIT_RETRIES else "ошибки"
        raise RuntimeError(f"OpenDota: {path} не ответил ({reason})") from last_error

    def _cache_path(self, key: str) -> Path | None:
        if not self.cache_dir:
            return None
        return self.cache_dir / f"{key}.json"

    def _read_cache(self, key: str) -> Any | None:
        path = self._cache_path(key)
        if path and path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                log.warning("битый кэш %s, перезапрашиваем", path)
        return None

    def _write_cache(self, key: str, payload: Any) -> None:
        path = self._cache_path(key)
        if not path:
            return
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)

    # --- эндпоинты ------------------------------------------------------------

    async def pro_matches(self, less_than_match_id: int | None = None) -> list[dict[str, Any]]:
        """Лента про-матчей, 100 штук за запрос, от новых к старым."""
        params = {}
        if less_than_match_id:
            params["less_than_match_id"] = less_than_match_id
        return await self._get("/proMatches", params)

    async def match(self, match_id: int, *, use_cache: bool = True) -> dict[str, Any]:
        """Полное тело матча. Кэшируется: распарсенный матч не меняется."""
        key = f"match_{match_id}"
        if use_cache:
            cached = self._read_cache(key)
            if cached is not None:
                self.cache_hits += 1
                return cached
        payload = await self._get(f"/matches/{match_id}")
        # Кэшируем только разобранные матчи: нераспарсенный может доехать позже.
        if payload.get("version") is not None:
            self._write_cache(key, payload)
        return payload

    async def matches(
        self,
        match_ids: Iterable[int],
        *,
        concurrency: int = 3,
        raise_on_error: bool = False,
    ) -> tuple[list[dict[str, Any]], list[int]]:
        """Пачка матчей с ограничением параллелизма.

        Возвращает `(загруженные матчи, id несработавших)`. Один недоступный матч
        не должен ронять загрузку истории шестнадцати команд — то, что не
        доехало, возвращается списком и просто загрузится в следующий заход.
        """
        semaphore = asyncio.Semaphore(concurrency)
        ids = [int(m) for m in match_ids]

        async def fetch(match_id: int) -> dict[str, Any]:
            async with semaphore:
                return await self.match(match_id)

        results = await asyncio.gather(
            *(fetch(m) for m in ids), return_exceptions=not raise_on_error
        )

        ok: list[dict[str, Any]] = []
        failed: list[int] = []
        for match_id, result in zip(ids, results, strict=True):
            if isinstance(result, BaseException):
                log.warning("матч %s не загрузился: %s", match_id, result)
                failed.append(match_id)
            else:
                ok.append(result)
        return ok, failed

    async def team_matches(self, team_id: int) -> list[dict[str, Any]]:
        return await self._get(f"/teams/{team_id}/matches")

    async def team(self, team_id: int) -> dict[str, Any]:
        return await self._get(f"/teams/{team_id}")

    async def team_players(self, team_id: int) -> list[dict[str, Any]]:
        return await self._get(f"/teams/{team_id}/players")

    async def teams(self) -> list[dict[str, Any]]:
        return await self._get("/teams")

    async def search_teams(self, name: str) -> list[dict[str, Any]]:
        """У OpenDota нет поиска команд — фильтруем полный список локально."""
        all_teams = await self.teams()
        needle = name.casefold().strip()
        exact = [t for t in all_teams if (t.get("name") or "").casefold().strip() == needle]
        if exact:
            return exact
        return [t for t in all_teams if needle in (t.get("name") or "").casefold()]

    async def player_matches(
        self, account_id: int, *, limit: int = 50, **filters: Any
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"limit": limit, **filters}
        return await self._get(f"/players/{account_id}/matches", params)

    async def player(self, account_id: int) -> dict[str, Any]:
        return await self._get(f"/players/{account_id}")

    async def league_matches(self, league_id: int) -> list[dict[str, Any]]:
        return await self._get(f"/leagues/{league_id}/matches")

    async def explorer(self, sql: str) -> dict[str, Any]:
        """Произвольный SQL к базе OpenDota (тяжёлый, использовать точечно)."""
        return await self._get("/explorer", {"sql": sql})

    async def request_parse(self, match_id: int) -> dict[str, Any]:
        """Поставить матч в очередь на парсинг реплея.

        Нужен, если матч важен для анализа, но `version` пустой. Результат
        появляется не мгновенно — перечитывать матч позже.
        """
        await self._limiter.acquire()
        response = await self._client.post(f"/request/{match_id}")
        self.requests_made += 1
        response.raise_for_status()
        return response.json()


async def fetch_parsed_matches(
    client: OpenDotaClient,
    match_ids: Sequence[int],
    *,
    concurrency: int = 4,
) -> tuple[list[dict[str, Any]], list[int]]:
    """Загрузить матчи и отделить разобранные от нераспарсенных.

    Возвращает `(разобранные матчи, id нераспарсенных)` — вторые стоит либо
    отправить в `request_parse`, либо честно исключить из выборки.
    """
    from .stat_mapping import is_parsed

    fetched, _failed = await client.matches(match_ids, concurrency=concurrency)
    parsed = [m for m in fetched if is_parsed(m)]
    unparsed = [int(m["match_id"]) for m in fetched if not is_parsed(m)]
    return parsed, unparsed
