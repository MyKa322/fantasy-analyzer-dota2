"""Лестница базовых моделей.

Смысл лестницы в том, чтобы у каждого улучшения был порог, ниже которого оно не
улучшение. Монетка задаёт абсолютный ноль (log loss = ln 2 ≈ 0.693). Базовая
частота Radiant показывает, сколько даёт вообще ничего не знающая модель, кроме
перекоса карты, — и этот порог уже нетривиален. Glicko-2 — то, что в проекте
работает сейчас; любая новая модель обязана обыграть именно его, а не монетку.

Все модели здесь копят состояние сами и обновляются только через `update`, то
есть по завершённым периодам. Никакая из них не видит матч, который прогнозирует.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from app.analytics.glicko2 import Glicko2, GameResult, Rating
from app.analytics.rating import MatchRecord


class CoinFlip:
    """Всегда 50%. Абсолютный ноль сравнения."""

    name = "coin-flip"

    def predict(self, match: MatchRecord) -> float | None:
        return 0.5

    def update(self, matches: Sequence[MatchRecord]) -> None:
        return None


class RadiantPrior:
    """Базовая частота побед Radiant по всему, что уже сыграно.

    Ноль знаний о командах — только перекос карты. Модель, не обыгрывающая этот
    порог, не знает про Dota ничего.
    """

    name = "radiant-prior"

    def __init__(self, *, prior_weight: float = 20.0) -> None:
        # Сглаживание к 0.5: без него первые же периоды дают дикие оценки вроде
        # 0.71 по семи матчам, и модель выглядит то гением, то дураком.
        self.prior_weight = prior_weight
        self._radiant_wins = 0
        self._games = 0

    def predict(self, match: MatchRecord) -> float | None:
        total = self._games + self.prior_weight
        return (self._radiant_wins + 0.5 * self.prior_weight) / total

    def update(self, matches: Sequence[MatchRecord]) -> None:
        for match in matches:
            self._games += 1
            self._radiant_wins += int(bool(match.radiant_win))


class Glicko2Predictor:
    """Действующая модель проекта: Glicko-2 по результатам карт.

    Воздерживается, пока обе команды не сыграли хотя бы `min_games` карт: до
    этого рейтинг — это стартовые 1500±350, то есть ровно 50% с видом знания.
    """

    name = "glicko2"

    def __init__(
        self,
        *,
        engine: Glicko2 | None = None,
        initial: Rating | None = None,
        min_games: int = 3,
    ) -> None:
        self.engine = engine or Glicko2()
        self.initial = initial or Rating()
        self.min_games = min_games
        self._ratings: dict[int, Rating] = {}
        self._games: dict[int, int] = {}

    def _rating(self, team_id: int) -> Rating:
        return self._ratings.get(team_id, self.initial)

    def predict(self, match: MatchRecord) -> float | None:
        radiant, dire = match.radiant_team_id, match.dire_team_id
        if min(self._games.get(radiant, 0), self._games.get(dire, 0)) < self.min_games:
            return None
        return self.engine.win_probability(self._rating(radiant), self._rating(dire))

    def update(self, matches: Sequence[MatchRecord]) -> None:
        """Впитать результаты периода — все матчи в нём считаются одновременными."""
        frozen = {
            team: self._rating(team)
            for match in matches
            for team in (match.radiant_team_id, match.dire_team_id)
        }
        results: dict[int, list[GameResult]] = {team: [] for team in frozen}

        for match in matches:
            winner, loser = match.winner(), match.loser()
            results[winner].append(GameResult(frozen[loser], 1.0))
            results[loser].append(GameResult(frozen[winner], 0.0))
            self._games[winner] = self._games.get(winner, 0) + 1
            self._games[loser] = self._games.get(loser, 0) + 1

        for team, played in results.items():
            self._ratings[team] = self.engine.rate(frozen[team], played)


class Glicko2WithSide(Glicko2Predictor):
    """Glicko-2 плюс поправка на сторону карты.

    Radiant выигрывает чаще Dire, и рейтинг об этом не знает: он симметричен по
    построению. Поправка вносится в логит-шкале — сложить вероятности напрямую
    нельзя, они выйдут за [0,1] на краях. Величина перекоса оценивается по уже
    сыгранному, а не задаётся константой: на разных патчах и уровнях игры он
    разный.

    Это первая модель лестницы, которая обязана обыграть предыдущую по log loss,
    иначе поправка не нужна.
    """

    name = "glicko2+side"

    def __init__(self, *, prior_weight: float = 50.0, **kwargs) -> None:
        super().__init__(**kwargs)
        self.prior_weight = prior_weight
        self._radiant_wins = 0
        self._games_total = 0

    def _side_logit(self) -> float:
        total = self._games_total + self.prior_weight
        rate = (self._radiant_wins + 0.5 * self.prior_weight) / total
        rate = min(max(rate, 1e-6), 1.0 - 1e-6)
        return math.log(rate / (1.0 - rate))

    def predict(self, match: MatchRecord) -> float | None:
        base = super().predict(match)
        if base is None:
            return None
        base = min(max(base, 1e-6), 1.0 - 1e-6)
        logit = math.log(base / (1.0 - base)) + self._side_logit()
        return 1.0 / (1.0 + math.exp(-logit))

    def update(self, matches: Sequence[MatchRecord]) -> None:
        super().update(matches)
        for match in matches:
            self._games_total += 1
            self._radiant_wins += int(bool(match.radiant_win))


class Glicko2Calibrated(Glicko2WithSide):
    """Glicko-2 с температурной калибровкой.

    Появилась не из общих соображений, а по таблице калибровки на реальной
    истории: там, где модель обещает 0.85, на деле выигрывают 0.70, а где обещает
    0.25 — выигрывают 0.35. Прогнозы систематически отодвинуты от 0.5 в обе
    стороны, то есть модель уверена сильнее, чем имеет право.

    Лечится одним числом: логит делится на температуру T. T > 1 стягивает
    прогнозы к 0.5, T < 1 растягивает. Температура подбирается по уже сыгранному
    и применяется к будущему — иначе это была бы подгонка под ответ.
    """

    name = "glicko2+calibrated"

    # Сетка вместо оптимизатора: функция одномерная и гладкая, а зависимость от
    # scipy ради подбора одного числа того не стоит.
    _GRID = tuple(round(0.6 + 0.05 * i, 2) for i in range(29))  # 0.60 .. 2.00

    def __init__(self, *, min_history: int = 100, **kwargs) -> None:
        super().__init__(**kwargs)
        self.min_history = min_history
        self.temperature = 1.0
        self._seen_logits: list[float] = []
        self._seen_outcomes: list[float] = []

    @staticmethod
    def _logit(p: float) -> float:
        p = min(max(p, 1e-6), 1.0 - 1e-6)
        return math.log(p / (1.0 - p))

    def predict(self, match: MatchRecord) -> float | None:
        base = super().predict(match)
        if base is None:
            return None
        return 1.0 / (1.0 + math.exp(-self._logit(base) / self.temperature))

    def _fit_temperature(self) -> None:
        """Подобрать T, минимизирующую log loss на накопленной истории."""
        if len(self._seen_logits) < self.min_history:
            return

        best_t, best_loss = self.temperature, math.inf
        for t in self._GRID:
            loss = 0.0
            for logit, outcome in zip(self._seen_logits, self._seen_outcomes, strict=True):
                p = 1.0 / (1.0 + math.exp(-logit / t))
                p = min(max(p, 1e-15), 1.0 - 1e-15)
                loss -= outcome * math.log(p) + (1.0 - outcome) * math.log(1.0 - p)
            if loss < best_loss:
                best_t, best_loss = t, loss
        self.temperature = best_t

    def update(self, matches: Sequence[MatchRecord]) -> None:
        # Прогнозы записываются ДО впитывания результатов периода: температура
        # должна подбираться по тем же условиям, в которых модель предсказывает.
        for match in matches:
            base = Glicko2WithSide.predict(self, match)
            if base is None:
                continue
            self._seen_logits.append(self._logit(base))
            self._seen_outcomes.append(float(bool(match.radiant_win)))

        super().update(matches)
        self._fit_temperature()


def default_ladder() -> list[object]:
    """Лестница по умолчанию — от абсолютного нуля до действующей модели."""
    return [
        CoinFlip(),
        RadiantPrior(),
        Glicko2Predictor(),
        Glicko2WithSide(),
        Glicko2Calibrated(),
    ]
