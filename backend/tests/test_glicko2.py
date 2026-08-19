"""Тесты Glicko-2, включая эталонный пример из статьи Гликмана."""

from __future__ import annotations

import math

import pytest

from app.analytics.glicko2 import (
    DEFAULT_RD,
    SCALE,
    GameResult,
    Glicko2,
    Rating,
)


@pytest.fixture(scope="module")
def engine():
    return Glicko2(tau=0.5)


def test_glickman_reference_example(engine):
    """Пример из "Example of the Glicko-2 system", стр. 3.

    Игрок 1500/200/0.06 против 1400/30, 1550/100, 1700/300 со счётом 1, 0, 0.
    Ожидание из статьи: 1464.06 / 151.52 / 0.05999.
    """
    player = Rating(rating=1500.0, rd=200.0, volatility=0.06)
    results = [
        GameResult(Rating(1400.0, 30.0), 1.0),
        GameResult(Rating(1550.0, 100.0), 0.0),
        GameResult(Rating(1700.0, 300.0), 0.0),
    ]

    updated = engine.rate(player, results)

    assert updated.rating == pytest.approx(1464.06, abs=0.01)
    assert updated.rd == pytest.approx(151.52, abs=0.01)
    assert updated.volatility == pytest.approx(0.05999, abs=1e-5)


def test_internal_scale_roundtrip():
    rating = Rating(1723.4, 87.2, 0.055)
    restored = Rating.from_internal(rating.mu, rating.phi, rating.volatility)
    assert restored.rating == pytest.approx(rating.rating)
    assert restored.rd == pytest.approx(rating.rd)


def test_default_rating_is_scale_origin():
    assert Rating().mu == pytest.approx(0.0)
    assert Rating(rd=SCALE).phi == pytest.approx(1.0)


def test_win_moves_rating_up_and_shrinks_rd(engine):
    player = Rating(1500.0, 200.0)
    updated = engine.rate(player, [GameResult(Rating(1500.0, 200.0), 1.0)])
    assert updated.rating > player.rating
    assert updated.rd < player.rd


def test_loss_moves_rating_down(engine):
    player = Rating(1500.0, 200.0)
    updated = engine.rate(player, [GameResult(Rating(1500.0, 200.0), 0.0)])
    assert updated.rating < player.rating


def test_draw_barely_moves_equal_teams(engine):
    player = Rating(1500.0, 100.0)
    updated = engine.rate(player, [GameResult(Rating(1500.0, 100.0), 0.5)])
    assert updated.rating == pytest.approx(1500.0, abs=0.5)


def test_uncertain_team_moves_more_than_established(engine):
    """Ключевое свойство Glicko-2: высокий RD = сильная реакция на результат."""
    opponent = GameResult(Rating(1500.0, 50.0), 1.0)
    rookie = engine.rate(Rating(1500.0, 300.0), [opponent])
    veteran = engine.rate(Rating(1500.0, 50.0), [opponent])
    assert rookie.rating - 1500.0 > (veteran.rating - 1500.0) * 3


def test_upset_over_stronger_opponent_gains_more(engine):
    player = Rating(1500.0, 120.0)
    vs_strong = engine.rate(player, [GameResult(Rating(1900.0, 60.0), 1.0)])
    vs_weak = engine.rate(player, [GameResult(Rating(1100.0, 60.0), 1.0)])
    assert vs_strong.rating > vs_weak.rating


def test_inactivity_grows_rd_but_keeps_rating(engine):
    player = Rating(1700.0, 80.0, 0.06)
    idle = engine.rate_unplayed(player)
    assert idle.rating == pytest.approx(player.rating)
    assert idle.rd > player.rd


def test_inactivity_rd_capped_at_default(engine):
    player = Rating(1700.0, 349.0, 0.9)
    for _ in range(20):
        player = engine.rate_unplayed(player)
    assert player.rd <= DEFAULT_RD


def test_empty_period_equals_unplayed(engine):
    player = Rating(1600.0, 90.0)
    assert engine.rate(player, []) == engine.rate_unplayed(player)


# --- вероятности --------------------------------------------------------------


