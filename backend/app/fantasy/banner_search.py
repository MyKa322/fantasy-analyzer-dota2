"""Подбор баннера: поиск, который не растёт экспоненциально от числа слотов.

Полный перебор качеств и трейтов — это |качества|^слотов × |трейты|^слотов
вариантов. На трёх слотах это 27 тысяч и считается мгновенно, на пяти (основной
этап) — двадцать четыре миллиона, и перебор перестаёт помещаться и во время, и
в память. При этом задача устроена гораздо проще, чем выглядит.

Счёт баннера раскладывается на независимые слагаемые:

    счёт = Σ base_i · (1 + качество_i + собственный трейт_i)
         + Σ эффект_на_соседей(трейт_i) · (сумма base соседей i)

Значит при фиксированном наборе *сработавших* условий каждый слот выбирается
независимо от остальных: и качество, и трейт. Связывают слоты только сами
условия — Fractal требует все качества разными, Unique — что он на баннере один,
Friendly — что таких эмблем хотя бы три. Поэтому перебираются не варианты
баннера, а варианты «какие условия сработали» (их восемь), и внутри каждого
выбор делается по слотам:

* качества: если Fractal активен — все разные, и по перестановочному неравенству
  наибольший бонус идёт к слоту с наибольшими базовыми очками; иначе везде
  максимальное качество (условий оно не нарушает, а бонус даёт больший);
* трейты: сначала лучший по слоту, затем поправка на счётные условия — ровно
  один Unique, не меньше трёх Friendly.

Найденный вариант в конце считается настоящей формулой множителей. Если
рассуждение выше где-то не покрыло экзотический случай, число всё равно будет
верным — потеряется разве что доля процента в самом варианте.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from itertools import combinations, product

from .rules import FantasyRules, TraitCondition, TraitScope
from .scoring import Emblem

# Условия, которые связывают слоты между собой, и как именно.
DISTINCT_QUALITIES = TraitCondition.ALL_QUALITIES_DISTINCT
EXACTLY_ONE = TraitCondition.ONLY_UNIQUE_ON_BANNER
AT_LEAST_THREE = TraitCondition.AT_LEAST_3_FRIENDLY


@dataclass(frozen=True, slots=True)
class TraitMath:
    """Трейт в виде двух чисел: что он даёт себе и что соседям."""

    key: str | None
    own: float
    adjacent: float
    condition: TraitCondition


def trait_math(rules: FantasyRules, keys: Sequence[str | None]) -> list[TraitMath]:
    """Разложить трейты в числа. `None` — пустой слот без трейта."""
    result: list[TraitMath] = []
    for key in keys:
        if key is None:
            result.append(TraitMath(None, 0.0, 0.0, TraitCondition.ALWAYS))
            continue
        rule = rules.trait(key)
        own = sum(
            e.amount
            for e in (
                *rule.effects_for(TraitScope.SELF_BONUS),
                *rule.effects_for(TraitScope.SELF_VALUE),
            )
        )
        adjacent = sum(e.amount for e in rule.effects_for(TraitScope.ADJACENT_VALUE))
        result.append(TraitMath(key, own, adjacent, rule.condition))
    return result


def _neighbour_sums(base: Sequence[float]) -> list[float]:
    """Сумма базовых очков соседей каждого слота — вес эффекта «на соседей»."""
    return [
        sum(base[j] for j in (i - 1, i + 1) if 0 <= j < len(base)) for i in range(len(base))
    ]


def _quality_vector(
    base: Sequence[float], qualities: Mapping[str, float], *, distinct: bool
) -> list[tuple[str, float]] | None:
    """Качество каждому слоту.

    Без требования различий выигрывает максимальное качество на каждом слоте.
    С требованием — берутся n лучших качеств, и большее достаётся слоту с
    большими базовыми очками (перестановочное неравенство).
    """
    if not qualities:
        return None
    ranked = sorted(qualities.items(), key=lambda item: -item[1])
    if not distinct:
        return [ranked[0]] * len(base)
    if len(ranked) < len(base):
        return None
    chosen = ranked[: len(base)]
    order = sorted(range(len(base)), key=lambda i: -base[i])
    vector: list[tuple[str, float]] = [("", 0.0)] * len(base)
    for rank, slot in enumerate(order):
        vector[slot] = chosen[rank]
    return vector


def _assign_traits(
    base: Sequence[float],
    neighbours: Sequence[float],
    quality: Sequence[tuple[str, float]],
    pool: Sequence[TraitMath],
    *,
    active: frozenset[str],
) -> list[TraitMath] | None:
    """Выбрать трейт каждому слоту при заданных сработавших условиях."""
    n = len(base)

    def works(trait: TraitMath) -> bool:
        """Даёт ли трейт что-нибудь в этом контексте."""
        return (
            trait.key is None
            or trait.condition is TraitCondition.ALWAYS
            or trait.key in active
        )

    def value(slot: int, trait: TraitMath) -> float:
        own = trait.own if works(trait) else 0.0
        adjacent = trait.adjacent if works(trait) else 0.0
        return base[slot] * (1.0 + quality[slot][1] + own) + adjacent * neighbours[slot]

    exact_one = [t for t in pool if t.key in active and t.condition is EXACTLY_ONE]
    at_least_three = [t for t in pool if t.key in active and t.condition is AT_LEAST_THREE]
    free_pool = [t for t in pool if t not in exact_one]
    if not free_pool or len(exact_one) > n:
        return None

    best: list[TraitMath] | None = None
    best_total = float("-inf")

    # Слоты под трейты, которых должно быть ровно по одному, перебираются: их
    # мало, а выбор слота меняет всё остальное распределение.
    for slots in combinations(range(n), len(exact_one)):
        chosen: list[TraitMath] = [free_pool[0]] * n
        for slot, trait in zip(slots, exact_one, strict=True):
            chosen[slot] = trait

        free = [i for i in range(n) if i not in slots]
        for i in free:
            chosen[i] = max(free_pool, key=lambda t: value(i, t))

        # «Не меньше трёх» — количество доводится на тех слотах, где такая
        # замена стоит дешевле всего. Слагаемые независимы, поэтому цена замены
        # считается по одному слоту, а не пересчётом всего баннера.
        short = False
        for trait in at_least_three:
            need = 3 - sum(1 for t in chosen if t is trait)
            if need <= 0:
                continue
            spare = sorted(
                (i for i in free if chosen[i] is not trait),
                key=lambda i: value(i, chosen[i]) - value(i, trait),
            )
            if len(spare) < need:
                short = True
                break
            for i in spare[:need]:
                chosen[i] = trait
        if short:
            continue

        total = sum(value(i, chosen[i]) for i in range(n))
        if total > best_total:
            best_total = total
            best = list(chosen)

    return best


def search_banners(
    rules: FantasyRules,
    *,
    slot_stats: Sequence[Sequence[str]],
    base_by_stat: Mapping[str, float],
    qualities: Mapping[str, float],
    traits: Sequence[str | None],
    multipliers: Callable[[Sequence[Emblem]], Sequence[float]],
    allow_duplicate_stats: bool = False,
    top_n: int = 3,
) -> list[tuple[float, tuple[Emblem, ...]]]:
    """Лучшие баннеры: список (очки, эмблемы), от большего к меньшему.

    `slot_stats` — кандидаты в каждый слот, уже отобранные по цвету слота.
    Комбинации статов перебираются полностью (их немного), а качества и трейты
    подбираются под каждую комбинацию по разложению из шапки модуля.
    """
    if not slot_stats or any(not pool for pool in slot_stats):
        return []

    pool = trait_math(rules, traits)
    conditional = {t.key for t in pool if t.key and t.condition is not TraitCondition.ALWAYS}

    results: dict[tuple[tuple[str, str, str | None], ...], float] = {}

    for stat_combo in product(*slot_stats):
        if not allow_duplicate_stats and len(set(stat_combo)) != len(stat_combo):
            continue
        base = [float(base_by_stat.get(stat, 0.0)) for stat in stat_combo]
        neighbours = _neighbour_sums(base)

        # Восемь контекстов: какие из условных трейтов считаем сработавшими.
        for size in range(len(conditional) + 1):
            for active_keys in combinations(sorted(conditional), size):
                active = frozenset(active_keys)
                distinct = any(
                    t.key in active and t.condition is DISTINCT_QUALITIES for t in pool
                )
                quality = _quality_vector(base, qualities, distinct=distinct)
                if quality is None:
                    continue
                allowed = [
                    t
                    for t in pool
                    if t.key is None
                    or t.condition is TraitCondition.ALWAYS
                    or t.key in active
                ]
                chosen = _assign_traits(
                    base, neighbours, quality, allowed, active=active
                )
                if chosen is None:
                    continue

                emblems = tuple(
                    Emblem(stat=stat, quality=quality[i][0], trait=chosen[i].key)
                    for i, stat in enumerate(stat_combo)
                )
                key = tuple((e.stat, e.quality, e.trait) for e in emblems)
                if key in results:
                    continue
                # Итоговое число — по настоящей формуле множителей, а не по
                # разложению: разложение выбирает вариант, формула его считает.
                factors = multipliers(emblems)
                results[key] = sum(b * m for b, m in zip(base, factors, strict=True))

    ranked = sorted(results.items(), key=lambda item: -item[1])[:top_n]
    return [
        (
            total,
            tuple(Emblem(stat=s, quality=q, trait=t) for s, q, t in key),
        )
        for key, total in ranked
    ]


def slot_pools(
    rules: FantasyRules,
    role: str,
    values_by_color: Mapping[str, Sequence[str]],
    *,
    stage: str | None = None,
    stats_per_slot: int = 3,
) -> list[list[str]]:
    """Кандидаты в каждый слот роли: лучшие статы нужного цвета."""
    pools: list[list[str]] = []
    for color in rules.slot_colors(role, stage):
        pool = list(values_by_color.get(str(color), ()))
        if not pool:
            raise ValueError(f"нет доступных статов цвета {color} для роли {role}")
        pools.append(pool[:stats_per_slot])
    return pools


def iter_stat_combos(pools: Iterable[Sequence[str]]) -> Iterable[tuple[str, ...]]:
    """Все сочетания статов по слотам без повторов — для тестов и отладки."""
    for combo in product(*pools):
        if len(set(combo)) == len(combo):
            yield combo
