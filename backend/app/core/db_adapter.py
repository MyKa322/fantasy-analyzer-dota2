"""Строки БД → канонический матч.

Второй адаптер после OpenDota, и именно он оправдывает канонический слой: фичи и
аналитика читают матч одинаково независимо от того, пришёл он из API только что
или лежит в базе с прошлого месяца.

Провенанс восстанавливается из колонок `source` / `stat_sources`: основной
источник строки плюс точечные отклонения по отдельным статам.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import timezone

from app.core.model import CanonicalMatch, PlayerGame
from app.core.provenance import Provenance, Source, describe
from app.db.models import Match, PlayerMatchStat


def _utc(moment):
    """SQLite отдаёт naive datetime — приводим к UTC, иначе арифметика падает."""
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def _source(value: str | None) -> Source:
    try:
        return Source(value or Source.OPENDOTA.value)
    except ValueError:
        # Незнакомое значение в колонке — не повод падать на чтении: считаем
        # источник самым слабым из известных, и провенанс честно это покажет.
        return Source.OPENDOTA


def _provenance(stat_row: PlayerMatchStat) -> dict[str, Provenance]:
    primary = _source(stat_row.source)
    overrides = stat_row.stat_sources or {}
    return {
        stat: describe(stat, _source(overrides.get(stat)) if stat in overrides else primary)
        for stat in (stat_row.stats or {})
    }


def _player(stat_row: PlayerMatchStat, match: Match) -> PlayerGame:
    is_radiant = bool(stat_row.is_radiant)
    return PlayerGame(
        account_id=int(stat_row.account_id),
        hero_id=stat_row.hero_id,
        # В базе слот не хранится — восстанавливаем сторону, а не выдумываем номер.
        player_slot=0 if is_radiant else 128,
        is_radiant=is_radiant,
        team_id=stat_row.team_id,
        won=stat_row.won,
        lane_role=stat_row.lane_role,
        fantasy=dict(stat_row.stats or {}),
        profile=dict(stat_row.profile or {}),
        provenance=_provenance(stat_row),
    )


def from_db(match: Match, stats: Iterable[PlayerMatchStat] | None = None) -> CanonicalMatch:
    """Собрать канонический матч из строки `matches` и её статов.

    `stats` можно передать явно, чтобы не дёргать ленивую связь по одному матчу
    в цикле — на полутора тысячах матчей это разница между секундой и минутой.
    """
    rows: Sequence[PlayerMatchStat] = list(
        stats if stats is not None else (match.player_stats or [])
    )

    sources: set[Source] = set()
    if rows:
        sources.add(Source.OPENDOTA if not match.replay_parsed else Source.REPLAY)
        for row in rows:
            sources.add(_source(row.source))
            for value in (row.stat_sources or {}).values():
                sources.add(_source(value))

    return CanonicalMatch(
        match_id=int(match.match_id),
        start_time=_utc(match.start_time),
        duration=int(match.duration or 0),
        series_key=match.series_key,
        sources=frozenset(sources),
        players=tuple(_player(row, match) for row in rows),
        league_id=match.league_id,
        league_name=match.league_name,
        series_type=match.series_type,
        radiant_team_id=match.radiant_team_id,
        dire_team_id=match.dire_team_id,
        radiant_win=match.radiant_win,
        patch=match.patch,
        first_blood_time=match.first_blood_time,
        is_lan=match.is_lan,
        stats_version=int(match.stats_version or 0),
    )
