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

NEUTRAL_QUALITY = "tier_3"


def neutral_banner(
    role: str,
    stats: tuple[str, ...] | list[str] | None = None,
    *,
    rules: FantasyRules | None = None,
) -> Banner:
    """Баннер для честного сравнения кандидатов на роль.

    Результат валидируется по цветам слотов: набор, который нельзя собрать в
    игре, сравнивать бессмысленно.
    """
    rules = rules or load_rules()
    chosen = tuple(stats) if stats else DEFAULT_ROLE_STATS.get(role, DEFAULT_ROLE_STATS["core"])
    banner = Banner(
        emblems=tuple(Emblem(stat=s, quality=NEUTRAL_QUALITY) for s in chosen),
        role=role,
    )
    banner.validate(rules, check_role_colors=True)
    return banner
