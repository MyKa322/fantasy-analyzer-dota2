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


# --- свой инвентарь эмблем ----------------------------------------------------


def test_inventory_gaps_names_missing_colors(advisor):
    only_red = [
        Emblem(stat="gpm", quality="tier_3", trait=None),
        Emblem(stat="kills", quality="tier_3", trait=None),
        Emblem(stat="creep_score", quality="tier_3", trait=None),
    ]
    # Саппорту нужны два синих и зелёный — красные тут бесполезны.
    gaps = advisor.inventory_gaps(only_red, "support")
    assert len(gaps) == 2
    assert any(g.startswith("blue") for g in gaps)
    assert any(g.startswith("green") for g in gaps)
    # Кору эти же эмблемы закрывают красные слоты, но не зелёный.
    assert advisor.inventory_gaps(only_red, "core") == ("green: нужно 1, есть 0",)


def test_inventory_uses_only_owned_emblems(advisor):
    inventory = [
        Emblem(stat="wards_placed", quality="tier_2", trait=None),
        Emblem(stat="camps_stacked", quality="tier_4", trait=None),
        Emblem(stat="stuns", quality="tier_1", trait=None),
        Emblem(stat="smokes_used", quality="tier_5", trait=None),
    ]
    fit = advisor.fit_inventory(history("support", SUPPORT_STATS), inventory)

    assert len(fit.used) == 3
    assert set(fit.used) <= set(inventory)
    assert len(fit.unused) == 1
    assert fit.slots[0].color == "blue"
    assert fit.slots[2].color == "green"


def test_benevolent_goes_to_the_middle_slot(advisor):
    """Бонус соседям выгоднее там, где соседей двое."""
    inventory = [
        Emblem(stat="wards_placed", quality="tier_3", trait="benevolent"),
        Emblem(stat="camps_stacked", quality="tier_3", trait=None),
        Emblem(stat="stuns", quality="tier_3", trait=None),
    ]
    fit = advisor.fit_inventory(history("support", SUPPORT_STATS), inventory)
    assert fit.used[1].trait == "benevolent"


def test_vampiric_goes_to_the_edge(advisor):
    """Vampiric отнимает у соседей, поэтому его место с краю."""
    inventory = [
        Emblem(stat="wards_placed", quality="tier_3", trait="vampiric"),
        Emblem(stat="camps_stacked", quality="tier_3", trait=None),
        Emblem(stat="stuns", quality="tier_3", trait=None),
    ]
    fit = advisor.fit_inventory(history("support", SUPPORT_STATS), inventory)
    assert fit.used[0].trait == "vampiric"


def test_inventory_fit_is_not_just_the_given_order(advisor):
    """Раскладка действительно оптимальна, а не «как передали»."""
    role_history = history("support", SUPPORT_STATS)
    inventory = [
        Emblem(stat="wards_placed", quality="tier_5", trait="benevolent"),
        Emblem(stat="camps_stacked", quality="tier_2", trait=None),
        Emblem(stat="stuns", quality="tier_3", trait=None),
    ]
    fit = advisor.fit_inventory(role_history, inventory)

    values = {v.stat: v for v in advisor.stat_values(role_history, role="support")}
    for order in ((0, 1, 2), (1, 0, 2)):
        banner = Banner(emblems=tuple(inventory[i] for i in order), role="support")
        multipliers = advisor.scorer.emblem_multipliers(banner)
        total = sum(
            values[e.stat].base_points * m
            for e, m in zip(banner.emblems, multipliers, strict=True)
        )
        assert fit.expected_card_points >= total - 1e-6


def test_inventory_refuses_a_role_it_cannot_fill(advisor):
    inventory = [
        Emblem(stat="gpm", quality="tier_3", trait=None),
        Emblem(stat="kills", quality="tier_3", trait=None),
        Emblem(stat="creep_score", quality="tier_3", trait=None),
    ]
    with pytest.raises(ValueError, match="не хватает"):
        advisor.fit_inventory(history("support", SUPPORT_STATS), inventory)


def test_rank_inventory_puts_the_best_pair_first(advisor):
    inventory = [
        Emblem(stat="wards_placed", quality="tier_3", trait=None),
        Emblem(stat="camps_stacked", quality="tier_3", trait=None),
        Emblem(stat="stuns", quality="tier_3", trait=None),
    ]
    weak = history("support", SUPPORT_STATS, team_id=1)
    strong = history(
        "support", {**SUPPORT_STATS, "wards_placed": 30, "camps_stacked": 12}, team_id=2
    )

    ranking = advisor.rank_inventory(inventory, [weak, strong])
    assert [f.team_id for f in ranking] == [2, 1]
    assert ranking[0].expected_card_points > ranking[1].expected_card_points


