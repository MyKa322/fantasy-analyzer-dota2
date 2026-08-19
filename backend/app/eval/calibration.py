"""Калибровка уверенности: во сколько раз рейтинг преувеличивает разрыв.

Glicko-2 хорошо отвечает на вопрос «кто сильнее» и хуже — «насколько». Разницу
рейтингов он переводит в вероятность по своей формуле, и на истории проекта эта
вероятность раз за разом оказывается смелее того, что показывают результаты:
матчи, которым модель давала 70%, выигрываются примерно в 63% случаев. Для
таблицы «кто фаворит» это неважно, а для сетки плей-офф важно вдвойне — там
вероятность серии возводится в степень, и завышенная уверенность в карте
превращается в завышенную уверенность в чемпионе.

Лечится это одним числом: логит прогноза умножается на температуру. Меньше
единицы — прогноз сжимается к 50%, порядок команд при этом не меняется вовсе.
Число не назначается, а подбирается по истории тем же ходом вперёд по времени,
что и проверка моделей: прогноз строится по состоянию на начало периода, и
только сыгранный период попадает в рейтинг. Иначе температура подгонялась бы
под матчи, которые модель уже знает, и на новых оказалась бы бесполезной.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from app.analytics.glicko2 import Glicko2
from app.analytics.rating import MatchRecord
from app.eval.backtest import by_period
from app.eval.baselines import Glicko2Predictor
from app.eval.metrics import log_loss

log = logging.getLogger(__name__)

#: Сетка перебора. Шире единицы — на случай, если модель окажется, наоборот,
#: слишком осторожной; это тоже стоит увидеть, а не спрятать.
DEFAULT_GRID: tuple[float, ...] = tuple(round(0.20 + 0.05 * i, 2) for i in range(37))

#: Меньше этого числа прогнозов калибровать нечего: температура сядет на шум.
MIN_SAMPLES = 200


@dataclass(frozen=True, slots=True)
class Calibration:
    """Итог подбора: сама температура и чем она обоснована."""

    temperature: float
    samples: int
    log_loss: float
    raw_log_loss: float

    @property
    def gain(self) -> float:
        """Насколько калибровка улучшила log loss. Ноль — калибровать нечего."""
        return self.raw_log_loss - self.log_loss

    def describe(self) -> str:
        return (
            f"температура {self.temperature:.2f} по {self.samples} прогнозам: "
            f"log loss {self.raw_log_loss:.4f} -> {self.log_loss:.4f}"
        )


def collect_predictions(
    matches: Iterable[MatchRecord],
    *,
    engine: Glicko2 | None = None,
    period_days: int = 3,
    warmup_periods: int = 4,
    min_games: int = 3,
) -> tuple[list[float], list[bool]]:
    """Прогнозы модели на матчи, которых она на момент прогноза не знала."""
    predictor = Glicko2Predictor(engine=engine or Glicko2(), min_games=min_games)
    probabilities: list[float] = []
    outcomes: list[bool] = []

    for number, (_, period_matches) in enumerate(by_period(matches, period_days)):
        if number >= warmup_periods:
            for match in period_matches:
                probability = predictor.predict(match)
                if probability is not None:
                    probabilities.append(float(probability))
                    outcomes.append(bool(match.radiant_win))
        predictor.update(period_matches)

    return probabilities, outcomes


def best_temperature(
    probabilities: Sequence[float],
    outcomes: Sequence[bool],
    *,
    grid: Sequence[float] = DEFAULT_GRID,
) -> Calibration:
    """Температура с наименьшим log loss на готовых прогнозах."""
    raw = log_loss(probabilities, outcomes)
    if len(probabilities) < MIN_SAMPLES:
        return Calibration(1.0, len(probabilities), raw, raw)

    scored = [
        (log_loss([_tempered(p, t) for p in probabilities], outcomes), t) for t in grid
    ]
    loss, temperature = min(scored)
    if loss >= raw:
        # Сжимать нечего: модель и так не переоценивает разрыв.
        return Calibration(1.0, len(probabilities), raw, raw)
    return Calibration(temperature, len(probabilities), loss, raw)


def fit_temperature(
    matches: Iterable[MatchRecord],
    *,
    engine: Glicko2 | None = None,
    period_days: int = 3,
    warmup_periods: int = 4,
    min_games: int = 3,
    grid: Sequence[float] = DEFAULT_GRID,
) -> Calibration:
    """Подобрать температуру по истории матчей.

    `engine` — движок без калибровки (её и подбираем); период должен совпадать с
    тем, которым считается сам рейтинг.
    """
    probabilities, outcomes = collect_predictions(
        matches,
        engine=engine,
        period_days=period_days,
        warmup_periods=warmup_periods,
        min_games=min_games,
    )
    calibration = best_temperature(probabilities, outcomes, grid=grid)
    log.info("калибровка: %s", calibration.describe())
    return calibration


def _tempered(probability: float, temperature: float) -> float:
    """Сжать логит вероятности. Порядок сохраняется, 50% остаётся 50%."""
    odds = min(max(probability, 1e-12), 1.0 - 1e-12)
    return odds**temperature / (odds**temperature + (1.0 - odds) ** temperature)
