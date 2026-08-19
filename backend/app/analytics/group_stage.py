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

Разбор карт в серии живёт в `series.py`: тот же вопрос — «кто с кем сыграл и с
каким счётом» — задаёт и сетка плей-офф, и ответ у него один на обе стадии.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy.orm import Session

from .series import Side, collect_series

__all__ = ["GroupStage", "Series", "Side", "Standing", "build_group_stage"]


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
    #: Карты, а не серии. Швейцарка сводит команды по сериям, но 4-1 набранное
    #: всухую и то же 4-1 через три решающие карты — разные турниры.
    maps_won: int = 0
    maps_lost: int = 0

    @property
    def record(self) -> str:
        return f"{self.wins}-{self.losses}"

    @property
    def map_record(self) -> str:
        return f"{self.maps_won}-{self.maps_lost}"

    @property
    def map_diff(self) -> int:
        return self.maps_won - self.maps_lost


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


def build_group_stage(
    session: Session,
    teams: dict[int, str],
    *,
    starts: date | None,
    until: date | None = None,
) -> GroupStage:
    """Собрать сетку по матчам между участниками, сыгранным с начала турнира.

    `until` отсекает плей-офф: те же команды играют между собой и в сетке, а
    четвертьфинал — не шестой раунд Swiss. По умолчанию границы нет: пока
    плей-офф не начался, отсекать нечего.
    """
    if not teams or starts is None:
        return GroupStage(standings=[Standing(tid, name) for tid, name in teams.items()])

    played: dict[int, tuple[int, int]] = {team_id: (0, 0) for team_id in teams}
    maps: dict[int, tuple[int, int]] = {team_id: (0, 0) for team_id in teams}
    series: list[Series] = []

    for played_series in collect_series(session, teams, since=starts):
        if until is not None and played_series.played_at >= until:
            continue
        left_id = played_series.left.team_id
        right_id = played_series.right.team_id

        # Раунд — по числу уже сыгранных серий. Если команды разошлись (перенос
        # матча, техническое поражение), берётся больший: сетка рисуется по
        # раундам, и серия должна попасть в тот, где она реально стоит.
        rounds_played = max(sum(played[left_id]), sum(played[right_id]))
        record = f"{played[left_id][0]}-{played[left_id][1]}"

        series.append(
            Series(
                round=rounds_played + 1,
                record=record,
                left=played_series.left,
                right=played_series.right,
                winner_id=played_series.winner_id,
                played_at=played_series.played_at,
                match_ids=played_series.match_ids,
            )
        )

        for side, other in (
            (played_series.left, played_series.right),
            (played_series.right, played_series.left),
        ):
            won, lost = maps[side.team_id]
            maps[side.team_id] = (won + side.score, lost + other.score)

        winner_id = played_series.winner_id
        loser_id = played_series.loser_id
        if winner_id is not None and loser_id is not None:
            played[winner_id] = (played[winner_id][0] + 1, played[winner_id][1])
            played[loser_id] = (played[loser_id][0], played[loser_id][1] + 1)

    # Порядок — по сериям, а при равенстве по разнице карт: это ближайшее к
    # смыслу «кто прошёл этап увереннее» из того, что видно из результатов.
    standings = sorted(
        (Standing(tid, name, *played[tid], *maps[tid]) for tid, name in teams.items()),
        key=lambda s: (-s.wins, s.losses, -s.map_diff, s.name),
    )
    return GroupStage(series=series, standings=standings)
