"""Загрузка матчей из OpenDota в локальную базу.

Принцип, который стоит соблюдать во всём пайплайне: данные пишутся ровно так,
как они были на момент матча, без обратной правки. Любая агрегация (рейтинг,
проекция) считается поверх, хронологически, и не имеет права видеть будущее —
иначе получится модель, которая прекрасно "предсказывает" уже сыгранное.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db.models import IngestState, Match, Player, PlayerMatchStat, Team
from .opendota import OpenDotaClient
from .stat_mapping import (
    STATS_VERSION,
    extract_player_stats,
    extract_profile_stats,
    is_parsed,
    series_key,
)

log = logging.getLogger(__name__)


def _to_datetime(unix_time: Any) -> datetime:
    return datetime.fromtimestamp(int(unix_time or 0), tz=timezone.utc)


def upsert_team(session: Session, team_id: int | None, payload: dict[str, Any]) -> Team | None:
    """Создать или обновить команду. Матчи без team_id (сборные) пропускаются."""
    if not team_id:
        return None
    team = session.get(Team, team_id)
    if team is None:
        team = Team(team_id=team_id, name=payload.get("name") or f"team {team_id}")
        session.add(team)
    if payload.get("name"):
        team.name = payload["name"]
    if payload.get("tag"):
        team.tag = payload["tag"]
    if payload.get("logo_url"):
        team.logo_url = payload["logo_url"]
    return team


def upsert_player(session: Session, account_id: int, name: str | None) -> Player:
    player = session.get(Player, account_id)
    if player is None:
        player = Player(account_id=account_id, name=name)
        session.add(player)
    elif name and not player.name:
        player.name = name
    return player


def upsert_match(session: Session, match: dict[str, Any]) -> Match:
    """Сохранить матч и статы всех идентифицированных игроков.

    Идемпотентно: повторный вызов обновляет существующие строки, а не плодит
    дубликаты, — важно, потому что матч может доехать до парсинга уже после
    первого забора.
    """
    match_id = int(match["match_id"])
    parsed = is_parsed(match)

    radiant_team = match.get("radiant_team") or {}
    dire_team = match.get("dire_team") or {}
    radiant_id = match.get("radiant_team_id") or radiant_team.get("team_id")
    dire_id = match.get("dire_team_id") or dire_team.get("team_id")

    upsert_team(session, radiant_id, {"name": match.get("radiant_name"), **radiant_team})
    upsert_team(session, dire_id, {"name": match.get("dire_name"), **dire_team})

    row = session.get(Match, match_id)
    start_time = _to_datetime(match.get("start_time"))
    if row is None:
        row = Match(match_id=match_id, start_time=start_time, series_key=series_key(match))
        session.add(row)

    row.start_time = start_time
    row.duration = int(match.get("duration") or 0)
    row.league_id = match.get("leagueid")
    row.league_name = (match.get("league") or {}).get("name") or match.get("league_name")
    row.series_key = series_key(match)
    row.series_type = match.get("series_type")
    row.radiant_team_id = radiant_id
    row.dire_team_id = dire_id
    row.radiant_win = match.get("radiant_win")
    row.patch = match.get("patch")
    row.is_parsed = parsed
    row.stats_version = STATS_VERSION
    first_blood = match.get("first_blood_time")
    row.first_blood_time = int(first_blood) if first_blood is not None else None

    if not parsed:
        # Без разобранного реплея статов игроков нет — записываем только факт матча,
        # он всё ещё пригоден для рейтинга команд.
        log.debug("матч %s не распарсен, статы игроков пропущены", match_id)
        return row

    existing = {
        stat.account_id: stat
        for stat in session.scalars(
            select(PlayerMatchStat).where(PlayerMatchStat.match_id == match_id)
        )
    }

    for player_payload in match.get("players") or []:
        account_id = player_payload.get("account_id")
        if account_id is None:
            continue
        account_id = int(account_id)
        upsert_player(
            session, account_id, player_payload.get("name") or player_payload.get("personaname")
        )

        is_radiant = player_payload.get("isRadiant")
        if is_radiant is None:
            is_radiant = (player_payload.get("player_slot") or 0) < 128
        team_id = radiant_id if is_radiant else dire_id
        won = None
        if match.get("radiant_win") is not None:
            won = bool(match["radiant_win"]) == bool(is_radiant)

        stat = existing.get(account_id)
        if stat is None:
            stat = PlayerMatchStat(match_id=match_id, account_id=account_id)
            session.add(stat)

        stat.team_id = team_id
        stat.hero_id = player_payload.get("hero_id")
        stat.is_radiant = bool(is_radiant)
        stat.won = won
        stat.lane_role = player_payload.get("lane_role")
        stat.stats = extract_player_stats(player_payload)
        stat.profile = extract_profile_stats(player_payload)
        stat.start_time = start_time

    return row


async def ingest_matches(
    client: OpenDotaClient,
    session: Session,
    match_ids: Iterable[int],
    *,
    concurrency: int = 4,
    skip_existing_parsed: bool = True,
) -> dict[str, int]:
    """Забрать матчи по списку id и записать в базу."""
    wanted = [int(m) for m in match_ids]
    if skip_existing_parsed:
        # Пропускаем только матчи, записанные текущим набором полей. Матч из
        # старой версии перечитывается: он уже разобран, но без ассистов и
        # нетворта, и без перезабора профиль игрока остался бы неполным.
        known_parsed = set(
            session.scalars(
                select(Match.match_id).where(
                    Match.match_id.in_(wanted),
                    Match.is_parsed.is_(True),
                    Match.stats_version >= STATS_VERSION,
                )
            )
        )
        wanted = [m for m in wanted if m not in known_parsed]

    if not wanted:
        return {"requested": 0, "parsed": 0, "unparsed": 0, "failed": 0}

    matches, failed = await client.matches(wanted, concurrency=concurrency)
    parsed_count = 0
    for match in matches:
        if not match.get("match_id"):
            continue
        row = upsert_match(session, match)
        parsed_count += int(row.is_parsed)
    session.flush()

    if failed:
        log.warning("не загрузилось %d матчей из %d", len(failed), len(wanted))

    return {
        "requested": len(wanted),
        "parsed": parsed_count,
        "unparsed": len(matches) - parsed_count,
        "failed": len(failed),
    }


async def ingest_pro_feed(
    client: OpenDotaClient,
    session: Session,
    *,
    days_back: int = 90,
    max_pages: int = 40,
    league_ids: Sequence[int] | None = None,
) -> dict[str, int]:
    """Пройти ленту про-матчей назад во времени и забрать полные тела матчей.

    `/proMatches` отдаёт по 100 записей и листается курсором `less_than_match_id`.
    Полное тело матча запрашивается отдельно — это и есть основной расход лимита,
    поэтому фильтруем по времени и (опционально) по лигам до запроса деталей.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)
    league_filter = set(league_ids or ())

    collected: list[int] = []
    cursor: int | None = None
    for _ in range(max_pages):
        page = await client.pro_matches(cursor)
        if not page:
            break
        for entry in page:
            if _to_datetime(entry.get("start_time")) < cutoff:
                cursor = None
                break
            if league_filter and entry.get("leagueid") not in league_filter:
                continue
            collected.append(int(entry["match_id"]))
        else:
            cursor = int(page[-1]["match_id"])
            continue
        break

    log.info("лента про-матчей: отобрано %d матчей за %d дней", len(collected), days_back)
    result = await ingest_matches(client, session, collected)

    state = session.get(IngestState, "pro_feed_last_run")
    if state is None:
        state = IngestState(key="pro_feed_last_run")
        session.add(state)
    state.value = datetime.now(timezone.utc).isoformat()
    state.updated_at = datetime.now(timezone.utc)

    return result


