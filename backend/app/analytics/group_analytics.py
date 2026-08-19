"""Аналитика группового этапа поверх сетки.

`group_stage.py` отвечает на вопрос «что произошло»: кто с кем сыграл и с каким
счётом. Этот модуль отвечает на «что это значит».

Ключевая величина здесь — разница между фактическими победами и ожидаемыми.
Запись 3-1 сама по себе не говорит ничего: она может быть провалом фаворита,
прошедшего лёгкую сетку, и может быть выдающимся результатом аутсайдера. Поэтому
для каждой сыгранной серии считается вероятность победы по рейтингам на момент
ДО турнира, эти вероятности складываются в ожидаемое число побед, и уже разрыв с
фактом показывает, кто действительно играет выше своего уровня.

Рейтинги берутся один раз, предтурнирные, и не пересчитываются по ходу этапа. Это
осознанно: если обновлять рейтинг после каждого раунда, команда, выигравшая три
серии подряд, получит настолько высокие ожидания, что её же победы начнут
выглядеть рядовыми, и метрика перестанет измерять то, ради чего заведена.

До старта турнира считать нечего, но и молчать незачем: тогда модуль показывает
разбор объявленного первого раунда — кто фаворит в каждой паре и насколько.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db.models import Match, MatchFeature
from .glicko2 import Glicko2, Rating
from .group_stage import GroupStage, Series

# Формат серий в Swiss: обычные раунды Bo1, решающие Bo3. Значения приходят из
# конфига турнира, здесь только запасные — на случай вызова без него.
DEFAULT_REGULAR_BEST_OF = 1
DEFAULT_DECISIVE_BEST_OF = 3


@dataclass(frozen=True, slots=True)
class Matchup:
    """Пара первого раунда с оценкой шансов."""

    left_id: int
    right_id: int
    left: str
    right: str
    left_win_probability: float | None
    rating_gap: float | None

    @property
    def is_toss_up(self) -> bool:
        """Пара, где рейтинги почти не расходятся."""
        return self.rating_gap is not None and abs(self.rating_gap) < 50.0


@dataclass(slots=True)
class TeamStage:
    """Что команда показала на групповом этапе — и чего от неё ждали."""

    team_id: int
    name: str
    wins: int = 0
    losses: int = 0
    maps_won: int = 0
    maps_lost: int = 0
    rating: float | None = None
    rd: float | None = None
    # Ожидаемые победы: сумма вероятностей выиграть каждую сыгранную серию.
    expected_wins: float | None = None
    # Средний рейтинг соперников, с которыми команда уже сыграла.
    opponent_rating: float | None = None
    # Текущая серия: +n подряд выигранных, -n подряд проигранных.
    streak: int = 0
    status: str = "alive"
    # Из витрины фич — по картам этапа, а не по всей истории.
    avg_duration_min: float | None = None
    avg_kill_diff: float | None = None
    upsets_won: int = 0
    upsets_lost: int = 0

    @property
    def record(self) -> str:
        return f"{self.wins}-{self.losses}"

    @property
    def map_diff(self) -> int:
        return self.maps_won - self.maps_lost

    @property
    def performance(self) -> float | None:
        """Победы сверх ожидаемых. Положительное — играет выше своего рейтинга."""
        if self.expected_wins is None:
            return None
        return self.wins - self.expected_wins

    @property
    def series_played(self) -> int:
        return self.wins + self.losses


@dataclass(frozen=True, slots=True)
class RoundStage:
    """Сводка по одному раунду."""

    round: int
    series: int
    decided: int
    upsets: int
    maps: int

    @property
    def upset_rate(self) -> float | None:
        return self.upsets / self.decided if self.decided else None


@dataclass(slots=True)
class GroupAnalytics:
    started: bool = False
    teams: list[TeamStage] = field(default_factory=list)
    rounds: list[RoundStage] = field(default_factory=list)
    matchups: list[Matchup] = field(default_factory=list)

    @property
    def series_played(self) -> int:
        return sum(r.series for r in self.rounds)

    @property
    def upsets(self) -> int:
        return sum(r.upsets for r in self.rounds)

    def leaders(self, limit: int = 3) -> list[TeamStage]:
        """Кто сильнее всех превзошёл ожидания."""
        scored = [t for t in self.teams if t.performance is not None and t.series_played]
        return sorted(scored, key=lambda t: -(t.performance or 0.0))[:limit]


def _rating(ratings: dict[int, tuple[float, float, float]], team_id: int) -> Rating | None:
    entry = ratings.get(team_id)
    if entry is None:
        return None
    return Rating(rating=entry[0], rd=entry[1], volatility=entry[2])


def _best_of(series: Series, *, regular: int, decisive: int) -> int:
    """Сколько карт в серии.

    Определяется по сыгранному, а не по номеру раунда: в Bo1 карта одна, в Bo3 их
    две или три. Число карт — самый прямой признак, и он не зависит от того,
    угадан ли формат в конфиге.
    """
    maps = series.left.score + series.right.score
    if maps >= 2:
        return decisive
    return regular


def _stage_map_features(
    session: Session, match_ids: set[int]
) -> dict[int, list[tuple[float | None, float | None, bool]]]:
    """Фичи карт этапа, разложенные по командам.

    Возвращает для каждой команды список (длительность, разница убийств в её
    пользу, была ли она на Radiant). Разница убийств в фичах со знаком в сторону
    Radiant, поэтому для Dire её надо перевернуть — иначе половина таблицы
    окажется с обратным знаком.
    """
    if not match_ids:
        return {}

    rows = session.execute(
        select(Match.match_id, Match.radiant_team_id, Match.dire_team_id, MatchFeature.features)
        .join(MatchFeature, MatchFeature.match_id == Match.match_id)
        .where(Match.match_id.in_(match_ids))
    )

    by_team: dict[int, list[tuple[float | None, float | None, bool]]] = defaultdict(list)
    for _, radiant_id, dire_id, features in rows:
        features = features or {}
        duration = features.get("duration_min")
        kill_diff = features.get("kill_diff")
        if radiant_id is not None:
            by_team[int(radiant_id)].append((duration, kill_diff, True))
        if dire_id is not None:
            flipped = None if kill_diff is None else -kill_diff
            by_team[int(dire_id)].append((duration, flipped, False))
    return dict(by_team)


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def build_group_analytics(
    session: Session,
    stage: GroupStage,
    teams: dict[int, str],
    *,
    ratings: dict[int, tuple[float, float, float]],
    engine: Glicko2 | None = None,
    first_round: list[tuple[int, int]] | None = None,
    wins_to_advance: int = 4,
    losses_to_eliminate: int = 4,
    regular_best_of: int = DEFAULT_REGULAR_BEST_OF,
    decisive_best_of: int = DEFAULT_DECISIVE_BEST_OF,
) -> GroupAnalytics:
    """Собрать аналитику этапа по разобранной сетке и рейтингам.

    `engine` приходит снаружи, чтобы вероятности серий здесь и в симуляциях
    считались с одной калибровкой.
    """
    engine = engine or Glicko2()

    analytics = GroupAnalytics(started=bool(stage.series))
    rows: dict[int, TeamStage] = {
        team_id: TeamStage(team_id=team_id, name=name) for team_id, name in teams.items()
    }
    for team_id, row in rows.items():
        entry = ratings.get(team_id)
        if entry is not None:
            row.rating, row.rd = entry[0], entry[1]

    # Разбор объявленного первого раунда. Он полезен до старта, когда сыгранного
    # ещё нет, и остаётся честным после: пары объявлены заранее.
    for left_id, right_id in first_round or []:
        left_rating, right_rating = _rating(ratings, left_id), _rating(ratings, right_id)
        probability = None
        gap = None
        if left_rating is not None and right_rating is not None:
            probability = engine.series_win_probability(
                left_rating, right_rating, best_of=regular_best_of
            )
            gap = left_rating.rating - right_rating.rating
        analytics.matchups.append(
            Matchup(
                left_id=left_id,
                right_id=right_id,
                left=teams.get(left_id, str(left_id)),
                right=teams.get(right_id, str(right_id)),
                left_win_probability=probability,
                rating_gap=gap,
            )
        )

    expected: dict[int, float] = defaultdict(float)
    opponents: dict[int, list[float]] = defaultdict(list)
    outcomes: dict[int, list[bool]] = defaultdict(list)
    by_round: dict[int, list[Series]] = defaultdict(list)
    stage_match_ids: set[int] = set()

    for series in stage.series:
        by_round[series.round].append(series)
        stage_match_ids.update(series.match_ids)

        left_id, right_id = series.left.team_id, series.right.team_id
        for side, opponent in ((left_id, right_id), (right_id, left_id)):
            if side in rows:
                rows[side].maps_won += (
                    series.left.score if side == left_id else series.right.score
                )
                rows[side].maps_lost += (
                    series.right.score if side == left_id else series.left.score
                )
                opponent_rating = ratings.get(opponent)
                if opponent_rating is not None:
                    opponents[side].append(opponent_rating[0])

        if not series.decided:
            continue

        best_of = _best_of(series, regular=regular_best_of, decisive=decisive_best_of)
        left_rating, right_rating = _rating(ratings, left_id), _rating(ratings, right_id)
        if left_rating is not None and right_rating is not None:
            left_chance = engine.series_win_probability(
                left_rating, right_rating, best_of=best_of
            )
            expected[left_id] += left_chance
            expected[right_id] += 1.0 - left_chance

        winner = series.winner_id
        loser = right_id if winner == left_id else left_id
        outcomes[winner].append(True)
        outcomes[loser].append(False)

        # Апсет: победила команда с рейтингом ниже. Без рейтинга у одной из
        # сторон вопрос не имеет смысла и серия просто не учитывается.
        winner_rating, loser_rating = ratings.get(winner), ratings.get(loser)
        if winner_rating is not None and loser_rating is not None:
            if winner_rating[0] < loser_rating[0]:
                rows[winner].upsets_won += 1
                rows[loser].upsets_lost += 1

    features = _stage_map_features(session, stage_match_ids)

    for team_id, row in rows.items():
        results = outcomes.get(team_id, [])
        row.wins = sum(1 for won in results if won)
        row.losses = sum(1 for won in results if not won)

        if results:
            row.expected_wins = expected.get(team_id)
            # Серия считается с конца: подряд идущие одинаковые исходы.
            last = results[-1]
            run = 0
            for won in reversed(results):
                if won is not last:
                    break
                run += 1
            row.streak = run if last else -run

        row.opponent_rating = _mean(opponents.get(team_id, []))

        maps = features.get(team_id, [])
        row.avg_duration_min = _mean([d for d, _, _ in maps if d is not None])
        row.avg_kill_diff = _mean([k for _, k, _ in maps if k is not None])

        if row.wins >= wins_to_advance:
            row.status = "advanced"
        elif row.losses >= losses_to_eliminate:
            row.status = "eliminated"

    for number in sorted(by_round):
        items = by_round[number]
        decided = [s for s in items if s.decided]
        upsets = 0
        for series in decided:
            winner = series.winner_id
            loser = (
                series.right.team_id if winner == series.left.team_id else series.left.team_id
            )
            winner_rating, loser_rating = ratings.get(winner), ratings.get(loser)
            if (
                winner_rating is not None
                and loser_rating is not None
                and winner_rating[0] < loser_rating[0]
            ):
                upsets += 1
        analytics.rounds.append(
            RoundStage(
                round=number,
                series=len(items),
                decided=len(decided),
                upsets=upsets,
                maps=sum(len(s.match_ids) for s in items),
            )
        )

    analytics.teams = sorted(
        rows.values(),
        key=lambda t: (-t.wins, t.losses, -t.map_diff, -(t.rating or 0.0), t.name),
    )
    return analytics
