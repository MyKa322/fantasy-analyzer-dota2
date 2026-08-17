"""Тесты сетки плей-офф: структура double elimination и разбор сыгранного."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.analytics.playoff_bracket import (
    BRACKET,
    FEEDS,
    QUARTERFINALS,
    SLOT_KEYS,
    Source,
    build_playoff_bracket,
)
from app.db.models import Base, Match

STARTS = date(2026, 8, 21)
DAY = datetime(2026, 8, 21, 10, 0, tzinfo=timezone.utc)

# id = посев: 1 и 2 играют первый четвертьфинал, 3 и 4 — второй и так далее.
TEAMS = {i: f"Team {i}" for i in range(1, 9)}
QF_PAIRS = ((1, 2), (3, 4), (5, 6), (7, 8))


@pytest.fixture()
def session() -> Session:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def add_series(
    session: Session,
    *,
    key: str,
    left: int,
    right: int,
    results: list[bool],
    hours: float = 0.0,
) -> None:
    for index, left_won in enumerate(results):
        session.add(
            Match(
                match_id=int(f"{abs(hash(key)) % 100_000}{index}"),
                start_time=DAY + timedelta(hours=hours, minutes=index * 40),
                duration=2400,
                series_key=key,
                radiant_team_id=left,
                dire_team_id=right,
                radiant_win=left_won,
                is_parsed=True,
            )
        )
    session.flush()


def build(session: Session, **kwargs) -> object:
    return build_playoff_bracket(session, TEAMS, QF_PAIRS, starts=STARTS, **kwargs)


# --- структура ----------------------------------------------------------------


def test_bracket_is_fourteen_series_of_double_elimination():
    assert len(BRACKET) == len(SLOT_KEYS) == 14
    assert len({spec.key for spec in BRACKET}) == 14


def test_every_slot_but_the_quarterfinals_knows_where_its_teams_come_from():
    for spec in BRACKET:
        expected = 0 if spec.key in QUARTERFINALS else 2
        assert len(spec.sources) == expected, spec.key


def test_each_result_goes_to_exactly_one_place():
    """Победитель и проигравший каждой серии попадают ровно в одно место.

    Кроме тех, кому дальше некуда: проигравший гранд-финала — второй, а
    проигравшие нижней сетки вылетают.
    """
    for spec in BRACKET:
        for winner in (True, False):
            targets = FEEDS.get(Source(spec.key, winner), ())
            assert len(targets) <= 1, f"{spec.key}: исход ведёт в {targets}"


def test_the_lower_bracket_takes_every_upper_bracket_loser():
    losers = {source.slot for source in FEEDS if not source.winner}
    assert losers == {"ubqf1", "ubqf2", "ubqf3", "ubqf4", "ubsf1", "ubsf2", "ubf"}


# --- заполнение ---------------------------------------------------------------


def test_before_the_first_series_only_the_quarterfinals_have_teams(session):
    bracket = build(session)

    assert bracket.started is False
    assert [m.left.team_id for m in bracket.matches if m.key in QUARTERFINALS] == [1, 3, 5, 7]
    assert bracket.by_key("ubsf1").left is None
    # Но известно, кто там может оказаться: победители первых двух четвертьфиналов.
    assert bracket.by_key("ubsf1").candidates == (1, 2, 3, 4)
    assert bracket.by_key("gf").candidates == tuple(range(1, 9))


def test_a_played_quarterfinal_fills_the_next_round(session):
    add_series(session, key="qf1", left=1, right=2, results=[True, True])

    bracket = build(session)
    quarterfinal = bracket.by_key("ubqf1")

    assert quarterfinal.winner_id == 1
    assert quarterfinal.left.score == 2 and quarterfinal.right.score == 0
    assert bracket.by_key("ubsf1").left.team_id == 1, "победитель ушёл в полуфинал"
    assert bracket.by_key("lbr1_1").left.team_id == 2, "проигравший — в нижнюю сетку"


def test_series_before_the_playoffs_are_not_part_of_the_bracket(session):
    """Те же восемь команд играли между собой в группе — сетку это не касается."""
    add_series(session, key="swiss", left=1, right=2, results=[True], hours=-72)

    bracket = build(session)

    assert bracket.started is False
    assert bracket.by_key("ubqf1").winner_id is None


def test_maps_already_counted_by_the_group_stage_are_skipped(session):
    """Тот же день, но карта уже разобрана групповым этапом — значит, не сетка."""
    add_series(session, key="qf1", left=1, right=2, results=[True, True])
    played = [row.match_id for row in session.query(Match).all()]

    bracket = build(session, exclude_match_ids=played)

    assert bracket.by_key("ubqf1").winner_id is None


def test_an_unusual_pairing_still_finds_its_round(session):
    """Разводка нижней сетки может отличаться от предполагаемой.

    Проигравшие четвертьфиналов сведены «1-4» вместо «1-2», и это не повод
    оставить раунд пустым: обе команды могли оказаться в этом раунде.
    """
    add_series(session, key="qf1", left=1, right=2, results=[True], hours=0)
    add_series(session, key="qf2", left=3, right=4, results=[True], hours=1)
    add_series(session, key="qf3", left=5, right=6, results=[True], hours=2)
    add_series(session, key="qf4", left=7, right=8, results=[True], hours=3)
    # Ожидалось 2 — 4 и 6 — 8, сыграли 2 — 8 и 4 — 6.
    add_series(session, key="lb1", left=2, right=8, results=[True], hours=5)
    add_series(session, key="lb2", left=4, right=6, results=[True], hours=6)

    bracket = build(session)

    assert bracket.unplaced == 0
    lower = {m.key: m for m in bracket.matches if m.round == "lbr1"}
    assert {m.winner_id for m in lower.values()} == {2, 4}


def test_a_full_bracket_gives_places_and_a_champion(session):
    """Сетка целиком: восемь команд, четырнадцать серий, места с первого по 7-8."""
    plan = [
        ("ubqf1", 1, 2, True),
        ("ubqf2", 3, 4, True),
        ("ubqf3", 5, 6, True),
        ("ubqf4", 7, 8, True),
        ("ubsf1", 1, 3, True),
        ("ubsf2", 5, 7, True),
        ("lbr1_1", 2, 4, True),
        ("lbr1_2", 6, 8, True),
        ("ubf", 1, 5, True),
        ("lbr2_1", 7, 2, False),
        ("lbr2_2", 3, 6, True),
        ("lbsf", 2, 3, True),
        ("lbf", 5, 2, True),
        ("gf", 1, 5, True),
    ]
    for index, (key, left, right, left_won) in enumerate(plan):
        add_series(session, key=key, left=left, right=right, results=[left_won], hours=index)

    bracket = build(session)
    places = {run.team_id: run.place for run in bracket.teams}

    assert bracket.unplaced == 0
    assert all(match.decided for match in bracket.matches)
    assert bracket.champion_id() == 1
    assert places[1] == "1"
    assert places[5] == "2"
    assert places[2] == "3"
    assert places[3] == "4"
    assert {places[6], places[7]} == {"5-6"}
    assert {places[4], places[8]} == {"7-8"}


def test_a_team_carries_its_record_and_next_series(session):
    add_series(session, key="qf1", left=1, right=2, results=[True, False, True])

    bracket = build(session)
    runs = {run.team_id: run for run in bracket.teams}

    assert runs[1].series_won == 1 and runs[1].maps_won == 2 and runs[1].maps_lost == 1
    assert runs[1].bracket == "upper" and runs[1].next_slot == "ubsf1"
    assert runs[2].series_lost == 1 and runs[2].bracket == "lower"
    assert runs[2].next_slot == "lbr1_1", "проигравший играет дальше в нижней сетке"


def test_an_unfinished_series_takes_its_place_but_decides_nothing(session):
    """Половина Bo3 в базе: место занято, победителя нет, дальше никто не идёт."""
    add_series(session, key="qf1", left=1, right=2, results=[True, False])

    bracket = build(session)

    assert bracket.by_key("ubqf1").winner_id is None
    assert bracket.by_key("ubsf1").left is None
    assert bracket.results() == {}


def test_the_grand_final_is_longer_than_the_rest(session):
    bracket = build(session, best_of=3, grand_final_best_of=5)
    assert bracket.by_key("gf").best_of == 5
    assert bracket.by_key("ubqf1").best_of == 3
