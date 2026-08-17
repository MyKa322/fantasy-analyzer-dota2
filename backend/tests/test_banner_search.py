"""Подбор баннера: разложение обязано совпадать с полным перебором.

Полный перебор — эталон, но он растёт как |качества|^слотов × |трейты|^слотов и
на пяти слотах уже не считается. Поэтому здесь он берётся как медленная, но
заведомо верная реализация и сравнивается с быстрым поиском на маленьких данных.
"""

from __future__ import annotations

import random
from itertools import product

import pytest

from app.fantasy.banner_search import search_banners
from app.fantasy.rules import load_rules
from app.fantasy.scoring import Banner, Emblem, FantasyScorer


@pytest.fixture(scope="module")
def rules():
    return load_rules()


@pytest.fixture(scope="module")
def scorer(rules):
    return FantasyScorer(rules)


def multipliers_for(scorer, role: str):
    return lambda emblems: scorer.emblem_multipliers(Banner(emblems=tuple(emblems), role=role))


def brute_force(
    scorer,
    role: str,
    slot_stats,
    base_by_stat,
    qualities,
    traits,
) -> tuple[float, tuple[Emblem, ...]]:
    """Эталон: перебрать вообще всё и вернуть лучший баннер."""
    best = (float("-inf"), ())
    for stat_combo in product(*slot_stats):
        if len(set(stat_combo)) != len(stat_combo):
            continue
        for quality_combo in product(qualities, repeat=len(stat_combo)):
            for trait_combo in product(traits, repeat=len(stat_combo)):
                emblems = tuple(
                    Emblem(stat=s, quality=q, trait=t)
                    for s, q, t in zip(stat_combo, quality_combo, trait_combo, strict=True)
                )
                factors = scorer.emblem_multipliers(Banner(emblems=emblems, role=role))
                total = sum(
                    base_by_stat[e.stat] * m for e, m in zip(emblems, factors, strict=True)
                )
                if total > best[0]:
                    best = (total, emblems)
    return best


def pools_for(rules, role: str, stage: str | None, per_slot: int) -> list[list[str]]:
    """Кандидаты в слоты роли — как их строит анализатор: лучшие статы цвета."""
    return [
        [stat.key for stat in rules.stats_by_color(color)][:per_slot]
        for color in rules.slot_colors(role, stage)
    ]


def distinct_pools(rules, role: str, stage: str | None) -> list[list[str]]:
    """По одному стату на слот, все разные.

    Нужно там, где перебирается эталон: комбинация статов должна быть ровно
    одна, иначе полный перебор не досчитается до конца теста.
    """
    used: dict[str, int] = {}
    pools: list[list[str]] = []
    for color in rules.slot_colors(role, stage):
        stats = [stat.key for stat in rules.stats_by_color(color)]
        index = used.get(str(color), 0)
        pools.append([stats[index]])
        used[str(color)] = index + 1
    return pools


@pytest.mark.parametrize("seed", [1, 2, 3, 4, 5])
def test_matches_brute_force_on_three_slots(rules, scorer, seed):
    """На трёх слотах есть с чем сравнить — совпадение должно быть точным."""
    rng = random.Random(seed)
    slot_stats = distinct_pools(rules, "mid", None)
    base = {
        stat: rng.uniform(100.0, 5000.0) for pool in slot_stats for stat in pool
    }
    qualities = dict(rules.qualities)
    traits = [None, *rules.traits]

    expected, _ = brute_force(scorer, "mid", slot_stats, base, qualities, traits)
    found = search_banners(
        rules,
        slot_stats=slot_stats,
        base_by_stat=base,
        qualities=qualities,
        traits=traits,
        multipliers=multipliers_for(scorer, "mid"),
        top_n=1,
    )

    assert found
    assert found[0][0] == pytest.approx(expected)


