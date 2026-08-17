"""Движок начисления Fantasy-очков компендиума TI15.

Порядок расчёта (по разделу Scoring внутриигрового глоссария):

    статы игрока за игру
      -> очки по каждой эмблеме баннера роли (база стата * множитель эмблемы)
      -> счёт игрока за игру (+ множители Coaching Titles)
      -> среднее по всем игрокам роли              = счёт роли за игру
      -> сумма двух лучших игр серии               = счёт роли за матч
      -> лучшая серия периода                      = счёт роли за период

Про множитель эмблемы. Все бонусы СКЛАДЫВАЮТСЯ — это видно на экране War Banner,
где каждая карточка показывает итоговый процент:

    процент_i = 100% + бонус качества + собственный трейт (если условие выполнено)
                + сумма эффектов соседних эмблем

Сверка на реальных карточках из игры:

    Creep Score  Tier II + Friendly (условие не выполнено)     = 100+30+0      = 130%
    Stuns        Tier I  + Fractal (не выполнен) + сосед-Vamp   = 100+10+0-10  = 100%
    GPM          Tier II + Vampiric сам себе                    = 100+30+50    = 180%
    GPM (mid)    Tier II + Unique + сосед-Vampiric              = 100+30+30-10 = 150%
    Teamfight    Tier II + Fractal (не выполнен) + сосед-Vamp   = 100+30+0-10  = 120%

Мультипликативная трактовка сохранена в `BonusMode` только как исторический
вариант — рабочий режим аддитивный и зафиксирован в конфиге.

Цвет каждого слота задан ролью (core RED/RED/GREEN, mid RED/BLUE/GREEN,
support BLUE/BLUE/GREEN) и не рероллится: меняются стат внутри цвета, качество и
трейт. Поэтому саппорту, например, GPM недоступен в принципе.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from math import prod, isclose
from typing import Self

from .rules import (
    BannerLayout,
    FantasyRules,
    TraitCondition,
    TraitScope,
    load_rules,
)


class BonusMode(StrEnum):
    """Как складываются бонусы эмблемы.

    ADDITIVE — режим игры: все проценты суммируются.
    MULTIPLICATIVE — устаревшая гипотеза, оставлена только для сравнения.
    """

    ADDITIVE = "additive"
    MULTIPLICATIVE = "multiplicative"


@dataclass(frozen=True, slots=True)
class Emblem:
    stat: str
    quality: str
    trait: str | None = None

    def __str__(self) -> str:
        trait = f"/{self.trait}" if self.trait else ""
        return f"{self.stat}({self.quality}{trait})"


@dataclass(frozen=True, slots=True)
class Banner:
    """War Banner роли: набор эмблем в фиксированном порядке (порядок важен —
    от него зависят соседи для Benevolent/Vampiric)."""

    emblems: tuple[Emblem, ...]
    role: str | None = None

    @classmethod
    def of(cls, *emblems: Emblem, role: str | None = None) -> Self:
        return cls(emblems=tuple(emblems), role=role)

    def __len__(self) -> int:
        return len(self.emblems)

    def __iter__(self):
        return iter(self.emblems)

    def stats(self) -> tuple[str, ...]:
        return tuple(e.stat for e in self.emblems)

    def colors(self, rules: FantasyRules) -> tuple[str, ...]:
        return tuple(str(rules.stats[e.stat].color) for e in self.emblems)

    def validate(
        self,
        rules: FantasyRules,
        *,
        strict_slots: bool = False,
        check_role_colors: bool = False,
        stage: str | None = None,
    ) -> None:
        """Проверить баннер на соответствие правилам. Бросает ValueError.

        `stage` выбирает раскладку периода: в группе у роли три слота, в
        основном этапе — пять, и цвета там свои.
        """
        layout = rules.layout(stage).banner
        if strict_slots and len(self.emblems) != layout.slots:
            raise ValueError(
                f"баннер должен содержать {layout.slots} эмблем, получено {len(self.emblems)}"
            )

        if check_role_colors:
            if self.role is None:
                raise ValueError("для проверки цветов у баннера должна быть указана роль")
            expected = rules.slot_colors(self.role, stage)
            if len(self.emblems) != len(expected):
                raise ValueError(
                    f"роль {self.role!r} использует {len(expected)} слотов, "
                    f"передано {len(self.emblems)}"
                )
            for index, (emblem, color) in enumerate(zip(self.emblems, expected, strict=True)):
                actual = rules.stats[emblem.stat].color
                if actual != color:
                    raise ValueError(
                        f"слот {index + 1} роли {self.role!r} должен быть {color}, "
                        f"а стат {emblem.stat!r} — {actual}"
                    )
        if not layout.allow_duplicate_stats:
            seen = self.stats()
            if len(set(seen)) != len(seen):
                dupes = sorted({s for s in seen if seen.count(s) > 1})
                raise ValueError(f"дублирующиеся статы на баннере: {dupes}")
        for emblem in self.emblems:
            if emblem.stat not in rules.stats:
                raise ValueError(f"неизвестный стат эмблемы: {emblem.stat!r}")
            rules.quality_bonus(emblem.quality)
            if emblem.trait is not None:
                rules.trait(emblem.trait)


@dataclass(frozen=True, slots=True)
class EmblemBreakdown:
    """Разложение очков одной эмблемы — то, что показываем в UI."""

    emblem: Emblem
    stat_value: float
    base_points: float
    multiplier: float
    points: float
    active_traits: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class GameScore:
    total: float
    breakdown: tuple[EmblemBreakdown, ...]
    title_multiplier: float = 1.0

    def by_stat(self) -> dict[str, float]:
        return {b.emblem.stat: b.points for b in self.breakdown}


@dataclass(frozen=True, slots=True)
class SeriesScore:
    """Счёт роли за серию: сумма N лучших игр (N = games_per_series)."""

    total: float
    counted_games: tuple[float, ...]
    all_games: tuple[float, ...]
    series_id: str | None = None


@dataclass(frozen=True, slots=True)
class PeriodScore:
    total: float
    best_series: SeriesScore | None
    all_series: tuple[SeriesScore, ...] = field(default=())


def _trait_active(trait_key: str, banner: Banner, rules: FantasyRules) -> bool:
    """Выполнено ли условие трейта на данном баннере."""
    condition = rules.trait(trait_key).condition
    match condition:
        case TraitCondition.ALWAYS:
            return True
        case TraitCondition.ALL_QUALITIES_DISTINCT:
            qualities = [e.quality for e in banner.emblems]
            return len(set(qualities)) == len(qualities)
        case TraitCondition.ONLY_UNIQUE_ON_BANNER:
            return sum(1 for e in banner.emblems if e.trait == trait_key) == 1
        case TraitCondition.AT_LEAST_3_FRIENDLY:
            return sum(1 for e in banner.emblems if e.trait == trait_key) >= 3
    raise ValueError(f"unknown trait condition: {condition}")


class FantasyScorer:
    """Считает Fantasy-очки по загруженным правилам."""

    def __init__(
        self,
        rules: FantasyRules | None = None,
        *,
        bonus_mode: BonusMode | None = None,
    ) -> None:
        self.rules = rules if rules is not None else load_rules()
        self.bonus_mode = bonus_mode or BonusMode(
            getattr(self.rules, "trait_bonus_mode", BonusMode.MULTIPLICATIVE)
        )

    # --- множители эмблем -----------------------------------------------------

    def emblem_multipliers(self, banner: Banner) -> tuple[float, ...]:
        """Множитель к базовым очкам стата для каждой эмблемы баннера."""
        rules = self.rules
        layout: BannerLayout = rules.banner
        active = {
            e.trait: _trait_active(e.trait, banner, rules)
            for e in banner.emblems
            if e.trait is not None
        }

        multipliers: list[float] = []
        for index, emblem in enumerate(banner.emblems):
            quality_bonus = rules.quality_bonus(emblem.quality)
            self_amounts: list[float] = []

            if emblem.trait and active.get(emblem.trait):
                trait = rules.trait(emblem.trait)
                # SELF_BONUS и SELF_VALUE в аддитивной модели неразличимы: и то и
                # другое просто добавляет свои проценты к итогу карточки.
                self_amounts = [
                    e.amount
                    for e in (
                        *trait.effects_for(TraitScope.SELF_BONUS),
                        *trait.effects_for(TraitScope.SELF_VALUE),
                    )
                ]

            adjacent_amounts: list[float] = []
            for neighbour_index in self._neighbours(index, len(banner.emblems), layout):
                neighbour = banner.emblems[neighbour_index]
                if not neighbour.trait or not active.get(neighbour.trait):
                    continue
                adjacent_amounts.extend(
                    e.amount
                    for e in rules.trait(neighbour.trait).effects_for(
                        TraitScope.ADJACENT_VALUE
                    )
                )

            if self.bonus_mode is BonusMode.ADDITIVE:
                multiplier = (
                    1.0 + quality_bonus + sum(self_amounts) + sum(adjacent_amounts)
                )
            else:
                multiplier = (
                    (1.0 + quality_bonus * prod(1 + a for a in self_amounts))
                    * prod(1 + a for a in adjacent_amounts)
                )
            multipliers.append(multiplier)
        return tuple(multipliers)

    @staticmethod
    def _neighbours(index: int, size: int, layout: BannerLayout) -> tuple[int, ...]:
        """Соседи с поправкой на фактический размер баннера (может отличаться от
        конфигурационного, например при переборе вариантов)."""
        if layout.adjacency == "ring":
            if size < 2:
                return ()
            if size == 2:
                return (1 - index,)
            return ((index - 1) % size, (index + 1) % size)
        return tuple(i for i in (index - 1, index + 1) if 0 <= i < size)

    # --- счёт за игру ---------------------------------------------------------

    def score_player_game(
        self,
        banner: Banner,
        stats: Mapping[str, float],
        *,
        title_multiplier: float = 1.0,
    ) -> GameScore:
        """Счёт одного игрока за одну карту.

        Очки начисляются только за статы, присутствующие на баннере роли —
        остальные поля `stats` игнорируются.
        """
        multipliers = self.emblem_multipliers(banner)
        breakdown: list[EmblemBreakdown] = []
        total = 0.0

        for emblem, multiplier in zip(banner.emblems, multipliers, strict=True):
            rule = self.rules.stats[emblem.stat]
            value = float(stats.get(emblem.stat, 0.0))
            base_points = rule.points(value)
            points = base_points * multiplier
            total += points
            traits = (emblem.trait,) if emblem.trait and _trait_active(
                emblem.trait, banner, self.rules
            ) else ()
            breakdown.append(
                EmblemBreakdown(
                    emblem=emblem,
                    stat_value=value,
                    base_points=base_points,
                    multiplier=multiplier,
                    points=points,
                    active_traits=traits,
                )
            )

        return GameScore(
            total=total * title_multiplier,
            breakdown=tuple(breakdown),
            title_multiplier=title_multiplier,
        )

    def score_role_game(
        self,
        banner: Banner,
        players_stats: Sequence[Mapping[str, float]],
        *,
        title_multiplier: float = 1.0,
    ) -> float:
        """Счёт роли за одну карту — среднее по всем игрокам роли.

        Игроки, не участвовавшие в карте, в `players_stats` не передаются:
        глоссарий считает счёт "in every game they participate in", то есть
        среднее берётся по фактически сыгравшим.
        """
        if not players_stats:
            return 0.0
        scores = [
            self.score_player_game(banner, s, title_multiplier=title_multiplier).total
            for s in players_stats
        ]
        if self.rules.scoring.aggregate_within_role != "mean":
            raise NotImplementedError(
                f"агрегация {self.rules.scoring.aggregate_within_role!r} не поддержана"
            )
        return sum(scores) / len(scores)

    # --- серии и период -------------------------------------------------------

    def score_series(
        self,
        game_scores: Iterable[float],
        *,
        series_id: str | None = None,
    ) -> SeriesScore:
        """Счёт роли за матч — сумма двух лучших карт серии."""
        games = tuple(float(g) for g in game_scores)
        take = self.rules.scoring.games_per_series
        counted = tuple(sorted(games, reverse=True)[:take])
        return SeriesScore(
            total=sum(counted),
            counted_games=counted,
            all_games=games,
            series_id=series_id,
        )

    def score_period(self, series_scores: Iterable[SeriesScore]) -> PeriodScore:
        """Счёт роли за период — лучшая серия из сыгранных."""
        all_series = tuple(series_scores)
        if not all_series:
            return PeriodScore(total=0.0, best_series=None, all_series=())
        if self.rules.scoring.series_per_period != "best":
            raise NotImplementedError(
                f"режим {self.rules.scoring.series_per_period!r} не поддержан"
            )
        best = max(all_series, key=lambda s: s.total)
        return PeriodScore(total=best.total, best_series=best, all_series=all_series)

    # --- утилиты --------------------------------------------------------------

    def stat_points(self, stat: str, value: float) -> float:
        """Базовые очки стата без учёта эмблемы — для калибровки и отладки."""
        return self.rules.stats[stat].points(value)

    def explain(self, banner: Banner, stats: Mapping[str, float]) -> str:
        """Человекочитаемое разложение счёта — для CLI и отладки конфига."""
        score = self.score_player_game(banner, stats)
        lines = [f"Banner: {' | '.join(str(e) for e in banner.emblems)}"]
        for b in score.breakdown:
            traits = f" [{', '.join(b.active_traits)}]" if b.active_traits else ""
            lines.append(
                f"  {self.rules.stats[b.emblem.stat].label:<24}"
                f" value={b.stat_value:>8.2f}"
                f" base={b.base_points:>10.1f}"
                f" x{b.multiplier:.3f}{traits}"
                f" = {b.points:>10.1f}"
            )
        if not isclose(score.title_multiplier, 1.0):
            lines.append(f"  titles x{score.title_multiplier:.3f}")
        lines.append(f"  TOTAL: {score.total:.1f}")
        return "\n".join(lines)
