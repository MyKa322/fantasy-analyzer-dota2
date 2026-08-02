"""Тесты проекции Fantasy-очков."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import numpy as np
import pytest

from app.fantasy.projection import (
    RoleGame,
    RoleHistory,
    RoleProjector,
    optimise_banner,
    recommend_roster,
)
from app.fantasy.scoring import Banner, Emblem, FantasyScorer

NOW = datetime(2026, 8, 1, tzinfo=timezone.utc)


def make_history(
    kills_per_game: list[float],
    *,
    role: str = "core",
    team_id: int = 1,
    account_ids: tuple[int, ...] = (10,),
    gpm: float = 600.0,
    days_ago: list[float] | None = None,
) -> RoleHistory:
    games = []
    for i, kills in enumerate(kills_per_game):
        age = days_ago[i] if days_ago else i
        stats = {account_id: {"kills": kills, "gpm": gpm} for account_id in account_ids}
        games.append(
            RoleGame(
                match_id=1000 + i,
                start_time=NOW - timedelta(days=age),
                series_key=f"series:{i // 2}",
                player_stats=stats,
            )
        )
    return RoleHistory(role=role, team_id=team_id, account_ids=account_ids, games=games)


@pytest.fixture(scope="module")
def scorer():
    return FantasyScorer()


@pytest.fixture()
def projector(scorer):
    return RoleProjector(scorer, seed=42)


KILLS_BANNER = Banner.of(Emblem("kills", "tier_1"))


# --- подготовка выборки -------------------------------------------------------


def test_base_matrix_averages_players_of_role(projector):
    history = RoleHistory(
        role="core",
        team_id=1,
        account_ids=(10, 20),
        games=[
            RoleGame(
                match_id=1,
                start_time=NOW,
                series_key="s1",
                player_stats={10: {"kills": 10}, 20: {"kills": 4}},
            )
        ],
    )
    matrix = projector.base_matrix(history)
    kills_column = matrix[0, projector.stat_keys.index("kills")]
    assert kills_column == pytest.approx(7 * 107.0)


def test_base_matrix_ignores_players_outside_role(projector):
    history = RoleHistory(
        role="mid",
        team_id=1,
        account_ids=(10,),
        games=[
            RoleGame(
                match_id=1,
                start_time=NOW,
                series_key="s1",
                player_stats={10: {"kills": 10}, 99: {"kills": 0}},
            )
        ],
    )
    matrix = projector.base_matrix(history)
    assert matrix[0, projector.stat_keys.index("kills")] == pytest.approx(10 * 107.0)


def test_recency_weights_favour_recent_games(projector):
    history = make_history([5, 5, 5], days_ago=[0, 30, 60])
    weights = projector.recency_weights(history, now=NOW)
    assert weights[0] > weights[1] > weights[2]
    assert weights.sum() == pytest.approx(1.0)
    # Половина периода полураспада -> вдвое меньший вес.
    assert weights[1] / weights[0] == pytest.approx(0.5, abs=0.01)


# --- симуляция ----------------------------------------------------------------


def test_projection_reports_distribution(projector):
    history = make_history([2, 6, 10, 14] * 5)
    projection = projector.project(history, KILLS_BANNER, simulations=2000)

    assert projection.mean > 0
    assert projection.floor <= projection.median <= projection.ceiling
    assert projection.samples.shape == (2000,)
    assert projection.games_used == 20


def test_volatile_player_beats_stable_one_with_equal_mean(projector):
    """Ключевое свойство формата: в зачёт идёт максимум, а не среднее.

    Оба игрока в среднем делают 8 килов за карту, но разброс второго выше —
    его проекция обязана быть выше, иначе модель систематически недооценивает
    именно тех игроков, которые выигрывают Fantasy.
    """
    stable = make_history([8] * 20, days_ago=[0] * 20)
    volatile = make_history([1, 15] * 10, days_ago=[0] * 20)

    stable_projection = projector.project(stable, KILLS_BANNER, simulations=4000)
    volatile_projection = projector.project(volatile, KILLS_BANNER, simulations=4000)

    assert volatile_projection.mean > stable_projection.mean
    assert volatile_projection.ceiling > stable_projection.ceiling


def test_more_series_means_more_points(projector):
    """Больше сыгранных серий — больше попыток выбить высокий результат."""
    history = make_history([2, 6, 10, 14] * 5, days_ago=[0] * 20)
    few = projector.project(
        history, KILLS_BANNER, series_distribution={2: 1.0}, simulations=4000
    )
    many = projector.project(
        history, KILLS_BANNER, series_distribution={6: 1.0}, simulations=4000
    )
    assert many.mean > few.mean
    assert many.expected_series == 6.0


def test_longer_series_help_because_worst_map_is_dropped(projector):
    """В Bo3 засчитываются лучшие 2 карты из 3 — это выгоднее, чем 2 из 2."""
    history = make_history([2, 6, 10, 14] * 5, days_ago=[0] * 20)
    bo2 = projector.project(
        history, KILLS_BANNER, series_lengths={2: 1.0}, simulations=4000
    )
    bo3 = projector.project(
        history, KILLS_BANNER, series_lengths={3: 1.0}, simulations=4000
    )
    assert bo3.mean > bo2.mean


def test_emblem_quality_scales_projection(projector):
    history = make_history([8] * 10, days_ago=[0] * 10)
    tier_1 = projector.project(history, Banner.of(Emblem("kills", "tier_1")), simulations=3000)
    tier_5 = projector.project(history, Banner.of(Emblem("kills", "tier_5")), simulations=3000)
    # 2.50 / 1.10 = 2.27
    assert tier_5.mean / tier_1.mean == pytest.approx(2.5 / 1.1, rel=0.02)


def test_title_multiplier_applies(projector):
    history = make_history([8] * 10, days_ago=[0] * 10)
    plain = projector.project(history, KILLS_BANNER, simulations=3000)
    boosted = projector.project(
        history, KILLS_BANNER, title_multiplier=1.2, simulations=3000
    )
    assert boosted.mean / plain.mean == pytest.approx(1.2, rel=0.02)


def test_unavailable_stats_reported(projector):
    history = make_history([8] * 10)
    banner = Banner.of(Emblem("kills", "tier_1"), Emblem("madstone_collected", "tier_3"))
    projection = projector.project(history, banner, simulations=500)
    assert projection.unavailable_stats == ("madstone_collected",)


def test_empty_history_rejected(projector):
    empty = RoleHistory(role="core", team_id=1, account_ids=(10,), games=[])
    with pytest.raises(ValueError, match="пустая история"):
        projector.project(empty, KILLS_BANNER, simulations=100)


def test_expected_card_score_is_linear_estimate(projector):
    history = make_history([8] * 10, days_ago=[0] * 10)
    estimate = projector.expected_card_score(history, KILLS_BANNER)
    assert estimate == pytest.approx(8 * 107.0 * 1.10)


# --- подбор баннера -----------------------------------------------------------


def test_optimise_banner_prefers_high_value_stats(projector):
    history = RoleHistory(
        role="core",
        team_id=1,
        account_ids=(10,),
        games=[
            RoleGame(
                match_id=i,
                start_time=NOW - timedelta(days=i),
                series_key=f"s{i}",
                player_stats={10: {"kills": 10, "gpm": 700, "wards_placed": 0}},
            )
            for i in range(10)
        ],
    )
    emblems = [
        Emblem("kills", "tier_3"),
        Emblem("gpm", "tier_3"),
        Emblem("wards_placed", "tier_5"),  # игрок не ставит варды — стат пустой
    ]
    options = optimise_banner(
        projector, history, emblems, slots=2, shortlist=6, simulations=800, top_n=3
    )

    assert options
    best_stats = set(options[0].banner.stats())
    assert best_stats == {"kills", "gpm"}
    assert options[0].score >= options[-1].score


def test_optimise_banner_respects_duplicate_stat_rule(projector):
    history = make_history([8] * 10)
    emblems = [
        Emblem("kills", "tier_1"),
        Emblem("kills", "tier_5"),
        Emblem("gpm", "tier_2"),
    ]
    options = optimise_banner(
        projector, history, emblems, slots=2, shortlist=4, simulations=400, top_n=3
    )
    for option in options:
        stats = option.banner.stats()
        assert len(set(stats)) == len(stats)


def test_optimise_banner_orders_adjacency_effects(projector):
    """Vampiric должен встать рядом с наименее ценной эмблемой, а не наоборот."""
    history = RoleHistory(
        role="core",
        team_id=1,
        account_ids=(10,),
        games=[
            RoleGame(
                match_id=i,
                start_time=NOW,
                series_key=f"s{i}",
                player_stats={10: {"kills": 12, "gpm": 800, "creep_score": 20}},
            )
            for i in range(8)
        ],
    )
    emblems = [
        Emblem("gpm", "tier_4", "vampiric"),
        Emblem("kills", "tier_3"),
        Emblem("creep_score", "tier_1"),
    ]
    options = optimise_banner(
        projector, history, emblems, slots=3, shortlist=6, simulations=600, top_n=1
    )
    order = options[0].banner.stats()
    # Дорогая эмблема kills не должна стоять вплотную к вампирику, если этого
    # можно избежать: правильный порядок ставит между ними дешёвый creep_score.
    assert order.index("creep_score") == 1


def test_optimise_banner_requires_enough_emblems(projector):
    history = make_history([8] * 5)
    with pytest.raises(ValueError, match="минимум"):
        optimise_banner(projector, history, [Emblem("kills", "tier_1")], slots=3)


# --- подбор ростера -----------------------------------------------------------


def _projection(projector, team_id: int, role: str, kills: float):
    history = make_history([kills] * 8, role=role, team_id=team_id, days_ago=[0] * 8)
    return projector.project(history, KILLS_BANNER, simulations=500)


def test_recommend_roster_picks_best_combination(projector):
    projections = {
        "core": {1: _projection(projector, 1, "core", 12), 2: _projection(projector, 2, "core", 4)},
        "mid": {1: _projection(projector, 1, "mid", 11), 3: _projection(projector, 3, "mid", 3)},
        "support": {
            2: _projection(projector, 2, "support", 6),
            3: _projection(projector, 3, "support", 5),
        },
    }
    rosters = recommend_roster(projections, top_n=3)

    assert rosters
    best = rosters[0]
    assert best.expected_total >= rosters[-1].expected_total
    teams = [pick.team_id for pick in best.picks]
    assert len(set(teams)) == 3


def test_recommend_roster_enforces_distinct_teams(projector):
    projections = {
        "core": {1: _projection(projector, 1, "core", 12)},
        "mid": {1: _projection(projector, 1, "mid", 12)},
    }
    assert recommend_roster(projections) == []
    assert recommend_roster(projections, distinct_teams=False)


def test_roster_summary_reports_interval(projector):
    projections = {
        "core": {1: _projection(projector, 1, "core", 10)},
        "mid": {2: _projection(projector, 2, "mid", 9)},
    }
    summary = recommend_roster(projections)[0].summary()
    assert summary["p5"] <= summary["expected_total"] <= summary["p95"]
    assert len(summary["picks"]) == 2


def test_combined_samples_length_matches_shortest(projector):
    a = _projection(projector, 1, "core", 10)
    b = _projection(projector, 2, "mid", 9)
    roster = recommend_roster({"core": {1: a}, "mid": {2: b}})[0]
    assert roster.combined_samples.shape == (min(len(a.samples), len(b.samples)),)
    assert np.all(roster.combined_samples > 0)
