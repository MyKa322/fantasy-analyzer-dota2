"""Тесты движка Fantasy-очков против цифр из глоссария TI15."""

from __future__ import annotations

import pytest

from app.fantasy.rules import load_rules
from app.fantasy.scoring import Banner, BonusMode, Emblem, FantasyScorer


@pytest.fixture(scope="module")
def rules():
    return load_rules()


@pytest.fixture(scope="module")
def scorer(rules):
    return FantasyScorer(rules)


# --- базовая стоимость статов -------------------------------------------------


@pytest.mark.parametrize(
    ("stat", "value", "expected"),
    [
        ("kills", 8, 8 * 107.0),
        ("deaths", 0, 1950.0),
        ("deaths", 3, 1950.0 - 3 * 195.0),
        ("deaths", 10, 1950.0 - 10 * 195.0),  # уходит в минус — так и задумано
        ("creep_score", 412, 412 * 3.0),
        ("gpm", 712, 712 * 2.0),
        ("madstone_collected", 24, 24 * 13.0),
        ("tower_kills", 3, 3 * 352.0),
        ("wards_placed", 19, 19 * 117.0),
        ("camps_stacked", 7, 7 * 234.0),
        ("runes_grabbed", 11, 11 * 141.0),
        ("watchers_taken", 4, 4 * 147.0),
        ("smokes_used", 5, 5 * 293.0),
        ("lotuses_grabbed", 6, 6 * 176.0),
        ("roshan_kills", 2, 2 * 1172.0),
        ("stuns", 63.4, 634.0),
        ("tormentor_kills", 1, 879.0),
        ("courier_kills", 1, 703.0),
        ("first_blood", 1, 1934.0),
        ("first_blood", 0, 0.0),
        ("teamfight_participation", 0.75, 0.75 * 2124.0),
        ("teamfight_participation", 1.4, 2124.0),  # клампится в потолок
    ],
)
def test_stat_base_points(scorer, stat, value, expected):
    assert scorer.stat_points(stat, value) == pytest.approx(expected)


def test_stat_colors_match_glossary(rules):
    red = {s.key for s in rules.stats_by_color("red")}
    blue = {s.key for s in rules.stats_by_color("blue")}
    green = {s.key for s in rules.stats_by_color("green")}

    assert red == {
        "kills",
        "deaths",
        "creep_score",
        "gpm",
        "madstone_collected",
        "tower_kills",
    }
    assert blue == {
        "wards_placed",
        "camps_stacked",
        "runes_grabbed",
        "watchers_taken",
        "smokes_used",
        "lotuses_grabbed",
    }
    assert green == {
        "roshan_kills",
        "teamfight_participation",
        "stuns",
        "tormentor_kills",
        "first_blood",
        "courier_kills",
    }


# --- эталон: реальные карточки War Banner из игры -----------------------------
#
# Три баннера со скриншота экрана крафта. Каждая карточка показывает итоговый
# процент — это самая прямая проверка формулы, какая вообще возможна.


@pytest.mark.parametrize(
    ("name", "emblems", "expected_percents"),
    [
        (
            "core",
            [
                ("creep_score", "tier_2", "friendly"),
                ("stuns", "tier_1", "fractal"),
                ("gpm", "tier_2", "vampiric"),
            ],
            [130, 100, 180],
        ),
        (
            "mid",
            [
                ("gpm", "tier_2", "unique"),
                ("smokes_used", "tier_2", "vampiric"),
                ("teamfight_participation", "tier_2", "fractal"),
            ],
            [150, 180, 120],
        ),
        (
            "support",
            [
                ("lotuses_grabbed", "tier_3", "fractal"),
                ("roshan_kills", "tier_2", "fractal"),
                ("smokes_used", "tier_2", "friendly"),
            ],
            [160, 130, 130],
        ),
    ],
)
def test_reference_banners_from_game(scorer, name, emblems, expected_percents):
    banner = Banner.of(*(Emblem(*e) for e in emblems), role=name)
    percents = [round(m * 100) for m in scorer.emblem_multipliers(banner)]
    assert percents == expected_percents


