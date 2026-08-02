"""Хронологический пересчёт рейтингов команд.

Главное правило модуля: рейтинг команды на момент матча считается только по
матчам, сыгранным ДО него. Это тот самый анти-лик, из-за которого модели на
исторических данных обычно выглядят гораздо лучше, чем работают вживую.
Поэтому история всегда пересчитывается с нуля вперёд по времени, а не
"досчитывается" точечно.

Glicko-2 работает рейтинговыми периодами: внутри периода все матчи считаются
одновременными. Для про-сцены разумный период — неделя (Гликман рекомендует
подбирать так, чтобы на период приходилось 10-15 игр на участника; у топ-команд
это как раз неделя турнирной сетки).
"""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from .glicko2 import Glicko2, GameResult, Rating

log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class MatchRecord:
    """Минимум, нужный рейтингу: кто, с кем, когда и чем кончилось."""

    match_id: int
    start_time: datetime
    radiant_team_id: int
    dire_team_id: int
    radiant_win: bool
    series_key: str | None = None
    is_lan: bool | None = None
    patch: int | None = None

    def winner(self) -> int:
        return self.radiant_team_id if self.radiant_win else self.dire_team_id

    def loser(self) -> int:
        return self.dire_team_id if self.radiant_win else self.radiant_team_id


@dataclass(slots=True)
class RatingSnapshot:
    team_id: int
    as_of: datetime
    rating: Rating
    matches_played: int


@dataclass(slots=True)
class RatingHistory:
    """Итог пересчёта: текущие рейтинги и вся траектория по периодам."""

    current: dict[int, Rating] = field(default_factory=dict)
    snapshots: list[RatingSnapshot] = field(default_factory=list)
    matches_played: dict[int, int] = field(default_factory=dict)
    last_match_at: dict[int, datetime] = field(default_factory=dict)

    def team_history(self, team_id: int) -> list[RatingSnapshot]:
        return [s for s in self.snapshots if s.team_id == team_id]

    def days_idle(self, team_id: int, *, now: datetime | None = None) -> float | None:
        last = self.last_match_at.get(team_id)
        if last is None:
            return None
        now = now or datetime.now(timezone.utc)
        return (now - last).total_seconds() / 86400.0

    def listable(self, *, now: datetime | None = None) -> dict[int, Rating]:
        """Команды, чьему рейтингу можно доверять (фильтр в духе Liquipedia)."""
        return {
            team_id: rating
            for team_id, rating in self.current.items()
            if rating.is_listable(self.days_idle(team_id, now=now))
        }


def _period_start(moment: datetime, origin: datetime, period: timedelta) -> datetime:
    elapsed = moment - origin
    periods = int(elapsed // period)
    return origin + periods * period


class RatingCalculator:
    """Пересчёт Glicko-2 по всей истории матчей."""

    def __init__(
        self,
        engine: Glicko2 | None = None,
        *,
        period_days: int = 7,
        initial_rating: Rating | None = None,
    ) -> None:
        self.engine = engine or Glicko2()
        self.period = timedelta(days=period_days)
        self.initial_rating = initial_rating or Rating()

    def compute(
        self,
        matches: Iterable[MatchRecord],
        *,
        seed_ratings: dict[int, Rating] | None = None,
    ) -> RatingHistory:
        """Прогнать всю историю вперёд по времени.

        `seed_ratings` позволяет стартовать не с 1500±350, а с внешней оценки
        (например, посева TI) — RD у такой затравки должен быть высоким, иначе
        модель слишком долго не будет верить фактическим результатам.
        """
        ordered = sorted(matches, key=lambda m: (m.start_time, m.match_id))
        history = RatingHistory()
        if not ordered:
            return history

        ratings: dict[int, Rating] = dict(seed_ratings or {})
        origin = ordered[0].start_time

        by_period: dict[datetime, list[MatchRecord]] = defaultdict(list)
        for match in ordered:
            by_period[_period_start(match.start_time, origin, self.period)].append(match)

        known_teams: set[int] = set(ratings)
        for period_start in sorted(by_period):
            period_matches = by_period[period_start]
            results: dict[int, list[GameResult]] = defaultdict(list)

            # Снимок рейтингов на начало периода — все матчи периода оцениваются
            # по нему, чтобы порядок матчей внутри периода не влиял на результат.
            frozen = {
                team_id: ratings.get(team_id, self.initial_rating)
                for team_id in known_teams
            }

            for match in period_matches:
                for team_id in (match.radiant_team_id, match.dire_team_id):
                    if team_id not in frozen:
                        frozen[team_id] = ratings.get(team_id, self.initial_rating)
                        known_teams.add(team_id)

                winner, loser = match.winner(), match.loser()
                results[winner].append(GameResult(frozen[loser], 1.0))
                results[loser].append(GameResult(frozen[winner], 0.0))
                history.matches_played[winner] = history.matches_played.get(winner, 0) + 1
                history.matches_played[loser] = history.matches_played.get(loser, 0) + 1
                history.last_match_at[winner] = match.start_time
                history.last_match_at[loser] = match.start_time

            period_end = period_start + self.period
            for team_id in known_teams:
                current = frozen.get(team_id, self.initial_rating)
                updated = self.engine.rate(current, results.get(team_id, []))
                ratings[team_id] = updated
                history.snapshots.append(
                    RatingSnapshot(
                        team_id=team_id,
                        as_of=period_end,
                        rating=updated,
                        matches_played=history.matches_played.get(team_id, 0),
                    )
                )

        history.current = ratings
        log.info(
            "рейтинги пересчитаны: %d команд, %d периодов",
            len(ratings),
            len(by_period),
        )
        return history

    def ratings_before(
        self, matches: Sequence[MatchRecord], moment: datetime
    ) -> dict[int, Rating]:
        """Рейтинги, какими они были на указанный момент.

        Нужно для честной проверки калибровки: прогноз матча должен строиться на
        данных строго до его начала.
        """
        past = [m for m in matches if m.start_time < moment]
        return self.compute(past).current
