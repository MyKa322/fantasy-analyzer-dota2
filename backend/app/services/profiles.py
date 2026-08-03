"""Профили команд и игроков: всё, что мы знаем о них из данных OpenDota.

Отличие от `analysis.py`: там данные готовятся под конкретный вопрос Fantasy
(история роли для проекции, кандидаты, рейтинги), здесь — просто витрина. На
странице команды и на странице игрока нужен не ответ модели, а сами числа:
сколько сыграно, с кем, на ком, с каким КДА и фармом.

Два принципа:

* **Ничего не досчитываем за OpenDota.** Матчи без разобранного реплея есть в
  базе, но в них нет вардов, станов и тимфайтов. Такие карты идут в счёт
  побед и поражений, но не в средние по статам — иначе средние поедут вниз
  ровно на долю неразобранных матчей. Число тех и других показывается явно.
* **Fantasy-оценка и обычная статистика разделены.** Килы в профиле — это килы,
  а в анализе — 107 очков за штуку. Смешивать их в одной таблице значит
  получить страницу, по которой нельзя ни оценить игрока, ни собрать состав.
"""

from __future__ import annotations

import json
import logging
from collections import Counter, defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db.models import Match, Player, PlayerMatchStat, Team, TeamRating, TeamRosterSlot
from ..ingest.stat_mapping import PROFILE_FIELDS

log = logging.getLogger(__name__)

HEROES_PATH = Path(__file__).resolve().parents[2] / "config" / "heroes.json"

# Средние считаются по разобранным матчам: в остальных половины полей нет.
DEFAULT_DAYS = 180


@dataclass(frozen=True, slots=True)
class MatchRow:
    """Одна карта в списке матчей — то, что видно в таблице на странице."""

    match_id: int
    start_time: datetime
    duration: int
    league_name: str | None
    opponent_id: int | None
    opponent_name: str | None
    won: bool | None
    is_parsed: bool
    hero_id: int | None = None
    hero_name: str | None = None
    kills: float | None = None
    deaths: float | None = None
    assists: float | None = None
    gpm: float | None = None
    xpm: float | None = None
    net_worth: float | None = None
    fantasy_points: float | None = None


@dataclass(frozen=True, slots=True)
class HeroRow:
    hero_id: int
    name: str
    games: int
    wins: int

    @property
    def win_rate(self) -> float:
        return self.wins / self.games if self.games else 0.0


@dataclass(slots=True)
class PlayerProfile:
    account_id: int
    name: str | None
    team_id: int | None
    team_name: str | None
    role: str | None
    position: int | None
    games: int
    parsed_games: int
    wins: int
    first_game: datetime | None
    last_game: datetime | None
    # Средние за карту: обычная статистика (assists, xpm, net_worth, …).
    averages: dict[str, float] = field(default_factory=dict)
    # Средние за карту по Fantasy-статам — в единицах, не в очках.
    fantasy_units: dict[str, float] = field(default_factory=dict)
    heroes: list[HeroRow] = field(default_factory=list)
    matches: list[MatchRow] = field(default_factory=list)

    @property
    def win_rate(self) -> float:
        return self.wins / self.games if self.games else 0.0


@dataclass(slots=True)
class TeamProfile:
    team_id: int
    name: str
    compendium_name: str | None
    tag: str | None
    rating: float | None
    rd: float | None
    volatility: float | None
    rating_history: list[tuple[datetime, float, float]]
    games: int
    parsed_games: int
    wins: int
    first_game: datetime | None
    last_game: datetime | None
    roster: list[PlayerProfile] = field(default_factory=list)
    matches: list[MatchRow] = field(default_factory=list)
    # Средние по команде за карту: сумма по пятерым, а не среднее — так принято
    # читать командные числа (килы команды, а не килы среднего игрока).
    team_averages: dict[str, float] = field(default_factory=dict)
    opponents: list[tuple[str, int, int]] = field(default_factory=list)

    @property
    def win_rate(self) -> float:
        return self.wins / self.games if self.games else 0.0


def load_heroes(path: Path | str = HEROES_PATH) -> dict[int, str]:
    """id -> имя героя. Справочник обновляется командой `cli.py ingest-heroes`.

    Файл лежит в репозитории, потому что герои меняются раз в патч, а страница
    игрока должна открываться и без сети.
    """
    path = Path(path)
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        log.warning("не удалось прочитать справочник героев %s", path)
        return {}
    return {int(key): str(value) for key, value in raw.items()}


def _since(days: int | None) -> datetime | None:
    return None if days is None else datetime.now(timezone.utc) - timedelta(days=days)


