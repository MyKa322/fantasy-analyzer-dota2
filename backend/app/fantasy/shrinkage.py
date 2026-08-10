"""Поправка на размер выборки при сравнении ролей между собой.

Зачем
-----
Анализатор берёт максимум по 48 кандидатам (16 команд × 3 роли). Максимум по
шумным оценкам систематически достаётся тому, у кого выборка меньше: у него
шире разброс, и в верхний хвост он попадает чаще, чем заслуживает.

Это не теория. На снапшоте от 09.08.2026 мид Team Resilience с 29 картами стоял
на 7,5% выше всего поля, где следующие десять команд укладывались в 2% друг от
друга. Через восемь карт его же оценка упала на 6% и с первого места ушла, а у
команд с сотней карт за то же обновление она сдвинулась на 0–0,1%. Побеждала не
команда, побеждала маленькая выборка.

Что делает
----------
Классическое эмпирическое байесовское сжатие. Для каждой пары (роль, стат)
оценка команды подтягивается к среднему по роли тем сильнее, чем менее она
надёжна:

    lambda = tau^2 / (tau^2 + se^2)
    оценка = mu + lambda * (наблюдение - mu)

где `se^2 = s^2 / n` — квадрат стандартной ошибки среднего команды, а `tau^2` —
разброс между командами за вычетом среднего шума: то, что остаётся от различий,
когда из них вычли неточность измерения. Если после вычитания не остаётся
ничего, значит все различия — шум, и все оценки схлопываются к среднему.
Команда со ста картами почти не двигается, команда с двадцатью — двигается
сильно. Никаких порогов и отсечений: правило одно и работает непрерывно.

Остальные числа стата (единицы за карту, медиана, перцентили) двигаются в той же
пропорции — иначе в таблице очки поехали бы, а «за карту» осталось на месте, и
одно перестало бы соответствовать другому.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace

import numpy as np

from .advisor import StatValue

# Ниже трёх команд оценивать разброс между ними бессмысленно: tau^2 будет
# случайным числом, и сжатие сделает хуже, чем его отсутствие.
MIN_TEAMS = 3

# Перевод межквартильного размаха в стандартное отклонение для нормального
# распределения: IQR = 1.349 sigma.
IQR_TO_SIGMA = 1.349


def _robust_variance(values: np.ndarray) -> float:
    """Разброс между командами, устойчивый к выбросам.

    Обычная дисперсия здесь не годится, и это не придирка. Ровно тот выброс,
    ради которого всё затевалось, сам входит в неё и раздувает: разброс между
    командами оказывается больше шума, сжатие выключается, и выброс защищает
    сам себя. Межквартильный размах одну-две крайние команды не замечает.
    """
    spread = float(np.percentile(values, 75) - np.percentile(values, 25))
    return (spread / IQR_TO_SIGMA) ** 2


def shrink_to_role_mean(
    entries: Sequence[tuple[str, Sequence[StatValue]]],
) -> list[list[StatValue]]:
    """Сжать оценки статов к среднему по роли. Порядок и состав сохраняются.

    На вход — пары «роль, статы этой роли у одной команды», по одной паре на
    каждую роль каждой команды. Сравнивать имеет смысл только внутри роли: у
    мида и саппорта разные слоты и разные статы.
    """
    result: list[list[StatValue]] = [list(values) for _, values in entries]

    # Где какой стат лежит: (роль, стат) -> [(номер команды, номер в списке)].
    groups: dict[tuple[str, str], list[tuple[int, int]]] = {}
    for team_index, (role, values) in enumerate(entries):
        for value_index, value in enumerate(values):
            groups.setdefault((role, value.stat), []).append((team_index, value_index))

    for positions in groups.values():
        if len(positions) < MIN_TEAMS:
            continue

        observed = np.array([result[t][v].base_points for t, v in positions])
        games = np.array([result[t][v].games for t, v in positions], dtype=np.float64)
        spread = np.array([result[t][v].std_points for t, v in positions])

        # Стандартная ошибка среднего. Ноль карт или ноль разброса — считаем
        # оценку точной, сжимать нечего.
        error = np.divide(spread**2, games, out=np.zeros_like(spread), where=games > 0)

        mean = float(np.median(observed))
        between = max(_robust_variance(observed) - float(error.mean()), 0.0)

        weight = np.divide(
            between, between + error, out=np.ones_like(error), where=(between + error) > 0
        )
        adjusted = mean + weight * (observed - mean)

        for (team_index, value_index), new_base, old_base in zip(
            positions, adjusted, observed, strict=True
        ):
            if old_base == 0:
                continue
            scale = float(new_base / old_base)
            value = result[team_index][value_index]
            result[team_index][value_index] = replace(
                value,
                base_points=float(new_base),
                units_per_game=value.units_per_game * scale,
                p95_points=value.p95_points * scale,
                p5_points=value.p5_points * scale,
                median_points=value.median_points * scale,
                p75_points=value.p75_points * scale,
            )

    for values in result:
        values.sort(key=lambda v: -v.base_points)
    return result
