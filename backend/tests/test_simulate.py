"""Тесты Monte-Carlo симуляций группового этапа и сетки."""

from __future__ import annotations

from collections import Counter

import numpy as np
import pytest

from app.analytics.glicko2 import Rating
from app.analytics.predictions_config import load_predictions_config
from app.analytics.simulate import (
    BRACKET_SLOTS,
    BracketSimulator,
    SwissSimulator,
    optimise_bracket_predictions,
    optimise_group_predictions,
)


@pytest.fixture(scope="module")
def config():
    return load_predictions_config()


@pytest.fixture(scope="module")
def group_config(config):
    return config.group_stage


def make_ratings(n: int = 16, *, spread: float = 40.0, rd: float = 60.0) -> dict[int, Rating]:
    """Команды с равномерно убывающей силой: id 1 — сильнейшая."""
    return {i + 1: Rating(1700.0 - i * spread, rd) for i in range(n)}


def equal_ratings(n: int = 16) -> dict[int, Rating]:
    return {i + 1: Rating(1500.0, 60.0) for i in range(n)}


# --- структура Swiss ----------------------------------------------------------


def test_bucket_sizes_match_compendium_every_run(group_config):
    """Главная проверка формата: каждый прогон обязан давать ровно 1/2/5/5/2/1.

    Если распределение не сходится — значит модель Swiss не соответствует той,
    из которой компендиум вывел свои корзины.
    """
    sim = SwissSimulator(make_ratings(), group_config, seed=7)
    expected = group_config.slots()
    for _ in range(200):
        result = sim.run_once()
        assert Counter(result.buckets.values()) == expected


def test_exactly_eight_teams_advance(group_config):
    sim = SwissSimulator(make_ratings(), group_config, seed=11)
    for _ in range(100):
        assert len(sim.run_once().advanced) == 8


def test_every_team_finishes_by_wins_losses_or_elimination_round(group_config):
    """Команда выходит из Swiss тремя способами: 4 победы, 4 поражения либо
    исход шестого раунда (Elimination Round) с записью 3-3."""
    sim = SwissSimulator(make_ratings(), group_config, seed=3)
    cfg = group_config.swiss
    for _ in range(50):
        for wins, losses in sim.run_once().records.values():
            assert (
                wins == cfg.wins_to_advance
                or losses == cfg.losses_to_eliminate
                or wins + losses == cfg.max_rounds
            )
            assert wins + losses <= cfg.max_rounds


def test_elimination_round_involves_exactly_ten_teams(group_config):
    """После пяти раундов остаются 5 команд с 3-2 и 5 с 2-3 — они и играют
    решающий раунд: 5 победителей проходят, 5 вылетают."""
    sim = SwissSimulator(make_ratings(), group_config, seed=97)
    for _ in range(50):
        result = sim.run_once()
        six_round_teams = [
            team for team, (w, l) in result.records.items() if w + l == 6
        ]
        assert len(six_round_teams) == 10
        buckets = {result.buckets[t] for t in six_round_teams}
        assert buckets <= {"elim_winner", "elim_loser"}


def test_undefeated_and_winless_are_unique(group_config):
    sim = SwissSimulator(make_ratings(), group_config, seed=5)
    for _ in range(50):
        buckets = sim.run_once().buckets
        assert sum(1 for b in buckets.values() if b == "4-0") == 1
        assert sum(1 for b in buckets.values() if b == "0-4") == 1


def test_no_rematches_within_swiss(group_config):
    """Пары в Swiss не должны повторяться — иначе формат смоделирован неверно."""
    sim = SwissSimulator(make_ratings(), group_config, seed=13)
    for _ in range(50):
        played: set[tuple[int, int]] = set()
        records = {i: (0, 0) for i in range(16)}
        finished: set[int] = set()
        for _round in range(group_config.swiss.max_rounds):
            active = [i for i in range(16) if i not in finished]
            if not active:
                break
            pairs = sim._pair_round(active, records, played)
            keys = [(min(a, b), max(a, b)) for a, b in pairs]
            assert len(keys) == len(set(keys))
            for a, b in pairs:
                records[a] = (records[a][0] + 1, records[a][1])
                records[b] = (records[b][0], records[b][1] + 1)
            for team in active:
                if records[team][0] >= 4 or records[team][1] >= 4:
                    finished.add(team)


# --- вероятности --------------------------------------------------------------


def test_probabilities_sum_to_one_per_team(group_config):
    sim = SwissSimulator(make_ratings(), group_config, seed=17)
    result = sim.run(simulations=400)
    assert np.allclose(result.probabilities.sum(axis=1), 1.0)


def test_expected_bucket_occupancy_matches_slots(group_config):
    """В среднем по симуляциям каждая корзина заполнена ровно на свои слоты."""
    sim = SwissSimulator(make_ratings(), group_config, seed=19)
    result = sim.run(simulations=400)
    occupancy = result.probabilities.sum(axis=0)
    expected = np.array([group_config.slots()[k] for k in result.bucket_keys], dtype=float)
    assert np.allclose(occupancy, expected)


def test_stronger_team_advances_more_often(group_config):
    sim = SwissSimulator(make_ratings(), group_config, seed=23)
    result = sim.run(simulations=600)
    strongest = result.advance_probability[0]
    weakest = result.advance_probability[-1]
    assert strongest > weakest
    assert strongest > 0.5 > weakest


