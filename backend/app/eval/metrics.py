"""Метрики качества вероятностного прогноза.

Точность (доля угаданных) для матчей Dota 2 — плохая метрика: она не отличает
уверенный правильный прогноз от прогноза 50.1%, и её легко улучшить, всегда
ставя на фаворита. Поэтому основные числа здесь — log loss и Brier: обе штрафуют
за уверенность в ошибке, и обе минимизируются только честной вероятностью.

Калибровка и острота (sharpness) идут парой и без второй первая бессмысленна:
модель, всегда выдающая базовую частоту, идеально откалибрована и совершенно
бесполезна. Поэтому отчёт всегда печатает обе.
"""

from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Sequence

import numpy as np

# Вероятности зажимаются перед логарифмом: одна уверенная ошибка (p=0) иначе
# даёт бесконечный log loss и уничтожает сравнение моделей.
EPSILON = 1e-15


def _arrays(probs: Sequence[float], outcomes: Sequence[bool]) -> tuple[np.ndarray, np.ndarray]:
    p = np.asarray(probs, dtype=float)
    y = np.asarray(outcomes, dtype=float)
    if p.shape != y.shape:
        raise ValueError(f"прогнозов {p.shape}, исходов {y.shape} — размеры должны совпадать")
    return p, y


def log_loss(probs: Sequence[float], outcomes: Sequence[bool]) -> float:
    """Средний отрицательный логарифм правдоподобия. Меньше — лучше.

    Ориентиры: 0.693 — честная монетка (ln 2), выше — модель хуже монетки.
    """
    p, y = _arrays(probs, outcomes)
    if p.size == 0:
        return float("nan")
    p = np.clip(p, EPSILON, 1.0 - EPSILON)
    return float(-np.mean(y * np.log(p) + (1.0 - y) * np.log(1.0 - p)))


def brier_score(probs: Sequence[float], outcomes: Sequence[bool]) -> float:
    """Средний квадрат ошибки вероятности. Меньше — лучше; монетка даёт 0.25."""
    p, y = _arrays(probs, outcomes)
    if p.size == 0:
        return float("nan")
    return float(np.mean((p - y) ** 2))


def accuracy(probs: Sequence[float], outcomes: Sequence[bool]) -> float:
    """Доля угаданных сторон. Прогноз ровно 0.5 не засчитывается никому."""
    p, y = _arrays(probs, outcomes)
    if p.size == 0:
        return float("nan")
    decided = p != 0.5
    if not decided.any():
        return float("nan")
    return float(np.mean((p[decided] > 0.5) == (y[decided] > 0.5)))


def sharpness(probs: Sequence[float]) -> float:
    """Разброс прогнозов. Ноль означает, что модель всегда говорит одно и то же."""
    p = np.asarray(probs, dtype=float)
    return float(np.std(p)) if p.size else float("nan")


@dataclass(frozen=True, slots=True)
class CalibrationBin:
    low: float
    high: float
    count: int
    mean_predicted: float
    observed: float

    @property
    def gap(self) -> float:
        return abs(self.mean_predicted - self.observed)


def calibration_bins(
    probs: Sequence[float], outcomes: Sequence[bool], *, bins: int = 10
) -> list[CalibrationBin]:
    """Разложить прогнозы по корзинам и сравнить обещанное с наблюдаемым.

    Пустые корзины пропускаются: строка «0 матчей, 0% против 0%» ничего не значит,
    а в глаза бросается наравне с настоящими.
    """
    p, y = _arrays(probs, outcomes)
    if p.size == 0:
        return []

    edges = np.linspace(0.0, 1.0, bins + 1)
    # `right=True` и сдвиг нуля: иначе p=0.0 попадает в корзину -1, а p=1.0 — за край.
    index = np.clip(np.digitize(p, edges[1:-1], right=True), 0, bins - 1)

    result: list[CalibrationBin] = []
    for b in range(bins):
        mask = index == b
        count = int(mask.sum())
        if count == 0:
            continue
        result.append(
            CalibrationBin(
                low=float(edges[b]),
                high=float(edges[b + 1]),
                count=count,
                mean_predicted=float(p[mask].mean()),
                observed=float(y[mask].mean()),
            )
        )
    return result


def expected_calibration_error(
    probs: Sequence[float], outcomes: Sequence[bool], *, bins: int = 10
) -> float:
    """Средневзвешенный разрыв между обещанным и наблюдаемым. Меньше — лучше."""
    rows = calibration_bins(probs, outcomes, bins=bins)
    total = sum(r.count for r in rows)
    if not total:
        return float("nan")
    return sum(r.count * r.gap for r in rows) / total


@dataclass(frozen=True, slots=True)
class Report:
    """Сводка по одной модели на одной выборке."""

    name: str
    predictions: int
    abstentions: int
    log_loss: float
    brier: float
    accuracy: float
    sharpness: float
    ece: float
    calibration: tuple[CalibrationBin, ...]

    @property
    def coverage(self) -> float:
        """Доля матчей, по которым модель вообще высказалась."""
        total = self.predictions + self.abstentions
        return self.predictions / total if total else float("nan")

    def summary(self) -> str:
        return (
            f"{self.name:<24} logloss={self.log_loss:.4f}  brier={self.brier:.4f}  "
            f"acc={self.accuracy:.3f}  ece={self.ece:.4f}  sharp={self.sharpness:.3f}  "
            f"n={self.predictions} ({self.coverage:.0%})"
        )

    def calibration_table(self) -> str:
        lines = [f"{'корзина':>12}  {'n':>5}  {'обещано':>8}  {'факт':>8}  {'разрыв':>7}"]
        for row in self.calibration:
            lines.append(
                f"{row.low:.1f}-{row.high:.1f}".rjust(12)
                + f"  {row.count:>5}  {row.mean_predicted:>8.3f}"
                f"  {row.observed:>8.3f}  {row.gap:>7.3f}"
            )
        return "\n".join(lines)


def evaluate(
    name: str,
    probs: Sequence[float],
    outcomes: Sequence[bool],
    *,
    abstentions: int = 0,
    bins: int = 10,
) -> Report:
    """Посчитать все метрики разом."""
    return Report(
        name=name,
        predictions=len(probs),
        abstentions=abstentions,
        log_loss=log_loss(probs, outcomes),
        brier=brier_score(probs, outcomes),
        accuracy=accuracy(probs, outcomes),
        sharpness=sharpness(probs),
        ece=expected_calibration_error(probs, outcomes, bins=bins),
        calibration=tuple(calibration_bins(probs, outcomes, bins=bins)),
    )