def test_equal_ratings_give_even_odds(engine):
    assert engine.win_probability(Rating(1500.0, 50.0), Rating(1500.0, 50.0)) == pytest.approx(0.5)


def test_probabilities_are_complementary(engine):
    a, b = Rating(1800.0, 60.0), Rating(1450.0, 110.0)
    assert engine.win_probability(a, b) + engine.win_probability(b, a) == pytest.approx(1.0)


def test_stronger_team_favoured(engine):
    p = engine.win_probability(Rating(1800.0, 60.0), Rating(1500.0, 60.0))
    assert 0.5 < p < 1.0


def test_high_uncertainty_pulls_prediction_toward_coinflip(engine):
    confident = engine.win_probability(Rating(1800.0, 40.0), Rating(1500.0, 40.0))
    uncertain = engine.win_probability(Rating(1800.0, 320.0), Rating(1500.0, 320.0))
    assert 0.5 < uncertain < confident


@pytest.mark.parametrize("best_of", [1, 3, 5])
def test_series_probability_amplifies_edge(engine, best_of):
    favourite, underdog = Rating(1750.0, 50.0), Rating(1500.0, 50.0)
    single = engine.win_probability(favourite, underdog)
    series = engine.series_win_probability(favourite, underdog, best_of=best_of)
    if best_of == 1:
        assert series == pytest.approx(single)
    else:
        assert series > single


def test_series_probability_symmetric(engine):
    a, b = Rating(1700.0, 70.0), Rating(1520.0, 90.0)
    total = engine.series_win_probability(a, b, best_of=5) + engine.series_win_probability(
        b, a, best_of=5
    )
    assert total == pytest.approx(1.0)


def test_even_best_of_rejected(engine):
    with pytest.raises(ValueError, match="нечётным"):
        engine.series_win_probability(Rating(), Rating(), best_of=2)


def test_invalid_score_rejected():
    with pytest.raises(ValueError, match=r"score"):
        GameResult(Rating(), 1.5)


def test_invalid_tau_rejected():
    with pytest.raises(ValueError, match="tau"):
        Glicko2(tau=0.0)


# --- практические фильтры -----------------------------------------------------


def test_listable_requires_low_rd_and_recent_match():
    assert Rating(1600.0, 80.0).is_listable(days_since_last_match=10)
    assert not Rating(1600.0, 120.0).is_listable(days_since_last_match=10)
    assert not Rating(1600.0, 80.0).is_listable(days_since_last_match=90)


def test_confidence_interval_brackets_rating():
    low, high = Rating(1600.0, 100.0).interval()
    assert low < 1600.0 < high
    assert math.isclose(high - low, 2 * 1.96 * 100.0)


# --- калибровка уверенности ---------------------------------------------------


def test_temperature_shrinks_the_forecast_without_touching_the_order():
    """Температура меняет меру уверенности, а не то, кто фаворит."""
    strong = Rating(1700.0, 50.0)
    weak = Rating(1500.0, 50.0)

    raw = Glicko2().win_probability(strong, weak)
    cool = Glicko2(temperature=0.6).win_probability(strong, weak)

    assert 0.5 < cool < raw
    assert Glicko2(temperature=0.6).win_probability(weak, strong) == pytest.approx(1 - cool)


def test_temperature_leaves_an_even_match_even():
    equal = Rating(1600.0, 60.0)
    assert Glicko2(temperature=0.4).win_probability(equal, equal) == pytest.approx(0.5)


def test_temperature_does_not_leak_into_the_rating():
    """Калибровка — свойство прогноза: рейтинг должен обновляться как обычно."""
    player = Rating(1500.0, 200.0)
    games = [GameResult(Rating(1400.0, 30.0), 1.0), GameResult(Rating(1550.0, 100.0), 0.0)]

    plain = Glicko2().rate(player, games)
    tempered = Glicko2(temperature=0.5).rate(player, games)

    assert tempered == plain


def test_a_temperature_outside_the_range_is_rejected():
    with pytest.raises(ValueError, match="temperature"):
        Glicko2(temperature=0.0)
