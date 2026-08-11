"""Проверка предсказательных моделей.

Модуль отвечает на единственный вопрос: стало ли лучше. Без него любое изменение
рейтинга или новая фича — это мнение, а не результат.
"""

from app.eval.backtest import BacktestResult, Predictor, walk_forward
from app.eval.baselines import (
    CoinFlip,
    Glicko2Calibrated,
    Glicko2Predictor,
    Glicko2WithSide,
    RadiantPrior,
    default_ladder,
)
from app.eval.metrics import (
    CalibrationBin,
    Report,
    accuracy,
    brier_score,
    calibration_bins,
    evaluate,
    expected_calibration_error,
    log_loss,
    sharpness,
)

__all__ = [
    "BacktestResult",
    "CalibrationBin",
    "CoinFlip",
    "Glicko2Calibrated",
    "Glicko2Predictor",
    "Glicko2WithSide",
    "Predictor",
    "RadiantPrior",
    "Report",
    "accuracy",
    "brier_score",
    "calibration_bins",
    "default_ladder",
    "evaluate",
    "expected_calibration_error",
    "log_loss",
    "sharpness",
    "walk_forward",
]