@pytest.mark.parametrize("seed", [11, 12, 13])
def test_matches_brute_force_on_five_slots(rules, scorer, seed):
    """Пять слотов основного этапа.

    Полный перебор здесь возможен только на урезанном наборе качеств и трейтов —
    на полном он и есть та самая стена в двадцать четыре миллиона вариантов.
    """
    rng = random.Random(seed)
    slot_stats = distinct_pools(rules, "core", "main")
    base = {stat: rng.uniform(100.0, 5000.0) for pool in slot_stats for stat in pool}
    qualities = {q: rules.qualities[q] for q in ("tier_1", "tier_3", "tier_5")}
    traits = [None, "vampiric", "friendly"]

    expected, _ = brute_force(scorer, "core", slot_stats, base, qualities, traits)
    found = search_banners(
        rules,
        slot_stats=slot_stats,
        base_by_stat=base,
        qualities=qualities,
        traits=traits,
        multipliers=multipliers_for(scorer, "core"),
        top_n=1,
    )

    assert found
    assert found[0][0] == pytest.approx(expected)


@pytest.mark.parametrize("seed", [21, 22])
def test_matches_brute_force_with_fractal_on_five_slots(rules, scorer, seed):
    """Fractal на пяти слотах требует пять разных качеств — их ровно пять."""
    rng = random.Random(seed)
    slot_stats = distinct_pools(rules, "mid", "main")
    base = {stat: rng.uniform(100.0, 5000.0) for pool in slot_stats for stat in pool}
    qualities = dict(rules.qualities)
    traits = [None, "fractal"]

    expected, _ = brute_force(scorer, "mid", slot_stats, base, qualities, traits)
    found = search_banners(
        rules,
        slot_stats=slot_stats,
        base_by_stat=base,
        qualities=qualities,
        traits=traits,
        multipliers=multipliers_for(scorer, "mid"),
        top_n=1,
    )

    assert found
    assert found[0][0] == pytest.approx(expected)


def test_five_slot_banner_has_five_emblems(rules, scorer):
    slot_stats = pools_for(rules, "support", "main", per_slot=3)
    base = {stat: 1000.0 + 10 * index for pool in slot_stats for index, stat in enumerate(pool)}

    found = search_banners(
        rules,
        slot_stats=slot_stats,
        base_by_stat=base,
        qualities=dict(rules.qualities),
        traits=[None, *rules.traits],
        multipliers=multipliers_for(scorer, "support"),
        top_n=3,
    )

    assert len(found) == 3
    for total, emblems in found:
        assert len(emblems) == 5
        assert len({e.stat for e in emblems}) == 5, "повторов статов на баннере не бывает"
        assert total > 0
    assert found[0][0] >= found[-1][0]


def test_restricted_qualities_are_respected(rules, scorer):
    """Из роллов выпало только два качества — искать надо среди них."""
    slot_stats = distinct_pools(rules, "core", "main")
    base = {stat: 1000.0 for pool in slot_stats for stat in pool}
    allowed = {"tier_1": rules.qualities["tier_1"], "tier_2": rules.qualities["tier_2"]}

    found = search_banners(
        rules,
        slot_stats=slot_stats,
        base_by_stat=base,
        qualities=allowed,
        traits=[None, *rules.traits],
        multipliers=multipliers_for(scorer, "core"),
        top_n=1,
    )

    assert found
    assert {e.quality for e in found[0][1]} <= set(allowed)


def test_fractal_on_the_banner_means_distinct_qualities(rules, scorer):
    """Если Fractal попал в баннер, качества обязаны быть разными."""
    slot_stats = distinct_pools(rules, "core", "main")
    base = {stat: 1000.0 for pool in slot_stats for stat in pool}

    found = search_banners(
        rules,
        slot_stats=slot_stats,
        base_by_stat=base,
        qualities=dict(rules.qualities),
        traits=[None, "fractal"],
        multipliers=multipliers_for(scorer, "core"),
        top_n=1,
    )

    _, emblems = found[0]
    if any(e.trait == "fractal" for e in emblems):
        assert len({e.quality for e in emblems}) == len(emblems)


def test_five_slots_are_searched_fast(rules, scorer):
    """Полный перебор здесь дал бы 24 миллиона вариантов — этот считает мгновенно."""
    slot_stats = pools_for(rules, "mid", "main", per_slot=3)
    base = {stat: 1000.0 for pool in slot_stats for stat in pool}

    found = search_banners(
        rules,
        slot_stats=slot_stats,
        base_by_stat=base,
        qualities=dict(rules.qualities),
        traits=[None, *rules.traits],
        multipliers=multipliers_for(scorer, "mid"),
        top_n=5,
    )

    assert len(found) == 5
