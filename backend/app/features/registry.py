"""Реестр фич: как метрика объявляется и почему именно так.

Фича здесь — чистая функция от канонического матча и ничего больше. Ограничение
намеренное: как только фича начинает ходить в базу за «средним по игроку», её
нельзя ни пересчитать задним числом, ни проверить на одном матче, а в бэктесте
она немедленно протекает будущим. Всё, что требует истории, считается слоем выше,
из уже материализованных фич.

Пропуск важнее нуля. Если у матча нет разбора, `cs_per_min` не равен нулю — он
неизвестен, и ключа в словаре просто нет. Ноль в этом месте означал бы «игрок за
всю карту не добил ни одного крипа» и тихо занижал бы любое среднее.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from typing import TypeVar

from app.core import CanonicalMatch, PlayerGame

# Версия набора фич. Растёт, когда меняется состав или смысл вычислений: по ней
# материализация понимает, что строка посчитана старым кодом и её надо
# пересчитать. Тот же механизм, что `STATS_VERSION` у ingest, — он уже показал,
# что без него половина базы навсегда остаётся в старом формате.
FEATURES_VERSION = 1

MatchFeatureFn = Callable[[CanonicalMatch], Mapping[str, float]]
PlayerFeatureFn = Callable[[CanonicalMatch, PlayerGame], Mapping[str, float]]

F = TypeVar("F", MatchFeatureFn, PlayerFeatureFn)


@dataclass(frozen=True, slots=True)
class FeatureGroup:
    """Одна функция, отдающая сразу несколько связанных фич.

    Группами, а не по одной фиче на функцию: доли участия считаются из общих
    сумм по команде, и разбивать их на пять функций значило бы пять раз пройти
    по одному и тому же списку игроков.
    """

    name: str
    keys: tuple[str, ...]
    fn: Callable
    doc: str = ""


MATCH_FEATURES: list[FeatureGroup] = []
PLAYER_FEATURES: list[FeatureGroup] = []


def match_feature(name: str, *keys: str) -> Callable[[MatchFeatureFn], MatchFeatureFn]:
    """Объявить группу фич уровня матча."""

    def wrap(fn: MatchFeatureFn) -> MatchFeatureFn:
        MATCH_FEATURES.append(FeatureGroup(name, keys, fn, (fn.__doc__ or "").strip()))
        return fn

    return wrap


def player_feature(name: str, *keys: str) -> Callable[[PlayerFeatureFn], PlayerFeatureFn]:
    """Объявить группу фич уровня «игрок в карте»."""

    def wrap(fn: PlayerFeatureFn) -> PlayerFeatureFn:
        PLAYER_FEATURES.append(FeatureGroup(name, keys, fn, (fn.__doc__ or "").strip()))
        return fn

    return wrap


def declared_keys(groups: Iterable[FeatureGroup]) -> tuple[str, ...]:
    """Все имена фич, которые группы обещают отдавать."""
    return tuple(key for group in groups for key in group.keys)


def safe_ratio(numerator: float | None, denominator: float | None) -> float | None:
    """Доля, где ноль в знаменателе означает «не определено», а не ноль.

    Доля добитых крипов в матче, где команда не убила ни одного крипа, — не ноль
    процентов, а бессмыслица. Возвращать ноль здесь означает изобрести данные.
    """
    if numerator is None or not denominator:
        return None
    return float(numerator) / float(denominator)
