"""Нейтральные баннеры для сравнения кандидатов между собой.

Когда задача — не «оценить конкретный баннер», а «выбрать игроков», всем
кандидатам роли нужно дать одинаковый набор эмблем. Иначе сравнение команд
незаметно превращается в сравнение баннеров.

Составы наборов — по профилю роли: у кора очки идут с фарма и убийств, у мида
добавляется участие в файтах, у саппорта — обзор, стаки и контроль. Tier III без
трейтов — середина шкалы качества, чтобы множители не искажали сравнение.
"""

from __future__ import annotations

from .scoring import Banner, Emblem

DEFAULT_ROLE_STATS: dict[str, tuple[str, ...]] = {
    "core": ("kills", "gpm", "creep_score"),
    "mid": ("kills", "gpm", "teamfight_participation"),
    "support": ("wards_placed", "stuns", "camps_stacked"),
}

NEUTRAL_QUALITY = "tier_3"


def neutral_banner(role: str, stats: tuple[str, ...] | list[str] | None = None) -> Banner:
    """Баннер для честного сравнения кандидатов на роль."""
    chosen = tuple(stats) if stats else DEFAULT_ROLE_STATS.get(role, DEFAULT_ROLE_STATS["core"])
    return Banner(
        emblems=tuple(Emblem(stat=s, quality=NEUTRAL_QUALITY) for s in chosen),
        role=role,
    )
