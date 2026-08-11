"""Тесты аналитики группового этапа.

Отдельного внимания стоит состояние «турнир ещё не начался»: именно в нём модуль
живёт большую часть времени, и именно в нём проще всего случайно поделить на ноль
или показать таблицу нулей с видом результата.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.analytics.group_analytics import build_group_analytics
from app.analytics.group_stage import GroupStage, Series, Side, Standing
from app.db.models import Base, Match, MatchFeature

NOW = datetime(2026, 8, 15, tzinfo=timezone.utc)

# Рейтинги: 1 — явный фаворит, 4 — явный аутсайдер.
RATINGS = {
    1: (1800.0, 60.0, 0.06),
    2: (1600.0, 60.0, 0.06),
    3: (1500.0, 60.0, 0.06),
    4: (1300.0, 60.0, 0.06),
}
TEAMS = {1: "Alpha", 2: "Beta", 3: "Gamma", 4: "Delta"}


@pytest.fixture()
def session() -> Session:
    engine = create_engine("sqlite://", future=True)
    Base.metadata.create_all(engine)
    with Session(engine, future=True) as s:
        yield s


def make_series(
    round_no: int,
    left_id: int,
    right_id: int,
    left_score: int,
    right_score: int,
    *,
    match_ids: tuple[int, ...] = (1,),
) -> Series:
    decided = left_score != right_score
    winner = (left_id if left_score > right_score else right_id) if decided else None
    return Series(
        round=round_no,
        record="0-0",
        left=Side(left_id, TEAMS[left_id], left_score),
        right=Side(right_id, TEAMS[right_id], right_score),
        winner_id=winner,
        played_at=date(2026, 8, 15),
        match_ids=match_ids,
    )


def seed_map(session: Session, match_id: int, radiant_id: int, dire_id: int, kill_diff: float):
    session.add(
        Match(
            match_id=match_id,
            start_time=NOW,
            duration=2100,
            series_key=f"s{match_id}",
            radiant_team_id=radiant_id,
            dire_team_id=dire_id,
            radiant_win=kill_diff > 0,
        )
    )
    session.add(
        MatchFeature(
            match_id=match_id,
            features={"duration_min": 35.0, "kill_diff": kill_diff},
            features_version=1,
        )
    )
    session.flush()


# --- турнир ещё не начался ----------------------------------------------------


def test_before_the_tournament_reports_not_started(session):
    stage = GroupStage(standings=[Standing(t, n) for t, n in TEAMS.items()])
    result = build_group_analytics(session, stage, TEAMS, ratings=RATINGS)

    assert result.started is False
    assert result.series_played == 0
    assert len(result.teams) == 4
    # Ожидаемых побед нет: не по чему считать. None, а не ноль — «не знаем».
    assert all(t.expected_wins is None for t in result.teams)
    assert all(t.performance is None for t in result.teams)


def test_first_round_preview_is_available_before_the_start(session):
    stage = GroupStage(standings=[])
    result = build_group_analytics(
        session, stage, TEAMS, ratings=RATINGS, first_round=[(1, 4), (2, 3)]
    )

    assert len(result.matchups) == 2
    favourite = result.matchups[0]
    assert favourite.left == "Alpha" and favourite.right == "Delta"
    # 1800 против 1300 — фаворит очевиден.
    assert favourite.left_win_probability > 0.7
    assert favourite.rating_gap == pytest.approx(500.0)
    assert not favourite.is_toss_up


def test_close_matchup_is_flagged_as_toss_up(session):
    ratings = {**RATINGS, 3: (1590.0, 60.0, 0.06)}
    result = build_group_analytics(
        session, GroupStage(), TEAMS, ratings=ratings, first_round=[(2, 3)]
    )
    assert result.matchups[0].is_toss_up


def test_missing_ratings_do_not_invent_a_probability(session):
    result = build_group_analytics(session, GroupStage(), TEAMS, ratings={}, first_round=[(1, 2)])
    assert result.matchups[0].left_win_probability is None
    assert result.matchups[0].rating_gap is None


# --- сыгранный этап -----------------------------------------------------------


def test_record_and_map_difference(session):
    stage = GroupStage(series=[make_series(1, 1, 2, 2, 1, match_ids=(1, 2, 3))])
    result = build_group_analytics(session, stage, TEAMS, ratings=RATINGS)

    alpha = next(t for t in result.teams if t.team_id == 1)
    beta = next(t for t in result.teams if t.team_id == 2)

    assert alpha.record == "1-0"
    assert alpha.maps_won == 2 and alpha.maps_lost == 1 and alpha.map_diff == 1
    assert beta.record == "0-1"
    assert beta.map_diff == -1


def test_underdog_win_counts_as_upset(session):
    """Delta (1300) обыгрывает Alpha (1800) — это апсет для обеих сторон."""
    stage = GroupStage(series=[make_series(1, 4, 1, 1, 0)])
    result = build_group_analytics(session, stage, TEAMS, ratings=RATINGS)

    delta = next(t for t in result.teams if t.team_id == 4)
    alpha = next(t for t in result.teams if t.team_id == 1)

    assert delta.upsets_won == 1
    assert alpha.upsets_lost == 1
    assert result.upsets == 1
    assert result.rounds[0].upset_rate == pytest.approx(1.0)


def test_performance_is_positive_for_overachiever(session):
    """Аутсайдер, выигравший у фаворита, обязан быть выше ожиданий."""
    stage = GroupStage(series=[make_series(1, 4, 1, 1, 0)])
    result = build_group_analytics(session, stage, TEAMS, ratings=RATINGS)

    delta = next(t for t in result.teams if t.team_id == 4)
    assert delta.expected_wins < 0.5  # от него такого не ждали
    assert delta.performance > 0.5

    alpha = next(t for t in result.teams if t.team_id == 1)
    assert alpha.performance < -0.5


def test_expected_wins_sum_matches_series_played(session):
    """Сумма ожидаемых побед по обеим сторонам серии равна единице."""
    stage = GroupStage(series=[make_series(1, 1, 2, 1, 0), make_series(1, 3, 4, 1, 0)])
    result = build_group_analytics(session, stage, TEAMS, ratings=RATINGS)

    total = sum(t.expected_wins for t in result.teams if t.expected_wins is not None)
    assert total == pytest.approx(2.0)


def test_undecided_series_does_not_count_towards_record(session):
    """Незавершённая серия (перенос, техпоражение) не должна давать победу."""
    stage = GroupStage(series=[make_series(1, 1, 2, 1, 1)])
    result = build_group_analytics(session, stage, TEAMS, ratings=RATINGS)

    alpha = next(t for t in result.teams if t.team_id == 1)
    assert alpha.wins == 0 and alpha.losses == 0
    assert result.rounds[0].series == 1
    assert result.rounds[0].decided == 0
    assert result.rounds[0].upset_rate is None


def test_streak_direction_and_length(session):
    stage = GroupStage(
        series=[
            make_series(1, 1, 2, 1, 0),
            make_series(2, 1, 3, 1, 0),
            make_series(3, 1, 4, 0, 1),
        ]
    )
    result = build_group_analytics(session, stage, TEAMS, ratings=RATINGS)
    alpha = next(t for t in result.teams if t.team_id == 1)

    assert alpha.wins == 2 and alpha.losses == 1
    assert alpha.streak == -1  # последняя серия проиграна

    delta = next(t for t in result.teams if t.team_id == 4)
    assert delta.streak == 1


def test_status_reflects_advance_and_elimination(session):
    stage = GroupStage(
        series=[
            make_series(1, 1, 2, 1, 0),
            make_series(2, 1, 3, 1, 0),
            make_series(3, 1, 4, 1, 0),
            make_series(4, 1, 2, 1, 0),
        ]
    )
    result = build_group_analytics(
        session, stage, TEAMS, ratings=RATINGS, wins_to_advance=4, losses_to_eliminate=4
    )
    alpha = next(t for t in result.teams if t.team_id == 1)
    beta = next(t for t in result.teams if t.team_id == 2)

    assert alpha.status == "advanced"
    assert beta.status == "alive"  # два поражения из четырёх


def test_strength_of_schedule_averages_opponents(session):
    stage = GroupStage(series=[make_series(1, 1, 2, 1, 0), make_series(2, 1, 4, 1, 0)])
    result = build_group_analytics(session, stage, TEAMS, ratings=RATINGS)

    alpha = next(t for t in result.teams if t.team_id == 1)
    assert alpha.opponent_rating == pytest.approx((1600.0 + 1300.0) / 2)


def test_bo3_uses_decisive_best_of(session):
    """Серия из трёх карт должна считаться как Bo3, а не как Bo1.

    Разница существенная: в Bo3 фаворит проходит чаще, чем в Bo1, и ожидаемые
    победы обязаны это учитывать.
    """
    bo1 = GroupStage(series=[make_series(1, 1, 4, 1, 0, match_ids=(1,))])
    bo3 = GroupStage(series=[make_series(1, 1, 4, 2, 1, match_ids=(1, 2, 3))])

    expected_bo1 = build_group_analytics(session, bo1, TEAMS, ratings=RATINGS)
    expected_bo3 = build_group_analytics(session, bo3, TEAMS, ratings=RATINGS)

    alpha_bo1 = next(t for t in expected_bo1.teams if t.team_id == 1)
    alpha_bo3 = next(t for t in expected_bo3.teams if t.team_id == 1)
    assert alpha_bo3.expected_wins > alpha_bo1.expected_wins


# --- связь с витриной фич -----------------------------------------------------


def test_kill_diff_is_flipped_for_dire_side(session):
    """Разница убийств в фичах в пользу Radiant — для Dire её надо перевернуть."""
    seed_map(session, 1, radiant_id=1, dire_id=2, kill_diff=12.0)
    stage = GroupStage(series=[make_series(1, 1, 2, 1, 0, match_ids=(1,))])

    result = build_group_analytics(session, stage, TEAMS, ratings=RATINGS)
    alpha = next(t for t in result.teams if t.team_id == 1)
    beta = next(t for t in result.teams if t.team_id == 2)

    assert alpha.avg_kill_diff == pytest.approx(12.0)
    assert beta.avg_kill_diff == pytest.approx(-12.0)
    assert alpha.avg_duration_min == pytest.approx(35.0)


def test_missing_features_leave_averages_unknown(session):
    stage = GroupStage(series=[make_series(1, 1, 2, 1, 0, match_ids=(77,))])
    result = build_group_analytics(session, stage, TEAMS, ratings=RATINGS)
    alpha = next(t for t in result.teams if t.team_id == 1)
    assert alpha.avg_kill_diff is None
    assert alpha.avg_duration_min is None


def test_leaders_rank_by_performance(session):
    stage = GroupStage(series=[make_series(1, 4, 1, 1, 0), make_series(1, 2, 3, 1, 0)])
    result = build_group_analytics(session, stage, TEAMS, ratings=RATINGS)
    leaders = result.leaders(limit=2)
    assert leaders[0].team_id == 4  # аутсайдер, обыгравший фаворита