def test_rank_inventory_skips_roles_without_matching_colors(advisor):
    """Роль, которую инвентарь не закрывает, выпадает из рейтинга целиком."""
    blue_and_green = [
        Emblem(stat="wards_placed", quality="tier_3", trait=None),
        Emblem(stat="camps_stacked", quality="tier_3", trait=None),
        Emblem(stat="stuns", quality="tier_3", trait=None),
    ]
    ranking = advisor.rank_inventory(
        blue_and_green,
        [
            history("support", SUPPORT_STATS, team_id=1),
            history("core", CARRY_STATS, team_id=2),
        ],
    )
    assert [f.role for f in ranking] == ["support"]


# --- точечные данные ----------------------------------------------------------


def test_player_values_split_the_pair(advisor):
    """Роль считается по среднему пары, но виден и вклад каждого."""
    games = [
        RoleGame(
            match_id=2000 + i,
            start_time=NOW - timedelta(days=i),
            series_key=f"s{i}",
            player_stats={
                10: {"wards_placed": 24, "camps_stacked": 2, "stuns": 30},
                11: {"wards_placed": 6, "camps_stacked": 10, "stuns": 30},
            },
        )
        for i in range(10)
    ]
    role_history = RoleHistory(
        role="support",
        team_id=1,
        account_ids=(10, 11),
        games=games,
        player_names=("Warder", "Stacker"),
    )

    profiles = {p.name: p for p in advisor.player_values(role_history)}
    assert profiles["Warder"].value("wards_placed").units_per_game == pytest.approx(24)
    assert profiles["Stacker"].value("wards_placed").units_per_game == pytest.approx(6)

    # Среднее по игрокам совпадает со значением роли — иначе разбивка врала бы.
    role_value = {v.stat: v for v in advisor.stat_values(role_history)}["wards_placed"]
    pair_mean = (
        profiles["Warder"].value("wards_placed").base_points
        + profiles["Stacker"].value("wards_placed").base_points
    ) / 2
    assert role_value.base_points == pytest.approx(pair_mean)


def test_player_values_ignore_games_a_player_missed(advisor):
    """Стенд-ин не должен обнулять средние тому, кого заменяли."""
    games = [
        RoleGame(
            match_id=3000 + i,
            start_time=NOW - timedelta(days=i),
            series_key=f"s{i}",
            player_stats=(
                {10: {"wards_placed": 20}, 11: {"wards_placed": 20}}
                if i < 5
                else {10: {"wards_placed": 20}}
            ),
        )
        for i in range(10)
    ]
    role_history = RoleHistory(
        role="support",
        team_id=1,
        account_ids=(10, 11),
        games=games,
        player_names=("Main", "Sub"),
    )
    profiles = {p.name: p for p in advisor.player_values(role_history)}
    assert profiles["Sub"].games == 5
    assert profiles["Sub"].value("wards_placed").units_per_game == pytest.approx(20)


def test_hit_rate_separates_rare_events_from_steady_ones(advisor):
    """0,3 Рошана за карту — это «каждая третья игра», а не «понемногу каждую»."""
    games = [
        RoleGame(
            match_id=4000 + i,
            start_time=NOW - timedelta(days=i),
            series_key=f"s{i}",
            player_stats={10: {"stuns": 30, "roshan_kills": 1.0 if i % 3 == 0 else 0.0}},
        )
        for i in range(12)
    ]
    values = {
        v.stat: v
        for v in advisor.stat_values(
            RoleHistory(role="support", team_id=1, account_ids=(10,), games=games)
        )
    }
    assert values["stuns"].hit_rate == pytest.approx(1.0)
    assert values["roshan_kills"].hit_rate == pytest.approx(4 / 12)


def test_trend_compares_the_last_month_with_the_previous_two(advisor):
    fresh = [
        RoleGame(
            match_id=5000 + i,
            start_time=NOW - timedelta(days=i),
            series_key=f"s{i}",
            player_stats={10: {"wards_placed": 20}},
        )
        for i in range(6)
    ]
    stale = [
        RoleGame(
            match_id=6000 + i,
            start_time=NOW - timedelta(days=45 + i),
            series_key=f"o{i}",
            player_stats={10: {"wards_placed": 10}},
        )
        for i in range(6)
    ]
    values = {
        v.stat: v
        for v in advisor.stat_values(
            RoleHistory(role="support", team_id=1, account_ids=(10,), games=stale + fresh),
            now=NOW,
        )
    }
    assert values["wards_placed"].trend == pytest.approx(2.0)