async def ingest_team_history(
    client: OpenDotaClient,
    session: Session,
    team_id: int,
    *,
    days_back: int = 120,
    limit: int = 100,
) -> dict[str, int]:
    """Забрать историю конкретной команды — точечно, для участников TI."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)
    history = await client.team_matches(team_id)
    match_ids = [
        int(m["match_id"])
        for m in history[:limit]
        if _to_datetime(m.get("start_time")) >= cutoff
    ]
    return await ingest_matches(client, session, match_ids)


@dataclass(frozen=True, slots=True)
class TeamMatchCandidate:
    """Результат сопоставления названия из компендиума с командой OpenDota."""

    compendium_name: str
    team_id: int | None
    opendota_name: str | None
    matched_via: str | None
    matches: int
    last_match_time: int | None
    exact: bool


async def resolve_compendium_teams(
    client: OpenDotaClient,
    session: Session,
    names: Sequence[str],
    aliases: Mapping[str, Sequence[str]] | None = None,
) -> list[TeamMatchCandidate]:
    """Сопоставить названия команд из компендиума с team_id OpenDota.

    Часть участников Valve показывает под изменёнными названиями (BoomBoys вместо
    BetBoom, Huligani вместо L1ga и т.д.), поэтому поиск идёт по названию из
    компендиума и по всем алиасам из конфига.

    Совпадение по имени неточное по своей природе: организации переименовываются,
    в базе OpenDota полно мёртвых тёзок. Поэтому среди кандидатов предпочтение
    отдаётся команде, которая недавно играла, а результат возвращается с деталями
    для глазной сверки, а не молча записывается как истина.
    """
    aliases = aliases or {}
    all_teams = await client.teams()
    by_name: dict[str, list[dict[str, Any]]] = {}
    for team in all_teams:
        key = (team.get("name") or "").casefold().strip()
        by_name.setdefault(key, []).append(team)

    def activity(team: dict[str, Any]) -> tuple[int, int]:
        return (
            int(team.get("last_match_time") or 0),
            int(team.get("wins") or 0) + int(team.get("losses") or 0),
        )

    resolved: list[TeamMatchCandidate] = []
    for name in names:
        search_names = [name, *aliases.get(name, ())]
        best: dict[str, Any] | None = None
        matched_via: str | None = None
        exact = False

        for candidate_name in search_names:
            needle = candidate_name.casefold().strip()
            exact_hits = by_name.get(needle, [])
            if exact_hits:
                best = max(exact_hits, key=activity)
                matched_via, exact = candidate_name, True
                break

        if best is None:
            for candidate_name in search_names:
                needle = candidate_name.casefold().strip()
                partial = [
                    t
                    for key, group in by_name.items()
                    if needle in key or key in needle
                    for t in group
                ]
                if partial:
                    best = max(partial, key=activity)
                    matched_via = candidate_name
                    break

        if best is None:
            resolved.append(
                TeamMatchCandidate(name, None, None, None, 0, None, False)
            )
            continue

        team_id = int(best["team_id"])
        team = upsert_team(session, team_id, best)
        if team is not None:
            team.compendium_name = name

        resolved.append(
            TeamMatchCandidate(
                compendium_name=name,
                team_id=team_id,
                opendota_name=best.get("name"),
                matched_via=matched_via,
                matches=int(best.get("wins") or 0) + int(best.get("losses") or 0),
                last_match_time=best.get("last_match_time"),
                exact=exact,
            )
        )

    return resolved
