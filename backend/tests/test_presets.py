"""Тесты нейтральных баннеров.

Регрессия: наборы для сравнения кандидатов остались от версии, где цвета слотов
ещё не были известны. У кора получалось три красных эмблемы, хотя третий слот
зелёный, — такой баннер в игре собрать нельзя, и сравнение опиралось на
несуществующую конфигурацию.
"""

from __future__ import annotations

import pytest

from app.fantasy.presets import DEFAULT_ROLE_STATS, NEUTRAL_QUALITY, neutral_banner
from app.fantasy.rules import load_rules


@pytest.fixture(scope="module")
def rules():
    return load_rules()


@pytest.mark.parametrize("role", ["core", "mid", "support"])
def test_neutral_banner_matches_role_colours(rules, role):
    banner = neutral_banner(role)
    colours = [str(rules.stats[e.stat].color) for e in banner.emblems]
    assert colours == [str(c) for c in rules.slot_colors(role)]


@pytest.mark.parametrize("role", ["core", "mid", "support"])
def test_neutral_banner_is_valid(rules, role):
    neutral_banner(role).validate(rules, strict_slots=True, check_role_colors=True)


@pytest.mark.parametrize("role", ["core", "mid", "support"])
def test_neutral_banner_uses_middle_quality(role):
    assert all(e.quality == NEUTRAL_QUALITY for e in neutral_banner(role).emblems)
    assert all(e.trait is None for e in neutral_banner(role).emblems)


def test_every_role_has_a_preset(rules):
    assert set(DEFAULT_ROLE_STATS) == set(rules.role_slots)


def test_custom_stats_still_checked_against_colours(rules):
    """Свой набор тоже обязан укладываться в цвета слотов роли."""
    with pytest.raises(ValueError, match="слот"):
        neutral_banner("support", ["gpm", "camps_stacked", "stuns"])


def test_banner_stats_are_distinct(rules):
    for role in DEFAULT_ROLE_STATS:
        stats = neutral_banner(role).stats()
        assert len(set(stats)) == len(stats)
