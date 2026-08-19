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


# --- объявленный первый раунд -------------------------------------------------

# Пары «сильнейшая против сильнейшей», каких посев никогда бы не дал.
FIXED_FIRST_ROUND = [(1, 2), (3, 4), (5, 6), (7, 8), (9, 10), (11, 12), (13, 14), (15, 16)]


def test_declared_first_round_is_played_as_written(group_config):
    sim = SwissSimulator(make_ratings(), group_config, seed=7, first_round=FIXED_FIRST_ROUND)
    played: set[tuple[int, int]] = set()
    pairs = sim._pair_round(range(16), {i: (0, 0) for i in range(16)}, played, round_index=0)

    expected = [(sim._index[a], sim._index[b]) for a, b in FIXED_FIRST_ROUND]
    assert pairs == expected
    assert len(played) == 8, "повторные встречи дальше по сетке должны исключаться"


def test_declared_first_round_does_not_leak_into_later_rounds(group_config):
    """Со второго раунда пары снова считаются по записям — сетка их не задаёт."""
    sim = SwissSimulator(make_ratings(), group_config, seed=7, first_round=FIXED_FIRST_ROUND)
    records = {i: (1, 0) if i < 8 else (0, 1) for i in range(16)}
    pairs = sim._pair_round(range(16), records, set(), round_index=1)

    assert sorted(pairs) != sorted(
        (sim._index[a], sim._index[b]) for a, b in FIXED_FIRST_ROUND
    )
    for a, b in pairs:
        assert records[a] == records[b], "Swiss сводит команды с одинаковой записью"


def test_seed_pairing_stays_when_no_first_round_declared(group_config):
    """Без сетки поведение прежнее: верх против низа по посеву."""
    sim = SwissSimulator(make_ratings(), group_config, seed=7)
    pairs = sim._pair_round(range(16), {i: (0, 0) for i in range(16)}, set(), round_index=0)

    ranks = {(sim._seed_rank[a], sim._seed_rank[b]) for a, b in pairs}
    assert (0, 15) in ranks, "сильнейшая должна встретить слабейшую"


def test_first_round_needs_ratings_for_every_listed_team(group_config):
    with pytest.raises(ValueError, match="нет рейтинга"):
        SwissSimulator(make_ratings(), group_config, seed=7, first_round=[(1, 999)])


def test_declared_first_round_changes_the_odds(group_config):
    """Ради этого всё и делается: сетка сдвигает вероятности по корзинам.

    По посеву сильнейшая команда первым же матчем получает слабейшую, по
    объявленной сетке — вторую по силе. Шанс пройти без поражений падает.
    """
    seeded = SwissSimulator(make_ratings(), group_config, seed=101)
    fixed = SwissSimulator(
        make_ratings(), group_config, seed=101, first_round=FIXED_FIRST_ROUND
    )
    favourite = 1

    seeded_odds = seeded.run(simulations=4000).bucket_probability(favourite, "4-0")
    fixed_odds = fixed.run(simulations=4000).bucket_probability(favourite, "4-0")
    assert fixed_odds < seeded_odds


def test_shipped_first_round_covers_every_team(config):
    """Сетка в конфиге: восемь пар, все шестнадцать участников по разу."""
    pairs = config.first_round_ids()
    assert len(pairs) == 8

    listed = [team for pair in pairs for team in pair]
    assert len(set(listed)) == 16
    assert set(listed) == {t for t in config.team_ids.values() if t is not None}


def test_first_round_ignored_for_a_different_set_of_teams(config):
    """Топ-16 по рейтингу — не та сетка, пары к нему не относятся."""
    assert config.first_round_for(set(range(16))) == ()
    assert config.first_round_for(set(config.team_ids.values())) == config.first_round_ids()


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


# --- объявленная сетка и уже сыгранное ----------------------------------------


def test_announced_pairs_replace_the_seeding(playoff_config):
    """Сетку разводят по итогам группы, а не по рейтингу: пары приходят снаружи."""
    sim = BracketSimulator(
        make_ratings(8),
        playoff_config,
        seed=79,
        quarterfinals=((1, 2), (3, 4), (5, 6), (7, 8)),
    )
    result = sim.run(simulations=200)

    first = result.participant_probabilities("ubqf1")
    assert set(first) == {1, 2}
    assert set(result.participant_probabilities("ubqf4")) == {7, 8}


def test_a_pair_outside_the_ratings_is_rejected(playoff_config):
    with pytest.raises(ValueError, match="нет рейтинга"):
        BracketSimulator(
            make_ratings(8),
            playoff_config,
            quarterfinals=((1, 2), (3, 4), (5, 6), (7, 99)),
        )


def test_played_series_enter_as_fact(playoff_config):
    """Сыгранное не разыгрывается заново: победитель четвертьфинала известен."""
    pairs = ((1, 2), (3, 4), (5, 6), (7, 8))
    before = BracketSimulator(
        make_ratings(8, spread=80.0), playoff_config, seed=83, quarterfinals=pairs
    ).run(simulations=400)
    # Фаворит проиграл четвертьфинал и ушёл в нижнюю сетку.
    after = BracketSimulator(
        make_ratings(8, spread=80.0),
        playoff_config,
        seed=83,
        quarterfinals=pairs,
        results={"ubqf1": 2},
        participants={"ubqf1": (1, 2)},
    ).run(simulations=400)

    assert after.match_probabilities("ubqf1") == {2: 1.0}
    assert set(after.participant_probabilities("ubsf1")) <= {2, 3, 4}
    assert after.champion_probability[1] < before.champion_probability[1]
    assert after.champion_probability[2] > before.champion_probability[2]
    assert after.top_probability(1, places=1) < after.top_probability(1, places=3), (
        "из нижней сетки путь к титулу длиннее, чем к призам"
    )


