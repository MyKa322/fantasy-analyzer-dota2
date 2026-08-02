"""Загрузка и типизация правил Fantasy Draft из YAML-конфига.

Все числа компендиума живут в `config/ti15_fantasy.yaml`, а не в коде: Valve
правит веса между турнирами, и обновление должно быть правкой одной строки.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from typing import Any, Self

import yaml

CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"
DEFAULT_RULES_PATH = CONFIG_DIR / "ti15_fantasy.yaml"


class Color(StrEnum):
    RED = "red"
    BLUE = "blue"
    GREEN = "green"


class StatKind(StrEnum):
    PER_UNIT = "per_unit"
    LINEAR = "linear"
    FLAT = "flat"
    CAPPED = "capped"


class TraitScope(StrEnum):
    SELF_BONUS = "self_bonus"
    SELF_VALUE = "self_value"
    ADJACENT_VALUE = "adjacent_value"


class TraitCondition(StrEnum):
    ALWAYS = "always"
    ALL_QUALITIES_DISTINCT = "all_qualities_distinct"
    ONLY_UNIQUE_ON_BANNER = "only_unique_on_banner"
    AT_LEAST_3_FRIENDLY = "at_least_3_friendly"


@dataclass(frozen=True, slots=True)
class StatRule:
    key: str
    label: str
    color: Color
    kind: StatKind
    per_unit: float = 0.0
    base: float = 0.0
    value_if_true: float = 0.0
    max_points: float = 0.0

    def points(self, value: float) -> float:
        """Базовые очки за стат до применения бонусов эмблемы."""
        match self.kind:
            case StatKind.PER_UNIT:
                return self.per_unit * value
            case StatKind.LINEAR:
                return self.base + self.per_unit * value
            case StatKind.FLAT:
                return self.value_if_true if value else 0.0
            case StatKind.CAPPED:
                return self.max_points * min(max(value, 0.0), 1.0)
        raise ValueError(f"unknown stat kind: {self.kind}")

    @classmethod
    def from_dict(cls, key: str, raw: dict[str, Any]) -> Self:
        return cls(
            key=key,
            label=raw.get("label", key),
            color=Color(raw["color"]),
            kind=StatKind(raw["kind"]),
            per_unit=float(raw.get("per_unit", 0.0)),
            base=float(raw.get("base", 0.0)),
            value_if_true=float(raw.get("value_if_true", 0.0)),
            max_points=float(raw.get("max_points", 0.0)),
        )


@dataclass(frozen=True, slots=True)
class TraitEffect:
    scope: TraitScope
    amount: float


@dataclass(frozen=True, slots=True)
class TraitRule:
    key: str
    label: str
    description: str
    condition: TraitCondition
    effects: tuple[TraitEffect, ...]

    def effects_for(self, scope: TraitScope) -> tuple[TraitEffect, ...]:
        return tuple(e for e in self.effects if e.scope is scope)

    @classmethod
    def from_dict(cls, key: str, raw: dict[str, Any]) -> Self:
        return cls(
            key=key,
            label=raw.get("label", key),
            description=raw.get("description", ""),
            condition=TraitCondition(raw.get("condition", "always")),
            effects=tuple(
                TraitEffect(scope=TraitScope(e["scope"]), amount=float(e["amount"]))
                for e in raw.get("effects", [])
            ),
        )


@dataclass(frozen=True, slots=True)
class BannerLayout:
    slots: int
    adjacency: str
    allow_duplicate_stats: bool
    per_role: bool

    def neighbours(self, index: int) -> tuple[int, ...]:
        """Индексы соседних слотов для трейтов вида `adjacent_value`."""
        if self.adjacency == "ring":
            if self.slots < 2:
                return ()
            if self.slots == 2:
                return (1 - index,)
            return ((index - 1) % self.slots, (index + 1) % self.slots)
        # linear: у крайних эмблем только один сосед
        return tuple(i for i in (index - 1, index + 1) if 0 <= i < self.slots)


@dataclass(frozen=True, slots=True)
class RoleRule:
    key: str
    label: str
    players: int


@dataclass(frozen=True, slots=True)
class ScoringRules:
    aggregate_within_role: str
    games_per_series: int
    series_per_period: str
    roles: dict[str, RoleRule]


@dataclass(frozen=True, slots=True)
class FantasyRules:
    version: str
    source: str
    stats: dict[str, StatRule]
    qualities: dict[str, float]
    traits: dict[str, TraitRule]
    banner: BannerLayout
    scoring: ScoringRules
    trait_bonus_mode: str = "additive"
    # Цвета слотов по ролям: core [red, red, green] и т.д. Цвет задан ролью и не
    # рероллится — он же ограничивает набор доступных роли статов.
    role_slots: dict[str, tuple[Color, ...]] = field(default_factory=dict)
    titles: dict[str, list[dict[str, Any]]] = field(default_factory=dict)

    def slot_colors(self, role: str) -> tuple[Color, ...]:
        try:
            return self.role_slots[role]
        except KeyError:
            raise KeyError(
                f"неизвестная роль {role!r}; известны: {sorted(self.role_slots)}"
            ) from None

    def stats_for_role(self, role: str) -> dict[int, list[StatRule]]:
        """Какие статы доступны роли в каждом слоте баннера."""
        return {
            index: self.stats_by_color(color)
            for index, color in enumerate(self.slot_colors(role))
        }

    def available_stats(self, role: str) -> set[str]:
        """Все статы, которые роль вообще может получить на баннер."""
        return {
            stat.key
            for color in set(self.slot_colors(role))
            for stat in self.stats_by_color(color)
        }

    def stats_by_color(self, color: Color | str) -> list[StatRule]:
        wanted = Color(color)
        return [s for s in self.stats.values() if s.color == wanted]

    def quality_bonus(self, quality: str) -> float:
        try:
            return self.qualities[quality]
        except KeyError:
            raise KeyError(
                f"unknown emblem quality {quality!r}; known: {sorted(self.qualities)}"
            ) from None

    def trait(self, key: str) -> TraitRule:
        try:
            return self.traits[key]
        except KeyError:
            raise KeyError(
                f"unknown emblem trait {key!r}; known: {sorted(self.traits)}"
            ) from None

    @classmethod
    def from_yaml(cls, path: Path | str = DEFAULT_RULES_PATH) -> Self:
        raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        banner_raw = raw.get("banner", {})
        scoring_raw = raw.get("scoring_rules", {})
        return cls(
            version=raw.get("version", "unknown"),
            source=raw.get("source", ""),
            stats={k: StatRule.from_dict(k, v) for k, v in raw["stats"].items()},
            qualities={k: float(v) for k, v in raw["qualities"].items()},
            traits={k: TraitRule.from_dict(k, v) for k, v in raw["traits"].items()},
            banner=BannerLayout(
                slots=int(banner_raw.get("slots", 3)),
                adjacency=str(banner_raw.get("adjacency", "linear")),
                allow_duplicate_stats=bool(banner_raw.get("allow_duplicate_stats", False)),
                per_role=bool(banner_raw.get("per_role", True)),
            ),
            scoring=ScoringRules(
                aggregate_within_role=scoring_raw.get("aggregate_within_role", "mean"),
                games_per_series=int(scoring_raw.get("games_per_series", 2)),
                series_per_period=scoring_raw.get("series_per_period", "best"),
                roles={
                    k: RoleRule(key=k, label=v.get("label", k), players=int(v["players"]))
                    for k, v in scoring_raw.get("roles", {}).items()
                },
            ),
            trait_bonus_mode=str(raw.get("trait_bonus_mode", "additive")),
            role_slots={
                role: tuple(Color(c) for c in colors)
                for role, colors in (raw.get("role_slots") or {}).items()
            },
            titles=raw.get("titles", {}) or {},
        )


@lru_cache(maxsize=4)
def load_rules(path: Path | str = DEFAULT_RULES_PATH) -> FantasyRules:
    """Загрузить правила с кэшем — конфиг читается один раз за процесс."""
    return FantasyRules.from_yaml(path)