def test_reference_core_banner_explained(scorer):
    """Разбор ключевой карточки: почему Stuns даёт ровно 100%.

    Tier I даёт +10%, Fractal не срабатывает (два Tier II на баннере — качества
    не все разные), а сосед снизу с Vampiric снимает 10%. Итого 100 + 10 - 10.
    """
    banner = Banner.of(
        Emblem("creep_score", "tier_2", "friendly"),
        Emblem("stuns", "tier_1", "fractal"),
        Emblem("gpm", "tier_2", "vampiric"),
        role="core",
    )
    top, middle, bottom = scorer.emblem_multipliers(banner)

    # Верхняя эмблема не соседствует с Vampiric — при кольцевой раскладке
    # соседствовала бы, и здесь было бы 120%.
    assert top == pytest.approx(1.30)
    assert middle == pytest.approx(1.00)
    assert bottom == pytest.approx(1.80)


# --- качество эмблем ----------------------------------------------------------


@pytest.mark.parametrize(
    ("quality", "expected_multiplier"),
    [("tier_1", 1.10), ("tier_2", 1.30), ("tier_3", 1.60), ("tier_4", 2.00), ("tier_5", 2.50)],
)
def test_quality_multiplier(scorer, quality, expected_multiplier):
    banner = Banner.of(Emblem("kills", quality))
    assert scorer.emblem_multipliers(banner)[0] == pytest.approx(expected_multiplier)


def test_quality_applies_to_points(scorer):
    banner = Banner.of(Emblem("kills", "tier_4"))
    score = scorer.score_player_game(banner, {"kills": 10})
    assert score.total == pytest.approx(10 * 107.0 * 2.0)


# --- трейты -------------------------------------------------------------------


def test_fractal_active_when_all_qualities_distinct(scorer):
    banner = Banner.of(
        Emblem("kills", "tier_3", "fractal"),
        Emblem("gpm", "tier_1"),
        Emblem("stuns", "tier_5"),
    )
    # 100% + 60% (tier III) + 60% (fractal) = 220%
    assert scorer.emblem_multipliers(banner)[0] == pytest.approx(2.20)


def test_fractal_inactive_on_repeated_quality(scorer):
    banner = Banner.of(
        Emblem("kills", "tier_3", "fractal"),
        Emblem("gpm", "tier_3"),
        Emblem("stuns", "tier_5"),
    )
    assert scorer.emblem_multipliers(banner)[0] == pytest.approx(1.60)


def test_unique_active_only_when_alone(scorer):
    alone = Banner.of(
        Emblem("kills", "tier_2", "unique"),
        Emblem("gpm", "tier_2"),
    )
    paired = Banner.of(
        Emblem("kills", "tier_2", "unique"),
        Emblem("gpm", "tier_2", "unique"),
    )
    # 100% + 30% (tier II) + 30% (unique) = 160%
    assert scorer.emblem_multipliers(alone)[0] == pytest.approx(1.60)
    assert scorer.emblem_multipliers(paired)[0] == pytest.approx(1.30)


def test_friendly_needs_three_on_banner(scorer):
    two = Banner.of(
        Emblem("kills", "tier_1", "friendly"),
        Emblem("gpm", "tier_1", "friendly"),
        Emblem("stuns", "tier_1"),
    )
    three = Banner.of(
        Emblem("kills", "tier_1", "friendly"),
        Emblem("gpm", "tier_1", "friendly"),
        Emblem("stuns", "tier_1", "friendly"),
    )
    assert scorer.emblem_multipliers(two)[0] == pytest.approx(1.10)
    # 100% + 10% (tier I) + 50% (friendly) = 160%
    assert scorer.emblem_multipliers(three)[0] == pytest.approx(1.60)


def test_benevolent_boosts_neighbours_not_itself(scorer):
    banner = Banner.of(
        Emblem("kills", "tier_1"),
        Emblem("gpm", "tier_1", "benevolent"),
        Emblem("stuns", "tier_1"),
    )
    left, middle, right = scorer.emblem_multipliers(banner)
    assert left == pytest.approx(1.30)  # 100 + 10 + 20
    assert middle == pytest.approx(1.10)
    assert right == pytest.approx(1.30)


def test_vampiric_boosts_self_and_drains_neighbours(scorer):
    banner = Banner.of(
        Emblem("kills", "tier_1"),
        Emblem("gpm", "tier_1", "vampiric"),
        Emblem("stuns", "tier_1"),
    )
    left, middle, right = scorer.emblem_multipliers(banner)
    assert left == pytest.approx(1.00)  # 100 + 10 - 10
    assert middle == pytest.approx(1.60)  # 100 + 10 + 50
    assert right == pytest.approx(1.00)


