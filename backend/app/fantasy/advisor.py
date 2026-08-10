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

4. **Что делать с эмблемами, которые уже выпали.** Роллы конечны, и обычно
   вопрос стоит не «какой баннер лучший вообще», а «под кого поставить то, что
   есть». Инвентарь раскладывается по цветам слотов каждой роли, и все пары
   TI15 ранжируются по очкам именно с этими эмблемами.

Все оценки идут по правилу «две лучшие карты лучшей серии» — то есть по
проекции, а не по среднему. Быстрая линейная оценка используется только для
предварительного отсева, и это отмечено в названиях функций.
"""

from __future__ import annotations

import logging
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from itertools import product

import numpy as np

from .projection import Projection, RoleGame, RoleHistory, RoleProjector
from .rules import FantasyRules
from .scoring import Banner, Emblem

log = logging.getLogger(__name__)

# Значение, которого хватает, чтобы стат вообще имело смысл ставить на баннер.
# Ниже этого эмблема — почти пустой слот.
NEGLIGIBLE_POINTS = 50.0

# Окно «свежей формы» и минимум карт в каждой половине сравнения.
TREND_WINDOW_DAYS = 30.0
MIN_TREND_GAMES = 3


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
    # Медиана и квартиль: среднее по одной-двум разгромным картам обманчиво,
    # а в зачёт идут две лучшие карты — важно видеть и центр, и верх.
    median_points: float = 0.0
    p75_points: float = 0.0
    # Доля карт, где стат вообще случился. Для Roshan и Tormentor это половина
    # ответа: 0.3 Рошана за карту — это «каждая третья игра», а не «понемногу
    # каждую».
    hit_rate: float = 0.0
    # Форма: очки за последние 30 дней делить на очки за предыдущие 60.
    # None — если одной из половин слишком мало карт, чтобы сравнение значило.
    trend: float | None = None
    # Разброс очков по картам. Нужен, чтобы понять, насколько точно среднее:
    # у команды с 29 картами и у команды со 134 это разная точность, а в
    # сравнении ролей между собой они иначе идут на равных.
    std_points: float = 0.0

    @property
    def is_negligible(self) -> bool:
        return self.base_points < NEGLIGIBLE_POINTS


@dataclass(frozen=True, slots=True)
class PlayerProfile:
    """Вклад одного игрока роли — то, что среднее по паре скрывает.

    В зачёт Fantasy идёт среднее по игрокам роли, поэтому пара, где варды
    ставит один человек, и пара, где оба, дают одинаковые очки — но разный
    риск: у первой всё держится на одном игроке.
    """

    account_id: int
    name: str | None
    games: int
    values: tuple[StatValue, ...]

    def value(self, stat: str) -> StatValue | None:
        return next((v for v in self.values if v.stat == stat), None)


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
class InventoryFit:
    """Лучшая раскладка имеющихся у игрока эмблем под конкретную роль команды."""

    role: str
    team_id: int
    team_name: str | None
    player_names: tuple[str, ...]
    slots: tuple[SlotAdvice, ...]
    expected_card_points: float
    used: tuple[Emblem, ...]
    unused: tuple[Emblem, ...]
    games: int

    def banner(self) -> Banner:
        return Banner(emblems=self.used, role=self.role)


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
class HeroPick:
    """Герой в пуле роли или игрока: сколько карт, сколько побед, кто играл."""

    hero_id: int
    name: str
    games: int
    wins: int
    # (account_id, карт) — у пары видно, чей это герой.
    players: tuple[tuple[int, int], ...] = ()

    @property
    def win_rate(self) -> float:
        return self.wins / self.games if self.games else 0.0


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
    # Тот же текст пояснения ключом словаря и числами к нему: интерфейс
    # переведён на четыре языка, а собрать фразу из готовой русской строки
    # нельзя. Русский текст остаётся — он нужен CLI и служит запасным
    # вариантом, если ключа в словаре ещё нет.
    note_key: str = ""
    note_params: Mapping[str, float | int | str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Estimate:
    """Оценка условия титула по данным: доля карт и пояснение к ней."""

    hit_rate: float | None
    note: str
    note_key: str
    params: Mapping[str, float | int | str] = field(default_factory=dict)


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
        role = role or history.role
        base = self.projector.base_matrix(history)
        weights = self.projector.recency_weights(history, now=now)
        return self._values_from(
            history, base, weights, role=role, now=now, include_unavailable=include_unavailable
        )

    def _values_from(
        self,
        history: RoleHistory,
        base: np.ndarray,
        weights: np.ndarray,
        *,
        role: str,
        now: datetime | None,
        include_unavailable: bool,
        games: Sequence[RoleGame] | None = None,
        account_ids: Sequence[int] | None = None,
    ) -> list[StatValue]:
        """Общая часть для роли целиком и для отдельного игрока."""
        from ..ingest.stat_mapping import STAT_SOURCES

        games = list(games if games is not None else history.games)
        account_ids = tuple(account_ids if account_ids is not None else history.account_ids)
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
            units = self._unit_series(games, account_ids, stat_key)

            values.append(
                StatValue(
                    stat=stat_key,
                    label=rule.label,
                    color=str(rule.color),
                    units_per_game=float(weights @ units) if len(units) else 0.0,
                    base_points=float(weights @ column) if len(column) else 0.0,
                    p95_points=float(np.percentile(column, 95)) if len(column) else 0.0,
                    p5_points=float(np.percentile(column, 5)) if len(column) else 0.0,
                    median_points=float(np.median(column)) if len(column) else 0.0,
                    p75_points=float(np.percentile(column, 75)) if len(column) else 0.0,
                    hit_rate=float((units > 0).mean()) if len(units) else 0.0,
                    trend=self._trend(games, column, now=now),
                    std_points=float(column.std(ddof=1)) if len(column) > 1 else 0.0,
                    availability=source.availability if source else "exact",
                    games=len(games),
                )
            )

        values.sort(key=lambda v: -v.base_points)
        return values

    def _unit_series(
        self,
        games: Sequence[RoleGame],
        account_ids: Sequence[int],
        stat_key: str,
    ) -> np.ndarray:
        """Единицы стата по картам, усреднённые по игрокам роли."""
        per_game = []
        for game in games:
            players = [game.player_stats[a] for a in account_ids if a in game.player_stats]
            if not players:
                per_game.append(0.0)
                continue
            per_game.append(sum(float(p.get(stat_key, 0.0)) for p in players) / len(players))
        return np.array(per_game, dtype=np.float64)

    def _trend(
        self,
        games: Sequence[RoleGame],
        column: np.ndarray,
        *,
        now: datetime | None = None,
    ) -> float | None:
        """Свежая форма относительно предыдущей: отношение средних очков.

        Веса давности сглаживают историю, но не отвечают на вопрос «стало лучше
        или хуже». Здесь сравниваются две непересекающиеся половины окна, и если
        в любой из них меньше трёх карт — сравнивать нечего.
        """
        if len(column) != len(games) or not len(games):
            return None
        now = now or datetime.now(timezone.utc)
        ages = np.array(
            [(now - g.start_time).total_seconds() / 86400.0 for g in games], dtype=np.float64
        )
        recent = column[ages <= TREND_WINDOW_DAYS]
        earlier = column[(ages > TREND_WINDOW_DAYS) & (ages <= TREND_WINDOW_DAYS * 3)]
        if len(recent) < MIN_TREND_GAMES or len(earlier) < MIN_TREND_GAMES:
            return None
        before = float(earlier.mean())
        if before <= 0:
            return None
        return float(recent.mean()) / before

    def player_values(
        self,
        history: RoleHistory,
        *,
        role: str | None = None,
        now: datetime | None = None,
        names: Mapping[int, str] | None = None,
    ) -> list[PlayerProfile]:
        """Те же ценности статов, но по каждому игроку роли отдельно.

        Карты, где игрок не выходил (замена, стенд-ин), в его выборку не идут —
        иначе средние занижаются нулями за чужие игры.
        """
        role = role or history.role
        names = names or dict(zip(history.account_ids, history.player_names, strict=False))

        profiles: list[PlayerProfile] = []
        for account_id in history.account_ids:
            games = [g for g in history.games if account_id in g.player_stats]
            if not games:
                continue
            solo = RoleHistory(
                role=role,
                team_id=history.team_id,
                account_ids=(account_id,),
                games=games,
                team_name=history.team_name,
            )
            base = self.projector.base_matrix(solo)
            weights = self.projector.recency_weights(solo, now=now)
            profiles.append(
                PlayerProfile(
                    account_id=account_id,
                    name=names.get(account_id),
                    games=len(games),
                    values=tuple(
                        self._values_from(
                            solo,
                            base,
                            weights,
                            role=role,
                            now=now,
                            include_unavailable=False,
                            games=games,
                            account_ids=(account_id,),
                        )
                    ),
                )
            )
        return profiles

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

    # --- 3. свои эмблемы -> под кого их ставить -------------------------------

    def inventory_gaps(
        self, inventory: Sequence[Emblem], role: str
    ) -> tuple[str, ...]:
        """Каких цветов не хватает, чтобы вообще заполнить баннер этой роли.

        Зависит только от инвентаря и роли, не от команды: цвета слотов
        фиксированы ролью, и если синих эмблем всего одна, саппорта не собрать
        ни с кем.
        """
        colors = [str(c) for c in self.rules.slot_colors(role)]
        need: dict[str, int] = {}
        for color in colors:
            need[color] = need.get(color, 0) + 1

        have: dict[str, int] = {}
        for emblem in inventory:
            rule = self.rules.stats.get(emblem.stat)
            if rule is None:
                continue
            have[str(rule.color)] = have.get(str(rule.color), 0) + 1

        return tuple(
            f"{color}: нужно {count}, есть {have.get(color, 0)}"
            for color, count in need.items()
            if have.get(color, 0) < count
        )

    def fit_inventory(
        self,
        history: RoleHistory,
        inventory: Sequence[Emblem],
        *,
        role: str | None = None,
        now: datetime | None = None,
        values: Mapping[str, StatValue] | None = None,
    ) -> InventoryFit:
        """Разложить имеющиеся эмблемы по слотам роли наилучшим образом.

        Обратная задача к `optimise_banner`: там перебирались все эмблемы, какие
        бывают, здесь — только те, что у игрока уже есть. Качества и трейты
        заданы, менять нечего, но остаётся выбор, какие три эмблемы поставить и
        в каком порядке: Benevolent и Vampiric действуют на соседей, поэтому
        порядок решает.

        Перебор ограничен цветом: в красный слот кандидатами идут только красные
        эмблемы инвентаря. Это превращает сотни тысяч перестановок в десятки.

        Статы, которых нет в данных OpenDota (Madstone, Watchers), оцениваются в
        ноль очков: в игре они считаются, у нас их измерить нечем. Такая эмблема
        встанет на баннер только если ставить больше нечего.
        """
        role = role or history.role
        colors = [str(c) for c in self.rules.slot_colors(role)]
        gaps = self.inventory_gaps(inventory, role)
        if gaps:
            raise ValueError(f"инвентаря не хватает на роль {role}: {'; '.join(gaps)}")

        if values is None:
            values = {v.stat: v for v in self.stat_values(history, role=role, now=now)}

        # Индексы инвентаря по цвету слота: перебираем только подходящее.
        by_slot: list[list[int]] = []
        for color in colors:
            by_slot.append(
                [
                    i
                    for i, e in enumerate(inventory)
                    if e.stat in self.rules.stats
                    and str(self.rules.stats[e.stat].color) == color
                ]
            )

        allow_duplicates = self.rules.banner.allow_duplicate_stats
        best_total = -np.inf
        best_indices: tuple[int, ...] = ()

        def walk(slot: int, chosen: list[int]) -> None:
            nonlocal best_total, best_indices
            if slot == len(colors):
                emblems = tuple(inventory[i] for i in chosen)
                banner = Banner(emblems=emblems, role=role)
                multipliers = self.scorer.emblem_multipliers(banner)
                total = sum(
                    values[e.stat].base_points * m
                    for e, m in zip(emblems, multipliers, strict=True)
                    if e.stat in values
                )
                if total > best_total:
                    best_total = total
                    best_indices = tuple(chosen)
                return
            for index in by_slot[slot]:
                if index in chosen:
                    continue  # одна эмблема — один слот
                if not allow_duplicates and any(
                    inventory[index].stat == inventory[c].stat for c in chosen
                ):
                    continue
                chosen.append(index)
                walk(slot + 1, chosen)
                chosen.pop()

        walk(0, [])
        if not best_indices:
            raise ValueError(
                f"из инвентаря не собрать баннер роли {role}: не хватает разных статов"
            )

        used = tuple(inventory[i] for i in best_indices)
        banner = Banner(emblems=used, role=role)
        multipliers = self.scorer.emblem_multipliers(banner)
        slots = tuple(
            SlotAdvice(
                slot=index,
                color=colors[index],
                emblem=emblem,
                percent=multiplier * 100.0,
                base_points=values[emblem.stat].base_points if emblem.stat in values else 0.0,
                points=(values[emblem.stat].base_points if emblem.stat in values else 0.0)
                * multiplier,
            )
            for index, (emblem, multiplier) in enumerate(
                zip(used, multipliers, strict=True)
            )
        )

        return InventoryFit(
            role=role,
            team_id=history.team_id,
            team_name=history.team_name,
            player_names=history.player_names,
            slots=slots,
            expected_card_points=float(best_total),
            used=used,
            unused=tuple(e for i, e in enumerate(inventory) if i not in best_indices),
            games=len(history.games),
        )

    def rank_inventory(
        self,
        inventory: Sequence[Emblem],
        histories: Iterable[RoleHistory],
        *,
        now: datetime | None = None,
        min_games: int = 5,
    ) -> list[InventoryFit]:
        """Кому из участников TI15 эти эмблемы принесут больше всего очков.

        Оценки сжимаются к среднему по роли: здесь берётся максимум по всем
        кандидатам, а он достаётся не сильнейшему, а самому шумному, если не
        поправить на размер выборки. Подробности — в app/fantasy/shrinkage.py.
        """
        from .shrinkage import shrink_to_role_mean  # noqa: PLC0415

        eligible = [
            history
            for history in histories
            if len(history.games) >= min_games
            and not self.inventory_gaps(inventory, history.role)
        ]
        adjusted = shrink_to_role_mean(
            [
                (history.role, self.stat_values(history, role=history.role, now=now))
                for history in eligible
            ]
        )

        fits = [
            self.fit_inventory(
                history, inventory, now=now, values={v.stat: v for v in values}
            )
            for history, values in zip(eligible, adjusted, strict=True)
        ]
        fits.sort(key=lambda f: -f.expected_card_points)
        return fits

    # --- 4. кто лучше под стат ------------------------------------------------

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
                    units_per_game=float(
                        weights @ self._unit_series(history.games, history.account_ids, stat)
                    ),
                    base_points=float(weights @ column),
                    p95_points=float(np.percentile(column, 95)),
                    games=len(history.games),
                )
            )

        rows.sort(key=lambda r: -r.base_points)
        return rows

    # --- Coaching Titles ------------------------------------------------------

    def title_advice(
        self,
        history: RoleHistory,
        *,
        heroes: Mapping[int, str] | None = None,
        account_ids: Sequence[int] | None = None,
    ) -> list[TitleAdvice]:
        """Какие титулы выгодны этой роли — по её же матчам.

        Часть условий из данных не проверить (смерть от Торментора, килл в
        фонтане) — такие титулы возвращаются без оценки и помечены, а не
        оцениваются наугад.
        """
        games = history.games
        accounts = tuple(account_ids) if account_ids else history.account_ids
        estimates = self._suffix_estimates(games)
        estimates.update(self._prefix_estimates(games, accounts, heroes))

        advice: list[TitleAdvice] = []
        for group in ("prefixes", "suffixes"):
            for title in self.rules.titles.get(group, []) or []:
                key = title["key"]
                bonus = float(title["bonus"])
                estimator = title.get("estimator", "unmodelled")
                estimate = estimates.get(key)
                hit_rate = estimate.hit_rate if estimate else None
                note = estimate.note if estimate else ""
                note_key = estimate.note_key if estimate else ""
                params = dict(estimate.params) if estimate else {}

                if estimator == "hero_pool" and hit_rate is None:
                    note = note or "нет справочника героев — выполните `cli.py ingest-heroes`"
                    note_key = note_key or "title.note.noHeroes"
                elif estimator == "unmodelled" and not note:
                    # Почему именно не оценивается — сказано в конфиге рядом с
                    # титулом: причина у каждого своя, и она важнее самого факта.
                    # Ключ перевода собирается по титулу: у каждой причины свой
                    # текст, общего шаблона тут нет.
                    note = title.get("note") or "условие вне наших данных"
                    note_key = f"title.note.{key}" if title.get("note") else "title.note.outside"
                elif hit_rate is None:
                    note = note or "недостаточно данных"
                    note_key = note_key or "title.note.notEnough"

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
                        note_key=note_key,
                        note_params=params,
                    )
                )

        # Сначала то, что реально посчитано, по убыванию ожидаемого вклада.
        advice.sort(key=lambda t: (t.expected_bonus is None, -(t.expected_bonus or 0.0)))
        return advice

    def _suffix_estimates(self, games: Sequence[RoleGame]) -> dict[str, Estimate]:
        """Суффиксы, которые видно в данных матча."""
        estimates: dict[str, Estimate] = {}

        durations = [g.duration for g in games if g.duration]
        if durations:
            short = sum(1 for d in durations if d < 25 * 60) / len(durations)
            estimates["decisive"] = Estimate(
                short,
                f"{short:.0%} игр короче 25 минут",
                "title.note.short",
                {"pct": round(short * 100)},
            )
            # «the Lucky» — последняя цифра длительности. На табло время идёт как
            # мм:сс, так что речь про последнюю цифру секунд: чистая лотерея
            # около 10%, и это само по себе ответ — титул не подкрутить.
            lucky = sum(1 for d in durations if d % 10 == 8) / len(durations)
            estimates["lucky"] = Estimate(
                lucky,
                f"{lucky:.0%} игр закончились на цифру 8",
                "title.note.lucky",
                {"pct": round(lucky * 100)},
            )

        losses = [g.won for g in games if g.won is not None]
        if losses:
            lost = sum(1 for won in losses if not won) / len(losses)
            estimates["underdog"] = Estimate(
                lost,
                f"{lost:.0%} игр проиграно",
                "title.note.lost",
                {"pct": round(lost * 100)},
            )

        # Время первой крови: ноль OpenDota ставит и когда события не поймала,
        # поэтому такие карты из выборки выбрасываем, а не считаем «до гонга».
        first_bloods = [g.first_blood_time for g in games if g.first_blood_time]
        if first_bloods:
            patient = sum(1 for t in first_bloods if t >= 600) / len(first_bloods)
            estimates["patient"] = Estimate(
                patient,
                f"{patient:.0%} игр без первой крови до 10:00 "
                f"(по {len(first_bloods)} картам из {len(games)})",
                "title.note.patient",
                {
                    "pct": round(patient * 100),
                    "sample": len(first_bloods),
                    "total": len(games),
                },
            )

        deciders = self._decider_share(games)
        if deciders is not None:
            estimates["clutch"] = Estimate(
                deciders,
                f"{deciders:.0%} карт были последними возможными в серии",
                "title.note.decider",
                {"pct": round(deciders * 100)},
            )

        return estimates

    def _decider_share(self, games: Sequence[RoleGame]) -> float | None:
        """Доля карт, которые были решающими в своей серии.

        Решающая — последняя возможная: третья в Bo3 и пятая в Bo5. Формат серии
        в данных не записан, но выводится из числа сыгранных карт: серия из трёх
        карт могла быть только Bo3, дошедшим до конца.
        """
        if not games:
            return None
        by_series: dict[str, list[RoleGame]] = {}
        for game in games:
            by_series.setdefault(game.series_key, []).append(game)

        deciders = 0
        for series in by_series.values():
            if len(series) not in (3, 5):
                continue
            last = max(series, key=lambda g: g.start_time)
            deciders += 1 if last in series else 0
        return deciders / len(games)

    def _prefix_estimates(
        self,
        games: Sequence[RoleGame],
        accounts: Sequence[int],
        heroes: Mapping[int, str] | None,
    ) -> dict[str, Estimate]:
        """Префиксы: доля карт, сыгранных на герое из списка титула.

        Считается по выборам конкретных игроков роли, а не по всем десяти в
        матче: титул привязан к карточке игрока.
        """
        if not heroes:
            return {}

        picks = [
            heroes.get(game.heroes[account])
            for game in games
            for account in accounts
            if account in game.heroes
        ]
        picks = [name for name in picks if name]
        if not picks:
            return {}

        estimates: dict[str, Estimate] = {}
        for title in self.rules.titles.get("prefixes", []) or []:
            listed = {str(name) for name in (title.get("heroes") or [])}
            if not listed:
                continue
            hits = sum(1 for name in picks if name in listed)
            share = hits / len(picks)
            estimates[title["key"]] = Estimate(
                share,
                f"{share:.0%} выборов — герои из списка ({hits} из {len(picks)})",
                "title.note.heroShare",
                {"pct": round(share * 100), "hits": hits, "total": len(picks)},
            )
        return estimates

    def hero_pool(
        self,
        history: RoleHistory,
        *,
        heroes: Mapping[int, str] | None = None,
        account_ids: Sequence[int] | None = None,
        limit: int = 15,
    ) -> list[HeroPick]:
        """Кого берёт эта роль: герой, сколько карт, сколько побед, кто играл."""
        accounts = tuple(account_ids) if account_ids else history.account_ids
        heroes = heroes or {}

        games: Counter[int] = Counter()
        wins: Counter[int] = Counter()
        by_player: dict[int, Counter[int]] = {}
        for game in history.games:
            for account in accounts:
                hero_id = game.heroes.get(account)
                if hero_id is None:
                    continue
                games[hero_id] += 1
                wins[hero_id] += int(bool(game.won))
                by_player.setdefault(hero_id, Counter())[account] += 1

        return [
            HeroPick(
                hero_id=hero_id,
                name=heroes.get(hero_id, f"hero {hero_id}"),
                games=count,
                wins=wins[hero_id],
                players=tuple(sorted(by_player[hero_id].items(), key=lambda kv: -kv[1])),
            )
            for hero_id, count in games.most_common(limit)
        ]
