"""Связка базы с аналитикой: достать матчи, пересчитать рейтинги, собрать роли."""

from __future__ import annotations

import logging
import uuid
from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from ..analytics.rating import MatchRecord, RatingCalculator, RatingHistory
from ..db.models import (
    Match,
    Player,
    PlayerMatchStat,
    Team,
    TeamRating,
    TeamRosterSlot,
)
from ..fantasy.projection import RoleGame, RoleHistory, Substitution

log = logging.getLogger(__name__)

# Роли компендиума и число игроков в каждой.
ROLE_SIZES = {"core": 2, "mid": 1, "support": 2}


def _utc(moment: datetime) -> datetime:
    """SQLite отдаёт naive datetime — приводим к UTC, иначе арифметика падает."""
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def load_match_records(
    session: Session, *, since: datetime | None = None, team_ids: Sequence[int] | None = None
) -> list[MatchRecord]:
    """Матчи для рейтинга. Нераспарсенные тоже годятся — исход известен."""
    query = select(Match).where(
        Match.radiant_team_id.is_not(None),
        Match.dire_team_id.is_not(None),
        Match.radiant_win.is_not(None),
    )
    if since is not None:
        query = query.where(Match.start_time >= since)
    if team_ids:
        query = query.where(
            Match.radiant_team_id.in_(team_ids) | Match.dire_team_id.in_(team_ids)
        )

    return [
        MatchRecord(
            match_id=m.match_id,
            start_time=_utc(m.start_time),
            radiant_team_id=int(m.radiant_team_id),
            dire_team_id=int(m.dire_team_id),
            radiant_win=bool(m.radiant_win),
            series_key=m.series_key,
            is_lan=m.is_lan,
            patch=m.patch,
        )
        for m in session.scalars(query)
    ]


def recompute_ratings(
    session: Session,
    *,
    history_days: int = 365,
    period_days: int = 7,
    persist: bool = True,
) -> RatingHistory:
    """Пересчитать рейтинги всех команд с нуля и сохранить снимки.

    Всегда с нуля и хронологически: досчитывать «сверху» нельзя, иначе в
    исторические значения протечёт информация из будущих матчей.
    """
    since = datetime.now(timezone.utc) - timedelta(days=history_days)
    matches = load_match_records(session, since=since)
    history = RatingCalculator(period_days=period_days).compute(matches)

    if persist and history.snapshots:
        run_id = uuid.uuid4().hex[:16]
        known_teams = set(session.scalars(select(Team.team_id)))
        for snapshot in history.snapshots:
            if snapshot.team_id not in known_teams:
                continue  # команда из матча, которую ещё не завели в справочник
            session.add(
                TeamRating(
                    team_id=snapshot.team_id,
                    as_of=snapshot.as_of,
                    rating=snapshot.rating.rating,
                    rd=snapshot.rating.rd,
                    volatility=snapshot.rating.volatility,
                    matches_played=snapshot.matches_played,
                    run_id=run_id,
                )
            )
        session.flush()
        log.info("сохранено %d снимков рейтинга (run %s)", len(history.snapshots), run_id)

    return history