def test_linear_adjacency_edges_have_one_neighbour(scorer):
    banner = Banner.of(
        Emblem("kills", "tier_1", "benevolent"),
        Emblem("gpm", "tier_1"),
        Emblem("stuns", "tier_1"),
        Emblem("wards_placed", "tier_1", "benevolent"),
    )
    m = scorer.emblem_multipliers(banner)
    assert m[1] == pytest.approx(1.30)  # сосед слева
    assert m[2] == pytest.approx(1.30)  # сосед справа
    assert m[0] == pytest.approx(1.10)
    assert m[3] == pytest.approx(1.10)


def test_stacked_adjacent_effects_add_up(scorer):
    """Эмблема между Benevolent и Vampiric получает оба эффекта суммой."""
    banner = Banner.of(
        Emblem("kills", "tier_2", "benevolent"),
        Emblem("gpm", "tier_3"),
        Emblem("stuns", "tier_4", "vampiric"),
    )
    middle = scorer.emblem_multipliers(banner)[1]
    assert middle == pytest.approx(1.70)  # 100 + 60 + 20 - 10


def test_additive_is_the_configured_mode(rules, scorer):
    assert rules.trait_bonus_mode == "additive"
    assert scorer.bonus_mode is BonusMode.ADDITIVE


def test_multiplicative_mode_kept_only_for_comparison(rules):
    """Старая гипотеза остаётся доступной, но даёт другие числа — и потому
    не совпала бы с карточками из игры."""
    legacy = FantasyScorer(rules, bonus_mode=BonusMode.MULTIPLICATIVE)
    banner = Banner.of(
        Emblem("creep_score", "tier_2", "friendly"),
        Emblem("stuns", "tier_1", "fractal"),
        Emblem("gpm", "tier_2", "vampiric"),
        role="core",
    )
    percents = [round(m * 100) for m in legacy.emblem_multipliers(banner)]
    assert percents != [130, 100, 180]


# --- счёт игрока / роли / серии / периода ------------------------------------


def test_only_stats_on_banner_are_counted(scorer):
    banner = Banner.of(Emblem("kills", "tier_1"), Emblem("gpm", "tier_1"))
    stats = {"kills": 10, "gpm": 700, "roshan_kills": 5, "first_blood": 1}
    score = scorer.score_player_game(banner, stats)
    expected = (10 * 107.0 + 700 * 2.0) * 1.10
    assert score.total == pytest.approx(expected)
    assert set(score.by_stat()) == {"kills", "gpm"}


def test_missing_stat_counts_as_zero_but_deaths_keep_base(scorer):
    banner = Banner.of(Emblem("deaths", "tier_1"), Emblem("kills", "tier_1"))
    score = scorer.score_player_game(banner, {})
    assert score.total == pytest.approx(1950.0 * 1.10)


def test_title_multiplier_applies_to_whole_game(scorer):
    banner = Banner.of(Emblem("kills", "tier_1"))
    plain = scorer.score_player_game(banner, {"kills": 10})
    boosted = scorer.score_player_game(banner, {"kills": 10}, title_multiplier=1.25)
    assert boosted.total == pytest.approx(plain.total * 1.25)


def test_role_score_is_mean_of_players(scorer):
    banner = Banner.of(Emblem("kills", "tier_1"))
    duo = [{"kills": 10}, {"kills": 4}]
    assert scorer.score_role_game(banner, duo) == pytest.approx(7 * 107.0 * 1.10)


def test_role_score_ignores_absent_players(scorer):
    banner = Banner.of(Emblem("kills", "tier_1"))
    assert scorer.score_role_game(banner, []) == 0.0


def test_series_takes_two_best_games(scorer):
    series = scorer.score_series([1000.0, 5000.0, 3000.0])
    assert series.total == pytest.approx(8000.0)
    assert series.counted_games == (5000.0, 3000.0)


def test_series_shorter_than_two_games(scorer):
    series = scorer.score_series([4200.0])
    assert series.total == pytest.approx(4200.0)


def test_period_takes_best_series(scorer):
    weak = scorer.score_series([1000.0, 1200.0], series_id="s1")
    strong = scorer.score_series([4000.0, 4500.0], series_id="s2")
    period = scorer.score_period([weak, strong])
    assert period.total == pytest.approx(8500.0)
    assert period.best_series is not None and period.best_series.series_id == "s2"


def test_period_without_games(scorer):
    period = scorer.score_period([])
    assert period.total == 0.0
    assert period.best_series is None


# --- валидация баннера --------------------------------------------------------


def test_duplicate_stats_rejected(rules, scorer):
    banner = Banner.of(Emblem("kills", "tier_1"), Emblem("kills", "tier_3"))
    with pytest.raises(ValueError, match="дублирующиеся статы"):
        banner.validate(rules)


