"""Тесты сетки группового этапа, собранной из сыгранных матчей."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.analytics.group_stage import build_group_stage
from app.db.models import Base, Match

STARTS = date(2026, 8, 13)
DAY = datetime(2026, 8, 13, 10, 0, tzinfo=timezone.utc)

TEAMS = {1: "Falcons", 2: "LGD", 3: "Liquid", 4: "VG"}


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
    """Серия из карт: results[i] — выиграла ли левая команда i-ю карту."""
    for index, left_won in enumerate(results):
        session.add(
            Match(
                match_id=int(f"{abs(hash(key)) % 10_000}{index}"),
                start_time=DAY + timedelta(hours=hours, minutes=index * 40),
                duration=2100,
                series_key=key,
                radiant_team_id=left,
                dire_team_id=right,
                radiant_win=left_won,
                is_parsed=True,
            )
        )
    session.flush()


def test_empty_before_the_tournament_starts(session):
    """До первого дня сетки нет, но таблица уже перечисляет всех участников."""
    add_series(session, key="qual", left=1, right=2, results=[True], hours=-72)

    stage = build_group_stage(session, TEAMS, starts=STARTS)

    assert stage.series == [], "матч до старта в сетку не попадает"
    assert {s.name for s in stage.standings} == set(TEAMS.values())
    assert all(s.wins == 0 and s.losses == 0 for s in stage.standings)


def test_a_bo3_counts_as_one_series(session):
    """Три карты — это одна победа, а не три: раунд идёт сериями."""
    add_series(session, key="s1", left=1, right=2, results=[True, False, True])

    stage = build_group_stage(session, TEAMS, starts=STARTS)

    (series,) = stage.series
    assert series.left.score == 2
    assert series.right.score == 1
    assert series.winner_id == 1
    assert len(series.match_ids) == 3

    record = {s.team_id: (s.wins, s.losses) for s in stage.standings}
    assert record[1] == (1, 0)
    assert record[2] == (0, 1)


def test_round_and_record_come_from_what_was_played_before(session):
    """Раунд — это число уже сыгранных серий, группа — запись на входе.

    Ровно так сетка и рисуется: во втором раунде победители встречаются в
    группе 1-0, проигравшие — в 0-1.
    """
    add_series(session, key="r1a", left=1, right=2, results=[True], hours=0)
    add_series(session, key="r1b", left=3, right=4, results=[True], hours=1)
    # Второй раунд: победители между собой, проигравшие между собой.
    add_series(session, key="r2a", left=1, right=3, results=[False], hours=24)
    add_series(session, key="r2b", left=2, right=4, results=[True], hours=25)

    stage = build_group_stage(session, TEAMS, starts=STARTS)
    rounds = stage.rounds()

    assert sorted(rounds) == [1, 2]
    assert {s.record for s in rounds[1]} == {"0-0"}
    assert {s.record for s in rounds[2]} == {"1-0", "0-1"}

    record = {s.team_id: (s.wins, s.losses) for s in stage.standings}
    assert record[3] == (2, 0), "выиграла оба раунда"
    assert record[4] == (0, 2)
    assert record[1] == (1, 1)


def test_standings_are_sorted_by_record(session):
    add_series(session, key="a", left=1, right=2, results=[True])
    add_series(session, key="b", left=3, right=4, results=[True])
    add_series(session, key="c", left=1, right=3, results=[True], hours=24)

    stage = build_group_stage(session, TEAMS, starts=STARTS)

    assert [s.team_id for s in stage.standings][0] == 1
    assert stage.standings[0].record == "2-0"


def test_a_draw_leaves_the_series_undecided(session):
    """Ничья в серии — сигнал о неполных данных, а не результат.

    Такое бывает, когда вторая карта Bo3 ещё не загружена. Записывать по ней
    победу нельзя: следующий раунд посчитался бы от выдуманного результата.
    """
    add_series(session, key="half", left=1, right=2, results=[True, False])

    stage = build_group_stage(session, TEAMS, starts=STARTS)

    (series,) = stage.series
    assert series.winner_id is None
    assert series.decided is False
    assert all(s.wins == 0 and s.losses == 0 for s in stage.standings)


def test_matches_against_outsiders_are_ignored(session):
    """В сетку идут только матчи участников между собой."""
    add_series(session, key="out", left=1, right=999, results=[True])

    stage = build_group_stage(session, TEAMS, starts=STARTS)
    assert stage.series == []


def test_without_a_start_date_nothing_is_assembled(session):
    """Без даты старта квалификации не отличить от группового этапа."""
    add_series(session, key="s", left=1, right=2, results=[True])

    stage = build_group_stage(session, TEAMS, starts=None)
    assert stage.series == []
    assert len(stage.standings) == len(TEAMS)