def _utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def team_directory(session: Session) -> list[dict[str, object]]:
    """Список команд для навигации: кто есть, сколько матчей, какой рейтинг."""
    counts = dict(
        session.execute(
            select(PlayerMatchStat.team_id, func.count(func.distinct(PlayerMatchStat.match_id)))
            .where(PlayerMatchStat.team_id.is_not(None))
            .group_by(PlayerMatchStat.team_id)
        ).all()
    )
    ratings = _latest_ratings(session)

    rows: list[dict[str, object]] = []
    for team in session.scalars(select(Team)):
        games = int(counts.get(team.team_id, 0))
        rating = ratings.get(team.team_id)
        if not games and team.compendium_name is None:
            continue  # команда без единого матча в базе — на странице пусто
        rows.append(
            {
                "team_id": team.team_id,
                "name": team.compendium_name or team.name,
                "opendota_name": team.name,
                "tag": team.tag,
                "is_ti": team.compendium_name is not None,
                "games": games,
                "rating": rating[0] if rating else None,
                "rd": rating[1] if rating else None,
            }
        )
    rows.sort(key=lambda r: (not r["is_ti"], -(r["rating"] or 0), -(r["games"] or 0)))
    return rows


def player_directory(session: Session, *, ti_only: bool = False) -> list[dict[str, object]]:
    """Список игроков: ник, команда, роль, сколько карт сыграно."""
    counts = dict(
        session.execute(
            select(PlayerMatchStat.account_id, func.count(PlayerMatchStat.id)).group_by(
                PlayerMatchStat.account_id
            )
        ).all()
    )
    slots = {
        slot.account_id: slot
        for slot in session.scalars(select(TeamRosterSlot).order_by(TeamRosterSlot.games))
    }
    team_names = {
        team.team_id: team.compendium_name or team.name for team in session.scalars(select(Team))
    }

    rows: list[dict[str, object]] = []
    for player in session.scalars(select(Player)):
        slot = slots.get(player.account_id)
        if ti_only and slot is None:
            continue
        games = int(counts.get(player.account_id, 0))
        if not games:
            continue
        team_id = slot.team_id if slot else player.team_id
        rows.append(
            {
                "account_id": player.account_id,
                "name": player.name,
                "team_id": team_id,
                "team_name": team_names.get(team_id) if team_id else None,
                "role": slot.role if slot else player.fantasy_role,
                "is_ti": slot is not None,
                "games": games,
            }
        )
    rows.sort(key=lambda r: (not r["is_ti"], -(r["games"] or 0)))
    return rows


def _latest_ratings(session: Session) -> dict[int, tuple[float, float, float]]:
    latest_run = session.scalar(select(TeamRating.run_id).order_by(TeamRating.id.desc()))
    if latest_run is None:
        return {}
    result: dict[int, tuple[float, float, float]] = {}
    for row in session.scalars(
        select(TeamRating).where(TeamRating.run_id == latest_run).order_by(TeamRating.as_of)
    ):
        result[row.team_id] = (row.rating, row.rd, row.volatility)
    return result


