"""Анализатор эмблем: что ставить на баннер и кого под это брать.

Три вопроса, на которые отвечает модуль:

1. **Что этот стат стоит для этой роли.** Ценность эмблемы — не свойство стата,
   а произведение его цены на то, сколько игрок его делает. Roshan Kills стоит
   1172 очка за штуку, но саппорту, который добивает Рошана раз в двадцать игр,
   он приносит меньше, чем Wards Placed по 117 за варду при девятнадцати вардах
   за карту. Ровно это и считается здесь по реальной истории матчей.

2. **Какой баннер собрать.** Цвет каждого слота фиксирован ролью, поэтому набор
   кандидатов в слот ограничен цветом. Внутри — перебор статов, качеств и
   трейтов: комбинация решает не меньше, чем сами статы, потому что Fractal
   требует три разных качества, Friendly — три Friendly-эмблемы, а Vampiric
   отнимает у соседей.

3. **Кого брать под конкретный стат.** Обратная задача: если на баннере уже
   стоит Camps Stacked, кто из шестнадцати команд стакает больше всех.

Все оценки идут по правилу «две лучшие карты лучшей серии» — то есть по
проекции, а не по среднему. Быстрая линейная оценка используется только для
предварительного отсева, и это отмечено в названиях функций.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from itertools import product

import numpy as np

from .projection import Projection, RoleHistory, RoleProjector
from .rules import Color, FantasyRules
from .scoring import Banner, Emblem

log = logging.getLogger(__name__)

# Значение, которого хватает, чтобы стат вообще имело смысл ставить на баннер.
# Ниже этого эмблема — почти пустой слот.
NEGLIGIBLE_POINTS = 50.0


@dataclass(frozen=True, slots=True)
class StatValue:
    """Во что превращается один стат для конкретной роли."""

    stat: str
    label: str
    color: str
    # Среднее количество единиц стата за карту (килов, вард, секунд стана).
    units_per_game: float
    # Базовые очки без учёта качества и трейтов.
    base_points: float
    # Разброс по картам: в Fantasy важен потолок, а не только среднее.
    p95_points: float
    p5_points: float
    availability: str
    games: int

    @property
    def is_negligible(self) -> bool:
        return self.base_points < NEGLIGIBLE_POINTS


@dataclass(frozen=True, slots=True)
class SlotAdvice:
    """Рекомендация по одному слоту баннера."""

    slot: int
    color: str
    emblem: Emblem
    percent: float
    base_points: float
    points: float
    alternatives: tuple[StatValue, ...] = ()


@dataclass(slots=True)
class BannerAdvice:
    role: str
    team_id: int
    emblems: tuple[Emblem, ...]
    slots: tuple[SlotAdvice, ...]
    expected_card_points: float
    projection: Projection | None = None

    def banner(self) -> Banner:
        return Banner(emblems=self.emblems, role=self.role)

    def summary(self) -> dict[str, object]:
        return {
            "role": self.role,
            "team_id": self.team_id,
            "expected_card_points": round(self.expected_card_points, 1),
            "period_mean": round(self.projection.mean, 1) if self.projection else None,
            "period_ceiling": round(self.projection.ceiling, 1) if self.projection else None,
            "emblems": [
                {
                    "slot": s.slot,
                    "color": s.color,
                    "stat": s.emblem.stat,
                    "quality": s.emblem.quality,
                    "trait": s.emblem.trait,
                    "percent": round(s.percent, 1),
                    "points": round(s.points, 1),
                }
                for s in self.slots
            ],
        }


@dataclass(frozen=True, slots=True)
class PlayerRanking:
    """Строка рейтинга «кто лучше всего отрабатывает этот стат»."""

    stat: str
    team_id: int
    team_name: str | None
    role: str
    player_names: tuple[str, ...]
    units_per_game: float
    base_points: float
    p95_points: float
    games: int


@dataclass(frozen=True, slots=True)
class TitleAdvice:
    key: str
    label: str
    bonus: float
    condition: str
    # Доля игр, в которых условие выполнялось (для оцениваемых по данным).
    hit_rate: float | None
    expected_bonus: float | None
    estimator: str
    note: str = ""


class EmblemAdvisor:
    """Советник по эмблемам поверх проекции очков."""

    def __init__(self, projector: RoleProjector | None = None) -> None:
        self.projector = projector or RoleProjector()
        self.rules: FantasyRules = self.projector.rules
        self.scorer = self.projector.scorer

    # --- 1. ценность статов ---------------------------------------------------

    def stat_values(
        self,
        history: RoleHistory,
        *,
        role: str | None = None,
        now: datetime | None = None,
        include_unavailable: bool = False,
    ) -> list[StatValue]:
        """Во что превращается каждый доступный роли стат, по убыванию ценности."""
        from ..ingest.stat_mapping import STAT_SOURCES

        role = role or history.role
        base = self.projector.base_matrix(history)
        weights = self.projector.recency_weights(history, now=now)
        allowed = self.rules.available_stats(role)

        values: list[StatValue] = []
        for stat_key in self.rules.stats:
            if stat_key not in allowed:
                continue  # цвет слота не позволит поставить этот стат этой роли
            source = STAT_SOURCES.get(stat_key)
            if (
                not include_unavailable
                and source is not None
                and source.availability == "unavailable"
            ):
                continue

            index = self.projector._stat_index[stat_key]
            column = base[:, index]
            rule = self.rules.stats[stat_key]

            # Средние единицы стата: обратная операция к базовым очкам. Для
            # «deaths» и «teamfight» это нелинейно, поэтому считаем по-честному
            # из исходных статов.
            units = self._mean_units(history, stat_key, weights)

            values.append(
                StatValue(
                    stat=stat_key,
                    label=rule.label,
                    color=str(rule.color),
                    units_per_game=units,
                    base_points=float(weights @ column),
                    p95_points=float(np.percentile(column, 95)) if len(column) else 0.0,
                    p5_points=float(np.percentile(column, 5)) if len(column) else 0.0,
                    availability=source.availability if source else "exact",
                    games=len(history.games),
                )
            )

        values.sort(key=lambda v: -v.base_points)
        return values

    def _mean_units(
        self, history: RoleHistory, stat_key: str, weights: np.ndarray
    ) -> float:
        per_game = []
        for game in history.games:
            players = [
                game.player_stats[a] for a in history.account_ids if a in game.player_stats
            ]
            if not players:
                per_game.append(0.0)
                continue
            per_game.append(
                sum(float(p.get(stat_key, 0.0)) for p in players) / len(players)
            )
        if not per_game:
            return 0.0
        return float(weights @ np.array(per_game))

    # --- 2. подбор баннера ----------------------------------------------------

    def optimise_banner(
        self,
        history: RoleHistory,
        *,
        role: str | None = None,
        qualities: Sequence[str] | None = None,
        traits: Sequence[str | None] | None = None,
        stats_per_slot: int = 3,
        simulate: bool = True,
        simulations: int = 3000,
        top_n: int = 3,
        now: datetime | None = None,
        **project_kwargs: object,
    ) -> list[BannerAdvice]:
        """Собрать лучший баннер для роли.

        `qualities` и `traits` ограничивают перебор тем, что реально доступно:
        если из роллов выпали только Tier II и III, оптимум надо искать среди
        них, а не среди недостижимых Tier V.

        Перебор идёт в два круга. Сначала по каждому цветному слоту берутся
        `stats_per_slot` лучших статов по базовым очкам — остальные при любых
        качестве и трейте не догонят. Затем полный перебор комбинаций качеств и
        трейтов: их взаимодействие нелинейно (Fractal требует три разных
        качества, Friendly — три одинаковых трейта), поэтому жадный выбор по
        слотам здесь ошибается.
        """
        role = role or history.role
        colors = self.rules.slot_colors(role)
        qualities = list(qualities or self.rules.qualities)
        traits = list(traits) if traits is not None else [None, *self.rules.traits]

        values = {v.stat: v for v in self.stat_values(history, role=role, now=now)}
        by_color: dict[str, list[StatValue]] = {}
        for value in values.values():
            by_color.setdefault(value.color, []).append(value)
        for color_values in by_color.values():
            color_values.sort(key=lambda v: -v.base_points)

        slot_candidates: list[list[StatValue]] = []
        for color in colors:
            pool = by_color.get(str(color), [])
            if not pool:
                raise ValueError(f"нет доступных статов цвета {color} для роли {role}")
            slot_candidates.append(pool[:stats_per_slot])

        # Множители зависят только от качеств и трейтов — статы на них не влияют.
        # Поэтому набор множителей считается один раз, а не заново для каждой
        # комбинации статов: 27 тысяч вариантов вместо трёх четвертей миллиона.
        layouts: list[tuple[tuple[str, ...], tuple[str | None, ...]]] = []
        multiplier_rows: list[list[float]] = []
        probe_stats = [pool[0].stat for pool in slot_candidates]
        for quality_combo in product(qualities, repeat=len(colors)):
            for trait_combo in product(traits, repeat=len(colors)):
                probe = Banner(
                    emblems=tuple(
                        Emblem(stat=s, quality=q, trait=t)
                        for s, q, t in zip(
                            probe_stats, quality_combo, trait_combo, strict=True
                        )
                    ),
                    role=role,
                )
                layouts.append((quality_combo, trait_combo))
                multiplier_rows.append(list(self.scorer.emblem_multipliers(probe)))

        multipliers_matrix = np.array(multiplier_rows)  # (варианты, слоты)

        stat_combos: list[tuple[str, ...]] = []
        base_rows: list[list[float]] = []
        for stat_combo in product(*slot_candidates):
            stats = tuple(v.stat for v in stat_combo)
            if not self.rules.banner.allow_duplicate_stats and len(set(stats)) != len(stats):
                continue
            stat_combos.append(stats)
            base_rows.append([values[s].base_points for s in stats])

        if not stat_combos:
            raise ValueError(f"не удалось собрать баннер для роли {role}")

        base_matrix = np.array(base_rows)  # (комбинации статов, слоты)
        totals = base_matrix @ multipliers_matrix.T  # (статы, качества-трейты)

        # Берём с запасом: часть верхних вариантов схлопнется как дубликаты.
        flat = totals.ravel()
        take = min(flat.size, max(top_n * 20, 50))
        order = np.argpartition(-flat, take - 1)[:take]
        order = order[np.argsort(-flat[order])]

        best: list[tuple[float, tuple[Emblem, ...]]] = []
        for position in order:
            stat_index, layout_index = divmod(int(position), multipliers_matrix.shape[0])
            stats = stat_combos[stat_index]
            quality_combo, trait_combo = layouts[layout_index]
            best.append(
                (
                    float(flat[position]),
                    tuple(
                        Emblem(stat=s, quality=q, trait=t)
                        for s, q, t in zip(stats, quality_combo, trait_combo, strict=True)
                    ),
                )
            )

        advices: list[BannerAdvice] = []
        seen: set[tuple[tuple[str, str, str | None], ...]] = set()
        for total, emblems in best:
            key = tuple((e.stat, e.quality, e.trait) for e in emblems)
            if key in seen:
                continue
            seen.add(key)
            advices.append(
                self._describe(history, role, emblems, total, values, by_color)
            )
            if len(advices) >= top_n:
                break

        if simulate:
            for advice in advices:
                advice.projection = self.projector.project(
                    history, advice.banner(), simulations=simulations, **project_kwargs
                )

        return advices

    def _describe(
        self,
        history: RoleHistory,
        role: str,
        emblems: tuple[Emblem, ...],
        total: float,
        values: Mapping[str, StatValue],
        by_color: Mapping[str, list[StatValue]],
    ) -> BannerAdvice:
        banner = Banner(emblems=emblems, role=role)
        multipliers = self.scorer.emblem_multipliers(banner)
        slots: list[SlotAdvice] = []
        for index, (emblem, multiplier) in enumerate(zip(emblems, multipliers, strict=True)):
            value = values[emblem.stat]
            slots.append(
                SlotAdvice(
                    slot=index,
                    color=value.color,
                    emblem=emblem,
                    percent=multiplier * 100.0,
                    base_points=value.base_points,
                    points=value.base_points * multiplier,
                    alternatives=tuple(
                        v for v in by_color.get(value.color, []) if v.stat != emblem.stat
                    )[:4],
                )
            )
        return BannerAdvice(
            role=role,
            team_id=history.team_id,
            emblems=emblems,
            slots=tuple(slots),
            expected_card_points=total,
        )

    def evaluate_swap(
        self,
        history: RoleHistory,
        banner: Banner,
        slot: int,
        candidate: Emblem,
        *,
        now: datetime | None = None,
    ) -> dict[str, float]:
        """Что даст замена одной эмблемы — в очках за карту.

        Ровно тот вопрос, который стоит перед каждым роллом: три предложенных
        варианта, один токен, и надо понять, стоит ли менять то, что уже стоит.
        Замена влияет не только на свой слот — трейт меняет и соседей.
        """
        if not 0 <= slot < len(banner.emblems):
            raise ValueError(f"слот {slot} вне баннера из {len(banner.emblems)} эмблем")

        values = {v.stat: v for v in self.stat_values(history, role=banner.role, now=now)}

        def total_for(target: Banner) -> float:
            multipliers = self.scorer.emblem_multipliers(target)
            return sum(
                values[e.stat].base_points * m
                for e, m in zip(target.emblems, multipliers, strict=True)
                if e.stat in values
            )

        before = total_for(banner)
        emblems = list(banner.emblems)
        emblems[slot] = candidate
        after = total_for(Banner(emblems=tuple(emblems), role=banner.role))

        return {
            "before": before,
            "after": after,
            "delta": after - before,
            "delta_pct": (after / before - 1.0) * 100.0 if before else 0.0,
        }

    # --- 3. кто лучше под стат ------------------------------------------------

    def rank_for_stat(
        self,
        stat: str,
        histories: Iterable[RoleHistory],
        *,
        team_names: Mapping[int, str] | None = None,
        now: datetime | None = None,
        min_games: int = 5,
    ) -> list[PlayerRanking]:
        """Кто из кандидатов лучше всего отрабатывает конкретный стат."""
        if stat not in self.rules.stats:
            raise KeyError(f"неизвестный стат {stat!r}")

        team_names = team_names or {}
        rows: list[PlayerRanking] = []
        index = self.projector._stat_index[stat]

        for history in histories:
            if len(history.games) < min_games:
                continue
            if stat not in self.rules.available_stats(history.role):
                continue  # цвет слота этой роли не позволит взять такой стат
            base = self.projector.base_matrix(history)
            weights = self.projector.recency_weights(history, now=now)
            column = base[:, index]
            rows.append(
                PlayerRanking(
                    stat=stat,
                    team_id=history.team_id,
                    team_name=team_names.get(history.team_id, history.team_name),
                    role=history.role,
                    player_names=history.player_names,
                    units_per_game=self._mean_units(history, stat, weights),
                    base_points=float(weights @ column),
                    p95_points=float(np.percentile(column, 95)),
                    games=len(history.games),
                )
            )

        rows.sort(key=lambda r: -r.base_points)
        return rows

    # --- Coaching Titles ------------------------------------------------------

    def title_advice(self, history: RoleHistory) -> list[TitleAdvice]:
        """Какие титулы выгодны этой роли — по её же матчам.

        Часть условий из данных не проверить (смерть от Торментора, килл в
        фонтане) — такие титулы возвращаются без оценки и помечены, а не
        оцениваются наугад.
        """
        games = history.games
        durations = [g.duration for g in games if g.duration]
        losses = [g.won for g in games if g.won is not None]

        estimates: dict[str, tuple[float, str]] = {}
        if durations:
            short = sum(1 for d in durations if d < 25 * 60) / len(durations)
            estimates["decisive"] = (short, f"{short:.0%} игр короче 25 минут")
        if losses:
            lost = sum(1 for won in losses if not won) / len(losses)
            estimates["underdog"] = (lost, f"{lost:.0%} игр проиграно")

        advice: list[TitleAdvice] = []
        for group in ("prefixes", "suffixes"):
            for title in self.rules.titles.get(group, []) or []:
                key = title["key"]
                bonus = float(title["bonus"])
                estimator = title.get("estimator", "unmodelled")
                hit_rate, note = estimates.get(key, (None, ""))

                if estimator == "hero_pool":
                    note = note or "зависит от пула героев — данных о цветах героев нет"
                elif estimator == "unmodelled" and not note:
                    note = "условие вне наших данных"
                elif hit_rate is None:
                    note = note or "недостаточно данных"

                advice.append(
                    TitleAdvice(
                        key=key,
                        label=title["label"],
                        bonus=bonus,
                        condition=title.get("condition", ""),
                        hit_rate=hit_rate,
                        expected_bonus=bonus * hit_rate if hit_rate is not None else None,
                        estimator=estimator,
                        note=note,
                    )
                )

        # Сначала то, что реально посчитано, по убыванию ожидаемого вклада.
        advice.sort(key=lambda t: (t.expected_bonus is None, -(t.expected_bonus or 0.0)))
        return advice
