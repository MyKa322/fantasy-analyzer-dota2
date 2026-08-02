"""Тесты анализатора эмблем."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.fantasy.advisor import EmblemAdvisor
from app.fantasy.projection import RoleGame, RoleHistory, RoleProjector
from app.fantasy.scoring import Banner, Emblem

NOW = datetime(2026, 8, 1, tzinfo=timezone.utc)


def history(
    role: str,
    stats: dict[str, float],
    *,
    team_id: int = 1,
    games: int = 12,
    account_ids: tuple[int, ...] = (10,),
    duration: int = 2100,
    won: bool = True,
    jitter: float = 0.0,
) -> RoleHistory:
    rows = []
    for i in range(games):
        scale = 1.0 + (jitter if i % 2 else -jitter)
        rows.append(
            RoleGame(
                match_id=1000 + i,
                start_time=NOW - timedelta(days=i),
                series_key=f"series:{i // 2}",
                player_stats={a: {k: v * scale for k, v in stats.items()} for a in account_ids},
                duration=duration,
                won=won,
            )
        )
    return RoleHistory(role=role, team_id=team_id, account_ids=account_ids, games=rows)


CARRY_STATS = {
    "gpm": 700,
    "kills": 9,
    "creep_score": 420,
    "stuns": 4,
    "roshan_kills": 0.3,
    # Без смертей стат Deaths даёт полные 1950 очков и обходит всё остальное —
    # в реальной выборке керри умирает несколько раз за карту.
    "deaths": 4,
}
SUPPORT_STATS = {
    "wards_placed": 18,
    "camps_stacked": 6,
    "smokes_used": 3,
    "stuns": 42,
    "gpm": 300,
    "roshan_kills": 0.1,
}


@pytest.fixture(scope="module")
def advisor():
    return EmblemAdvisor(RoleProjector(seed=7))


# --- ценность статов ----------------------------------------------------------


def test_stat_values_limited_to_role_colors(advisor):
    values = advisor.stat_values(history("support", SUPPORT_STATS))
    stats = {v.stat for v in values}
    assert "gpm" not in stats  # у саппорта нет красных слотов
    assert {"wards_placed", "camps_stacked", "stuns"} <= stats


def test_stat_values_sorted_by_points(advisor):
    values = advisor.stat_values(history("core", CARRY_STATS))
    points = [v.base_points for v in values]
    assert points == sorted(points, reverse=True)


def test_gpm_dominates_for_a_carry(advisor):
    values = advisor.stat_values(history("core", CARRY_STATS))
    assert values[0].stat == "gpm"  # 700 GPM * 2 = 1400 очков за карту


def test_deaths_stat_is_worth_more_when_the_player_dies_less(advisor):
    """Deaths стартует с 1950 и вычитает 195 за смерть, поэтому у аккуратного
    игрока это одна из самых дорогих эмблем — легко упустить из виду."""
    careful = advisor.stat_values(history("core", {**CARRY_STATS, "deaths": 1}))
    reckless = advisor.stat_values(history("core", {**CARRY_STATS, "deaths": 8}))

    careful_deaths = next(v for v in careful if v.stat == "deaths")
    reckless_deaths = next(v for v in reckless if v.stat == "deaths")

    assert careful_deaths.base_points == pytest.approx(1950 - 195)
    assert reckless_deaths.base_points == pytest.approx(1950 - 8 * 195)
    assert careful[0].stat == "deaths"  # у аккуратного керри обгоняет даже GPM


def test_cheap_stat_can_beat_expensive_one(advisor):
    """Смысл модуля: цена стата ничего не значит без объёма.

    Roshan стоит 1172 за штуку против 117 за варду, но саппорт ставит 18 вард
    за игру и добивает Рошана раз в десять игр.
    """
    values = {v.stat: v for v in advisor.stat_values(history("support", SUPPORT_STATS))}
    assert values["wards_placed"].base_points > values["roshan_kills"].base_points
    assert values["wards_placed"].units_per_game == pytest.approx(18, rel=0.01)


def test_units_per_game_reported(advisor):
    values = {v.stat: v for v in advisor.stat_values(history("core", CARRY_STATS))}
    assert values["kills"].units_per_game == pytest.approx(9, rel=0.01)
    assert values["gpm"].base_points == pytest.approx(1400, rel=0.01)


def test_unavailable_stats_hidden_by_default(advisor):
    values = advisor.stat_values(history("core", CARRY_STATS))
    assert "madstone_collected" not in {v.stat for v in values}

    with_unavailable = advisor.stat_values(
        history("core", CARRY_STATS), include_unavailable=True
    )
    assert "madstone_collected" in {v.stat for v in with_unavailable}


def test_negligible_flag(advisor):
    values = {v.stat: v for v in advisor.stat_values(history("core", CARRY_STATS))}
    # Курьеров керри не убивает вовсе — такая эмблема равна пустому слоту.
    assert values["courier_kills"].is_negligible
    assert not values["gpm"].is_negligible
    # А вот 0.3 Рошана за карту — это уже 350 очков, вопреки интуиции «редко».
    assert not values["roshan_kills"].is_negligible


# --- подбор баннера -----------------------------------------------------------


def test_banner_respects_role_colors(advisor):
    advice = advisor.optimise_banner(
        history("support", SUPPORT_STATS), simulate=False, top_n=1
    )[0]
    colors = [s.color for s in advice.slots]
    assert colors == ["blue", "blue", "green"]


def test_core_banner_colors(advisor):
    advice = advisor.optimise_banner(
        history("core", CARRY_STATS), simulate=False, top_n=1
    )[0]
    assert [s.color for s in advice.slots] == ["red", "red", "green"]


def test_mid_banner_uses_all_three_colors(advisor):
    advice = advisor.optimise_banner(
        history("mid", {**CARRY_STATS, "smokes_used": 4, "runes_grabbed": 8}),
        simulate=False,
        top_n=1,
    )[0]
    assert [s.color for s in advice.slots] == ["red", "blue", "green"]


def test_banner_picks_the_strongest_stats(advisor):
    advice = advisor.optimise_banner(
        history("core", CARRY_STATS), simulate=False, top_n=1
    )[0]
    stats = {s.emblem.stat for s in advice.slots}
    assert "gpm" in stats  # сильнейший красный стат обязан попасть


def test_no_duplicate_stats_in_banner(advisor):
    advice = advisor.optimise_banner(
        history("support", SUPPORT_STATS), simulate=False, top_n=1
    )[0]
    stats = [s.emblem.stat for s in advice.slots]
    assert len(set(stats)) == len(stats)


def test_best_banner_uses_top_quality_when_available(advisor):
    advice = advisor.optimise_banner(
        history("core", CARRY_STATS), simulate=False, top_n=1
    )[0]
    assert all(s.emblem.quality == "tier_5" for s in advice.slots)


def test_quality_pool_can_be_restricted(advisor):
    """Из роллов выпало только два качества — оптимум ищется среди них."""
    advice = advisor.optimise_banner(
        history("core", CARRY_STATS),
        qualities=["tier_1", "tier_2"],
        simulate=False,
        top_n=1,
    )[0]
    assert {s.emblem.quality for s in advice.slots} <= {"tier_1", "tier_2"}


def test_trait_pool_can_be_restricted(advisor):
    advice = advisor.optimise_banner(
        history("core", CARRY_STATS),
        traits=[None, "vampiric"],
        simulate=False,
        top_n=1,
    )[0]
    assert {s.emblem.trait for s in advice.slots} <= {None, "vampiric"}


def test_vampiric_lands_on_the_most_valuable_slot(advisor):
    """Vampiric даёт +50% себе и -10% соседям, поэтому его место — на самой
    дорогой эмблеме, а не где придётся."""
    advice = advisor.optimise_banner(
        history("core", CARRY_STATS),
        qualities=["tier_3"],  # одинаковые качества -> Fractal заведомо мёртв
        traits=[None, "vampiric"],
        simulate=False,
        top_n=1,
    )[0]
    vampiric_slots = [s for s in advice.slots if s.emblem.trait == "vampiric"]
    assert vampiric_slots
    best_slot = max(advice.slots, key=lambda s: s.base_points)
    assert best_slot.emblem.trait == "vampiric"


def test_fractal_requires_three_different_qualities(advisor):
    """Когда доступен только Fractal, выгодно взять три разных качества —
    иначе трейт не сработает вовсе."""
    advice = advisor.optimise_banner(
        history("core", CARRY_STATS),
        traits=["fractal"],
        simulate=False,
        top_n=1,
    )[0]
    qualities = [s.emblem.quality for s in advice.slots]
    assert len(set(qualities)) == 3
    assert all(s.percent >= 160 for s in advice.slots)


def test_percentages_match_the_scoring_engine(advisor):
    advice = advisor.optimise_banner(
        history("core", CARRY_STATS), simulate=False, top_n=1
    )[0]
    banner = advice.banner()
    expected = [m * 100 for m in advisor.scorer.emblem_multipliers(banner)]
    assert [s.percent for s in advice.slots] == pytest.approx(expected)


def test_advice_reports_alternatives_per_slot(advisor):
    advice = advisor.optimise_banner(
        history("support", SUPPORT_STATS), simulate=False, top_n=1
    )[0]
    for slot in advice.slots:
        assert all(alt.color == slot.color for alt in slot.alternatives)


def test_simulation_attaches_projection(advisor):
    advice = advisor.optimise_banner(
        history("core", CARRY_STATS), simulate=True, simulations=400, top_n=1
    )[0]
    assert advice.projection is not None
    assert advice.projection.mean > 0
    assert advice.summary()["period_mean"] is not None


def test_top_n_returns_distinct_banners(advisor):
    advices = advisor.optimise_banner(
        history("core", CARRY_STATS), simulate=False, top_n=3
    )
    keys = {tuple((e.stat, e.quality, e.trait) for e in a.emblems) for a in advices}
    assert len(keys) == 3
    assert advices[0].expected_card_points >= advices[-1].expected_card_points


# --- оценка замены ------------------------------------------------------------


def test_swap_reports_gain(advisor):
    core = history("core", CARRY_STATS)
    banner = Banner.of(
        Emblem("gpm", "tier_1"),
        Emblem("kills", "tier_1"),
        Emblem("stuns", "tier_1"),
        role="core",
    )
    result = advisor.evaluate_swap(core, banner, 0, Emblem("gpm", "tier_5"))
    assert result["delta"] > 0
    assert result["after"] > result["before"]
    assert result["delta_pct"] > 0


def test_swap_can_be_negative(advisor):
    core = history("core", CARRY_STATS)
    banner = Banner.of(
        Emblem("gpm", "tier_5"),
        Emblem("kills", "tier_3"),
        Emblem("stuns", "tier_2"),
        role="core",
    )
    result = advisor.evaluate_swap(core, banner, 0, Emblem("creep_score", "tier_1"))
    assert result["delta"] < 0


def test_swap_accounts_for_neighbour_effects(advisor):
    """Vampiric в середине бьёт по обоим соседям — замена трейта меняет
    больше, чем свой слот."""
    core = history("core", CARRY_STATS)
    banner = Banner.of(
        Emblem("gpm", "tier_3"),
        Emblem("kills", "tier_3"),
        Emblem("stuns", "tier_3"),
        role="core",
    )
    neutral = advisor.evaluate_swap(core, banner, 1, Emblem("kills", "tier_3"))
    vampiric = advisor.evaluate_swap(core, banner, 1, Emblem("kills", "tier_3", "vampiric"))

    assert neutral["delta"] == pytest.approx(0.0)

    kills_base = next(
        v.base_points for v in advisor.stat_values(core) if v.stat == "kills"
    )
    # Сам по себе Vampiric дал бы +50% к своей эмблеме, но 10% он отнимает у
    # соседей — а сосед здесь дорогой GPM, так что чистый прирост заметно меньше.
    assert 0 < vampiric["delta"] < 0.5 * kills_base


def test_swap_rejects_bad_slot(advisor):
    core = history("core", CARRY_STATS)
    banner = Banner.of(Emblem("gpm", "tier_1"), role="core")
    with pytest.raises(ValueError, match="слот"):
        advisor.evaluate_swap(core, banner, 5, Emblem("kills", "tier_1"))


# --- кто лучше под стат -------------------------------------------------------


def test_rank_for_stat_orders_by_output(advisor):
    warders = history("support", {**SUPPORT_STATS, "wards_placed": 22}, team_id=1)
    stackers = history("support", {**SUPPORT_STATS, "wards_placed": 9}, team_id=2)

    ranking = advisor.rank_for_stat("wards_placed", [warders, stackers])
    assert [r.team_id for r in ranking] == [1, 2]
    assert ranking[0].units_per_game > ranking[1].units_per_game


def test_rank_skips_roles_that_cannot_take_the_stat(advisor):
    """GPM саппорту недоступен, поэтому в рейтинге по GPM его быть не должно."""
    core = history("core", CARRY_STATS, team_id=1)
    support = history("support", SUPPORT_STATS, team_id=2)

    ranking = advisor.rank_for_stat("gpm", [core, support])
    assert [r.team_id for r in ranking] == [1]


def test_rank_skips_thin_samples(advisor):
    thin = history("core", CARRY_STATS, team_id=1, games=2)
    solid = history("core", CARRY_STATS, team_id=2, games=12)
    ranking = advisor.rank_for_stat("gpm", [thin, solid], min_games=5)
    assert [r.team_id for r in ranking] == [2]


def test_rank_rejects_unknown_stat(advisor):
    with pytest.raises(KeyError):
        advisor.rank_for_stat("nonsense", [history("core", CARRY_STATS)])


# --- титулы -------------------------------------------------------------------


def test_titles_estimated_from_match_data(advisor):
    short_games = history("core", CARRY_STATS, duration=20 * 60, won=False)
    advice = {t.key: t for t in advisor.title_advice(short_games)}

    assert advice["decisive"].hit_rate == pytest.approx(1.0)
    assert advice["decisive"].expected_bonus == pytest.approx(0.24)
    assert advice["underdog"].hit_rate == pytest.approx(1.0)


def test_long_games_kill_the_decisive_title(advisor):
    long_games = history("core", CARRY_STATS, duration=45 * 60)
    advice = {t.key: t for t in advisor.title_advice(long_games)}
    assert advice["decisive"].hit_rate == pytest.approx(0.0)
    assert advice["decisive"].expected_bonus == pytest.approx(0.0)


def test_unmodelled_titles_are_flagged_not_guessed(advisor):
    advice = {t.key: t for t in advisor.title_advice(history("core", CARRY_STATS))}
    assert advice["tormented"].expected_bonus is None
    assert advice["tormented"].note
    assert advice["crimson"].estimator == "hero_pool"


def test_titles_sorted_by_expected_value(advisor):
    advice = advisor.title_advice(history("core", CARRY_STATS, duration=20 * 60, won=False))
    estimated = [t for t in advice if t.expected_bonus is not None]
    assert estimated == sorted(
        estimated, key=lambda t: -t.expected_bonus
    )
    # Неоценённые титулы уходят в конец списка.
    assert advice[-1].expected_bonus is None
