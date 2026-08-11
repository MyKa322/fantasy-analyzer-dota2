"""Тесты харнесса проверки моделей.

Харнесс — инструмент измерения, поэтому его самого надо мерить по известным
ответам: у монетки log loss равен ln 2, у идеального прогноза — нулю, у уверенно
ошибающейся модели — большой величине. Если эти три числа сходятся, числам по
настоящим моделям можно верить.

Отдельно проверяется анти-лик: модель, которой скормили её же будущее, обязана
показать невозможно хороший результат — тест на это гарантирует, что цикл
walk-forward действительно не пускает результаты матча в его собственный прогноз.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

import pytest

from app.analytics.rating import MatchRecord
from app.eval import (
    CoinFlip,
    Glicko2Calibrated,
    Glicko2Predictor,
    Glicko2WithSide,
    RadiantPrior,
    accuracy,
    brier_score,
    calibration_bins,
    evaluate,
    expected_calibration_error,
    log_loss,
    sharpness,
    walk_forward,
)

START = datetime(2026, 1, 1, tzinfo=timezone.utc)


def make_matches(count: int, *, radiant_wins_every: int = 2, days_step: float = 1.0):
    """Синтетическая история: команды 1..4, детерминированные результаты."""
    matches = []
    for i in range(count):
        radiant = 1 + (i % 2)
        dire = 3 + (i % 2)
        matches.append(
            MatchRecord(
                match_id=1000 + i,
                start_time=START + timedelta(days=days_step * i),
                radiant_team_id=radiant,
                dire_team_id=dire,
                radiant_win=(i % radiant_wins_every == 0),
            )
        )
    return matches


# --- метрики по известным ответам --------------------------------------------


def test_coin_flip_log_loss_is_ln2():
    """Опорное число всей лестницы."""
    assert log_loss([0.5] * 100, [True, False] * 50) == pytest.approx(math.log(2), abs=1e-12)


def test_perfect_prediction_scores_zero():
    assert log_loss([1.0, 0.0, 1.0], [True, False, True]) == pytest.approx(0.0, abs=1e-9)
    assert brier_score([1.0, 0.0, 1.0], [True, False, True]) == pytest.approx(0.0)


def test_confident_and_wrong_is_punished_but_finite():
    """Без зажима p=0 дал бы бесконечность и сломал сравнение моделей."""
    value = log_loss([0.0], [True])
    assert value > 30.0
    assert math.isfinite(value)


def test_brier_of_coin_flip_is_quarter():
    assert brier_score([0.5] * 4, [True, False, True, False]) == pytest.approx(0.25)


def test_accuracy_ignores_undecided_predictions():
    # Три прогноза 0.5 не засчитываются никому, остаются два — оба верных.
    assert accuracy([0.5, 0.5, 0.5, 0.9, 0.1], [True, False, True, True, False]) == 1.0


def test_accuracy_is_nan_when_nothing_is_decided():
    assert math.isnan(accuracy([0.5, 0.5], [True, False]))


def test_sharpness_zero_for_constant_model():
    assert sharpness([0.6] * 10) == pytest.approx(0.0)


def test_empty_input_is_nan_not_crash():
    assert math.isnan(log_loss([], []))
    assert math.isnan(brier_score([], []))
    assert calibration_bins([], []) == []


def test_mismatched_lengths_rejected():
    with pytest.raises(ValueError):
        log_loss([0.5, 0.5], [True])


# --- калибровка ---------------------------------------------------------------


def test_calibration_bins_cover_the_edges():
    """p=0.0 и p=1.0 должны попадать в крайние корзины, а не выпадать за край."""
    rows = calibration_bins([0.0, 1.0], [False, True], bins=10)
    assert len(rows) == 2
    assert rows[0].low == pytest.approx(0.0)
    assert rows[-1].high == pytest.approx(1.0)
    assert sum(r.count for r in rows) == 2


def test_perfectly_calibrated_model_has_zero_ece():
    # 100 прогнозов по 0.7, ровно 70 сбылось.
    probs = [0.7] * 100
    outcomes = [True] * 70 + [False] * 30
    assert expected_calibration_error(probs, outcomes) == pytest.approx(0.0, abs=1e-9)


def test_overconfident_model_has_visible_ece():
    probs = [0.9] * 100
    outcomes = [True] * 50 + [False] * 50
    assert expected_calibration_error(probs, outcomes) == pytest.approx(0.4, abs=1e-9)


def test_empty_bins_are_dropped():
    rows = calibration_bins([0.05, 0.06], [True, False], bins=10)
    assert len(rows) == 1
    assert rows[0].count == 2


def test_report_summary_mentions_coverage():
    report = evaluate("m", [0.5, 0.5], [True, False], abstentions=2)
    assert report.coverage == pytest.approx(0.5)
    assert "logloss" in report.summary()
    assert "корзина" in report.calibration_table()


# --- walk-forward -------------------------------------------------------------


def test_empty_history_returns_empty_result():
    result = walk_forward([], [CoinFlip()])
    assert result.matches_scored == 0
    assert result.reports == ()


def test_warmup_periods_are_excluded_from_scoring():
    matches = make_matches(40, days_step=1.0)  # ~6 недельных периодов
    without = walk_forward(matches, [CoinFlip()], warmup_periods=0)
    with_warmup = walk_forward(matches, [CoinFlip()], warmup_periods=4)

    assert without.matches_scored == 40
    assert with_warmup.matches_scored < without.matches_scored
    assert with_warmup.matches_skipped_warmup == 40 - with_warmup.matches_scored


def test_coin_flip_scores_ln2_on_real_loop():
    """Сквозная проверка: цикл не искажает метрику."""
    result = walk_forward(make_matches(60), [CoinFlip()], warmup_periods=1)
    report = result.reports[0]
    assert report.log_loss == pytest.approx(math.log(2), abs=1e-12)


def test_glicko_abstains_until_teams_have_history():
    matches = make_matches(60)
    result = walk_forward(matches, [Glicko2Predictor(min_games=3)], warmup_periods=0)
    report = result.reports[0]
    # Первые матчи каждой команды непредсказуемы по построению — модель молчит.
    assert report.abstentions > 0
    assert report.predictions > 0
    assert report.coverage < 1.0


def test_predictor_does_not_see_its_own_match():
    """Анти-лик: модель, знающая исход, показала бы ноль — а она его не знает.

    Модель ниже жульничает настолько, насколько ей позволяет цикл: она отвечает
    по последнему, что ей рассказали через `update`. Если бы цикл обновлял её
    матчами до прогноза, она угадывала бы идеально.
    """

    class Peeker:
        name = "peeker"

        def __init__(self) -> None:
            self.known: dict[int, bool] = {}

        def predict(self, match: MatchRecord) -> float | None:
            if match.match_id in self.known:
                return 1.0 if self.known[match.match_id] else 0.0
            return 0.5

        def update(self, matches) -> None:
            for m in matches:
                self.known[m.match_id] = bool(m.radiant_win)

    result = walk_forward(make_matches(60), [Peeker()], warmup_periods=1)
    report = result.reports[0]
    # Ни один матч не был известен заранее — значит все прогнозы остались 0.5.
    assert report.log_loss == pytest.approx(math.log(2), abs=1e-12)
    assert report.sharpness == pytest.approx(0.0)


def test_ladder_runs_and_ranks_by_log_loss():
    matches = make_matches(120)
    result = walk_forward(
        matches,
        [CoinFlip(), RadiantPrior(), Glicko2Predictor(), Glicko2WithSide()],
        warmup_periods=2,
    )
    assert len(result.reports) == 4
    assert {r.name for r in result.reports} == {
        "coin-flip",
        "radiant-prior",
        "glicko2",
        "glicko2+side",
    }
    best = result.best()
    assert best is not None
    assert best.log_loss <= min(r.log_loss for r in result.reports if r.predictions)


def test_calibration_is_monotone_and_cannot_change_accuracy():
    """Температура тянет прогнозы к 0.5, но порядок сохраняет.

    Свойство важно практически: калибровка не должна «чинить» долю угаданных —
    если она её меняет, значит преобразование не монотонное и где-то ошибка.
    """
    matches = make_matches(300)
    plain = Glicko2WithSide()
    calibrated = Glicko2Calibrated()
    result = walk_forward(matches, [plain, calibrated], warmup_periods=2)

    by_name = {r.name: r for r in result.reports}
    assert by_name["glicko2+side"].accuracy == pytest.approx(
        by_name["glicko2+calibrated"].accuracy
    )


def test_temperature_stays_at_default_until_enough_history():
    model = Glicko2Calibrated(min_history=10_000)
    walk_forward(make_matches(60), [model], warmup_periods=0)
    assert model.temperature == 1.0


def test_overconfident_history_pushes_temperature_above_one():
    """Если модель уверена сильнее, чем права, температура обязана вырасти."""
    model = Glicko2Calibrated(min_history=20)
    model._seen_logits = [2.0] * 60 + [-2.0] * 60  # обещает ~0.88 / ~0.12
    model._seen_outcomes = [1.0] * 36 + [0.0] * 24 + [0.0] * 36 + [1.0] * 24  # выходит 0.6 / 0.4
    model._fit_temperature()
    assert model.temperature > 1.0


def test_radiant_prior_learns_the_base_rate():
    """История, где Radiant выигрывает всегда: приор обязан уехать вверх."""
    matches = [
        MatchRecord(
            match_id=i,
            start_time=START + timedelta(days=i),
            radiant_team_id=1,
            dire_team_id=2,
            radiant_win=True,
        )
        for i in range(200)
    ]
    model = RadiantPrior()
    result = walk_forward(matches, [model], warmup_periods=2)
    assert model.predict(matches[-1]) > 0.85
    assert result.reports[0].log_loss < math.log(2)