def infer_team_roles(
    session: Session,
    team_id: int,
    *,
    since: datetime | None = None,
    min_games: int = 3,
    recent_matches: int = 20,
) -> dict[str, tuple[int, ...]]:
    """Определить, кто в команде core duo, mid и support duo.

    Прямого поля роли в данных нет, поэтому эвристика по фактической игре:
    мид — тот, кто чаще всех стоит на центральной линии (`lane_role == 2`),
    кор-дуо — двое с наибольшим фарм-приоритетом (GPM и добивания), остальные —
    саппорты. На про-сцене такое разделение устойчиво: у саппортов GPM кратно
    ниже, и ошибиться сложно.

    Состав отбирается по последним `recent_matches` матчам команды, а не по
    общему числу игр за период. Иначе замена в середине сезона не видна: в
    Team Vision у SSS 55 карт (март-апрель), у сменившего его Noticed — 50
    (май-июнь), и подсчёт «кто сыграл больше» ставит в ростер игрока, который
    на TI уже не поедет.
    """
    query = (
        select(PlayerMatchStat)
        .where(PlayerMatchStat.team_id == team_id)
        .order_by(PlayerMatchStat.start_time.desc())
    )
    if since is not None:
        query = query.where(PlayerMatchStat.start_time >= since)

    by_player: dict[int, list[PlayerMatchStat]] = defaultdict(list)
    for stat in session.scalars(query):
        by_player[stat.account_id].append(stat)

    eligible = {a: rows for a, rows in by_player.items() if len(rows) >= min_games}
    if len(eligible) < 5:
        # Слишком мало данных для эвристики — берём всех, кто вообще играл.
        eligible = by_player
    if not eligible:
        return {}

    def mid_share(rows: list[PlayerMatchStat]) -> float:
        return sum(1 for r in rows if r.lane_role == 2) / len(rows)

    def farm_priority(rows: list[PlayerMatchStat]) -> float:
        gpm = sum(float(r.stats.get("gpm", 0.0)) for r in rows) / len(rows)
        creeps = sum(float(r.stats.get("creep_score", 0.0)) for r in rows) / len(rows)
        return gpm + creeps

    def last_played(rows: list[PlayerMatchStat]) -> float:
        return max(_utc(r.start_time).timestamp() for r in rows)

    # Свежие матчи команды — по ним видно, кто играет сейчас.
    recent_ids = set(
        session.scalars(
            select(PlayerMatchStat.match_id)
            .where(PlayerMatchStat.team_id == team_id)
            .order_by(PlayerMatchStat.start_time.desc())
            .distinct()
            .limit(recent_matches)
        )
    )

    def recent_appearances(rows: list[PlayerMatchStat]) -> int:
        return sum(1 for r in rows if r.match_id in recent_ids)

    # Сначала отсекаем состав, и только потом раздаём роли. Иначе стендин или
    # игрок другой команды, сыгравший пару карт, вытесняет из ростера настоящего
    # саппорта: сравнение шло по фарму, а у чужого кора он заведомо выше.
    squad = sorted(
        eligible,
        key=lambda a: (
            -recent_appearances(eligible[a]),
            -last_played(eligible[a]),
            -len(eligible[a]),
        ),
    )[:5]

    mid = max(squad, key=lambda a: mid_share(eligible[a]))
    rest = sorted((a for a in squad if a != mid), key=lambda a: -farm_priority(eligible[a]))

    return {
        "mid": (mid,),
        "core": tuple(rest[:2]),
        "support": tuple(rest[2:4]),
    }


def squad_account_ids(session: Session, team_id: int) -> set[int]:
    """Текущая пятёрка команды по разметке ростера."""
    return set(
        session.scalars(
            select(TeamRosterSlot.account_id).where(TeamRosterSlot.team_id == team_id)
        )
    )


