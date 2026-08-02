"""Glicko-2: рейтинг команд с явной неопределённостью.

Реализация ровно по статье Марка Гликмана "Example of the Glicko-2 system"
(http://www.glicko.net/glicko/glicko2.pdf). Эталонный пример из статьи вынесен
в тесты — при любой правке модуля он должен сходиться до второго знака.

Почему Glicko-2, а не Elo: datdota публикует оба, а Liquipedia в июне 2026
перевела свой рейтинг команд именно на Glicko-2. Практическая разница в RD —
величине неопределённости: неожиданный результат сильнее двигает команду с
короткой историей, чем команду с полусотней стабильных игр. Для TI это
критично — половина участников либо новые организации, либо со свежей заменой.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Self

# Перевод из привычной шкалы (1500 ± 350) во внутреннюю шкалу Glicko-2.
SCALE = 173.7178

DEFAULT_RATING = 1500.0
DEFAULT_RD = 350.0
DEFAULT_VOLATILITY = 0.06

# Ограничивает изменчивость рейтинга во времени. Гликман рекомендует 0.3–1.2;
# меньшие значения = более инертный рейтинг. 0.5 — значение из его же примера.
DEFAULT_TAU = 0.5

# Порог сходимости итерации Illinois при поиске новой волатильности.
CONVERGENCE_EPSILON = 1e-6

# Практические фильтры Liquipedia: команду показываем в листинге, только если
# неопределённость упала ниже 100 и есть матч за последние 8 недель.
LISTING_MAX_RD = 100.0
LISTING_MAX_INACTIVE_DAYS = 56


@dataclass(frozen=True, slots=True)
class Rating:
    """Состояние команды: рейтинг, неопределённость, волатильность."""

    rating: float = DEFAULT_RATING
    rd: float = DEFAULT_RD
    volatility: float = DEFAULT_VOLATILITY

    @property
    def mu(self) -> float:
        return (self.rating - DEFAULT_RATING) / SCALE

    @property
    def phi(self) -> float:
        return self.rd / SCALE

    @classmethod
    def from_internal(cls, mu: float, phi: float, volatility: float) -> Self:
        return cls(
            rating=mu * SCALE + DEFAULT_RATING,
            rd=phi * SCALE,
            volatility=volatility,
        )

    def interval(self, z: float = 1.96) -> tuple[float, float]:
        """Доверительный интервал рейтинга — то, что стоит показывать в UI
        вместо голого числа."""
        return (self.rating - z * self.rd, self.rating + z * self.rd)

    def is_listable(self, days_since_last_match: float | None = None) -> bool:
        """Фильтр в духе Liquipedia: рейтингу можно доверять."""
        if self.rd >= LISTING_MAX_RD:
            return False
        if days_since_last_match is None:
            return True
        return days_since_last_match <= LISTING_MAX_INACTIVE_DAYS


@dataclass(frozen=True, slots=True)
class GameResult:
    """Один матч рейтингового периода: соперник и результат с точки зрения
    рейтингуемой команды (1 — победа, 0 — поражение, 0.5 — ничья)."""

    opponent: Rating
    score: float

    def __post_init__(self) -> None:
        if not 0.0 <= self.score <= 1.0:
            raise ValueError(f"score должен быть в [0, 1], получено {self.score}")


def _g(phi: float) -> float:
    return 1.0 / math.sqrt(1.0 + 3.0 * phi**2 / math.pi**2)


def _expected(mu: float, mu_j: float, phi_j: float) -> float:
    return 1.0 / (1.0 + math.exp(-_g(phi_j) * (mu - mu_j)))


class Glicko2:
    """Движок рейтинга. Экземпляр хранит только настройки, состояние — в Rating."""

    def __init__(self, tau: float = DEFAULT_TAU, epsilon: float = CONVERGENCE_EPSILON) -> None:
        if not 0.0 < tau <= 2.0:
            raise ValueError(f"tau вне разумного диапазона (0, 2]: {tau}")
        self.tau = tau
        self.epsilon = epsilon

    # --- обновление рейтинга --------------------------------------------------

    def rate(self, player: Rating, results: Sequence[GameResult]) -> Rating:
        """Пересчитать рейтинг по итогам одного рейтингового периода."""
        if not results:
            return self.rate_unplayed(player)

        mu, phi = player.mu, player.phi

        variance_inv = 0.0
        delta_sum = 0.0
        for result in results:
            g_j = _g(result.opponent.phi)
            e_j = _expected(mu, result.opponent.mu, result.opponent.phi)
            variance_inv += g_j**2 * e_j * (1.0 - e_j)
            delta_sum += g_j * (result.score - e_j)

        if variance_inv == 0.0:
            # Все соперники бесконечно неопределённы — обновлять нечего.
            return self.rate_unplayed(player)

        v = 1.0 / variance_inv
        delta = v * delta_sum

        new_volatility = self._new_volatility(phi, v, delta, player.volatility)
        phi_star = math.sqrt(phi**2 + new_volatility**2)
        new_phi = 1.0 / math.sqrt(1.0 / phi_star**2 + 1.0 / v)
        new_mu = mu + new_phi**2 * delta_sum

        return Rating.from_internal(new_mu, new_phi, new_volatility)

    def rate_unplayed(self, player: Rating) -> Rating:
        """Период без игр: рейтинг не меняется, неопределённость растёт."""
        phi_star = math.sqrt(player.phi**2 + player.volatility**2)
        return replace(player, rd=min(phi_star * SCALE, DEFAULT_RD))

    def _new_volatility(self, phi: float, v: float, delta: float, volatility: float) -> float:
        """Итерация Illinois (алгоритм из шага 5 статьи Гликмана)."""
        a = math.log(volatility**2)
        tau_sq = self.tau**2
        phi_sq = phi**2
        delta_sq = delta**2

        def f(x: float) -> float:
            ex = math.exp(x)
            denom = phi_sq + v + ex
            return ex * (delta_sq - denom) / (2.0 * denom**2) - (x - a) / tau_sq

        big_a = a
        if delta_sq > phi_sq + v:
            big_b = math.log(delta_sq - phi_sq - v)
        else:
            k = 1
            while f(a - k * self.tau) < 0:
                k += 1
                if k > 100:  # практически недостижимо, страховка от вечного цикла
                    raise RuntimeError("не удалось локализовать корень волатильности")
            big_b = a - k * self.tau

        f_a, f_b = f(big_a), f(big_b)
        for _ in range(100):
            if abs(big_b - big_a) <= self.epsilon:
                break
            big_c = big_a + (big_a - big_b) * f_a / (f_b - f_a)
            f_c = f(big_c)
            if f_c * f_b <= 0:
                big_a, f_a = big_b, f_b
            else:
                f_a /= 2.0
            big_b, f_b = big_c, f_c
        else:
            raise RuntimeError("итерация волатильности не сошлась за 100 шагов")

        return math.exp(big_a / 2.0)

    # --- прогноз --------------------------------------------------------------

    def win_probability(self, player: Rating, opponent: Rating) -> float:
        """Вероятность победы `player` в одной карте.

        Неопределённость учитывается по обеим сторонам: чем меньше мы знаем о
        любой из команд, тем ближе прогноз к 50%.
        """
        combined_phi = math.sqrt(player.phi**2 + opponent.phi**2)
        return 1.0 / (1.0 + math.exp(-_g(combined_phi) * (player.mu - opponent.mu)))

    def series_win_probability(
        self, player: Rating, opponent: Rating, *, best_of: int = 3
    ) -> float:
        """Вероятность выиграть серию Bo1/Bo2*/Bo3/Bo5 при независимых картах.

        Допущение независимости карт — упрощение (в реальности есть импульс и
        драфт-адаптация), но без модели по-картам оно нейтральнее любой
        произвольной поправки.
        """
        if best_of < 1 or best_of % 2 == 0:
            raise ValueError(f"best_of должен быть нечётным и >= 1, получено {best_of}")
        p = self.win_probability(player, opponent)
        needed = best_of // 2 + 1
        total = 0.0
        for losses in range(needed):
            games = needed + losses
            total += math.comb(games - 1, losses) * p**needed * (1.0 - p) ** losses
        return total
