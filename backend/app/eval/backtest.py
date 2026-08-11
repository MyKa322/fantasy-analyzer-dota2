"""Проверка моделей вперёд по времени (walk-forward).

Устройство цикла — единственная защита от утечки будущего, и оно повторяет
логику `analytics/rating.py`: матчи разложены по рейтинговым периодам, прогноз на
матч строится по состоянию модели на *начало* его периода, и только когда период
отыгран целиком, модель узнаёт его результаты.

Почему период, а не «строго предыдущий матч»: Glicko-2 сам по себе считает матчи
внутри периода одновременными, и оценивать матч по рейтингу, уже впитавшему
соседний матч того же дня, — это лик, пусть и маленький. Побочная выгода:
один проход вместо пересчёта всей истории на каждый матч.

Первые периоды выбрасываются из зачёта. На старте у моделей нет данных ни о ком,
и включать эти матчи означает мерить не модель, а длину разгона: разница между
моделями там тонет в общем шуме.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Protocol, runtime_checkable

from app.analytics.rating import MatchRecord
from app.eval.metrics import Report, evaluate

log = logging.getLogger(__name__)


@runtime_checkable
class Predictor(Protocol):
    """Модель, дающая вероятность победы Radiant.

    `predict` возвращает None, если модель не берётся судить (например, команда
    встречается впервые). Воздержание — не ошибка и в метрики не идёт, но и
    прятать его нельзя: модель, точная на 5% матчей, не лучше модели, честной на
    всех. Поэтому покрытие печатается рядом с качеством.
    """

    name: str

    def predict(self, match: MatchRecord) -> float | None: ...

    def update(self, matches: Sequence[MatchRecord]) -> None: ...


def period_start(moment: datetime, origin: datetime, period: timedelta) -> datetime:
    elapsed = moment - origin
    return origin + int(elapsed // period) * period


@dataclass(slots=True)
class _Tally:
    probs: list[float] = field(default_factory=list)
    outcomes: list[bool] = field(default_factory=list)
    abstentions: int = 0


@dataclass(frozen=True, slots=True)
class BacktestResult:
    reports: tuple[Report, ...]
    matches_scored: int
    matches_skipped_warmup: int
    periods: int

    def table(self) -> str:
        head = (
            f"матчей в зачёте: {self.matches_scored}  "
            f"(разгон отброшен: {self.matches_skipped_warmup}, периодов: {self.periods})"
        )
        body = "\n".join(r.summary() for r in self.reports)
        return f"{head}\n{body}"

    def best(self) -> Report | None:
        """Модель с лучшим log loss среди высказавшихся."""
        scored = [r for r in self.reports if r.predictions > 0 and r.log_loss == r.log_loss]
        return min(scored, key=lambda r: r.log_loss) if scored else None


def walk_forward(
    matches: Iterable[MatchRecord],
    predictors: Sequence[Predictor],
    *,
    period_days: int = 7,
    warmup_periods: int = 4,
    bins: int = 10,
) -> BacktestResult:
    """Прогнать модели по истории вперёд по времени."""
    ordered = sorted(matches, key=lambda m: (m.start_time, m.match_id))
    if not ordered:
        return BacktestResult(reports=(), matches_scored=0, matches_skipped_warmup=0, periods=0)

    period = timedelta(days=period_days)
    origin = ordered[0].start_time

    buckets: dict[datetime, list[MatchRecord]] = defaultdict(list)
    for match in ordered:
        buckets[period_start(match.start_time, origin, period)].append(match)

    tallies: dict[str, _Tally] = {p.name: _Tally() for p in predictors}
    scored = 0
    skipped = 0

    for number, start in enumerate(sorted(buckets)):
        period_matches = buckets[start]
        counts_for_score = number >= warmup_periods

        for match in period_matches:
            if counts_for_score:
                scored += 1
            else:
                skipped += 1

            for predictor in predictors:
                probability = predictor.predict(match)
                if not counts_for_score:
                    continue
                tally = tallies[predictor.name]
                if probability is None:
                    tally.abstentions += 1
                    continue
                tally.probs.append(float(probability))
                tally.outcomes.append(bool(match.radiant_win))

        # Период отыгран — только теперь модели узнают его результаты.
        for predictor in predictors:
            predictor.update(period_matches)

    reports = tuple(
        evaluate(
            predictor.name,
            tallies[predictor.name].probs,
            tallies[predictor.name].outcomes,
            abstentions=tallies[predictor.name].abstentions,
            bins=bins,
        )
        for predictor in predictors
    )

    log.info(
        "walk-forward: %d матчей в зачёте, %d периодов, %d моделей",
        scored,
        len(buckets),
        len(predictors),
    )
    return BacktestResult(
        reports=reports,
        matches_scored=scored,
        matches_skipped_warmup=skipped,
        periods=len(buckets),
    )