def build_role_history(
    session: Session,
    team_id: int,
    role: str,
    account_ids: Sequence[int],
    *,
    since: datetime | None = None,
    parsed_only: bool = True,
    squad: set[int] | None = None,
    min_squad_overlap: int = 3,
) -> RoleHistory:
    """Собрать историю карт роли для проекции.

    Только распарсенные матчи: в нераспарсенных нет вардов, станов и тимфайтов,
    и включение их занизило бы проекцию.

    Карта засчитывается, только если в ней играло минимум `min_squad_overlap`
    игроков текущей пятёрки. Отбор по account_id без этой проверки смешивает две
    разные вещи:

    * коллектив переехал под новый бренд — Iron Wing раньше играл как Tundra и
      1w, LGD как HEROIC, Huligani как L1GA. Это те же пять человек, и их матчи
      выборке нужны: под новым тегом карт бывает всего два десятка.
    * игрок перешёл из другой команды — Noticed отыграл 26 карт за Team Yandex
      до перехода в Team Vision. Эти карты к текущей роли отношения не имеют:
      там были другие напарники, другой стиль, и «среднее по игрокам роли»
      считалось бы по одному человеку вместо двух.

    Пересечение состава различает эти случаи без ручных списков переименований.
    """
    if not account_ids:
        raise ValueError(f"для роли {role!r} команды {team_id} не заданы игроки")

    # Замена в составе: у пришедшего своих карт в выборке нет, берём карты того,
    # кого он заменил. Дальше по коду account_ids — уже история, а не ростер.
    swap = roster_substitutions(session, team_id)
    roster_ids = tuple(account_ids)
    account_ids = tuple(swap.get(a, a) for a in roster_ids)

    squad = squad if squad is not None else squad_account_ids(session, team_id)
    squad = squad | set(account_ids) | set(roster_ids)

    query = (
        select(PlayerMatchStat, Match)
        .join(Match, Match.match_id == PlayerMatchStat.match_id)
        .where(PlayerMatchStat.account_id.in_(account_ids))
        .order_by(PlayerMatchStat.start_time)
    )
    if since is not None:
        query = query.where(PlayerMatchStat.start_time >= since)
    if parsed_only:
        query = query.where(Match.is_parsed.is_(True))

    if min_squad_overlap > 1 and len(squad) >= min_squad_overlap:
        overlap = (
            select(PlayerMatchStat.match_id)
            .where(PlayerMatchStat.account_id.in_(squad))
            .group_by(PlayerMatchStat.match_id)
            .having(func.count(PlayerMatchStat.account_id.distinct()) >= min_squad_overlap)
        )
        query = query.where(PlayerMatchStat.match_id.in_(overlap))

    games: dict[int, dict] = {}
    for stat, match in session.execute(query):
        entry = games.setdefault(
            match.match_id,
            {
                "start_time": _utc(match.start_time),
                "series_key": match.series_key,
                "patch": match.patch,
                "is_lan": match.is_lan,
                "duration": match.duration,
                "won": stat.won,
                "first_blood_time": match.first_blood_time,
                "players": {},
                "heroes": {},
            },
        )
        entry["players"][stat.account_id] = dict(stat.stats)
        if stat.hero_id is not None:
            entry["heroes"][stat.account_id] = stat.hero_id

    names = {
        p.account_id: p.name
        for p in session.scalars(
            select(Player).where(Player.account_id.in_(set(account_ids) | set(roster_ids)))
        )
    }
    team = session.get(Team, team_id)

    def _name(account_id: int) -> str:
        return names.get(account_id) or str(account_id)

    return RoleHistory(
        role=role,
        team_id=team_id,
        account_ids=tuple(account_ids),
        team_name=team.name if team else None,
        player_names=tuple(_name(a) for a in account_ids),
        substitutions=tuple(
            Substitution(
                account_id=new_id,
                name=_name(new_id),
                replaced_account_id=swap[new_id],
                replaced_name=_name(swap[new_id]),
            )
            for new_id in roster_ids
            if new_id in swap
        ),
        games=[
            RoleGame(
                match_id=match_id,
                start_time=entry["start_time"],
                series_key=entry["series_key"],
                player_stats=entry["players"],
                patch=entry["patch"],
                is_lan=entry["is_lan"],
                duration=entry["duration"],
                won=entry["won"],
                first_blood_time=entry["first_blood_time"],
                heroes=entry["heroes"],
            )
            for match_id, entry in sorted(games.items(), key=lambda kv: kv[1]["start_time"])
        ],
    )


ROSTER_OVERRIDES_PATH = Path(__file__).resolve().parents[2] / "config" / "ti15_rosters.yaml"


def load_roster_overrides(
    path: Path | str | None = None,
) -> dict[str, dict[str, list[str]]]:
    """Ручные составы из конфига: {название команды: {роль: [ники]}}.

    Путь берётся в момент вызова, а не при импорте: иначе подменить конфиг в
    тесте можно было бы только патчем самой функции.
    """
    path = Path(path or ROSTER_OVERRIDES_PATH)
    if not path.exists():
        return {}
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return raw.get("overrides") or {}


def _override_entries(raw: object) -> list[dict[str, object]]:
    """Привести запись роли к списку словарей: строка — это просто ник."""
    entries: list[dict[str, object]] = []
    for item in raw or ():  # type: ignore[union-attr]
        if isinstance(item, str):
            entries.append({"name": item})
        elif isinstance(item, Mapping):
            entries.append(dict(item))
        else:
            raise ValueError(f"состав: непонятная запись игрока {item!r}")
    return entries