def player_profile(
    session: Session,
    account_id: int,
    *,
    days: int | None = DEFAULT_DAYS,
    match_limit: int = 25,
    hero_limit: int = 12,
    heroes: dict[int, str] | None = None,
) -> PlayerProfile | None:
    """Всё, что известно об игроке: средние, герои, матчи, команда, роль."""
    player = session.get(Player, account_id)
    since = _since(days)

    query = (
        select(PlayerMatchStat, Match)
        .join(Match, Match.match_id == PlayerMatchStat.match_id)
        .where(PlayerMatchStat.account_id == account_id)
        .order_by(PlayerMatchStat.start_time.desc())
    )
    if since is not None:
        query = query.where(PlayerMatchStat.start_time >= since)

    rows = list(session.execute(query))
    if player is None and not rows:
        return None

    heroes = heroes if heroes is not None else load_heroes()
    team_names = {
        team.team_id: team.compendium_name or team.name for team in session.scalars(select(Team))
    }
    slot = session.scalar(
        select(TeamRosterSlot).where(TeamRosterSlot.account_id == account_id)
    )

    wins = sum(1 for stat, _ in rows if stat.won)
    parsed = [(stat, match) for stat, match in rows if match.is_parsed]

    # Обычная статистика появилась в базе позже Fantasy-статов, и матчи, забранные
    # старым кодом, её не содержат. Считать по ним нельзя: отсутствующее поле
    # превратилось бы в ноль и занизило среднее ровно на долю таких карт.
    profiled = [(stat, match) for stat, match in parsed if stat.profile]
    averages = {
        key: _mean([float(stat.profile.get(key, 0.0)) for stat, _ in profiled])
        for key in PROFILE_FIELDS
    }
    fantasy_units: dict[str, float] = {}
    if parsed:
        keys = set()
        for stat, _ in parsed:
            keys.update(stat.stats or {})
        for key in sorted(keys):
            fantasy_units[key] = _mean([float((stat.stats or {}).get(key, 0.0)) for stat, _ in parsed])

    hero_games: Counter[int] = Counter()
    hero_wins: Counter[int] = Counter()
    for stat, _ in rows:
        if stat.hero_id is None:
            continue
        hero_games[stat.hero_id] += 1
        hero_wins[stat.hero_id] += int(bool(stat.won))

    # Команда игрока: та, за которую он играл в последних матчах, а не поле в
    # профиле — оно устаревает при переходах.
    recent_team = next((stat.team_id for stat, _ in rows if stat.team_id), None)
    team_id = (slot.team_id if slot else None) or recent_team
    if team_id is None and player is not None:
        team_id = player.team_id

    matches = [
        _match_row(
            stat, match, team_id=stat.team_id, heroes=heroes, opponent_names=team_names
        )
        for stat, match in rows[:match_limit]
    ]

    return PlayerProfile(
        account_id=account_id,
        name=player.name if player else None,
        team_id=team_id,
        team_name=team_names.get(team_id) if team_id else None,
        role=slot.role if slot else (player.fantasy_role if player else None),
        position=player.position if player else None,
        games=len(rows),
        parsed_games=len(parsed),
        wins=wins,
        first_game=_utc(rows[-1][0].start_time) if rows else None,
        last_game=_utc(rows[0][0].start_time) if rows else None,
        averages=averages,
        fantasy_units=fantasy_units,
        heroes=[
            HeroRow(
                hero_id=hero_id,
                name=heroes.get(hero_id, f"hero {hero_id}"),
                games=games,
                wins=hero_wins[hero_id],
            )
            for hero_id, games in hero_games.most_common(hero_limit)
        ],
        matches=matches,
    )


def _match_row(
    stat: PlayerMatchStat | None,
    match: Match,
    *,
    team_id: int | None,
    heroes: dict[int, str],
    opponent_names: dict[int, str] | None = None,
) -> MatchRow:
    opponent_id = (
        match.dire_team_id if team_id == match.radiant_team_id else match.radiant_team_id
    )
    profile = (stat.profile or {}) if stat else {}
    stats = (stat.stats or {}) if stat else {}
    return MatchRow(
        match_id=match.match_id,
        start_time=_utc(match.start_time),
        duration=match.duration,
        league_name=match.league_name,
        opponent_id=opponent_id,
        opponent_name=(opponent_names or {}).get(opponent_id) if opponent_id else None,
        won=stat.won if stat else None,
        is_parsed=match.is_parsed,
        hero_id=stat.hero_id if stat else None,
        hero_name=heroes.get(stat.hero_id) if stat and stat.hero_id else None,
        kills=stats.get("kills"),
        deaths=stats.get("deaths"),
        assists=profile.get("assists"),
        gpm=stats.get("gpm"),
        xpm=profile.get("xpm"),
        net_worth=profile.get("net_worth"),
    )