def test_equal_teams_give_uniform_advance_chance(group_config):
    sim = SwissSimulator(equal_ratings(), group_config, seed=29)
    result = sim.run(simulations=1500)
    # 8 из 16 проходят -> у каждой примерно 50%.
    assert result.advance_probability.mean() == pytest.approx(0.5, abs=0.01)
    assert result.advance_probability.std() < 0.06


def test_wrong_number_of_teams_rejected(group_config):
    with pytest.raises(ValueError, match="16 команд"):
        SwissSimulator(make_ratings(10), group_config)


# --- оптимизация предсказаний -------------------------------------------------


def test_group_plan_respects_slot_capacity(group_config):
    sim = SwissSimulator(make_ratings(), group_config, seed=31)
    result = sim.run(simulations=500)
    plan = optimise_group_predictions(result, group_config.slots(), group_config.points)

    assert len(plan.assignment) == 16
    assert Counter(plan.assignment.values()) == group_config.slots()


def test_group_plan_beats_naive_probability_pick(group_config):
    """Оптимизация должна быть не хуже жадного выбора по вероятностям."""
    sim = SwissSimulator(make_ratings(), group_config, seed=37)
    result = sim.run(simulations=800)
    plan = optimise_group_predictions(result, group_config.slots(), group_config.points)

    # Наивный план: сортировка команд по силе, разложенная по корзинам сверху вниз.
    naive_assignment = []
    for key in result.bucket_keys:
        naive_assignment.extend([key] * group_config.slots()[key])
    bucket_index = {k: i for i, k in enumerate(result.bucket_keys)}
    naive = np.array([bucket_index[b] for b in naive_assignment], dtype=np.int64)
    lookup = np.array(group_config.points.as_array(16), dtype=float)
    naive_points = lookup[(result.outcomes == naive[np.newaxis, :]).sum(axis=1)].mean()

    assert plan.expected_points >= naive_points


def test_group_plan_puts_favourite_high(group_config):
    sim = SwissSimulator(make_ratings(spread=70.0), group_config, seed=41)
    result = sim.run(simulations=800)
    plan = optimise_group_predictions(result, group_config.slots(), group_config.points)

    strong_buckets = {"4-0", "4-1", "elim_winner"}
    assert plan.assignment[1] in strong_buckets
    assert plan.assignment[16] in {"0-4", "1-4", "elim_loser"}


def test_plan_reports_distribution(group_config):
    sim = SwissSimulator(make_ratings(), group_config, seed=43)
    result = sim.run(simulations=500)
    plan = optimise_group_predictions(result, group_config.slots(), group_config.points)

    assert 0 <= plan.expected_correct <= 16
    assert plan.points_distribution.shape == (500,)
    assert plan.points_percentiles[5] <= plan.points_percentiles[95]


def test_slot_mismatch_rejected(group_config):
    sim = SwissSimulator(make_ratings(), group_config, seed=47)
    result = sim.run(simulations=100)
    broken = dict(group_config.slots())
    broken["4-0"] = 5
    with pytest.raises(ValueError, match="слотов"):
        optimise_group_predictions(result, broken, group_config.points)


# --- плей-офф -----------------------------------------------------------------


@pytest.fixture(scope="module")
def playoff_config(config):
    return config.playoffs


def test_bracket_has_fourteen_matches(playoff_config):
    assert len(BRACKET_SLOTS) == playoff_config.predictions == 14


def test_bracket_produces_all_match_winners(playoff_config):
    sim = BracketSimulator(make_ratings(8), playoff_config, seed=53)
    outcome = sim.run_once()
    assert set(outcome) == set(BRACKET_SLOTS)
    assert all(0 <= v < 8 for v in outcome.values())


def test_champion_probabilities_sum_to_one(playoff_config):
    sim = BracketSimulator(make_ratings(8), playoff_config, seed=59)
    result = sim.run(simulations=800)
    assert sum(result.champion_probability.values()) == pytest.approx(1.0)


def test_seed_one_is_most_likely_champion(playoff_config):
    sim = BracketSimulator(make_ratings(8, spread=60.0), playoff_config, seed=61)
    result = sim.run(simulations=1200)
    champion = max(result.champion_probability, key=result.champion_probability.get)
    assert champion == 1


def test_equal_teams_champion_chance_is_uniform(playoff_config):
    sim = BracketSimulator(
        {i + 1: Rating(1500.0, 50.0) for i in range(8)}, playoff_config, seed=67
    )
    result = sim.run(simulations=2000)
    values = list(result.champion_probability.values())
    assert max(values) - min(values) < 0.06


def test_loser_of_grand_final_can_come_from_lower_bracket(playoff_config):
    """Проигравший верхнего финала обязан получить второй шанс в нижней сетке."""
    sim = BracketSimulator(make_ratings(8, spread=80.0), playoff_config, seed=71)
    result = sim.run(simulations=500)
    ubf_column = result.winners[:, BRACKET_SLOTS.index("ubf")]
    gf_column = result.winners[:, BRACKET_SLOTS.index("gf")]
    assert (ubf_column != gf_column).any()


def test_bracket_plan_picks_most_likely_winner(playoff_config):
    sim = BracketSimulator(make_ratings(8, spread=80.0), playoff_config, seed=73)
    result = sim.run(simulations=1000)
    plan = optimise_bracket_predictions(result, playoff_config.points)

    assert len(plan.assignment) == 14
    assert plan.assignment["gf"] == max(
        result.champion_probability, key=result.champion_probability.get
    )
    assert 0 <= plan.expected_correct <= 14
    assert plan.expected_points > 0