def _team_nicknames(session: Session, team_id: int) -> dict[str, int]:
    """Ники тех, кто играл за команду: {ник: account_id}."""
    return {
        name: account_id
        for account_id, name in session.execute(
            select(Player.account_id, Player.name)
            .join(PlayerMatchStat, PlayerMatchStat.account_id == Player.account_id)
            .where(PlayerMatchStat.team_id == team_id)
            .distinct()
        )
        if name
    }


def _apply_roster_override(
    session: Session,
    team_id: int,
    team_name: str,
    roles: dict[str, tuple[int, ...]],
    override: Mapping[str, object],
) -> dict[str, tuple[int, ...]]:
    """Подставить вручную заданный состав вместо автоматического.

    Ник резолвится только среди тех, кто реально играл за эту команду: иначе
    опечатка в конфиге тихо привела бы в ростер постороннего игрока. Игрок со
    стороны задаётся явным account_id — ник в OpenDota не уникален, и такому
    игроку заводится строка в players, чтобы у слота было имя.
    """
    known = _team_nicknames(session, team_id)

    resolved: dict[str, tuple[int, ...]] = dict(roles)
    for role, raw in override.items():
        entries = _override_entries(raw)
        # Роль резолвится целиком и только потом попадает в базу: наполовину
        # применённая замена оставила бы слот за игроком без единой карты.
        account_ids: list[int] = []
        newcomers: list[tuple[int, str | None]] = []
        for entry in entries:
            name = entry.get("name")
            given = entry.get("account_id")
            replaces = entry.get("replaces")
            if given is None:
                account_id = known.get(str(name))
                problem = None if account_id is not None else f"ник {name!r} не найден"
            elif replaces and known.get(str(replaces)) is None:
                # Своих карт у пришедшего нет, а чьи брать — не выяснилось.
                account_id, problem = None, f"заменённый {replaces!r} не найден"
            else:
                account_id = int(given)  # type: ignore[arg-type]
                problem = None
                newcomers.append((account_id, str(name) if name else None))
            if problem is not None:
                log.warning(
                    "состав %s: %s среди игравших за команду — "
                    "роль %s остаётся за автоматикой",
                    team_name,
                    problem,
                    role,
                )
                account_ids = []
                break
            account_ids.append(account_id)

        if not account_ids:
            continue
        for account_id, name in newcomers:
            player = session.get(Player, account_id)
            if player is None:
                session.add(Player(account_id=account_id, name=name))
            elif name and player.name != name:
                player.name = name
        resolved[role] = tuple(account_ids)
    return resolved


def roster_substitutions(
    session: Session, team_id: int, *, team_name: str | None = None
) -> dict[int, int]:
    """Замены команды из конфига: {account_id пришедшего: account_id заменённого}.

    Заменённый резолвится среди игравших за команду — это его карты пойдут в
    выборку. Не нашли по нику (опечатка, игрока не было в этой команде) —
    замена не регистрируется: лучше пустая история роли, чем чужая.
    """
    if team_name is None:
        team = session.get(Team, team_id)
        team_name = (team.compendium_name or team.name) if team else None
    override = load_roster_overrides().get(team_name or "")
    if not override:
        return {}

    known = _team_nicknames(session, team_id)
    pairs: dict[int, int] = {}
    for role, raw in override.items():
        for entry in _override_entries(raw):
            replaces = entry.get("replaces")
            account_id = entry.get("account_id")
            if not replaces or account_id is None:
                continue
            replaced = known.get(str(replaces))
            if replaced is None:
                log.warning(
                    "состав %s: заменённый %r не найден среди игравших за команду — "
                    "роль %s останется без истории",
                    team_name,
                    replaces,
                    role,
                )
                continue
            pairs[int(account_id)] = replaced  # type: ignore[arg-type]
    return pairs


def ti_team_ids() -> dict[int, str]:
    """team_id участников TI15 из конфига: {team_id: название в компендиуме}."""
    from ..analytics.predictions_config import load_predictions_config

    config = load_predictions_config()
    return {
        int(team_id): name for name, team_id in config.team_ids.items() if team_id is not None
    }