def test_an_eliminated_team_plays_no_more_series(playoff_config):
    """Две проигранные серии — конец турнира, а значит и конец Fantasy-очкам."""
    sim = BracketSimulator(
        equal_ratings(8),
        playoff_config,
        seed=89,
        quarterfinals=((1, 2), (3, 4), (5, 6), (7, 8)),
        results={"ubqf1": 1, "ubqf2": 3, "lbr1_1": 4},
        participants={"ubqf1": (1, 2), "ubqf2": (3, 4), "lbr1_1": (2, 4)},
    )
    result = sim.run(simulations=200)

    assert result.series_distribution(2) == {2: 1.0}
    assert result.expected_series(2) == 2.0
    assert result.place_probabilities(2) == {"7-8": 1.0}
    assert result.champion_probability[2] == 0.0


def test_series_count_spans_the_whole_run(playoff_config):
    """Путь по сетке — от двух серий до шести, и это вход для Fantasy."""
    sim = BracketSimulator(equal_ratings(8), playoff_config, seed=97)
    result = sim.run(simulations=500)

    distribution = result.series_distribution(1)
    assert min(distribution) == 2
    assert max(distribution) == 6
    assert sum(distribution.values()) == pytest.approx(1.0)
    assert 2 < result.expected_series(1) < 6


def test_places_add_up_to_a_full_bracket(playoff_config):
    """Восемь команд занимают ровно восемь мест: одно первое, два места 5-6."""
    sim = BracketSimulator(make_ratings(8), playoff_config, seed=101)
    result = sim.run(simulations=400)

    for team in result.team_ids:
        assert sum(result.place_probabilities(team).values()) == pytest.approx(1.0)

    champions = sum(
        result.place_probabilities(t).get("1", 0.0) for t in result.team_ids
    )
    shared = sum(result.place_probabilities(t).get("5-6", 0.0) for t in result.team_ids)
    assert champions == pytest.approx(1.0)
    assert shared == pytest.approx(2.0)


def test_top_probability_grows_with_the_bar(playoff_config):
    sim = BracketSimulator(make_ratings(8, spread=60.0), playoff_config, seed=103)
    result = sim.run(simulations=600)

    champion = result.top_probability(1, places=1)
    top_four = result.top_probability(1, places=4)
    assert champion == pytest.approx(result.champion_probability[1])
    assert champion <= result.top_probability(1, places=2) <= top_four <= 1.0
    assert result.top_probability(1, places=8) == pytest.approx(1.0)


# --- прогноз на незакрытые места ----------------------------------------------


def test_the_forecast_is_one_bracket_and_not_fourteen_answers(playoff_config):
    """Прогноз проходит турнир целиком, а не отвечает по каждому месту отдельно.

    Самая вероятная команда каждого места по отдельности складывается в сетку,
    которой не бывает: команда стоит и в финале верхней, и в полуфинале нижней,
    куда после выигранного полуфинала верхней попасть уже нельзя.
    """
    sim = BracketSimulator(
        make_ratings(8, spread=60.0),
        playoff_config,
        quarterfinals=((1, 8), (4, 5), (3, 6), (2, 7)),
    )
    pairs = sim.projected_pairs()

    assert pairs["ubqf1"] == (1, 8)
    # В каждой серии проходит фаворит, поэтому верхняя сетка идёт по посеву.
    assert pairs["ubsf1"] == (1, 4)
    assert pairs["ubf"] == (1, 2)
    # Проигравший полуфинала верхней уходит в противоположную половину нижней.
    assert pairs["lbr2_1"] == (3, 5)
    assert pairs["lbr2_2"] == (4, 6)
    # Главное: выигравший полуфинал верхней в полуфинале нижней оказаться не может.
    assert not set(pairs["ubf"]) & set(pairs["lbsf"])
    assert pairs["lbf"] == (2, 3)
    assert pairs["gf"] == (1, 2)


def test_the_forecast_starts_from_what_is_already_played(playoff_config):
    """Сыгранное задаёт разводку: дальше идёт тот, кто выиграл, а не кто сильнее."""
    sim = BracketSimulator(
        make_ratings(8, spread=60.0),
        playoff_config,
        quarterfinals=((1, 8), (4, 5), (3, 6), (2, 7)),
        results={"ubqf1": 8},
        participants={"ubqf1": (1, 8)},
    )
    pairs = sim.projected_pairs()

    assert pairs["ubsf1"] == (8, 4)
    assert pairs["lbr1_1"] == (1, 5)


def test_side_probabilities_answer_by_branch(playoff_config):
    """У места два входа, и вопрос «кто здесь окажется» у каждого свой."""
    sim = BracketSimulator(
        make_ratings(8),
        playoff_config,
        seed=11,
        quarterfinals=((1, 8), (4, 5), (3, 6), (2, 7)),
    )
    result = sim.run(simulations=400)

    left = result.side_probabilities("ubsf1", 0)
    right = result.side_probabilities("ubsf1", 1)
    assert set(left) <= {1, 8}, "слева приходит только победитель первого четвертьфинала"
    assert set(right) <= {4, 5}
    assert sum(left.values()) == pytest.approx(1.0)

    merged = result.participant_probabilities("ubsf1")
    for team, value in merged.items():
        assert left.get(team, 0.0) + right.get(team, 0.0) == pytest.approx(value)