def test_trend_stays_none_without_enough_games(advisor):
    values = {
        v.stat: v
        for v in advisor.stat_values(history("support", SUPPORT_STATS), now=NOW)
    }
    # Все карты в одном окне — сравнивать не с чем.
    assert values["wards_placed"].trend is None


# --- герои и титулы -----------------------------------------------------------


def hero_history(
    picks: list[tuple[int, bool]],
    *,
    role: str = "core",
    account_ids: tuple[int, ...] = (10,),
    duration: int = 2100,
    first_blood: int | None = 120,
    series_size: int = 1,
) -> RoleHistory:
    """История с заданными героями: (hero_id, победа) на каждую карту."""
    games = []
    for i, (hero_id, won) in enumerate(picks):
        games.append(
            RoleGame(
                match_id=7000 + i,
                start_time=NOW - timedelta(days=len(picks) - i),
                series_key=f"series:{i // series_size}",
                player_stats={a: {"kills": 5, "gpm": 500} for a in account_ids},
                duration=duration,
                won=won,
                first_blood_time=first_blood,
                heroes={a: hero_id for a in account_ids},
            )
        )
    return RoleHistory(role=role, team_id=1, account_ids=account_ids, games=games)


AXE, LINA, PUDGE = 2, 25, 14  # красные по списку Crimson
CM = 5  # Crystal Maiden — синяя, но не красная
HERO_NAMES = {AXE: "Axe", LINA: "Lina", PUDGE: "Pudge", CM: "Crystal Maiden"}


def test_hero_pool_counts_games_and_wins(advisor):
    history = hero_history([(AXE, True), (AXE, False), (LINA, True)])
    pool = advisor.hero_pool(history, heroes=HERO_NAMES)

    assert [p.name for p in pool] == ["Axe", "Lina"]
    assert pool[0].games == 2
    assert pool[0].wins == 1
    assert pool[0].win_rate == pytest.approx(0.5)
    assert pool[0].players == ((10, 2),)


def test_hero_pool_splits_a_duo(advisor):
    """У пары видно, чей это герой, — иначе пул выглядит общим."""
    games = [
        RoleGame(
            match_id=8000 + i,
            start_time=NOW - timedelta(days=i),
            series_key=f"s{i}",
            player_stats={10: {"kills": 5}, 11: {"kills": 5}},
            won=True,
            heroes={10: AXE, 11: LINA},
        )
        for i in range(4)
    ]
    history = RoleHistory(role="core", team_id=1, account_ids=(10, 11), games=games)
    pool = {p.name: p for p in advisor.hero_pool(history, heroes=HERO_NAMES)}

    assert pool["Axe"].players == ((10, 4),)
    assert pool["Lina"].players == ((11, 4),)


def test_prefix_estimated_from_hero_pool(advisor):
    """Crimson даёт +6% за красного героя — значит, считаем долю таких карт."""
    history = hero_history([(AXE, True), (LINA, True), (CM, True), (CM, False)])
    titles = {t.key: t for t in advisor.title_advice(history, heroes=HERO_NAMES)}

    # Axe и Lina есть в списке Crimson, Crystal Maiden — нет.
    assert titles["crimson"].hit_rate == pytest.approx(0.5)
    assert titles["crimson"].expected_bonus == pytest.approx(0.06 * 0.5)
    # Crystal Maiden в списке Cerulean, остальные трое — нет.
    assert titles["cerulean"].hit_rate == pytest.approx(0.5)


def test_prefixes_stay_unestimated_without_hero_directory(advisor):
    history = hero_history([(AXE, True)])
    titles = {t.key: t for t in advisor.title_advice(history)}
    assert titles["crimson"].expected_bonus is None
    assert "справочник" in titles["crimson"].note


def test_lucky_counts_durations_ending_in_eight(advisor):
    history = hero_history([(AXE, True), (AXE, True)], duration=1508)
    titles = {t.key: t for t in advisor.title_advice(history, heroes=HERO_NAMES)}
    assert titles["lucky"].hit_rate == pytest.approx(1.0)

    history = hero_history([(AXE, True)], duration=1500)
    titles = {t.key: t for t in advisor.title_advice(history, heroes=HERO_NAMES)}
    assert titles["lucky"].hit_rate == pytest.approx(0.0)


