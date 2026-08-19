"""Выгрузка карт для пересчёта рейтинга на странице.

Файл читает браузер, поэтому проверяется не «что-то выгрузилось», а форма: пять
чисел в строке, справочник турниров покрывает выгруженное, окно отрезает старое
и турниры самого события узнаются по данным, а не по названию.
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.analytics.predictions_config import load_predictions_config
from app.db.models import Base, Match, Team

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from export_snapshot import export_matches  # noqa: E402

NOW = datetime.now(timezone.utc)


@pytest.fixture()
def session() -> Session:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def add_match(
    session: Session,
    *,
    match_id: int,
    radiant: int,
    dire: int,
    days_ago: float,
    league: int | None = 100,
    league_name: str = "Test League",
    radiant_win: bool = True,
) -> None:
    session.add(
        Match(
            match_id=match_id,
            start_time=NOW - timedelta(days=days_ago),
            duration=2000,
            series_key=f"s{match_id}",
            league_id=league,
            league_name=league_name,
            radiant_team_id=radiant,
            dire_team_id=dire,
            radiant_win=radiant_win,
            is_parsed=True,
        )
    )
    session.flush()


def test_a_row_is_five_numbers(session):
    """Строка — массив, а не объект: имена полей в двух тысячах строк не нужны."""
    session.add_all([Team(team_id=1, name="Alpha"), Team(team_id=2, name="Beta")])
    add_match(session, match_id=10, radiant=1, dire=2, days_ago=3, radiant_win=False)

    data = export_matches(session, days=30)

    (row,) = data["matches"]
    ts, league, radiant, dire, win = row
    assert (league, radiant, dire, win) == (100, 1, 2, 0)
    assert ts == pytest.approx((NOW - timedelta(days=3)).timestamp(), abs=1)
    assert data["leagues"] == {"100": "Test League"}
    assert data["teams"] == {"1": "Alpha", "2": "Beta"}


def test_the_window_cuts_off_what_is_older(session):
    session.add_all([Team(team_id=1, name="Alpha"), Team(team_id=2, name="Beta")])
    add_match(session, match_id=10, radiant=1, dire=2, days_ago=5)
    add_match(session, match_id=11, radiant=1, dire=2, days_ago=90)

    assert len(export_matches(session, days=30)["matches"]) == 1
    assert len(export_matches(session, days=180)["matches"]) == 2


def test_a_match_without_a_result_does_not_go_out(session):
    """Рейтингу нужен исход: карта без победителя ничего не говорит."""
    session.add_all([Team(team_id=1, name="Alpha"), Team(team_id=2, name="Beta")])
    session.add(
        Match(
            match_id=12,
            start_time=NOW - timedelta(days=1),
            duration=2000,
            series_key="s12",
            league_id=100,
            radiant_team_id=1,
            dire_team_id=2,
            radiant_win=None,
        )
    )
    session.flush()

    assert export_matches(session, days=30)["matches"] == []


def test_the_event_is_recognised_by_who_played_and_when(session):
    """Турниры события выводятся из данных: участники, играющие с даты старта."""
    predictions = load_predictions_config()
    first, second = list(predictions.team_ids.values())[:2]
    started = (NOW.date() - predictions.starts).days

    session.add_all([Team(team_id=first, name="One"), Team(team_id=second, name="Two")])
    # Тот же состав участников, но до старта — это ещё не событие.
    add_match(
        session,
        match_id=20,
        radiant=first,
        dire=second,
        days_ago=started + 10,
        league=555,
        league_name="Before",
    )
    add_match(
        session,
        match_id=21,
        radiant=first,
        dire=second,
        days_ago=max(started - 1, 0),
        league=777,
        league_name="The Event",
    )

    data = export_matches(session, days=365)

    assert data["event_leagues"] == [777]
