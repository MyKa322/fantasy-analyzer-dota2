"""Проекция Fantasy-очков: сколько наберёт роль за период.

Почему нельзя обойтись средним. В зачёт идёт сумма двух лучших карт лучшей
серии периода — то есть максимум из нескольких попыток. Средний перформанс тут
систематически врёт: игрок со стабильными 8k за карту и игрок, у которого разброс
4k-14k, имеют одинаковое среднее, но второй почти всегда выигрывает у первого по
"лучшей серии". Поэтому моделируется распределение целиком, а не точка.

Как моделируется. Ресэмплинг реальных карт (bootstrap), а не параметрические
распределения по каждому стату отдельно. Причина простая: статы внутри карты
сильно скоррелированы — в разгромной игре у игрока одновременно высокие GPM,
килы и участие в файтах. Если сэмплировать каждый стат независимо, хвосты
распределения (а именно они и решают) разрушатся.

Карта сэмплируется целиком и сразу для обоих игроков роли — по той же причине:
в реальной игре core duo выступает вместе, и их результаты коррелируют.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from itertools import combinations, permutations

import numpy as np

from .rules import FantasyRules
from .scoring import Banner, Emblem, FantasyScorer

log = logging.getLogger(__name__)

# По умолчанию: серия Bo3, где 2 и 3 карты примерно равновероятны.
DEFAULT_SERIES_LENGTHS = {2: 0.5, 3: 0.5}

# Период полураспада веса матча: результат месячной давности весит вдвое меньше
# вчерашнего. Компромисс между "меты уже нет" и "выборка слишком мала".
DEFAULT_HALF_LIFE_DAYS = 30.0


@dataclass(frozen=True, slots=True)
class RoleGame:
    """Одна карта в истории роли: статы всех игроков роли в этой игре."""

    match_id: int
    start_time: datetime
    series_key: str
    player_stats: Mapping[int, Mapping[str, float]]
    patch: int | None = None
    is_lan: bool | None = None
    # Нужны для оценки Coaching Titles: "the Decisive" смотрит на длительность,
    # "the Underdog" — на поражение, "the Patient" — на время первой крови, а
    # префиксы вроде "Crimson" — на то, за кого играли.
    duration: int | None = None
    won: bool | None = None
    first_blood_time: int | None = None
    heroes: Mapping[int, int] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Substitution:
    """Замена в составе: пришедшему игроку нечего показать, взяли историю слота.

    Возникает перед турниром, когда команда меняет игрока и своих карт на этом
    уровне у новичка в выборке нет. Прогноз считается по картам заменённого —
    очки роли во многом заданы тем, как играет команда, — но выдавать их за
    статистику пришедшего нельзя, и эта пара имён едет до самой страницы.
    """

    account_id: int
    name: str
    replaced_account_id: int
    replaced_name: str


@dataclass(slots=True)
class RoleHistory:
    """История конкретной пары/игрока в роли."""

    role: str
    team_id: int
    # Чьи карты в выборке. При замене здесь заменённый игрок, а не пришедший:
    # по этим id проекция достаёт статы из RoleGame.player_stats.
    account_ids: tuple[int, ...]
    games: list[RoleGame] = field(default_factory=list)
    team_name: str | None = None
    player_names: tuple[str, ...] = ()
    substitutions: tuple[Substitution, ...] = ()

    def __len__(self) -> int:
        return len(self.games)

    @property
    def roster_names(self) -> tuple[str, ...]:
        """Кто выйдет играть — для подписи роли, в отличие от player_names."""
        swap = {s.replaced_name: s.name for s in self.substitutions}
        return tuple(swap.get(name, name) for name in self.player_names)


@dataclass(slots=True)
class Projection:
    """Распределение очков роли за период."""

    role: str
    team_id: int
    banner: Banner
    mean: float
    median: float
    std: float
    percentiles: dict[int, float]
    samples: np.ndarray = field(repr=False)
    games_used: int = 0
    unavailable_stats: tuple[str, ...] = ()
    expected_series: float = 0.0

    @property
    def ceiling(self) -> float:
        """95-й перцентиль — то, ради чего в Fantasy берут нестабильных игроков."""
        return self.percentiles.get(95, self.mean)

    @property
    def floor(self) -> float:
        return self.percentiles.get(5, self.mean)

    def summary(self) -> dict[str, object]:
        return {
            "role": self.role,
            "team_id": self.team_id,
            "mean": round(self.mean, 1),
            "median": round(self.median, 1),
            "floor_p5": round(self.floor, 1),
            "ceiling_p95": round(self.ceiling, 1),
            "std": round(self.std, 1),
            "games_used": self.games_used,
            "expected_series": round(self.expected_series, 2),
            "unavailable_stats": list(self.unavailable_stats),
        }


class RoleProjector:
    """Симулятор очков роли за период компендиума."""

    def __init__(
        self,
        scorer: FantasyScorer | None = None,
        *,
        half_life_days: float = DEFAULT_HALF_LIFE_DAYS,
        seed: int | None = None,
    ) -> None:
        self.scorer = scorer or FantasyScorer()
        self.rules: FantasyRules = self.scorer.rules
        self.half_life_days = half_life_days
        self.rng = np.random.default_rng(seed)
        self.stat_keys = tuple(self.rules.stats)
        self._stat_index = {key: i for i, key in enumerate(self.stat_keys)}

    # --- подготовка выборки ---------------------------------------------------

    def base_matrix(self, history: RoleHistory) -> np.ndarray:
        """Матрица (карты × статы) базовых очков, усреднённых по игрокам роли.

        Усреднение по игрокам можно делать до применения множителей эмблем:
        счёт линеен по базовым очкам, поэтому среднее от счетов равно счёту от
        средних. Это экономит порядок по времени при переборе баннеров.
        """
        matrix = np.zeros((len(history.games), len(self.stat_keys)), dtype=np.float64)
        for row, game in enumerate(history.games):
            players = [
                game.player_stats[a] for a in history.account_ids if a in game.player_stats
            ]
            if not players:
                continue
            for stat_key, index in self._stat_index.items():
                rule = self.rules.stats[stat_key]
                values = [rule.points(float(p.get(stat_key, 0.0))) for p in players]
                matrix[row, index] = sum(values) / len(values)
        return matrix

    def recency_weights(
        self, history: RoleHistory, *, now: datetime | None = None
    ) -> np.ndarray:
        """Веса карт: свежие важнее. Экспоненциальное затухание по времени."""
        if not history.games:
            return np.zeros(0)
        now = now or datetime.now(timezone.utc)
        ages = np.array(
            [max((now - g.start_time).total_seconds() / 86400.0, 0.0) for g in history.games]
        )
        weights = np.exp(-np.log(2.0) * ages / self.half_life_days)
        total = weights.sum()
        if total <= 0:
            return np.full(len(history.games), 1.0 / len(history.games))
        return weights / total

    # --- симуляция ------------------------------------------------------------

    def _sample_scores(
        self,
        base: np.ndarray,
        weights: np.ndarray,
        multiplier_vector: np.ndarray,
        *,
        simulations: int,
        max_series: int,
        max_cards: int,
    ) -> np.ndarray:
        """Счёт каждой карты каждой серии: (simulations, max_series, max_cards)."""
        total = simulations * max_series * max_cards
        indices = self.rng.choice(len(base), size=total, p=weights)
        card_scores = base[indices] @ multiplier_vector
        return card_scores.reshape(simulations, max_series, max_cards)

    def project(
        self,
        history: RoleHistory,
        banner: Banner,
        *,
        series_distribution: Mapping[int, float] | None = None,
        series_lengths: Mapping[int, float] | None = None,
        simulations: int = 4000,
        title_multiplier: float = 1.0,
        now: datetime | None = None,
    ) -> Projection:
        """Оценить распределение очков роли за период.

        `series_distribution` — сколько серий команда сыграет за период (можно
        взять прямо из симуляции группового этапа: чем дальше команда проходит,
        тем больше у неё попыток выбить высокую серию).
        """
        from ..ingest.stat_mapping import missing_stats

        banner.validate(self.rules)
        if not history.games:
            raise ValueError(f"пустая история роли {history.role} команды {history.team_id}")

        series_distribution = series_distribution or {5: 1.0}
        series_lengths = series_lengths or DEFAULT_SERIES_LENGTHS

        base = self.base_matrix(history)
        weights = self.recency_weights(history, now=now)

        multipliers = self.scorer.emblem_multipliers(banner)
        multiplier_vector = np.zeros(len(self.stat_keys))
        for emblem, multiplier in zip(banner.emblems, multipliers, strict=True):
            multiplier_vector[self._stat_index[emblem.stat]] = multiplier * title_multiplier

        series_counts = np.array(sorted(series_distribution), dtype=np.int64)
        series_probs = np.array(
            [series_distribution[int(c)] for c in series_counts], dtype=np.float64
        )
        series_probs = series_probs / series_probs.sum()
        max_series = int(series_counts.max())

        length_values = np.array(sorted(series_lengths), dtype=np.int64)
        length_probs = np.array(
            [series_lengths[int(v)] for v in length_values], dtype=np.float64
        )
        length_probs = length_probs / length_probs.sum()
        max_cards = int(length_values.max())

        card_scores = self._sample_scores(
            base,
            weights,
            multiplier_vector,
            simulations=simulations,
            max_series=max_series,
            max_cards=max_cards,
        )

        # Сколько серий сыграно и какой длины — маскируем лишнее.
        n_series = self.rng.choice(series_counts, size=simulations, p=series_probs)
        n_cards = self.rng.choice(
            length_values, size=(simulations, max_series), p=length_probs
        )

        card_index = np.arange(max_cards)[np.newaxis, np.newaxis, :]
        card_mask = card_index < n_cards[:, :, np.newaxis]
        masked_cards = np.where(card_mask, card_scores, -np.inf)

        # Топ-2 карты серии (games_per_series из конфига).
        take = min(self.rules.scoring.games_per_series, max_cards)
        top_cards = np.sort(masked_cards, axis=2)[:, :, -take:]
        series_scores = np.where(np.isfinite(top_cards), top_cards, 0.0).sum(axis=2)

        series_index = np.arange(max_series)[np.newaxis, :]
        series_mask = series_index < n_series[:, np.newaxis]
        masked_series = np.where(series_mask, series_scores, -np.inf)

        # Лучшая серия периода.
        period_scores = masked_series.max(axis=1)
        period_scores = np.where(np.isfinite(period_scores), period_scores, 0.0)

        return Projection(
            role=history.role,
            team_id=history.team_id,
            banner=banner,
            mean=float(period_scores.mean()),
            median=float(np.median(period_scores)),
            std=float(period_scores.std()),
            percentiles={
                p: float(np.percentile(period_scores, p)) for p in (5, 25, 50, 75, 95)
            },
            samples=period_scores,
            games_used=len(history.games),
            unavailable_stats=tuple(missing_stats(banner.stats())),
            expected_series=float((series_counts * series_probs).sum()),
        )

    # --- быстрая линейная оценка ----------------------------------------------

    def expected_card_score(
        self, history: RoleHistory, banner: Banner, *, now: datetime | None = None
    ) -> float:
        """Ожидаемые очки за одну карту — дешёвая оценка для отсева вариантов.

        Не учитывает правила "топ-2 карты" и "лучшая серия", поэтому годится для
        ранжирования кандидатов, но не для финальной цифры.
        """
        base = self.base_matrix(history)
        weights = self.recency_weights(history, now=now)
        mean_base = weights @ base
        multipliers = self.scorer.emblem_multipliers(banner)
        return float(
            sum(
                multiplier * mean_base[self._stat_index[emblem.stat]]
                for emblem, multiplier in zip(banner.emblems, multipliers, strict=True)
            )
        )


# --- подбор баннера -----------------------------------------------------------


@dataclass(slots=True)
class BannerOption:
    banner: Banner
    projection: Projection

    @property
    def score(self) -> float:
        return self.projection.mean


def optimise_banner(
    projector: RoleProjector,
    history: RoleHistory,
    available_emblems: Sequence[Emblem],
    *,
    slots: int | None = None,
    shortlist: int = 40,
    simulations: int = 2000,
    top_n: int = 5,
    **project_kwargs: object,
) -> list[BannerOption]:
    """Найти лучшую раскладку эмблем по баннеру.

    Порядок эмблем имеет значение: Benevolent и Vampiric действуют на соседей,
    поэтому перебираются и сочетания, и перестановки. Полный перебор с симуляцией
    дорогой, поэтому сначала все варианты ранжируются линейной оценкой
    `expected_card_score`, а симуляция считается только для шортлиста.
    """
    slots = slots or projector.rules.banner.slots
    if len(available_emblems) < slots:
        raise ValueError(
            f"нужно минимум {slots} эмблем, передано {len(available_emblems)}"
        )

    allow_duplicates = projector.rules.banner.allow_duplicate_stats
    candidates: list[tuple[float, Banner]] = []
    seen: set[tuple[tuple[str, str, str | None], ...]] = set()

    for combo in combinations(range(len(available_emblems)), slots):
        emblems = [available_emblems[i] for i in combo]
        if not allow_duplicates:
            stats = [e.stat for e in emblems]
            if len(set(stats)) != len(stats):
                continue
        for order in permutations(emblems):
            key = tuple((e.stat, e.quality, e.trait) for e in order)
            # Отражение баннера даёт те же соседства — считаем один раз.
            if key[::-1] in seen:
                continue
            seen.add(key)
            banner = Banner(emblems=tuple(order), role=history.role)
            candidates.append((projector.expected_card_score(history, banner), banner))

    candidates.sort(key=lambda item: -item[0])
    log.info("подбор баннера: %d вариантов, симулируем %d", len(candidates), shortlist)

    options: list[BannerOption] = []
    for _, banner in candidates[:shortlist]:
        projection = projector.project(
            history, banner, simulations=simulations, **project_kwargs
        )
        options.append(BannerOption(banner=banner, projection=projection))

    options.sort(key=lambda option: -option.score)
    return options[:top_n]


# --- подбор ростера -----------------------------------------------------------


@dataclass(slots=True)
class RosterPick:
    role: str
    team_id: int
    projection: Projection


@dataclass(slots=True)
class Roster:
    picks: tuple[RosterPick, ...]
    expected_total: float
    combined_samples: np.ndarray = field(repr=False)

    def summary(self) -> dict[str, object]:
        return {
            "expected_total": round(self.expected_total, 1),
            "p5": round(float(np.percentile(self.combined_samples, 5)), 1),
            "p95": round(float(np.percentile(self.combined_samples, 95)), 1),
            "picks": [
                {"role": p.role, "team_id": p.team_id, "mean": round(p.projection.mean, 1)}
                for p in self.picks
            ],
        }


def recommend_roster(
    projections: Mapping[str, Mapping[int, Projection]],
    *,
    distinct_teams: bool = False,
    top_n: int = 5,
) -> list[Roster]:
    """Собрать лучшие ростеры из проекций по ролям.

    `projections[role][team_id]`. Слоты независимы: компендиум разрешает брать
    core, mid и support из одного состава — на экране Fantasy мид и пара
    саппортов стоят от одной команды. Раньше здесь стояло обратное ограничение,
    и оно вычёркивало варианты, которые в игре собираются свободно.

    `distinct_teams` оставлен для случая, когда сочетание из трёх разных команд
    нужно именно как отдельный вопрос: очки ролей одной команды приходят из
    одних и тех же серий, и разброс у такого состава выше.
    """
    roles = list(projections)
    if not roles:
        return []

    results: list[Roster] = []

    def walk(index: int, used: set[int], chosen: list[RosterPick]) -> None:
        if index == len(roles):
            samples = [p.projection.samples for p in chosen]
            length = min(len(s) for s in samples)
            combined = np.sum([s[:length] for s in samples], axis=0)
            results.append(
                Roster(
                    picks=tuple(chosen),
                    expected_total=float(sum(p.projection.mean for p in chosen)),
                    combined_samples=combined,
                )
            )
            return
        role = roles[index]
        for team_id, projection in projections[role].items():
            if distinct_teams and team_id in used:
                continue
            chosen.append(RosterPick(role=role, team_id=team_id, projection=projection))
            walk(index + 1, used | {team_id}, chosen)
            chosen.pop()

    walk(0, set(), [])
    results.sort(key=lambda r: -r.expected_total)
    return results[:top_n]