def test_patient_looks_at_first_blood_time(advisor):
    late = hero_history([(AXE, True), (AXE, True)], first_blood=700)
    titles = {t.key: t for t in advisor.title_advice(late, heroes=HERO_NAMES)}
    assert titles["patient"].hit_rate == pytest.approx(1.0)
    assert titles["patient"].expected_bonus == pytest.approx(0.23)

    early = hero_history([(AXE, True)], first_blood=90)
    titles = {t.key: t for t in advisor.title_advice(early, heroes=HERO_NAMES)}
    assert titles["patient"].hit_rate == pytest.approx(0.0)


def test_patient_ignores_matches_without_first_blood_time(advisor):
    """Ноль у OpenDota значит и «до гонга», и «событие не поймано»."""
    mixed = hero_history([(AXE, True), (AXE, True)], first_blood=700)
    mixed.games[0] = RoleGame(
        match_id=mixed.games[0].match_id,
        start_time=mixed.games[0].start_time,
        series_key=mixed.games[0].series_key,
        player_stats=mixed.games[0].player_stats,
        duration=mixed.games[0].duration,
        won=mixed.games[0].won,
        first_blood_time=0,
        heroes=mixed.games[0].heroes,
    )
    titles = {t.key: t for t in advisor.title_advice(mixed, heroes=HERO_NAMES)}
    # Карта с нулём выброшена, а не засчитана как «первая кровь на нулевой секунде».
    assert titles["patient"].hit_rate == pytest.approx(1.0)
    assert "1 картам из 2" in titles["patient"].note


def test_clutch_counts_deciders_of_full_series(advisor):
    """Решающая карта — последняя возможная: третья в Bo3, пятая в Bo5."""
    bo3 = hero_history([(AXE, True)] * 3, series_size=3)
    titles = {t.key: t for t in advisor.title_advice(bo3, heroes=HERO_NAMES)}
    assert titles["clutch"].hit_rate == pytest.approx(1 / 3)

    # Серия 2-0 решающей карты не имела.
    swept = hero_history([(AXE, True)] * 2, series_size=2)
    titles = {t.key: t for t in advisor.title_advice(swept, heroes=HERO_NAMES)}
    assert titles["clutch"].hit_rate == pytest.approx(0.0)


def test_unmodelled_titles_explain_themselves(advisor):
    titles = {
        t.key: t
        for t in advisor.title_advice(hero_history([(AXE, True)]), heroes=HERO_NAMES)
    }
    # Причина у каждого своя и живёт в конфиге рядом с титулом.
    assert titles["flayed"].expected_bonus is None
    assert "нулём" in titles["flayed"].note
    assert titles["cruel"].expected_bonus is None
    assert titles["tormented"].note


def test_notes_carry_translation_key_and_numbers(advisor):
    """Пояснение уходит на фронт и текстом, и ключом с числами.

    Интерфейс переведён на четыре языка, и собрать «34% выборов — герои из
    списка» из готовой русской строки нельзя: числа приходится отдавать
    отдельно от шаблона.
    """
    titles = {
        t.key: t
        for t in advisor.title_advice(hero_history([(AXE, True)]), heroes=HERO_NAMES)
    }

    crimson = titles["crimson"]
    assert crimson.note_key == "title.note.heroShare"
    assert crimson.note_params["total"] == 1
    # Проценты уходят целыми: подставлять «0.34» в «{pct}%» бессмысленно.
    assert crimson.note_params["pct"] == round((crimson.hit_rate or 0) * 100)

    # У неоцениваемых ключ собирается из титула: у каждого своя причина.
    assert titles["flayed"].note_key == "title.note.flayed"
    assert all(t.note_key for t in titles.values() if t.note)


def test_every_prefix_lists_known_heroes():
    """Опечатка в списке героев молча выкинула бы его из оценки титула."""
    from app.fantasy.rules import load_rules
    from app.services.profiles import load_heroes

    known = set(load_heroes().values())
    assert known, "справочник героев не собран"

    for title in load_rules().titles["prefixes"]:
        listed = title.get("heroes") or []
        assert listed, f"у префикса {title['key']} нет списка героев"
        unknown = [name for name in listed if name not in known]
        assert not unknown, f"{title['key']}: неизвестные герои {unknown}"
