"""Серии между участниками турнира — общий разбор матчей для группы и сетки.

Обе стадии читают одну и ту же базу и задают ей один и тот же вопрос: кто с кем
сыграл серию, с каким счётом и когда. Различаются они тем, что делают с ответом:
групповой этап раскладывает серии по раундам Swiss, плей-офф — по местам сетки.
Поэтому разбор карт в серии живёт здесь, а не в каждой стадии по-своему.

Серия, а не карта: в Bo3 три матча, и считать их тремя победами неверно. Карты
склеиваются по series_key, победитель серии — тот, кто выиграл больше карт.
Равный счёт означает, что серия догружена не полностью (вторую карту Bo3 ещё не
разобрали), и победителя у неё нет — выдумывать его нельзя, от него посчитается
следующий раунд.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db.models import Match


@dataclass(frozen=True, slots=True)
class Side:
    team_id: int
    name: str
    score: int


@dataclass(frozen=True, slots=True)
class PlayedSeries:
    """Сыгранная серия: две стороны, счёт по картам и время начала."""

    left: Side
    right: Side
    winner_id: int | None
    started_at: datetime
    match_ids: tuple[int, ...]

    @property
    def played_at(self) -> date:
        return self.started_at.date()

    @property
    def decided(self) -> bool:
        return self.winner_id is not None

    @property
    def team_ids(self) -> frozenset[int]:
        return frozenset({self.left.team_id, self.right.team_id})

    @property
    def loser_id(self) -> int | None:
        if self.winner_id is None:
            return None
        return self.right.team_id if self.winner_id == self.left.team_id else self.left.team_id


def utc(moment: datetime) -> datetime:
    """SQLite отдаёт naive datetime — приводим к UTC, иначе сравнения падают."""
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def collect_series(
    session: Session,
    teams: dict[int, str],
    *,
    since: date | None = None,
    exclude_match_ids: frozenset[int] = frozenset(),
) -> list[PlayedSeries]:
    """Серии между командами `teams`, сыгранные не раньше `since`.

    `exclude_match_ids` отсекает карты, уже разобранные другой стадией: те же
    восемь команд играли и в группе, и в сетке, а Iron Wing — Team Spirit в
    четвертьфинале и в третьем раунде Swiss — это разные серии.
    """
    if not teams:
        return []

    query = (
        select(Match)
        .where(
            Match.radiant_team_id.in_(teams),
            Match.dire_team_id.in_(teams),
        )
        .order_by(Match.start_time)
    )

    by_series: dict[str, list[Match]] = defaultdict(list)
    for match in session.scalars(query):
        if since is not None and utc(match.start_time).date() < since:
            continue
        if match.match_id in exclude_match_ids:
            continue
        if match.radiant_team_id == match.dire_team_id:
            continue
        by_series[match.series_key].append(match)

    series: list[PlayedSeries] = []
    for maps in sorted(by_series.values(), key=lambda ms: utc(ms[0].start_time)):
        first = maps[0]
        left_id, right_id = first.radiant_team_id, first.dire_team_id
        if left_id is None or right_id is None:
            continue

        wins = {left_id: 0, right_id: 0}
        for game in maps:
            if game.radiant_win is None:
                continue
            winner = game.radiant_team_id if game.radiant_win else game.dire_team_id
            if winner in wins:
                wins[winner] += 1

        decided = wins[left_id] != wins[right_id]
        winner_id = (left_id if wins[left_id] > wins[right_id] else right_id) if decided else None

        series.append(
            PlayedSeries(
                left=Side(left_id, teams[left_id], wins[left_id]),
                right=Side(right_id, teams[right_id], wins[right_id]),
                winner_id=winner_id,
                started_at=utc(first.start_time),
                match_ids=tuple(m.match_id for m in maps),
            )
        )
    return series
