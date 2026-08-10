"""Сетка группового этапа, собранная из сыгранных матчей.

Заполнять её руками нельзя: раунд идёт полтора часа, а данные обновляются раз в
сутки автоматически. Поэтому сетка выводится из матчей, которые уже есть в базе,
и никакого отдельного источника результатов не заводится.

Как определяется, что матч относится к групповому этапу: обе команды —
участники TI15 и матч сыгран не раньше первого дня турнира. League id для этого
не нужен (на момент написания он ещё не существовал), а квалификации и
товарищеские отсекаются датой.

Как определяется раунд. В Swiss команда играет ровно одну серию за раунд,
поэтому номер раунда серии — это число серий, сыгранных её участниками до неё.
Серии перебираются в хронологическом порядке, записи команд накапливаются, и
каждая серия попадает в раунд и в группу «по записи на входе» (0-0, 1-0, 0-1 и
так далее) — ровно так, как их рисует сетка турнира.

Серия, а не карта: в Bo3 три матча, и считать их как три победы было бы
неверно. Матчи склеиваются по series_key, победитель серии — тот, кто выиграл
больше карт.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
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
class Series:
    """Одна серия сетки: кто с кем, с каким счётом и в каком раунде."""

    round: int
    record: str
    left: Side
    right: Side
    winner_id: int | None
    played_at: date
    match_ids: tuple[int, ...]

    @property
    def decided(self) -> bool:
        return self.winner_id is not None


@dataclass(slots=True)
class Standing:
    team_id: int
    name: str
    wins: int = 0
    losses: int = 0

    @property
    def record(self) -> str:
        return f"{self.wins}-{self.losses}"


@dataclass(slots=True)
class GroupStage:
    """Разобранный групповой этап: серии по раундам и таблица."""

    series: list[Series] = field(default_factory=list)
    standings: list[Standing] = field(default_factory=list)

    def rounds(self) -> dict[int, list[Series]]:
        by_round: dict[int, list[Series]] = defaultdict(list)
        for item in self.series:
            by_round[item.round].append(item)
        return dict(sorted(by_round.items()))


def _utc(moment: datetime) -> datetime:
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def build_group_stage(
    session: Session,
    teams: dict[int, str],
    *,
    starts: date | None,
) -> GroupStage:
    """Собрать сетку по матчам между участниками, сыгранным с начала турнира."""
    if not teams or starts is None:
        return GroupStage(standings=[Standing(tid, name) for tid, name in teams.items()])

    query = (
        select(Match)
        .where(
            Match.radiant_team_id.in_(teams),
            Match.dire_team_id.in_(teams),
        )
        .order_by(Match.start_time)
    )

    # Карты в серии: победитель серии — тот, у кого больше выигранных карт.
    by_series: dict[str, list[Match]] = defaultdict(list)
    for match in session.scalars(query):
        if _utc(match.start_time).date() < starts:
            continue
        if match.radiant_team_id == match.dire_team_id:
            continue
        by_series[match.series_key].append(match)

    played: dict[int, tuple[int, int]] = {team_id: (0, 0) for team_id in teams}
    series: list[Series] = []

    for maps in sorted(by_series.values(), key=lambda ms: _utc(ms[0].start_time)):
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

        # Раунд — по числу уже сыгранных серий. Если команды разошлись (перенос
        # матча, техническое поражение), берётся больший: сетка рисуется по
        # раундам, и серия должна попасть в тот, где она реально стоит.
        rounds_played = max(sum(played[left_id]), sum(played[right_id]))
        record = f"{played[left_id][0]}-{played[left_id][1]}"

        decided = wins[left_id] != wins[right_id]
        winner_id = (left_id if wins[left_id] > wins[right_id] else right_id) if decided else None

        series.append(
            Series(
                round=rounds_played + 1,
                record=record,
                left=Side(left_id, teams[left_id], wins[left_id]),
                right=Side(right_id, teams[right_id], wins[right_id]),
                winner_id=winner_id,
                played_at=_utc(first.start_time).date(),
                match_ids=tuple(m.match_id for m in maps),
            )
        )

        if decided:
            loser_id = right_id if winner_id == left_id else left_id
            played[winner_id] = (played[winner_id][0] + 1, played[winner_id][1])
            played[loser_id] = (played[loser_id][0], played[loser_id][1] + 1)

    standings = sorted(
        (Standing(tid, name, *played[tid]) for tid, name in teams.items()),
        key=lambda s: (-s.wins, s.losses, s.name),
    )
    return GroupStage(series=series, standings=standings)
