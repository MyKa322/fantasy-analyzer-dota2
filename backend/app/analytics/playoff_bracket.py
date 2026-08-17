"""Сетка плей-офф: структура double elimination и то, что в ней уже сыграно.

Структура сетки — единственный источник правды на весь модуль плей-офф: по ней
рисуется страница, по ней же идёт симуляция (`simulate.BracketSimulator`) и
считаются 14 предсказаний компендиума. Две копии этой схемы разошлись бы в
первый же вечер, когда проигравший верхнего полуфинала попал бы в разные места
нижней сетки у страницы и у прогноза.

Как заполняется. Четвертьфиналы верхней сетки объявлены заранее и лежат в
конфиге; всё остальное выводится из сыгранных матчей. Серия попадает на своё
место так: у каждого места известно, откуда приходят участники («победитель
ubqf1», «проигравший ubsf2»), и как только оба источника решены, участники
места известны — остаётся найти серию с такой парой.

Отдельно разбирается случай, когда пара сошлась не по предполагаемой разводке.
Порядок пар первого раунда нижней сетки Valve объявляет вместе с сеткой, но
экран его не показывает, поэтому здесь он выведен по классической схеме
(проигравшие сводятся из противоположных половин). Если реальная пара окажется
другой, серия всё равно встанет на место того же раунда: место принимает её,
если обе команды входят в число тех, кто в принципе может там оказаться. Так
сетка переживает расхождение с догадкой вместо того, чтобы оставить раунд пустым
и потерять всё, что за ним.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy.orm import Session

from .series import PlayedSeries, Side, collect_series

log = logging.getLogger(__name__)

# Стороны сетки — по ним страница раскладывает раунды на две ленты.
UPPER = "upper"
LOWER = "lower"
GRAND = "grand"

# Положение команды в сетке: без поражений, с одним, вылетела, чемпион.
CHAMPION = "champion"
OUT = "out"


@dataclass(frozen=True, slots=True)
class Source:
    """Откуда приходит участник места: победитель или проигравший другой серии."""

    slot: str
    winner: bool

    def __str__(self) -> str:
        return f"{'W' if self.winner else 'L'}({self.slot})"


@dataclass(frozen=True, slots=True)
class SlotSpec:
    """Место в сетке: раунд, позиция сверху вниз и откуда приходят участники.

    У четвертьфиналов верхней сетки источников нет — их пары объявлены.
    """

    key: str
    round: str
    side: str
    order: int
    sources: tuple[Source, ...] = ()
    #: Проигравший здесь заканчивает турнир на этом месте.
    elimination_place: str | None = None


def _w(slot: str) -> Source:
    return Source(slot, winner=True)


def _l(slot: str) -> Source:
    return Source(slot, winner=False)


# Порядок важен вдвойне: он и хронологический (место не считается раньше тех,
# от кого зависит), и тот, в котором сетка читается сверху вниз.
BRACKET: tuple[SlotSpec, ...] = (
    SlotSpec("ubqf1", "ubqf", UPPER, 1),
    SlotSpec("ubqf2", "ubqf", UPPER, 2),
    SlotSpec("ubqf3", "ubqf", UPPER, 3),
    SlotSpec("ubqf4", "ubqf", UPPER, 4),
    SlotSpec("ubsf1", "ubsf", UPPER, 1, (_w("ubqf1"), _w("ubqf2"))),
    SlotSpec("ubsf2", "ubsf", UPPER, 2, (_w("ubqf3"), _w("ubqf4"))),
    SlotSpec("lbr1_1", "lbr1", LOWER, 1, (_l("ubqf1"), _l("ubqf2")), "7-8"),
    SlotSpec("lbr1_2", "lbr1", LOWER, 2, (_l("ubqf3"), _l("ubqf4")), "7-8"),
    SlotSpec("ubf", "ubf", UPPER, 1, (_w("ubsf1"), _w("ubsf2"))),
    # Проигравшие полуфиналов уходят в противоположную половину нижней сетки:
    # иначе пара сыграла бы дважды подряд.
    SlotSpec("lbr2_1", "lbr2", LOWER, 1, (_l("ubsf2"), _w("lbr1_1")), "5-6"),
    SlotSpec("lbr2_2", "lbr2", LOWER, 2, (_l("ubsf1"), _w("lbr1_2")), "5-6"),
    SlotSpec("lbsf", "lbsf", LOWER, 1, (_w("lbr2_1"), _w("lbr2_2")), "4"),
    SlotSpec("lbf", "lbf", LOWER, 1, (_l("ubf"), _w("lbsf")), "3"),
    SlotSpec("gf", "gf", GRAND, 1, (_w("ubf"), _w("lbf")), "2"),
)

SLOT_KEYS: tuple[str, ...] = tuple(spec.key for spec in BRACKET)
SPEC_BY_KEY: dict[str, SlotSpec] = {spec.key: spec for spec in BRACKET}

#: Места, участники которых заданы объявленной сеткой, в порядке пар конфига.
QUARTERFINALS: tuple[str, ...] = ("ubqf1", "ubqf2", "ubqf3", "ubqf4")

#: Кто кого кормит: (место, победитель?) -> места, куда попадает эта команда.
FEEDS: dict[Source, tuple[str, ...]] = {}
for _spec in BRACKET:
    for _source in _spec.sources:
        FEEDS[_source] = (*FEEDS.get(_source, ()), _spec.key)


def best_of_for(key: str, *, best_of: int, grand_final_best_of: int) -> int:
    return grand_final_best_of if key == "gf" else best_of


@dataclass(slots=True)
class BracketMatch:
    """Место сетки вместе с тем, что в нём уже произошло."""

    key: str
    round: str
    side: str
    order: int
    best_of: int
    left: Side | None = None
    right: Side | None = None
    winner_id: int | None = None
    played_at: date | None = None
    match_ids: tuple[int, ...] = ()
    #: Кто ещё может здесь оказаться, пока участники не определились.
    candidates: tuple[int, ...] = ()

    @property
    def decided(self) -> bool:
        return self.winner_id is not None

    @property
    def loser_id(self) -> int | None:
        if self.winner_id is None or self.left is None or self.right is None:
            return None
        return (
            self.right.team_id if self.winner_id == self.left.team_id else self.left.team_id
        )

    def team_ids(self) -> tuple[int, ...]:
        return tuple(side.team_id for side in (self.left, self.right) if side is not None)


@dataclass(slots=True)
class TeamRun:
    """Путь команды по сетке: где она сейчас и чем всё кончилось."""

    team_id: int
    name: str
    series_won: int = 0
    series_lost: int = 0
    maps_won: int = 0
    maps_lost: int = 0
    #: upper — ещё без поражений, lower — одно, out — вылетела.
    bracket: str = UPPER
    #: Итоговое место, когда путь окончен: «1», «2», «3», «4», «5-6», «7-8».
    place: str | None = None
    #: Ближайшая серия, если команда ещё играет.
    next_slot: str | None = None


@dataclass(slots=True)
class PlayoffBracket:
    matches: list[BracketMatch] = field(default_factory=list)
    teams: list[TeamRun] = field(default_factory=list)
    #: Серии между участниками, которым не нашлось места, — сигнал о расхождении.
    unplaced: int = 0

    @property
    def started(self) -> bool:
        return any(match.match_ids for match in self.matches)

    def by_key(self, key: str) -> BracketMatch:
        return next(match for match in self.matches if match.key == key)

    def results(self) -> dict[str, int]:
        """Решённые места: {ключ -> team_id победителя}. Вход для симуляции."""
        return {m.key: m.winner_id for m in self.matches if m.winner_id is not None}

    def champion_id(self) -> int | None:
        return self.by_key("gf").winner_id


def _possible_participants(
    key: str, participants: Mapping[str, list[int | None]], memo: dict[str, frozenset[int]]
) -> frozenset[int]:
    """Все команды, которые ещё могут оказаться на месте `key`.

    Известный участник даёт себя одного, нерешённый источник — всех, кто может
    оказаться в серии, откуда он придёт (и победитель, и проигравший той серии
    приходят из одного и того же множества участников).
    """
    if key in memo:
        return memo[key]

    spec = SPEC_BY_KEY[key]
    memo[key] = frozenset()  # защита от цикла, которого в корректной сетке нет
    result: set[int] = set()
    for index, known in enumerate(participants[key]):
        if known is not None:
            result.add(known)
        elif index < len(spec.sources):
            result |= _possible_participants(spec.sources[index].slot, participants, memo)
    memo[key] = frozenset(result)
    return memo[key]


def build_playoff_bracket(
    session: Session,
    teams: Mapping[int, str],
    quarterfinals: Sequence[tuple[int, int]],
    *,
    starts: date | None,
    best_of: int = 3,
    grand_final_best_of: int = 5,
    exclude_match_ids: Iterable[int] = (),
) -> PlayoffBracket:
    """Собрать сетку: объявленные четвертьфиналы плюс всё, что уже сыграно.

    До первой серии сетка не пустая, а расставленная: четвертьфиналы известны,
    остальные места ждут участников. Это не украшение — по этой же структуре
    считаются вероятности, и место без участников всё равно имеет смысл («кто
    может здесь оказаться»).
    """
    matches = [
        BracketMatch(
            key=spec.key,
            round=spec.round,
            side=spec.side,
            order=spec.order,
            best_of=best_of_for(
                spec.key, best_of=best_of, grand_final_best_of=grand_final_best_of
            ),
        )
        for spec in BRACKET
    ]
    by_key = {match.key: match for match in matches}
    # Разводка и реальность держатся отдельно. `routed` — кого сюда ведёт схема;
    # `actual` — кто вышел. Расходятся они ровно в том случае, ради которого
    # написан запасной разбор ниже, и тогда разводка всё ещё нужна: по ней
    # считается, кто вообще играет этот раунд.
    routed: dict[str, list[int | None]] = {spec.key: [None, None] for spec in BRACKET}
    actual: dict[str, list[int | None]] = {spec.key: [None, None] for spec in BRACKET}

    names = dict(teams)
    for announced, key in zip(quarterfinals, QUARTERFINALS, strict=False):
        routed[key] = [int(announced[0]), int(announced[1])]
        actual[key] = list(routed[key])

    bracket = PlayoffBracket(matches=matches)
    if not quarterfinals:
        return bracket

    def place(key: str, series: PlayedSeries) -> None:
        """Поставить серию на место и раздать её исход дальше по сетке."""
        match = by_key[key]
        match.left, match.right = series.left, series.right
        match.winner_id = series.winner_id
        match.played_at = series.played_at
        match.match_ids = series.match_ids
        actual[key] = [series.left.team_id, series.right.team_id]

        if series.winner_id is None:
            return
        for source, team_id in (
            (Source(key, True), series.winner_id),
            (Source(key, False), series.loser_id),
        ):
            for target in FEEDS.get(source, ()):
                index = SPEC_BY_KEY[target].sources.index(source)
                routed[target][index] = team_id
                actual[target][index] = team_id

    def round_pool(round_key: str) -> frozenset[int]:
        """Кто играет этот раунд — по разводке, а не по конкретным парам."""
        memo: dict[str, frozenset[int]] = {}
        pool: set[int] = set()
        for spec in BRACKET:
            if spec.round == round_key:
                pool |= _possible_participants(spec.key, routed, memo)
        # Те, кто уже отыграл свою серию раунда, второй раз в нём не играют.
        played = {
            team
            for spec in BRACKET
            if spec.round == round_key and by_key[spec.key].match_ids
            for team in by_key[spec.key].team_ids()
        }
        return frozenset(pool - played)

    def ready(key: str) -> bool:
        return all(by_key[source.slot].decided for source in SPEC_BY_KEY[key].sources)

    for series in collect_series(
        session,
        dict(names),
        since=starts,
        exclude_match_ids=frozenset(exclude_match_ids),
    ):
        pair = series.team_ids
        free = [m.key for m in matches if not m.match_ids]

        # Сначала точное совпадение: у места оба участника известны и это они.
        exact = next(
            (key for key in free if set(filter(None, actual[key])) == pair),
            None,
        )
        if exact is not None:
            place(exact, series)
            continue

        # Иначе — первое свободное место раунда, который эти двое как раз
        # играют. Так серия встаёт на место, даже если Valve свела пары не так,
        # как предполагает разводка: раунд от этого не меняется.
        fallback = next(
            (key for key in free if ready(key) and pair <= round_pool(SPEC_BY_KEY[key].round)),
            None,
        )
        if fallback is None:
            bracket.unplaced += 1
            log.warning(
                "серия %s — %s не встала в сетку плей-офф",
                series.left.name,
                series.right.name,
            )
            continue
        log.info(
            "серия %s — %s поставлена на %s по составу раунда, а не по разводке",
            series.left.name,
            series.right.name,
            fallback,
        )
        place(fallback, series)

    # Кто ещё может оказаться на нерешённых местах — для подписи пустой строки.
    memo: dict[str, frozenset[int]] = {}
    for match in matches:
        if match.match_ids:
            continue
        match.candidates = tuple(sorted(_possible_participants(match.key, actual, memo)))
        known = actual[match.key]
        match.left = Side(known[0], names.get(known[0], str(known[0])), 0) if known[0] else None
        match.right = Side(known[1], names.get(known[1], str(known[1])), 0) if known[1] else None

    bracket.teams = _team_runs(matches, names, actual)
    return bracket


def _team_runs(
    matches: Sequence[BracketMatch],
    names: Mapping[int, str],
    participants: Mapping[str, list[int | None]],
) -> list[TeamRun]:
    """Путь каждой команды: победы, поражения, где играет дальше и какое место."""
    runs: dict[int, TeamRun] = {}
    for key in QUARTERFINALS:
        for team_id in participants[key]:
            if team_id is not None:
                runs[team_id] = TeamRun(team_id, names.get(team_id, str(team_id)))

    for match in matches:
        if match.left is None or match.right is None:
            continue
        for side, other in ((match.left, match.right), (match.right, match.left)):
            run = runs.get(side.team_id)
            if run is None:
                continue
            run.maps_won += side.score
            run.maps_lost += other.score
        if not match.decided:
            continue
        winner = runs.get(match.winner_id)  # type: ignore[arg-type]
        loser = runs.get(match.loser_id)  # type: ignore[arg-type]
        if winner is not None:
            winner.series_won += 1
            if match.key == "gf":
                winner.bracket = CHAMPION
                winner.place = "1"
        if loser is not None:
            loser.series_lost += 1
            spec = SPEC_BY_KEY[match.key]
            if spec.elimination_place is not None:
                loser.bracket = OUT
                loser.place = spec.elimination_place
            else:
                loser.bracket = LOWER

    # Где команда играет дальше: первое нерешённое место, где она уже стоит.
    for match in matches:
        if match.decided:
            continue
        for team_id in participants[match.key]:
            run = runs.get(team_id) if team_id is not None else None
            if run is not None and run.place is None and run.next_slot is None:
                run.next_slot = match.key

    return sorted(
        runs.values(),
        key=lambda r: (r.place is not None, -r.series_won, r.series_lost, r.name),
    )
