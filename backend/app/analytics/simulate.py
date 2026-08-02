"""Monte-Carlo симуляции группового этапа и плей-офф.

Рейтинг отвечает на вопрос "кто сильнее", а компендиум спрашивает "какой будет
итоговый счёт" и "кто пройдёт сетку". Мост между ними — симуляция: турнир
разыгрывается тысячи раз со случайными исходами, взвешенными вероятностями из
Glicko-2, и на выходе получается распределение, а не одно число.

Отдельно решается задача, которой в исходном плане не было: какие предсказания
проставить, чтобы максимизировать ожидаемые очки. Это не то же самое, что
"расставить самые вероятные исходы" — шкала начисления нелинейная (16 угаданных
дают 12000, а 15 — 10920), поэтому оптимум ищется по ожидаемым очкам напрямую.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

import numpy as np

from .glicko2 import Glicko2, Rating
from .predictions_config import GroupStageConfig, PlayoffConfig, PointsTable

log = logging.getLogger(__name__)

# Корзины Swiss в терминах "итоговая запись -> ключ корзины".
FINAL_RECORD_BUCKETS = {
    (4, 0): "4-0",
    (4, 1): "4-1",
    (1, 4): "1-4",
    (0, 4): "0-4",
}


@dataclass(slots=True)
class SwissResult:
    """Результат одного прогона Swiss."""

    buckets: dict[int, str]
    records: dict[int, tuple[int, int]]
    advanced: list[int]


@dataclass(slots=True)
class GroupSimulation:
    """Итог серии прогонов группового этапа."""

    team_ids: tuple[int, ...]
    bucket_keys: tuple[str, ...]
    # outcomes[sim, team] = индекс корзины
    outcomes: np.ndarray
    # probabilities[team_index, bucket_index]
    probabilities: np.ndarray
    advance_probability: np.ndarray
    simulations: int
    # series_played[sim, team] — сколько серий команда успела сыграть.
    # Нужно модулю Fantasy: в зачёт идёт лучшая серия периода, поэтому команда,
    # играющая шесть серий, даёт игроку больше попыток выбить высокий результат,
    # чем команда, вылетевшая после четырёх.
    series_played: np.ndarray | None = None

    def expected_series(self, team_id: int) -> float:
        if self.series_played is None:
            raise ValueError("симуляция не сохраняла число серий")
        return float(self.series_played[:, self.team_ids.index(team_id)].mean())

    def series_distribution(self, team_id: int) -> dict[int, float]:
        """Распределение числа серий команды — вход для проекции Fantasy."""
        if self.series_played is None:
            raise ValueError("симуляция не сохраняла число серий")
        column = self.series_played[:, self.team_ids.index(team_id)]
        counts = np.bincount(column)
        return {
            int(n): float(c / self.simulations) for n, c in enumerate(counts) if c
        }

    def bucket_probability(self, team_id: int, bucket_key: str) -> float:
        return float(
            self.probabilities[self.team_ids.index(team_id), self.bucket_keys.index(bucket_key)]
        )

    def as_table(self) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        for i, team_id in enumerate(self.team_ids):
            row: dict[str, object] = {"team_id": team_id}
            row |= {
                key: round(float(self.probabilities[i, j]), 4)
                for j, key in enumerate(self.bucket_keys)
            }
            row["advance"] = round(float(self.advance_probability[i]), 4)
            rows.append(row)
        return rows


class SwissSimulator:
    """Симулятор Swiss-этапа: 16 команд, до 4 побед или 4 поражений."""

    def __init__(
        self,
        ratings: Mapping[int, Rating],
        config: GroupStageConfig,
        *,
        engine: Glicko2 | None = None,
        seed: int | None = None,
    ) -> None:
        if len(ratings) != config.teams:
            raise ValueError(
                f"нужно ровно {config.teams} команд с рейтингом, получено {len(ratings)}"
            )
        self.config = config
        self.engine = engine or Glicko2()
        self.rng = np.random.default_rng(seed)
        self.team_ids = tuple(ratings)
        self._index = {team_id: i for i, team_id in enumerate(self.team_ids)}
        self.ratings = dict(ratings)
        # Посев: сильнейший по рейтингу получает seed 0. Внутри группы одинаковых
        # записей пары строятся "верх против низа", как в реальном Swiss.
        self._seed_order = sorted(
            range(len(self.team_ids)),
            key=lambda i: -self.ratings[self.team_ids[i]].rating,
        )
        self._seed_rank = {idx: rank for rank, idx in enumerate(self._seed_order)}
        self._p_regular = self._probability_matrix(config.swiss.regular_best_of)
        self._p_decisive = self._probability_matrix(config.swiss.decisive_best_of)

    def _probability_matrix(self, best_of: int) -> np.ndarray:
        n = len(self.team_ids)
        matrix = np.zeros((n, n), dtype=np.float64)
        for i, team_a in enumerate(self.team_ids):
            for j, team_b in enumerate(self.team_ids):
                if i == j:
                    continue
                matrix[i, j] = self.engine.series_win_probability(
                    self.ratings[team_a], self.ratings[team_b], best_of=best_of
                )
        return matrix

    # --- один прогон ----------------------------------------------------------

    def _pair_round(
        self,
        active: Sequence[int],
        records: Mapping[int, tuple[int, int]],
        played: set[tuple[int, int]],
    ) -> list[tuple[int, int]]:
        """Разбить активные команды на пары.

        Классический Swiss: пары внутри группы с одинаковой записью, верх против
        низа по посеву, повторных встреч избегаем. Нечётный остаток группы
        спускается в следующую (именно так в шестом раунде 3-2 встречается с 2-3).
        """
        groups: dict[tuple[int, int], list[int]] = defaultdict(list)
        for team in active:
            groups[records[team]].append(team)

        pairs: list[tuple[int, int]] = []
        carry: list[int] = []
        # От лучшей записи к худшей.
        for record in sorted(groups, key=lambda r: (-r[0], r[1])):
            pool = carry + sorted(groups[record], key=lambda t: self._seed_rank[t])
            carry = []
            if len(pool) % 2:
                carry = [pool.pop()]  # худший по посеву спускается ниже
            half = len(pool) // 2
            top, bottom = pool[:half], pool[half:][::-1]
            # Повторные встречи в Swiss не допускаются; одной ротации нижней
            # половины хватает почти всегда, а идеальный поиск паросочетания
            # здесь не окупается — на распределение по корзинам он не влияет.
            has_rematch = any(
                (min(a, b), max(a, b)) in played for a, b in zip(top, bottom, strict=True)
            )
            if has_rematch and len(pool) > 2:
                bottom.append(bottom.pop(0))
            for a, b in zip(top, bottom, strict=True):
                pairs.append((a, b))
                played.add((min(a, b), max(a, b)))
        if carry:
            # Нечётное число активных команд — редкий случай, оставшаяся команда
            # пропускает раунд (bye).
            log.debug("bye для команды с индексом %s", carry[0])
        return pairs

    def run_once(self) -> SwissResult:
        cfg = self.config.swiss
        n = len(self.team_ids)
        records: dict[int, tuple[int, int]] = {i: (0, 0) for i in range(n)}
        finished: dict[int, bool] = {}
        last_round_won: dict[int, bool] = {}
        played: set[tuple[int, int]] = set()

        for _ in range(cfg.max_rounds):
            active = [i for i in range(n) if i not in finished]
            if not active:
                break

            for a, b in self._pair_round(active, records, played):
                wins_a, losses_a = records[a]
                wins_b, losses_b = records[b]
                decisive = (
                    max(wins_a, wins_b) == cfg.wins_to_advance - 1
                    or max(losses_a, losses_b) == cfg.losses_to_eliminate - 1
                )
                matrix = self._p_decisive if decisive else self._p_regular
                a_wins = self.rng.random() < matrix[a, b]

                winner, loser = (a, b) if a_wins else (b, a)
                records[winner] = (records[winner][0] + 1, records[winner][1])
                records[loser] = (records[loser][0], records[loser][1] + 1)
                last_round_won[winner] = True
                last_round_won[loser] = False

            for team in list(active):
                wins, losses = records[team]
                if wins >= cfg.wins_to_advance or losses >= cfg.losses_to_eliminate:
                    finished[team] = True

        buckets: dict[int, str] = {}
        advanced: list[int] = []
        for team in range(n):
            wins, losses = records[team]
            bucket = FINAL_RECORD_BUCKETS.get((wins, losses))
            if bucket is None:
                # Судьбу решил последний сыгранный раунд (Elimination Round).
                bucket = "elim_winner" if last_round_won.get(team) else "elim_loser"
            buckets[team] = bucket
            if bucket in ("4-0", "4-1", "elim_winner"):
                advanced.append(team)

        return SwissResult(buckets=buckets, records=records, advanced=advanced)

    # --- серия прогонов -------------------------------------------------------

    def run(self, simulations: int = 20_000) -> GroupSimulation:
        bucket_keys = self.config.bucket_keys()
        bucket_index = {key: i for i, key in enumerate(bucket_keys)}
        n_teams = len(self.team_ids)

        outcomes = np.empty((simulations, n_teams), dtype=np.int8)
        series_played = np.zeros((simulations, n_teams), dtype=np.int8)
        advanced_count = np.zeros(n_teams, dtype=np.int64)

        for sim in range(simulations):
            result = self.run_once()
            for team, bucket in result.buckets.items():
                outcomes[sim, team] = bucket_index[bucket]
            for team, (wins, losses) in result.records.items():
                series_played[sim, team] = wins + losses
            for team in result.advanced:
                advanced_count[team] += 1

        probabilities = np.zeros((n_teams, len(bucket_keys)), dtype=np.float64)
        for j in range(len(bucket_keys)):
            probabilities[:, j] = (outcomes == j).mean(axis=0)

        return GroupSimulation(
            team_ids=self.team_ids,
            bucket_keys=bucket_keys,
            outcomes=outcomes,
            probabilities=probabilities,
            advance_probability=advanced_count / simulations,
            simulations=simulations,
            series_played=series_played,
        )


# --- выбор предсказаний -------------------------------------------------------


@dataclass(slots=True)
class PredictionPlan:
    """Готовый набор предсказаний с оценкой ожидаемых очков.

    `assignment` читается по-разному в двух режимах: для группового этапа это
    `team_id -> ключ корзины`, для сетки — `ключ матча -> team_id`. Формы разные,
    потому что и предсказания разные: в группе распределяем команды по слотам, в
    сетке выбираем победителя матча.
    """

    assignment: dict[object, object]
    expected_points: float
    expected_correct: float
    points_percentiles: dict[int, float]
    points_distribution: np.ndarray = field(repr=False)

    def as_rows(self) -> list[dict[str, object]]:
        return [{"key": key, "pick": pick} for key, pick in self.assignment.items()]


def _points_for(
    outcomes: np.ndarray, assignment: np.ndarray, points_lookup: np.ndarray
) -> np.ndarray:
    correct = (outcomes == assignment[np.newaxis, :]).sum(axis=1)
    return points_lookup[correct]


def optimise_group_predictions(
    simulation: GroupSimulation,
    slots: Mapping[str, int],
    points: PointsTable,
    *,
    max_passes: int = 50,
) -> PredictionPlan:
    """Подобрать расстановку команд по корзинам под максимум ожидаемых очков.

    Старт — жадная расстановка по вероятностям, дальше локальный поиск обменами.
    Обмен двух команд местами меняет ровно два столбца матрицы исходов, поэтому
    прирост считается дельтой и перебор дешёвый.

    Почему не "просто самые вероятные корзины": шкала очков выпуклая, и иногда
    выгоднее поставить менее вероятный, но скоррелированный с остальными исход —
    угадать 12 из 16 разом ценнее, чем стабильно угадывать 9.
    """
    bucket_keys = simulation.bucket_keys
    n_teams = len(simulation.team_ids)
    outcomes = simulation.outcomes
    points_lookup = np.array(points.as_array(n_teams), dtype=np.float64)

    capacity = [int(slots[key]) for key in bucket_keys]
    if sum(capacity) != n_teams:
        raise ValueError(f"слотов {sum(capacity)}, команд {n_teams}")

    # --- жадный старт ---
    assignment = np.full(n_teams, -1, dtype=np.int64)
    remaining = capacity.copy()
    candidates = [
        (-simulation.probabilities[t, b], t, b)
        for t in range(n_teams)
        for b in range(len(bucket_keys))
    ]
    candidates.sort()
    for _, team, bucket in candidates:
        if assignment[team] == -1 and remaining[bucket] > 0:
            assignment[team] = bucket
            remaining[bucket] -= 1
    if (assignment == -1).any():  # страховка: добиваем остатки в свободные слоты
        for team in np.where(assignment == -1)[0]:
            bucket = next(b for b, left in enumerate(remaining) if left > 0)
            assignment[team] = bucket
            remaining[bucket] -= 1

    # --- локальный поиск обменами ---
    best_points = float(_points_for(outcomes, assignment, points_lookup).mean())
    matches = np.equal(outcomes, assignment[np.newaxis, :])
    correct = matches.sum(axis=1)

    for _ in range(max_passes):
        improved = False
        for i in range(n_teams):
            for j in range(i + 1, n_teams):
                bi, bj = assignment[i], assignment[j]
                if bi == bj:
                    continue
                delta = (
                    (outcomes[:, i] == bj).astype(np.int64)
                    + (outcomes[:, j] == bi).astype(np.int64)
                    - matches[:, i]
                    - matches[:, j]
                )
                candidate_points = float(points_lookup[correct + delta].mean())
                if candidate_points > best_points + 1e-9:
                    assignment[i], assignment[j] = bj, bi
                    correct = correct + delta
                    matches[:, i] = outcomes[:, i] == bj
                    matches[:, j] = outcomes[:, j] == bi
                    best_points = candidate_points
                    improved = True
        if not improved:
            break

    distribution = points_lookup[correct]
    percentiles = {
        p: float(np.percentile(distribution, p)) for p in (5, 25, 50, 75, 95)
    }

    return PredictionPlan(
        assignment={
            simulation.team_ids[t]: bucket_keys[int(assignment[t])] for t in range(n_teams)
        },
        expected_points=best_points,
        expected_correct=float(correct.mean()),
        points_percentiles=percentiles,
        points_distribution=distribution,
    )


# --- плей-офф -----------------------------------------------------------------

# Double elimination на 8 команд = 14 матчей, ровно столько предсказаний просит
# компендиум. UB QF -> UB SF -> UB F, параллельно LB, затем гранд-финал.
BRACKET_SLOTS = (
    "ubqf1",
    "ubqf2",
    "ubqf3",
    "ubqf4",
    "ubsf1",
    "ubsf2",
    "ubf",
    "lbr1_1",
    "lbr1_2",
    "lbr2_1",
    "lbr2_2",
    "lbsf",
    "lbf",
    "gf",
)


@dataclass(slots=True)
class BracketSimulation:
    team_ids: tuple[int, ...]
    match_keys: tuple[str, ...]
    # winners[sim, match] = индекс команды-победителя
    winners: np.ndarray
    champion_probability: dict[int, float]
    simulations: int

    def match_probabilities(self, match_key: str) -> dict[int, float]:
        column = self.winners[:, self.match_keys.index(match_key)]
        counts = np.bincount(column, minlength=len(self.team_ids))
        return {
            self.team_ids[i]: float(counts[i] / self.simulations)
            for i in range(len(self.team_ids))
            if counts[i]
        }


class BracketSimulator:
    """Double elimination на 8 команд с посевом по итогам группового этапа."""

    def __init__(
        self,
        ratings: Mapping[int, Rating],
        config: PlayoffConfig,
        *,
        engine: Glicko2 | None = None,
        seed: int | None = None,
    ) -> None:
        if len(ratings) != config.teams:
            raise ValueError(f"нужно {config.teams} команд, получено {len(ratings)}")
        self.config = config
        self.engine = engine or Glicko2()
        self.rng = np.random.default_rng(seed)
        # Порядок = посев: первая команда — лучший результат группы.
        self.team_ids = tuple(ratings)
        self.ratings = dict(ratings)
        self._p = self._probability_matrix(config.best_of)
        self._p_gf = self._probability_matrix(config.grand_final_best_of)

    def _probability_matrix(self, best_of: int) -> np.ndarray:
        n = len(self.team_ids)
        matrix = np.zeros((n, n))
        for i, a in enumerate(self.team_ids):
            for j, b in enumerate(self.team_ids):
                if i != j:
                    matrix[i, j] = self.engine.series_win_probability(
                        self.ratings[a], self.ratings[b], best_of=best_of
                    )
        return matrix

    def _play(self, a: int, b: int, *, grand_final: bool = False) -> tuple[int, int]:
        matrix = self._p_gf if grand_final else self._p
        if self.rng.random() < matrix[a, b]:
            return a, b
        return b, a

    def run_once(self) -> dict[str, int]:
        """Один прогон сетки. Возвращает победителя каждого матча."""
        result: dict[str, int] = {}

        # Верхняя сетка: 1-8, 4-5, 3-6, 2-7 по посеву.
        qf_pairs = ((0, 7), (3, 4), (2, 5), (1, 6))
        qf_winners, qf_losers = [], []
        for idx, (a, b) in enumerate(qf_pairs, start=1):
            winner, loser = self._play(a, b)
            result[f"ubqf{idx}"] = winner
            qf_winners.append(winner)
            qf_losers.append(loser)

        sf1_w, sf1_l = self._play(qf_winners[0], qf_winners[1])
        sf2_w, sf2_l = self._play(qf_winners[2], qf_winners[3])
        result["ubsf1"], result["ubsf2"] = sf1_w, sf2_w

        ubf_w, ubf_l = self._play(sf1_w, sf2_w)
        result["ubf"] = ubf_w

        # Нижняя сетка.
        lb1_w, _ = self._play(qf_losers[0], qf_losers[1])
        lb2_w, _ = self._play(qf_losers[2], qf_losers[3])
        result["lbr1_1"], result["lbr1_2"] = lb1_w, lb2_w

        # Проигравшие полуфиналов встречаются с победителями из противоположной части.
        lb3_w, _ = self._play(lb1_w, sf2_l)
        lb4_w, _ = self._play(lb2_w, sf1_l)
        result["lbr2_1"], result["lbr2_2"] = lb3_w, lb4_w

        lbsf_w, _ = self._play(lb3_w, lb4_w)
        result["lbsf"] = lbsf_w

        lbf_w, _ = self._play(lbsf_w, ubf_l)
        result["lbf"] = lbf_w

        champion, _ = self._play(ubf_w, lbf_w, grand_final=True)
        result["gf"] = champion
        return result

    def run(self, simulations: int = 20_000) -> BracketSimulation:
        winners = np.empty((simulations, len(BRACKET_SLOTS)), dtype=np.int16)
        for sim in range(simulations):
            outcome = self.run_once()
            for j, key in enumerate(BRACKET_SLOTS):
                winners[sim, j] = outcome[key]

        champion_column = winners[:, BRACKET_SLOTS.index("gf")]
        counts = np.bincount(champion_column, minlength=len(self.team_ids))
        return BracketSimulation(
            team_ids=self.team_ids,
            match_keys=BRACKET_SLOTS,
            winners=winners,
            champion_probability={
                self.team_ids[i]: float(counts[i] / simulations)
                for i in range(len(self.team_ids))
            },
            simulations=simulations,
        )


def optimise_bracket_predictions(
    simulation: BracketSimulation, points: PointsTable
) -> PredictionPlan:
    """Выбрать победителя каждого матча сетки.

    В отличие от группового этапа здесь нет ограничения по слотам: для каждого
    матча независимо берётся команда с максимальной вероятностью пройти. Это и
    есть оптимум по числу угаданных — а поскольку шкала очков монотонна по этому
    числу, он же максимизирует ожидаемые очки.
    """
    n_matches = len(simulation.match_keys)
    points_lookup = np.array(points.as_array(n_matches), dtype=np.float64)

    picks = np.empty(n_matches, dtype=np.int64)
    for j in range(n_matches):
        counts = np.bincount(simulation.winners[:, j], minlength=len(simulation.team_ids))
        picks[j] = int(counts.argmax())

    correct = (simulation.winners == picks[np.newaxis, :]).sum(axis=1)
    distribution = points_lookup[correct]

    return PredictionPlan(
        assignment={
            key: simulation.team_ids[int(picks[j])]
            for j, key in enumerate(simulation.match_keys)
        },
        expected_points=float(distribution.mean()),
        expected_correct=float(correct.mean()),
        points_percentiles={
            p: float(np.percentile(distribution, p)) for p in (5, 25, 50, 75, 95)
        },
        points_distribution=distribution,
    )
