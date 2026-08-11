"""OpenDota JSON → канонический матч.

Адаптер намеренно тонкий: разбор статов уже написан и покрыт тестами в
`ingest/stat_mapping.py`, и дублировать его здесь означало бы завести вторую
версию правды про `camps_stacked` и лотосы. Задача этого модуля — только форма и
провенанс.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from app.core.model import CanonicalMatch, DraftPick, PlayerGame
from app.core.provenance import Provenance, Source, describe
from app.ingest.stat_mapping import (
    STAT_SOURCES,
    extract_player_stats,
    extract_profile_stats,
    is_parsed,
    series_key,
)


def _to_datetime(unix_time: Any) -> datetime:
    return datetime.fromtimestamp(int(unix_time or 0), tz=timezone.utc)


def _int_or_none(value: Any) -> int | None:
    return None if value is None else int(value)


# Провенанс одинаков для всех игроков карты: источник у неё общий, а таблица
# доступности не зависит от игрока. Считаем один раз на процесс.
_OPENDOTA_PROVENANCE: dict[str, Provenance] = {
    stat: describe(stat, Source.OPENDOTA) for stat in STAT_SOURCES
}


def _draft(match: Mapping[str, Any]) -> tuple[DraftPick, ...]:
    """Пики и баны, если OpenDota их отдала.

    У части матчей `picks_bans` отсутствует (нераспарсенные, а также урезанные
    фикстуры) — это «источник не знает», и пустой драфт здесь честнее выдуманного.
    Таймингов и резервного времени в OpenDota нет ни у одного матча: они приедут
    только из реплея.
    """
    rows = match.get("picks_bans") or []
    picks: list[DraftPick] = []
    for row in rows:
        hero_id = row.get("hero_id")
        if hero_id is None:
            continue
        # `or` здесь нельзя: order нулевой у первого бана, и он бы провалился
        # в запасной вариант, сместив весь драфт на один ход.
        order = row.get("order")
        picks.append(
            DraftPick(
                order=int(order) if order is not None else len(picks),
                is_pick=bool(row.get("is_pick")),
                hero_id=int(hero_id),
                # team: 0 — Radiant, 1 — Dire.
                is_radiant=int(row.get("team") or 0) == 0,
            )
        )
    return tuple(sorted(picks, key=lambda p: p.order))


def _player(payload: Mapping[str, Any], match: Mapping[str, Any], *, detailed: bool) -> PlayerGame:
    is_radiant = payload.get("isRadiant")
    if is_radiant is None:
        is_radiant = int(payload.get("player_slot") or 0) < 128
    is_radiant = bool(is_radiant)

    radiant_win = match.get("radiant_win")
    won = None if radiant_win is None else (bool(radiant_win) is is_radiant)

    team_id = match.get("radiant_team_id") if is_radiant else match.get("dire_team_id")

    # У нераспарсенного матча статов нет вовсе — не нули, а отсутствие. Пустые
    # словари не дадут посчитать по такой карте очки и не притворятся нулевой игрой.
    fantasy = extract_player_stats(payload) if detailed else {}
    profile = extract_profile_stats(payload) if detailed else {}

    return PlayerGame(
        account_id=_int_or_none(payload.get("account_id")),
        hero_id=_int_or_none(payload.get("hero_id")),
        player_slot=int(payload.get("player_slot") or 0),
        is_radiant=is_radiant,
        team_id=_int_or_none(team_id),
        won=won,
        lane_role=_int_or_none(payload.get("lane_role")),
        fantasy=fantasy,
        profile=profile,
        provenance=dict(_OPENDOTA_PROVENANCE) if detailed else {},
    )


def from_opendota(match: Mapping[str, Any]) -> CanonicalMatch:
    """Разложить ответ `GET /api/matches/{id}` в канонический матч."""
    detailed = is_parsed(match)

    return CanonicalMatch(
        match_id=int(match["match_id"]),
        start_time=_to_datetime(match.get("start_time")),
        duration=int(match.get("duration") or 0),
        series_key=series_key(match),
        # Нераспарсенный матч не даёт ни одного стата, поэтому источников у него
        # нет: факт игры для рейтинга есть, а измерений — нет.
        sources=frozenset({Source.OPENDOTA}) if detailed else frozenset(),
        players=tuple(_player(p, match, detailed=detailed) for p in match.get("players") or []),
        league_id=_int_or_none(match.get("leagueid")),
        league_name=(match.get("league") or {}).get("name") or match.get("league_name"),
        series_type=_int_or_none(match.get("series_type")),
        radiant_team_id=_int_or_none(
            match.get("radiant_team_id") or (match.get("radiant_team") or {}).get("team_id")
        ),
        dire_team_id=_int_or_none(
            match.get("dire_team_id") or (match.get("dire_team") or {}).get("team_id")
        ),
        radiant_win=match.get("radiant_win"),
        patch=_int_or_none(match.get("patch")),
        first_blood_time=_int_or_none(match.get("first_blood_time")),
        draft=_draft(match),
    )