def mark_ti_participants(
    session: Session, *, since: datetime | None = None, min_games: int = 3
) -> dict[str, dict[str, tuple[int, ...]]]:
    """Пометить игроков команд-участниц и определить их роли.

    Пул кандидатов в Fantasy ограничен игроками этих 16 команд, поэтому пометка
    нужна и как фильтр, и как проверка: если у команды не набралось пяти игроков,
    значит история загружена не полностью.
    """
    teams = ti_team_ids()
    if not teams:
        raise ValueError("в конфиге компендиума не проставлены team_id участников")

    # Сбрасываем прошлую разметку: составы меняются, устаревшие метки хуже пустых.
    for player in session.scalars(select(Player).where(Player.is_ti_participant.is_(True))):
        player.is_ti_participant = False
        player.fantasy_role = None
    session.execute(delete(TeamRosterSlot).where(TeamRosterSlot.team_id.in_(teams)))

    overrides = load_roster_overrides()

    result: dict[str, dict[str, tuple[int, ...]]] = {}
    for team_id, name in teams.items():
        # Название компендиума проставляется здесь, а не только при ручном
        # `resolve-teams`: связка «team_id -> участник TI15» задана конфигом и
        # сомнений не вызывает, а без метки команда выпадает из выгрузки — база,
        # собранная автоматикой с нуля, оказывалась вообще без участников.
        team = session.get(Team, team_id)
        if team is None:
            log.warning("команда %s (%s) не найдена в базе — нет ни одного матча", name, team_id)
        elif team.compendium_name != name:
            team.compendium_name = name

        roles = infer_team_roles(session, team_id, since=since, min_games=min_games)
        if name in overrides:
            roles = _apply_roster_override(session, team_id, name, roles, overrides[name])
        result[name] = roles
        for role, account_ids in roles.items():
            for account_id in account_ids:
                player = session.get(Player, account_id)
                if player is None:
                    continue
                player.is_ti_participant = True
                # Поля у игрока — «основная» команда для UI; источник истины по
                # составам — слоты, они переживают пересечение ростеров.
                player.fantasy_role = role
                player.team_id = team_id
                session.add(
                    TeamRosterSlot(team_id=team_id, account_id=account_id, role=role)
                )

    session.flush()
    return result


def ti_candidates(session: Session) -> dict[str, list[tuple[int, str, tuple[int, ...]]]]:
    """Кандидаты по ролям: {role: [(team_id, team_name, account_ids), ...]}."""
    teams = ti_team_ids()
    by_role: dict[str, list[tuple[int, str, tuple[int, ...]]]] = {}

    for team_id, compendium_name in teams.items():
        slots = session.scalars(
            select(TeamRosterSlot).where(TeamRosterSlot.team_id == team_id)
        ).all()
        grouped: dict[str, list[int]] = defaultdict(list)
        for slot in slots:
            grouped[slot.role].append(slot.account_id)

        for role, account_ids in grouped.items():
            by_role.setdefault(role, []).append(
                (team_id, compendium_name, tuple(account_ids))
            )

    return by_role


def latest_rating_run(session: Session) -> str | None:
    """Идентификатор последнего пересчёта рейтингов.

    По нему кэшируется всё, что считается поверх рейтингов: пересчитали их —
    и производные (например, калибровка прогноза) обязаны пересчитаться тоже.
    """
    return session.scalar(select(TeamRating.run_id).order_by(TeamRating.id.desc()))


def latest_ratings(session: Session) -> dict[int, tuple[float, float, float]]:
    """Последний снимок рейтинга каждой команды: (rating, rd, volatility)."""
    latest_run = latest_rating_run(session)
    if latest_run is None:
        return {}

    rows = session.scalars(
        select(TeamRating)
        .where(TeamRating.run_id == latest_run)
        .order_by(TeamRating.as_of)
    )
    result: dict[int, tuple[float, float, float]] = {}
    for row in rows:
        result[row.team_id] = (row.rating, row.rd, row.volatility)
    return result
