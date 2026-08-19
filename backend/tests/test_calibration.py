"""Подбор температуры: модель должна сама признавать, что переоценила разрыв."""

from __future__ import annotations

import math
import random
from datetime import datetime, timedelta, timezone

import pytest

from app.analytics.glicko2 import Glicko2, Rating
from app.analytics.rating import MatchRecord
from app.eval.calibration import (
    MIN_SAMPLES,
    best_temperature,
    fit_temperature,
)

START = datetime(2026, 1, 1, tzinfo=timezone.utc)


def synthetic_matches(
    *, teams: int = 12, days: int = 120, per_day: int = 6, shrink: float = 1.0, seed: int = 7
) -> list[MatchRecord]:
    """История, где настоящая сила команд известна, а разрыв сжат `shrink`.

    `shrink < 1` — мир, в котором результаты ближе к монетке, чем предсказывает
    разница сил: ровно та ситуация, ради которой калибровка и нужна.
    """
    rng = random.Random(seed)
    strength = {team: (team - teams / 2) * 0.25 for team in range(1, teams + 1)}
    matches: list[MatchRecord] = []
    match_id = 1
    for day in range(days):
        for _ in range(per_day):
            left, right = rng.sample(range(1, teams + 1), 2)
            gap = shrink * (strength[left] - strength[right])
            probability = 1.0 / (1.0 + math.exp(-gap))
            matches.append(
                MatchRecord(
                    match_id=match_id,
                    start_time=START + timedelta(days=day, minutes=match_id % 600),
                    radiant_team_id=left,
                    dire_team_id=right,
                    radiant_win=rng.random() < probability,
                )
            )
            match_id += 1
    return matches


def test_a_flatter_world_asks_for_a_colder_forecast():
    """Если результаты ровнее, чем думает рейтинг, температура падает ниже единицы."""
    calibration = fit_temperature(synthetic_matches(shrink=0.45), period_days=3)

    assert calibration.temperature < 0.9
    assert calibration.log_loss < calibration.raw_log_loss
    assert calibration.gain > 0.0


def test_a_world_the_model_describes_needs_no_correction():
    """Там, где мир устроен как модель, калибровка почти ничего не меняет."""
    calibration = fit_temperature(synthetic_matches(shrink=1.0, seed=11), period_days=3)

    assert calibration.temperature == pytest.approx(1.0, abs=0.35)
    assert calibration.gain < 0.02


def test_the_forecast_keeps_its_order_after_calibration():
    calibration = fit_temperature(synthetic_matches(shrink=0.4, seed=3), period_days=3)
    engine = Glicko2(temperature=calibration.temperature)
    strong, weak = Rating(1700.0, 60.0), Rating(1500.0, 60.0)

    assert engine.win_probability(strong, weak) > 0.5
    assert engine.win_probability(strong, weak) < Glicko2().win_probability(strong, weak)


def test_too_little_history_leaves_the_forecast_alone():
    """На горстке прогнозов температура сядет на шум — лучше не трогать."""
    probabilities = [0.6] * (MIN_SAMPLES - 1)
    outcomes = [True] * (MIN_SAMPLES - 1)

    assert best_temperature(probabilities, outcomes).temperature == 1.0


def test_an_already_honest_forecast_is_left_alone():
    """Если сжатие не улучшает log loss, температура остаётся единицей."""
    probabilities = [0.75] * 400 + [0.25] * 400
    outcomes = [i % 4 != 0 for i in range(400)] + [i % 4 == 0 for i in range(400)]

    assert best_temperature(probabilities, outcomes).temperature == 1.0


def test_calibration_is_measured_out_of_sample():
    """Прогнозы берутся до того, как модель узнала период — иначе это подгонка."""
    matches = synthetic_matches(shrink=0.5, seed=5)
    calibration = fit_temperature(matches, period_days=3, warmup_periods=4)

    # Разгонные периоды в зачёт не идут, значит прогнозов меньше, чем матчей.
    assert 0 < calibration.samples < len(matches)
