"""Тесты клиента OpenDota: лимиты, ретраи, кэш, устойчивость к 429.

Регрессия, ради которой написан файл: серия 429 подряд роняла загрузку истории
всех команд на третьей из шестнадцати.
"""

from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from app.ingest.opendota import (
    MAX_RATE_LIMIT_RETRIES,
    OpenDotaClient,
    RateLimiter,
)


@pytest.fixture()
def no_sleep(monkeypatch):
    """Убрать паузы бэкоффа, сохранив настоящий asyncio.sleep для планировщика."""
    real_sleep = asyncio.sleep
    monkeypatch.setattr(asyncio, "sleep", lambda _delay: real_sleep(0))


def make_client(handler, **kwargs) -> OpenDotaClient:
    transport = httpx.MockTransport(handler)
    http = httpx.AsyncClient(transport=transport, base_url="https://api.opendota.com/api")
    return OpenDotaClient(client=http, **kwargs)


def match_payload(match_id: int, *, parsed: bool = True) -> dict:
    return {
        "match_id": match_id,
        "version": 22 if parsed else None,
        "players": [{"account_id": 1, "stuns": 10.0 if parsed else None}],
    }


# --- ограничитель частоты -----------------------------------------------------


@pytest.mark.asyncio
async def test_rate_limiter_allows_burst_within_limit():
    limiter = RateLimiter(limit=5, period=60.0)
    await asyncio.wait_for(
        asyncio.gather(*(limiter.acquire() for _ in range(5))), timeout=1.0
    )


@pytest.mark.asyncio
async def test_rate_limiter_blocks_over_limit():
    limiter = RateLimiter(limit=2, period=30.0)
    await limiter.acquire()
    await limiter.acquire()
    with pytest.raises(TimeoutError):
        await asyncio.wait_for(limiter.acquire(), timeout=0.2)


# --- ретраи -------------------------------------------------------------------


@pytest.mark.asyncio
async def test_retries_after_429(no_sleep):
    """Троттлинг — не ошибка: клиент обязан дождаться и получить данные."""
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] <= 3:
            return httpx.Response(429, headers={"retry-after": "0"})
        return httpx.Response(200, json=match_payload(1))

    client = make_client(handler)
    result = await client.match(1, use_cache=False)

    assert result["match_id"] == 1
    assert calls["n"] == 4
    assert client.throttle_events == 3


@pytest.mark.asyncio
async def test_429_budget_is_larger_than_network_retries(no_sleep):
    """429 не должны расходовать тот же бюджет, что и сетевые сбои."""
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] <= 5:  # больше, чем MAX_RETRIES для обычных ошибок
            return httpx.Response(429, headers={"retry-after": "0"})
        return httpx.Response(200, json=match_payload(7))

    client = make_client(handler)
    assert (await client.match(7, use_cache=False))["match_id"] == 7


@pytest.mark.asyncio
async def test_gives_up_after_persistent_429(no_sleep):

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, headers={"retry-after": "0"})

    client = make_client(handler)
    with pytest.raises(RuntimeError, match="троттлинг"):
        await client.match(1, use_cache=False)
    assert client.throttle_events == MAX_RATE_LIMIT_RETRIES


@pytest.mark.asyncio
async def test_server_errors_do_not_loop_forever(no_sleep):
    """Регрессия: ветка 5xx не инкрементировала счётчик попыток."""
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(503)

    client = make_client(handler)
    with pytest.raises(RuntimeError):
        await asyncio.wait_for(client.match(1, use_cache=False), timeout=5.0)
    assert calls["n"] <= 5


@pytest.mark.asyncio
async def test_retries_transport_errors(no_sleep):
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            raise httpx.ConnectError("boom", request=request)
        return httpx.Response(200, json=match_payload(3))

    client = make_client(handler)
    assert (await client.match(3, use_cache=False))["match_id"] == 3


# --- пачка матчей -------------------------------------------------------------


@pytest.mark.asyncio
async def test_batch_returns_partial_results_on_failure(no_sleep):
    """Один сломанный матч не должен ронять загрузку всей пачки."""

    def handler(request: httpx.Request) -> httpx.Response:
        match_id = int(request.url.path.rsplit("/", 1)[-1])
        if match_id == 2:
            return httpx.Response(429, headers={"retry-after": "0"})
        return httpx.Response(200, json=match_payload(match_id))

    client = make_client(handler)
    ok, failed = await client.matches([1, 2, 3], concurrency=1)

    assert [m["match_id"] for m in ok] == [1, 3]
    assert failed == [2]


@pytest.mark.asyncio
async def test_batch_can_raise_when_asked(no_sleep):

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, headers={"retry-after": "0"})

    client = make_client(handler)
    with pytest.raises(RuntimeError):
        await client.matches([1], concurrency=1, raise_on_error=True)


# --- кэш ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_parsed_match_is_cached(tmp_path):
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(200, json=match_payload(11))

    client = make_client(handler, cache_dir=tmp_path)
    await client.match(11)
    await client.match(11)

    assert calls["n"] == 1
    assert client.cache_hits == 1
    assert json.loads((tmp_path / "match_11.json").read_text(encoding="utf-8"))


@pytest.mark.asyncio
async def test_unparsed_match_is_not_cached(tmp_path):
    """Нераспарсенный матч может доехать позже — кэшировать его нельзя."""
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(200, json=match_payload(12, parsed=False))

    client = make_client(handler, cache_dir=tmp_path)
    await client.match(12)
    await client.match(12)

    assert calls["n"] == 2
    assert not (tmp_path / "match_12.json").exists()


@pytest.mark.asyncio
async def test_corrupt_cache_is_refetched(tmp_path):
    (tmp_path / "match_13.json").write_text("{битый json", encoding="utf-8")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=match_payload(13))

    client = make_client(handler, cache_dir=tmp_path)
    assert (await client.match(13))["match_id"] == 13


# --- поиск команд -------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_teams_prefers_exact_name():
    teams = [
        {"team_id": 1, "name": "Team Spirit"},
        {"team_id": 2, "name": "Team Spirit Academy"},
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=teams)

    client = make_client(handler)
    found = await client.search_teams("Team Spirit")
    assert [t["team_id"] for t in found] == [1]


@pytest.mark.asyncio
async def test_search_teams_falls_back_to_substring():
    teams = [{"team_id": 3, "name": "PARIVISION"}]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=teams)

    client = make_client(handler)
    assert [t["team_id"] for t in await client.search_teams("parivi")] == [3]