def test_unknown_stat_rejected(rules):
    banner = Banner.of(Emblem("nonexistent_stat", "tier_1"))
    with pytest.raises(ValueError, match="неизвестный стат"):
        banner.validate(rules)


def test_unknown_quality_rejected(rules):
    banner = Banner.of(Emblem("kills", "tier_9"))
    with pytest.raises(KeyError, match="unknown emblem quality"):
        banner.validate(rules)


# --- цвета слотов по ролям ----------------------------------------------------


def test_role_slot_colors_match_game(rules):
    assert [str(c) for c in rules.slot_colors("core")] == ["red", "red", "green"]
    assert [str(c) for c in rules.slot_colors("mid")] == ["red", "blue", "green"]
    assert [str(c) for c in rules.slot_colors("support")] == ["blue", "blue", "green"]


def test_support_cannot_get_farm_stats(rules):
    """Цвет слота задан ролью, поэтому GPM саппорту не выпадет в принципе."""
    support_stats = rules.available_stats("support")
    assert "gpm" not in support_stats
    assert "creep_score" not in support_stats
    assert {"wards_placed", "camps_stacked", "stuns"} <= support_stats


def test_core_cannot_get_support_stats(rules):
    core_stats = rules.available_stats("core")
    assert "wards_placed" not in core_stats
    assert "smokes_used" not in core_stats
    assert {"gpm", "kills", "roshan_kills"} <= core_stats


def test_mid_can_take_all_three_colors(rules):
    mid_stats = rules.available_stats("mid")
    assert {"gpm", "smokes_used", "teamfight_participation"} <= mid_stats


def test_valid_role_banner_passes_color_check(rules):
    banner = Banner.of(
        Emblem("gpm", "tier_2"),
        Emblem("kills", "tier_3"),
        Emblem("stuns", "tier_1"),
        role="core",
    )
    banner.validate(rules, strict_slots=True, check_role_colors=True)


def test_wrong_color_in_slot_rejected(rules):
    """У кора второй слот красный — синяя эмблема туда встать не может."""
    banner = Banner.of(
        Emblem("gpm", "tier_2"),
        Emblem("wards_placed", "tier_3"),
        Emblem("stuns", "tier_1"),
        role="core",
    )
    with pytest.raises(ValueError, match="слот 2"):
        banner.validate(rules, check_role_colors=True)


def test_color_check_requires_role(rules):
    banner = Banner.of(Emblem("gpm", "tier_2"))
    with pytest.raises(ValueError, match="роль"):
        banner.validate(rules, check_role_colors=True)


def test_banner_has_three_slots(rules):
    assert rules.banner.slots == 3


def test_strict_slots_checks_banner_size(rules):
    banner = Banner.of(Emblem("kills", "tier_1"))
    with pytest.raises(ValueError, match="баннер должен содержать"):
        banner.validate(rules, strict_slots=True)


# --- сквозной сценарий --------------------------------------------------------


def test_realistic_carry_series(scorer):
    """Керри-дуо, реалистичные строки статов, полный путь до счёта за период."""
    banner = Banner.of(
        Emblem("gpm", "tier_4", "vampiric"),
        Emblem("kills", "tier_3", "benevolent"),
        Emblem("creep_score", "tier_2"),
        role="core",
    )
    game_1 = [
        {"gpm": 780, "kills": 12, "creep_score": 480},
        {"gpm": 640, "kills": 7, "creep_score": 390},
    ]
    game_2 = [
        {"gpm": 520, "kills": 3, "creep_score": 300},
        {"gpm": 610, "kills": 5, "creep_score": 355},
    ]

    m_gpm, m_kills, m_cs = scorer.emblem_multipliers(banner)
    # 100 + 100 (tier IV) + 50 (vampiric сам себе) + 20 (benevolent-сосед)
    assert m_gpm == pytest.approx(2.70)
    # 100 + 60 (tier III) - 10 (сосед-vampiric сверху)
    assert m_kills == pytest.approx(1.50)
    # 100 + 30 (tier II) + 20 (benevolent-сосед сверху)
    assert m_cs == pytest.approx(1.50)

    def role_score(game):
        return scorer.score_role_game(banner, game)

    s1, s2 = role_score(game_1), role_score(game_2)
    assert s1 > s2

    series = scorer.score_series([s1, s2])
    assert series.total == pytest.approx(s1 + s2)

    period = scorer.score_period([series, scorer.score_series([s2])])
    assert period.total == pytest.approx(series.total)
