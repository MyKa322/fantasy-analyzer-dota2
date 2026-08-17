"""Нейтральные баннеры для сравнения кандидатов между собой.

Когда задача — не «оценить конкретный баннер», а «выбрать игроков», всем
кандидатам роли нужно дать одинаковый набор эмблем. Иначе сравнение команд
незаметно превращается в сравнение баннеров.

Наборы обязаны укладываться в цвета слотов роли: core — красный, красный,
зелёный; mid — красный, синий, зелёный; support — синий, синий, зелёный. Иначе
получается баннер, который в игре собрать нельзя, и сравнение опирается на
несуществующую конфигурацию.

Внутри цвета берётся типичный для роли стат: у кора фарм и убийства, у мида
добавляется руна, у саппорта — обзор и стаки. Tier III без трейтов — середина
шкалы качества, чтобы множители не искажали сравнение.
"""

from __future__ import annotations

from .rules import FantasyRules, load_rules
from .scoring import Banner, Emblem

# Порядок статов соответствует порядку цветов слотов у роли.
DEFAULT_ROLE_STATS: dict[str, tuple[str, ...]] = {
    # red, red, green
    "core": ("gpm", "kills", "teamfight_participation"),
    # red, blue, green
    "mid": ("gpm", "runes_grabbed", "teamfight_participation"),
    # blue, blue, green
    "support": ("wards_placed", "camps_stacked", "stuns"),
}

# Основной этап играется баннером на пять эмблем, и цвета слотов там свои.
# Наборы те же по смыслу — типичное для роли внутри доступного цвета.
MAIN_ROLE_STATS: dict[str, tuple[str, ...]] = {
    # red, green, red, green, red
    "core": ("gpm", "teamfight_participation", "kills", "roshan_kills", "creep_score"),
    # red, blue, green, red, green
    "mid": ("gpm", "runes_grabbed", "teamfight_participation", "kills", "first_blood"),
    # blue, green, blue, green, blue
    "support": (
        "wards_placed",
        "stuns",
        "camps_stacked",
        "teamfight_participation",
        "smokes_used",
    ),
}

STAGE_ROLE_STATS: dict[str, dict[str, tuple[str, ...]]] = {"main": MAIN_ROLE_STATS}

NEUTRAL_QUALITY = "tier_3"


def neutral_stats(role: str, stage: str | None = None) -> tuple[str, ...]:
    """Нейтральный набор статов роли для периода."""
    table = STAGE_ROLE_STATS.get(stage or "", DEFAULT_ROLE_STATS)
    return table.get(role, table["core"])


def neutral_banner(
    role: str,
    stats: tuple[str, ...] | list[str] | None = None,
    *,
    rules: FantasyRules | None = None,
    stage: str | None = None,
) -> Banner:
    """Баннер для честного сравнения кандидатов на роль.

    Результат валидируется по цветам слотов: набор, который нельзя собрать в
    игре, сравнивать бессмысленно. В основном этапе слотов пять, поэтому и
    набор другой — сравнивать периоды между собой всё равно нельзя.
    """
    rules = rules or load_rules()
    chosen = tuple(stats) if stats else neutral_stats(role, stage)
    banner = Banner(
        emblems=tuple(Emblem(stat=s, quality=NEUTRAL_QUALITY) for s in chosen),
        role=role,
    )
    banner.validate(rules, check_role_colors=True, stage=stage)
    return banner
