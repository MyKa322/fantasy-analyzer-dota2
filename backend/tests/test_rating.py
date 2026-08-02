"""Тесты хронологического пересчёта рейтингов."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.analytics.glicko2 import Rating
from app.analytics.rating import MatchRecord, RatingCalculator

START = datetime(2026, 4, 1, tzinfo=timezone.utc)


def match(
    match_id: int,
    day: int,
    radiant: int,
    dire: int,
    radiant_win: bool,
) -> MatchRecord:
    return MatchRecord(
        match_id=match_id,
        start_time=START + timedelta(days=day),
        radiant_team_id=radiant,
        dire_team_id=dire,
        radiant_win=radiant_win,
    )


def test_empty_history_gives_empty_result():
    history = RatingCalculator().compute([])
    assert history.current == {}
    assert history.snapshots == []


def test_winner_ends_above_loser():
    history = RatingCalculator().compute([match(1, 0, 100, 200, True)])
    assert history.current[100].rating > history.current[200].rating


def test_match_counts_tracked():
    matches = [match(1, 0, 100, 200, True), match(2, 8, 100, 300, False)]
    history = RatingCalculator().compute(matches)
    assert history.matches_played[100] == 2
    assert history.matches_played[200] == 1


def test_snapshots_cover_every_period_per_team():
    matches = [match(1, 0, 100, 200, True), match(2, 21, 100, 200, True)]
    history = RatingCalculator(period_days=7).compute(matches)
    periods = {s.as_of for s in history.snapshots}
    # Периоды с матчами: первый и четвёртый; промежуточные пустые не создаются.
    assert len(periods) == 2
    assert len(history.team_history(100)) == 2


def test_order_within_period_does_not_matter():
    """Матчи одного рейтингового периода считаются одновременными."""
    forward = [match(1, 0, 100, 200, True), match(2, 1, 100, 300, True)]
    backward = [match(2, 1, 100, 300, True), match(1, 0, 100, 200, True)]
    a = RatingCalculator(period_days=7).compute(forward).current
    b = RatingCalculator(period_days=7).compute(backward).current
    assert a[100].rating == pytest.approx(b[100].rating)


def test_rating_grows_with_streak():
    matches = [match(i, i * 8, 100, 200 + i, True) for i in range(1, 6)]
    history = RatingCalculator().compute(matches)
    ratings = [s.rating.rating for s in history.team_history(100)]
    assert ratings == sorted(ratings)
    assert ratings[-1] > 1500.0


def test_rd_shrinks_with_games_and_grows_when_idle():
    playing = [match(i, i * 8, 100, 200, i % 2 == 0) for i in range(1, 8)]
    history = RatingCalculator().compute(playing)
    team_rds = [s.rating.rd for s in history.team_history(100)]
    assert team_rds[-1] < 350.0

    idle_history = RatingCalculator().compute(
        playing + [match(99, 200, 300, 400, True)]
    )
    # Команда 100 пропустила поздние периоды — её RD должен вырасти обратно.
    idle_rds = [s.rating.rd for s in idle_history.team_history(100)]
    assert idle_rds[-1] > team_rds[-1]


def test_ratings_before_ignores_future_matches():
    """Анти-лик: рейтинг на момент времени не должен видеть более поздние матчи."""
    matches = [
        match(1, 0, 100, 200, True),
        match(2, 10, 100, 200, True),
        match(3, 20, 100, 200, True),
    ]
    calculator = RatingCalculator()
    early = calculator.ratings_before(matches, START + timedelta(days=5))
    late = calculator.ratings_before(matches, START + timedelta(days=25))
    assert early[100].rating < late[100].rating


def test_seed_ratings_are_starting_point():
    seeded = RatingCalculator().compute(
        [match(1, 0, 100, 200, True)],
        seed_ratings={100: Rating(1900.0, 80.0), 200: Rating(1400.0, 80.0)},
    )
    assert seeded.current[100].rating > 1900.0 - 50
    assert seeded.current[200].rating < 1400.0


def test_listable_filters_unreliable_and_inactive():
    matches = [match(i, i * 2, 100, 200, i % 3 == 0) for i in range(1, 20)]
    history = RatingCalculator(period_days=7).compute(matches)
    now = START + timedelta(days=40)

    listable = history.listable(now=now)
    assert set(listable) <= {100, 200}

    stale = history.listable(now=START + timedelta(days=400))
    assert stale == {}


def test_days_idle_reported():
    history = RatingCalculator().compute([match(1, 0, 100, 200, True)])
    idle = history.days_idle(100, now=START + timedelta(days=10))
    assert idle == pytest.approx(10.0)
    assert history.days_idle(999) is None


def test_upset_over_strong_team_gains_more_than_beating_weak_one():
    strong_win = RatingCalculator().compute(
        [match(1, 0, 100, 200, True)],
        seed_ratings={100: Rating(1500.0, 100.0), 200: Rating(2000.0, 60.0)},
    )
    weak_win = RatingCalculator().compute(
        [match(1, 0, 100, 300, True)],
        seed_ratings={100: Rating(1500.0, 100.0), 300: Rating(1100.0, 60.0)},
    )
    assert strong_win.current[100].rating > weak_win.current[100].rating


def test_match_record_winner_and_loser():
    m = match(1, 0, 100, 200, True)
    assert m.winner() == 100 and m.loser() == 200
    m2 = match(2, 0, 100, 200, False)
    assert m2.winner() == 200 and m2.loser() == 100