def team_profile(
    session: Session,
    team_id: int,
    *,
    days: int | None = DEFAULT_DAYS,
    match_limit: int = 30,
    roster_limit: int = 8,
    heroes: dict[int, str] | None = None,
) -> TeamProfile | None:
    """Всё о команде: рейтинг с историей, матчи, состав, средние по картам."""
    team = session.get(Team, team_id)
    if team is None:
        return None

    heroes = heroes if heroes is not None else load_heroes()
    since = _since(days)
    team_names = {t.team_id: t.compendium_name or t.name for t in session.scalars(select(Team))}

    query = (
        select(Match)
        .where((Match.radiant_team_id == team_id) | (Match.dire_team_id == team_id))
        .order_by(Match.start_time.desc())
    )
    if since is not None:
        query = query.where(Match.start_time >= since)
    matches = list(session.scalars(query))

    stats_query = (
        select(PlayerMatchStat)
        .where(PlayerMatchStat.team_id == team_id)
        .order_by(PlayerMatchStat.start_time.desc())
    )
    if since is not None:
        stats_query = stats_query.where(PlayerMatchStat.start_time >= since)
    stats = list(session.scalars(stats_query))

    by_match: dict[int, list[PlayerMatchStat]] = defaultdict(list)
    for stat in stats:
        by_match[stat.match_id].append(stat)

    wins = 0
    opponents: Counter[str] = Counter()
    opponent_wins: Counter[str] = Counter()
    for match in matches:
        is_radiant = match.radiant_team_id == team_id
        if match.radiant_win is not None:
            won = bool(match.radiant_win) == is_radiant
            wins += int(won)
            opponent_id = match.dire_team_id if is_radiant else match.radiant_team_id
            if opponent_id:
                name = team_names.get(opponent_id, str(opponent_id))
                opponents[name] += 1
                opponent_wins[name] += int(won)

    parsed = [m for m in matches if m.is_parsed]

    # Командные средние — сумма пятерых за карту. По ним читается стиль: сколько
    # команда убивает, как быстро фармит, сколько ставит вардов.
    team_averages: dict[str, float] = {}
    per_match_totals: dict[str, list[float]] = defaultdict(list)
    for match in parsed:
        rows = by_match.get(match.match_id, [])
        if not rows:
            continue
        for key in ("kills", "deaths", "gpm", "wards_placed", "camps_stacked", "stuns"):
            per_match_totals[key].append(sum(float((r.stats or {}).get(key, 0.0)) for r in rows))
        # Та же причина, что и у игрока: карта без обычной статистики в средние
        # по ней не идёт вовсе, а не идёт нулём.
        if all(r.profile for r in rows):
            for key in ("assists", "net_worth", "hero_damage"):
                per_match_totals[key].append(
                    sum(float(r.profile.get(key, 0.0)) for r in rows)
                )
        per_match_totals["duration"].append(float(match.duration))
    for key, values in per_match_totals.items():
        team_averages[key] = _mean(values)

    roster_counts: Counter[int] = Counter()
    for stat in stats:
        roster_counts[stat.account_id] += 1
    slots = {
        slot.account_id: slot.role
        for slot in session.scalars(
            select(TeamRosterSlot).where(TeamRosterSlot.team_id == team_id)
        )
    }
    # Сначала размеченный ростер TI, затем остальные по числу карт: стенд-ины
    # видно, но они не вытесняют основу.
    ordered = sorted(
        roster_counts.items(),
        key=lambda item: (item[0] not in slots, -item[1]),
    )[:roster_limit]

    roster = []
    for account_id, _ in ordered:
        profile = player_profile(
            session, account_id, days=days, match_limit=0, hero_limit=5, heroes=heroes
        )
        if profile is not None:
            roster.append(profile)

    history = [
        (_utc(row.as_of), row.rating, row.rd)
        for row in session.scalars(
            select(TeamRating)
            .where(TeamRating.team_id == team_id)
            .order_by(TeamRating.as_of)
        )
    ]
    latest = _latest_ratings(session).get(team_id)

    match_rows = []
    for match in matches[:match_limit]:
        rows = by_match.get(match.match_id, [])
        won = None
        if match.radiant_win is not None:
            won = bool(match.radiant_win) == (match.radiant_team_id == team_id)
        row = _match_row(
            rows[0] if rows else None,
            match,
            team_id=team_id,
            heroes=heroes,
            opponent_names=team_names,
        )
        # У командной строки герой и КДА одного игрока смысла не имеют.
        match_rows.append(
            MatchRow(
                match_id=row.match_id,
                start_time=row.start_time,
                duration=row.duration,
                league_name=row.league_name,
                opponent_id=row.opponent_id,
                opponent_name=row.opponent_name,
                won=won,
                is_parsed=row.is_parsed,
                kills=sum(float((r.stats or {}).get("kills", 0.0)) for r in rows) or None,
                deaths=sum(float((r.stats or {}).get("deaths", 0.0)) for r in rows) or None,
                assists=sum(float((r.profile or {}).get("assists", 0.0)) for r in rows) or None,
                # GPM команды — сумма пятерых: столбец должен читаться так же,
                # как килы рядом, а не как среднее по одному игроку.
                gpm=sum(float((r.stats or {}).get("gpm", 0.0)) for r in rows) or None,
                net_worth=sum(float((r.profile or {}).get("net_worth", 0.0)) for r in rows)
                or None,
            )
        )

    return TeamProfile(
        team_id=team_id,
        name=team.compendium_name or team.name,
        compendium_name=team.compendium_name,
        tag=team.tag,
        rating=latest[0] if latest else None,
        rd=latest[1] if latest else None,
        volatility=latest[2] if latest else None,
        rating_history=history,
        games=len(matches),
        parsed_games=len(parsed),
        wins=wins,
        first_game=_utc(matches[-1].start_time) if matches else None,
        last_game=_utc(matches[0].start_time) if matches else None,
        roster=roster,
        matches=match_rows,
        team_averages=team_averages,
        opponents=[
            (name, games, opponent_wins[name]) for name, games in opponents.most_common(10)
        ],
    )
