"""HTTP API аналитика."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..analytics.glicko2 import Rating
from ..analytics.predictions_config import load_predictions_config
from ..analytics.simulate import (
    BRACKET_SLOTS,
    BracketSimulator,
    SwissSimulator,
    optimise_bracket_predictions,
    optimise_group_predictions,
)
from ..db.models import Player, Team, TeamRating
from ..db.session import get_db
from ..fantasy.advisor import EmblemAdvisor
from ..fantasy.presets import neutral_banner
from ..fantasy.projection import RoleProjector, optimise_banner, recommend_roster
from ..fantasy.rules import load_rules
from ..fantasy.scoring import Banner, Emblem
from ..ingest.opendota import OpenDotaClient
from ..ingest.pipeline import ingest_pro_feed, ingest_team_history, resolve_compendium_teams
from ..ingest.stat_mapping import STAT_SOURCES
from ..services.analysis import (
    ROLE_SIZES,
    build_role_history,
    infer_team_roles,
    latest_ratings,
    recompute_ratings,
    ti_candidates,
)
from ..services.profiles import (
    load_heroes,
    player_directory,
    player_profile,
    team_directory,
    team_profile,
)
from ..settings import settings
from . import schemas

log = logging.getLogger(__name__)

router = APIRouter()


def _client() -> OpenDotaClient:
    return OpenDotaClient(
        api_key=settings.opendota_api_key,
        cache_dir=settings.cache_dir,
        rate_limit_per_minute=settings.opendota_rate_limit,
    )


def _since(days: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=days)


# --- конфигурация -------------------------------------------------------------


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/config/fantasy", response_model=schemas.FantasyRulesOut)
def fantasy_rules() -> schemas.FantasyRulesOut:
    """Правила начисления очков — фронтенд рисует конструктор баннера по ним."""
    rules = load_rules()
    return schemas.FantasyRulesOut(
        version=rules.version,
        source=rules.source,
        stats=[
            {
                "key": s.key,
                "label": s.label,
                "color": str(s.color),
                "kind": str(s.kind),
                "per_unit": s.per_unit,
                "base": s.base,
                "value_if_true": s.value_if_true,
                "max_points": s.max_points,
            }
            for s in rules.stats.values()
        ],
        qualities=rules.qualities,
        traits=[
            {
                "key": t.key,
                "label": t.label,
                "description": t.description,
                "condition": str(t.condition),
                "effects": [{"scope": str(e.scope), "amount": e.amount} for e in t.effects],
            }
            for t in rules.traits.values()
        ],
        banner_slots=rules.banner.slots,
        trait_bonus_mode=rules.trait_bonus_mode,
        sources=[
            schemas.StatSourceOut(
                stat=key,
                label=rules.stats[key].label,
                color=str(rules.stats[key].color),
                availability=str(source.availability),
                note=source.note,
            )
            for key, source in STAT_SOURCES.items()
        ],
    )


@router.get("/config/predictions")
def predictions_config() -> dict:
    config = load_predictions_config()
    return {
        "version": config.version,
        "event": config.event,
        "teams": list(config.team_names),
        "team_ids": config.team_ids,
        "buckets": [
            {"key": b.key, "label": b.label, "description": b.description, "slots": b.slots}
            for b in config.group_stage.buckets
        ],
        "group_points": config.group_stage.points.by_correct,
        "playoff_points": config.playoffs.points.by_correct,
        "bracket_slots": list(BRACKET_SLOTS),
    }


# --- команды и рейтинги -------------------------------------------------------


@router.get("/teams", response_model=list[schemas.TeamOut])
def list_teams(
    session: Session = Depends(get_db),
    compendium_only: bool = Query(False, description="только участники TI15"),
) -> list[schemas.TeamOut]:
    query = select(Team)
    if compendium_only:
        query = query.where(Team.compendium_name.is_not(None))

    ratings = latest_ratings(session)
    result: list[schemas.TeamOut] = []
    for team in session.scalars(query):
        rating = ratings.get(team.team_id)
        out = schemas.TeamOut(
            team_id=team.team_id,
            name=team.name,
            tag=team.tag,
            compendium_name=team.compendium_name,
        )
        if rating:
            out.rating, out.rd, out.volatility = rating
            out.is_listable = Rating(*rating).is_listable()
        result.append(out)

    result.sort(key=lambda t: -(t.rating or 0))
    return result


@router.get("/teams/{team_id}/rating-history", response_model=schemas.RatingHistoryOut)
def rating_history(
    team_id: int, session: Session = Depends(get_db)
) -> schemas.RatingHistoryOut:
    latest_run = session.scalar(select(TeamRating.run_id).order_by(TeamRating.id.desc()))
    if latest_run is None:
        raise HTTPException(404, "рейтинги ещё не считались — вызовите /ratings/recompute")

    rows = session.scalars(
        select(TeamRating)
        .where(TeamRating.team_id == team_id, TeamRating.run_id == latest_run)
        .order_by(TeamRating.as_of)
    ).all()
    team = session.get(Team, team_id)

    return schemas.RatingHistoryOut(
        team_id=team_id,
        name=team.name if team else None,
        points=[
            schemas.RatingPoint(
                as_of=r.as_of, rating=r.rating, rd=r.rd, matches_played=r.matches_played
            )
            for r in rows
        ],
    )


@router.post("/ratings/recompute")
def ratings_recompute(
    session: Session = Depends(get_db),
    history_days: int = Query(365, ge=30, le=1500),
    period_days: int = Query(7, ge=1, le=30),
) -> dict:
    history = recompute_ratings(
        session, history_days=history_days, period_days=period_days
    )
    return {
        "teams": len(history.current),
        "snapshots": len(history.snapshots),
        "listable": len(history.listable()),
    }


# --- Predictions --------------------------------------------------------------


def _tournament_ratings(session: Session, team_ids: list[int] | None) -> dict[int, Rating]:
    """Рейтинги 16 участников: явный список, участники компендиума или топ-16."""
    ratings = latest_ratings(session)
    if not ratings:
        raise HTTPException(400, "нет рейтингов — вызовите /ratings/recompute")

    if team_ids:
        missing = [t for t in team_ids if t not in ratings]
        if missing:
            raise HTTPException(400, f"нет рейтинга для команд: {missing}")
        chosen = team_ids
    else:
        compendium = list(
            session.scalars(select(Team.team_id).where(Team.compendium_name.is_not(None)))
        )
        chosen = [t for t in compendium if t in ratings]
        if len(chosen) != 16:
            chosen = sorted(ratings, key=lambda t: -ratings[t][0])[:16]

    return {t: Rating(*ratings[t]) for t in chosen}


@router.get("/predictions/group", response_model=schemas.GroupPredictionOut)
def predict_group(
    session: Session = Depends(get_db),
    simulations: int = Query(20_000, ge=200, le=200_000),
    seed: int | None = None,
    team_ids: list[int] | None = Query(None),
) -> schemas.GroupPredictionOut:
    """Распределение по корзинам Swiss и оптимальный набор предсказаний."""
    config = load_predictions_config().group_stage
    ratings = _tournament_ratings(session, team_ids)
    if len(ratings) != config.teams:
        raise HTTPException(400, f"нужно {config.teams} команд, найдено {len(ratings)}")

    simulator = SwissSimulator(ratings, config, seed=seed)
    result = simulator.run(simulations=simulations)
    plan = optimise_group_predictions(result, config.slots(), config.points)

    names = {
        t.team_id: t.name for t in session.scalars(select(Team).where(Team.team_id.in_(ratings)))
    }
    bucket_labels = {b.key: b.label for b in config.buckets}

    teams_out = [
        schemas.BucketProbabilityOut(
            team_id=team_id,
            name=names.get(team_id),
            probabilities={
                key: round(float(result.probabilities[i, j]), 4)
                for j, key in enumerate(result.bucket_keys)
            },
            advance=round(float(result.advance_probability[i]), 4),
            expected_series=round(result.expected_series(team_id), 2),
        )
        for i, team_id in enumerate(result.team_ids)
    ]
    teams_out.sort(key=lambda t: -t.advance)

    return schemas.GroupPredictionOut(
        simulations=result.simulations,
        teams=teams_out,
        plan=[
            schemas.PredictionPickOut(
                key=str(names.get(int(team), team)),
                pick=str(bucket),
                label=bucket_labels.get(str(bucket)),
                team_id=int(team),
            )
            for team, bucket in plan.assignment.items()
        ],
        expected_points=round(plan.expected_points, 1),
        expected_correct=round(plan.expected_correct, 2),
        points_percentiles={k: round(v, 1) for k, v in plan.points_percentiles.items()},
    )


@router.get("/predictions/bracket", response_model=schemas.BracketPredictionOut)
def predict_bracket(
    session: Session = Depends(get_db),
    simulations: int = Query(20_000, ge=200, le=200_000),
    seed: int | None = None,
    team_ids: list[int] = Query(..., description="8 команд плей-офф в порядке посева"),
) -> schemas.BracketPredictionOut:
    config = load_predictions_config().playoffs
    if len(team_ids) != config.teams:
        raise HTTPException(400, f"нужно {config.teams} команд в порядке посева")

    ratings = latest_ratings(session)
    missing = [t for t in team_ids if t not in ratings]
    if missing:
        raise HTTPException(400, f"нет рейтинга для команд: {missing}")

    seeded = {t: Rating(*ratings[t]) for t in team_ids}
    result = BracketSimulator(seeded, config, seed=seed).run(simulations=simulations)
    plan = optimise_bracket_predictions(result, config.points)

    names = {
        t.team_id: t.name for t in session.scalars(select(Team).where(Team.team_id.in_(team_ids)))
    }

    return schemas.BracketPredictionOut(
        simulations=result.simulations,
        champion_probability={k: round(v, 4) for k, v in result.champion_probability.items()},
        plan=[
            schemas.BracketMatchOut(
                match_key=str(key),
                pick_team_id=int(team_id),
                pick_name=names.get(int(team_id)),
                probability=round(result.match_probabilities(str(key)).get(int(team_id), 0.0), 4),
            )
            for key, team_id in plan.assignment.items()
        ],
        expected_points=round(plan.expected_points, 1),
        expected_correct=round(plan.expected_correct, 2),
    )


# --- Fantasy ------------------------------------------------------------------


@router.get("/fantasy/roles/{team_id}", response_model=schemas.RolesOut)
def team_roles(
    team_id: int,
    session: Session = Depends(get_db),
    history_days: int = Query(120, ge=7, le=730),
) -> schemas.RolesOut:
    """Кто в команде core duo, mid и support duo — по фактической игре."""
    roles = infer_team_roles(session, team_id, since=_since(history_days))
    if not roles:
        raise HTTPException(404, f"нет данных по команде {team_id}")

    account_ids = [a for group in roles.values() for a in group]
    names = {
        p.account_id: p.name
        for p in session.scalars(select(Player).where(Player.account_id.in_(account_ids)))
    }
    team = session.get(Team, team_id)

    return schemas.RolesOut(
        team_id=team_id,
        team_name=team.name if team else None,
        roles={role: list(group) for role, group in roles.items()},
        player_names=names,
    )


def _role_history(session: Session, request) -> tuple:
    """История роли по запросу. Работает со всеми схемами, где есть team_id,
    role и history_days; явный список игроков — необязательное поле."""
    if request.role not in ROLE_SIZES:
        raise HTTPException(400, f"роль должна быть одной из {sorted(ROLE_SIZES)}")

    account_ids = getattr(request, "account_ids", None)
    if not account_ids:
        roles = infer_team_roles(session, request.team_id, since=_since(request.history_days))
        account_ids = list(roles.get(request.role, ()))
    if not account_ids:
        raise HTTPException(404, f"не удалось определить игроков роли {request.role}")

    history = build_role_history(
        session,
        request.team_id,
        request.role,
        account_ids,
        since=_since(request.history_days),
    )
    if not history.games:
        raise HTTPException(
            404,
            "нет разобранных матчей за период — сначала загрузите историю "
            "через /ingest/team/{team_id}",
        )
    return history, account_ids


@router.post("/fantasy/project", response_model=schemas.ProjectionOut)
def project_role(
    request: schemas.ProjectionRequest = Body(...),
    session: Session = Depends(get_db),
) -> schemas.ProjectionOut:
    """Ожидаемые очки роли за период с заданным баннером."""
    history, _ = _role_history(session, request)
    banner = Banner(
        emblems=tuple(
            Emblem(stat=e.stat, quality=e.quality, trait=e.trait) for e in request.banner.emblems
        ),
        role=request.role,
    )
    projector = RoleProjector()
    try:
        projection = projector.project(
            history,
            banner,
            simulations=request.simulations,
            title_multiplier=request.title_multiplier,
            series_distribution=request.series_distribution,
            series_lengths=request.series_lengths,
        )
    except (ValueError, KeyError) as exc:
        raise HTTPException(400, str(exc)) from exc

    return schemas.ProjectionOut(
        role=projection.role,
        team_id=projection.team_id,
        team_name=history.team_name,
        player_names=list(history.player_names),
        mean=round(projection.mean, 1),
        median=round(projection.median, 1),
        floor_p5=round(projection.floor, 1),
        ceiling_p95=round(projection.ceiling, 1),
        std=round(projection.std, 1),
        games_used=projection.games_used,
        expected_series=projection.expected_series,
        unavailable_stats=list(projection.unavailable_stats),
    )


@router.post("/fantasy/optimise-banner", response_model=list[schemas.BannerOptionOut])
def optimise_banner_route(
    request: schemas.BannerOptimiseRequest = Body(...),
    session: Session = Depends(get_db),
) -> list[schemas.BannerOptionOut]:
    """Лучшая раскладка из доступных эмблем (порядок учитывает соседство)."""
    history, _ = _role_history(session, request)
    emblems = [
        Emblem(stat=e.stat, quality=e.quality, trait=e.trait) for e in request.available_emblems
    ]
    projector = RoleProjector()
    try:
        options = optimise_banner(
            projector,
            history,
            emblems,
            slots=request.slots,
            shortlist=request.shortlist,
            simulations=request.simulations,
            top_n=request.top_n,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    return [
        schemas.BannerOptionOut(
            emblems=[
                schemas.EmblemIn(stat=e.stat, quality=e.quality, trait=e.trait)
                for e in option.banner.emblems
            ],
            mean=round(option.projection.mean, 1),
            ceiling_p95=round(option.projection.ceiling, 1),
            floor_p5=round(option.projection.floor, 1),
        )
        for option in options
    ]


@router.post("/fantasy/roster", response_model=schemas.RosterResponse)
def recommend_roster_route(
    request: schemas.RosterRequest = Body(default=schemas.RosterRequest()),
    session: Session = Depends(get_db),
) -> schemas.RosterResponse:
    """Кандидаты по ролям среди участников TI15 и лучшие сочетания.

    Все кандидаты роли считаются по одному и тому же баннеру — иначе сравнение
    команд превратится в сравнение баннеров. Ограничение «три разные команды» —
    из механики компендиума.
    """
    candidates = ti_candidates(session)
    if not candidates:
        raise HTTPException(
            400,
            "игроки TI15 не размечены — выполните ingest истории команд "
            "(cli.py ingest-ti) и повторите",
        )

    banners: dict[str, Banner] = {}
    for role in candidates:
        override = (request.banners or {}).get(role)
        if override:
            banners[role] = Banner(
                emblems=tuple(
                    Emblem(stat=e.stat, quality=e.quality, trait=e.trait) for e in override
                ),
                role=role,
            )
        else:
            banners[role] = neutral_banner(role)

    projector = RoleProjector()
    projections: dict[str, dict[int, object]] = {}
    out_candidates: dict[str, list[schemas.RosterCandidateOut]] = {}
    skipped: list[str] = []

    for role, entries in candidates.items():
        for team_id, team_name, account_ids in entries:
            history = build_role_history(
                session, team_id, role, account_ids, since=_since(request.history_days)
            )
            if len(history.games) < request.min_games:
                skipped.append(f"{team_name} / {role}: {len(history.games)} карт")
                continue
            projection = projector.project(
                history,
                banners[role],
                simulations=request.simulations,
                series_distribution={request.series: 1.0},
            )
            projections.setdefault(role, {})[team_id] = projection
            out_candidates.setdefault(role, []).append(
                schemas.RosterCandidateOut(
                    role=role,
                    team_id=team_id,
                    team_name=team_name,
                    player_names=list(history.player_names),
                    mean=round(projection.mean, 1),
                    floor_p5=round(projection.floor, 1),
                    ceiling_p95=round(projection.ceiling, 1),
                    games_used=projection.games_used,
                )
            )

    for role in out_candidates:
        out_candidates[role].sort(key=lambda c: -c.mean)

    rosters: list[schemas.RosterOut] = []
    if len(projections) == len(ROLE_SIZES):
        team_names = {
            team_id: name
            for entries in candidates.values()
            for team_id, name, _ in entries
        }
        for roster in recommend_roster(projections, top_n=request.top_n):
            summary = roster.summary()
            rosters.append(
                schemas.RosterOut(
                    expected_total=summary["expected_total"],
                    p5=summary["p5"],
                    p95=summary["p95"],
                    picks=[
                        schemas.RosterPickOut(
                            role=pick.role,
                            team_id=pick.team_id,
                            team_name=team_names.get(pick.team_id),
                            mean=round(pick.projection.mean, 1),
                        )
                        for pick in roster.picks
                    ],
                )
            )

    return schemas.RosterResponse(
        candidates=out_candidates,
        rosters=rosters,
        banners={
            role: [
                schemas.EmblemIn(stat=e.stat, quality=e.quality, trait=e.trait)
                for e in banner.emblems
            ]
            for role, banner in banners.items()
        },
        skipped=skipped,
    )


# --- анализатор эмблем --------------------------------------------------------


def _stat_value_out(value) -> schemas.StatValueOut:
    return schemas.StatValueOut(
        stat=value.stat,
        label=value.label,
        color=value.color,
        units_per_game=round(value.units_per_game, 2),
        base_points=round(value.base_points, 1),
        p95_points=round(value.p95_points, 1),
        p5_points=round(value.p5_points, 1),
        availability=str(value.availability),
        negligible=value.is_negligible,
        median_points=round(value.median_points, 1),
        p75_points=round(value.p75_points, 1),
        hit_rate=round(value.hit_rate, 3),
        trend=round(value.trend, 3) if value.trend is not None else None,
    )


@router.post("/fantasy/stat-report", response_model=list[schemas.StatValueOut])
def stat_report(
    request: schemas.StatReportRequest = Body(...),
    session: Session = Depends(get_db),
) -> list[schemas.StatValueOut]:
    """Во что превращается каждый доступный роли стат — по её реальным матчам.

    Показывает не цену стата из глоссария, а произведение цены на объём: сколько
    очков он приносит именно этим игрокам.
    """
    history, _ = _role_history(session, request)
    advisor = EmblemAdvisor()
    try:
        values = advisor.stat_values(
            history, role=request.role, include_unavailable=request.include_unavailable
        )
    except KeyError as exc:
        raise HTTPException(400, str(exc)) from exc
    return [_stat_value_out(v) for v in values]


@router.post("/fantasy/best-banner", response_model=list[schemas.BannerAdviceOut])
def best_banner(
    request: schemas.BannerAdviceRequest = Body(...),
    session: Session = Depends(get_db),
) -> list[schemas.BannerAdviceOut]:
    """Лучший баннер для роли с учётом цветов слотов, качеств и трейтов."""
    history, _ = _role_history(session, request)
    advisor = EmblemAdvisor()
    try:
        advices = advisor.optimise_banner(
            history,
            role=request.role,
            qualities=request.qualities,
            traits=request.traits,
            simulate=request.simulate,
            simulations=request.simulations,
            top_n=request.top_n,
            series_distribution={request.series: 1.0},
        )
    except (ValueError, KeyError) as exc:
        raise HTTPException(400, str(exc)) from exc

    return [
        schemas.BannerAdviceOut(
            role=advice.role,
            team_id=advice.team_id,
            team_name=history.team_name,
            player_names=list(history.player_names),
            expected_card_points=round(advice.expected_card_points, 1),
            period_mean=round(advice.projection.mean, 1) if advice.projection else None,
            period_ceiling=(
                round(advice.projection.ceiling, 1) if advice.projection else None
            ),
            slots=[
                schemas.SlotAdviceOut(
                    slot=slot.slot,
                    color=slot.color,
                    stat=slot.emblem.stat,
                    label=load_rules().stats[slot.emblem.stat].label,
                    quality=slot.emblem.quality,
                    trait=slot.emblem.trait,
                    percent=round(slot.percent, 1),
                    base_points=round(slot.base_points, 1),
                    points=round(slot.points, 1),
                    alternatives=[_stat_value_out(a) for a in slot.alternatives],
                )
                for slot in advice.slots
            ],
        )
        for advice in advices
    ]


@router.post("/fantasy/evaluate-swap", response_model=schemas.SwapOut)
def evaluate_swap(
    request: schemas.SwapRequest = Body(...),
    session: Session = Depends(get_db),
) -> schemas.SwapOut:
    """Что даст замена одной эмблемы — главный вопрос перед каждым роллом."""
    history, _ = _role_history(session, request)
    banner = Banner(
        emblems=tuple(
            Emblem(stat=e.stat, quality=e.quality, trait=e.trait)
            for e in request.banner.emblems
        ),
        role=request.role,
    )
    try:
        result = EmblemAdvisor().evaluate_swap(
            history,
            banner,
            request.slot,
            Emblem(
                stat=request.candidate.stat,
                quality=request.candidate.quality,
                trait=request.candidate.trait,
            ),
        )
    except (ValueError, KeyError) as exc:
        raise HTTPException(400, str(exc)) from exc
    return schemas.SwapOut(**{k: round(v, 2) for k, v in result.items()})


@router.get("/fantasy/stat-ranking/{stat}", response_model=list[schemas.StatRankingOut])
def stat_ranking(
    stat: str,
    session: Session = Depends(get_db),
    role: str | None = Query(None, description="ограничить одной ролью"),
    history_days: int = Query(180, ge=7, le=730),
    min_games: int = Query(5, ge=1),
) -> list[schemas.StatRankingOut]:
    """Кто из участников TI15 лучше всех отрабатывает конкретный стат."""
    candidates = ti_candidates(session)
    if not candidates:
        raise HTTPException(400, "игроки TI15 не размечены — выполните ingest истории")

    histories = []
    team_names: dict[int, str] = {}
    for role_key, entries in candidates.items():
        if role and role_key != role:
            continue
        for team_id, team_name, account_ids in entries:
            team_names[team_id] = team_name
            histories.append(
                build_role_history(
                    session,
                    team_id,
                    role_key,
                    account_ids,
                    since=_since(history_days),
                )
            )

    try:
        ranking = EmblemAdvisor().rank_for_stat(
            stat, histories, team_names=team_names, min_games=min_games
        )
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc

    return [
        schemas.StatRankingOut(
            stat=row.stat,
            team_id=row.team_id,
            team_name=row.team_name,
            role=row.role,
            player_names=list(row.player_names),
            units_per_game=round(row.units_per_game, 2),
            base_points=round(row.base_points, 1),
            p95_points=round(row.p95_points, 1),
            games=row.games,
        )
        for row in ranking
    ]


@router.post("/fantasy/players", response_model=list[schemas.PlayerProfileOut])
def player_report(
    request: schemas.StatReportRequest = Body(...),
    session: Session = Depends(get_db),
) -> list[schemas.PlayerProfileOut]:
    """Разбивка роли по игрокам: кто именно набирает очки внутри пары.

    В зачёт идёт среднее по игрокам роли, поэтому пара, где всё делает один
    человек, и пара, где оба, стоят одинаково — но ведут себя по-разному, если
    один из двоих провалит серию.
    """
    history, _ = _role_history(session, request)
    names = {
        p.account_id: p.name
        for p in session.scalars(
            select(Player).where(Player.account_id.in_(history.account_ids))
        )
    }
    return [
        schemas.PlayerProfileOut(
            account_id=profile.account_id,
            name=profile.name,
            games=profile.games,
            values=[_stat_value_out(v) for v in profile.values],
        )
        for profile in EmblemAdvisor().player_values(history, names=names)
    ]


@router.post("/fantasy/timeline", response_model=schemas.TimelineOut)
def role_timeline(
    request: schemas.StatReportRequest = Body(...),
    session: Session = Depends(get_db),
) -> schemas.TimelineOut:
    """Очки за каждую карту с нейтральным баннером — форма роли во времени.

    Баннер нейтральный намеренно: кривая сравнима между командами и не зависит
    от того, какие эмблемы выберет пользователь. Важна не абсолютная величина, а
    форма и разброс: в зачёт идут две лучшие карты серии, и роль с редкими
    высокими картами может стоить дороже ровной.
    """
    history, _ = _role_history(session, request)
    projector = RoleProjector()
    banner = neutral_banner(request.role)

    base = projector.base_matrix(history)
    multipliers = projector.scorer.emblem_multipliers(banner)
    vector = [0.0] * base.shape[1]
    for emblem, multiplier in zip(banner.emblems, multipliers, strict=True):
        vector[projector._stat_index[emblem.stat]] = multiplier

    scores = base @ vector
    return schemas.TimelineOut(
        role=request.role,
        team_id=request.team_id,
        banner=[
            schemas.EmblemIn(stat=e.stat, quality=e.quality, trait=e.trait)
            for e in banner.emblems
        ],
        points=[
            schemas.TimelinePointOut(
                d=game.start_time.date().isoformat(),
                p=round(float(score)),
                w=None if game.won is None else int(game.won),
            )
            for game, score in zip(history.games, scores, strict=True)
        ],
    )


@router.post("/fantasy/inventory", response_model=schemas.InventoryResponse)
def inventory_fit(
    request: schemas.InventoryRequest = Body(...),
    session: Session = Depends(get_db),
    simulate_top: int = Query(5, ge=0, le=16, description="для скольких пар считать период"),
    simulations: int = Query(3000, ge=200, le=50_000),
) -> schemas.InventoryResponse:
    """Под кого ставить эмблемы, которые уже есть.

    Цвета слотов фиксированы ролью, качества и трейты в инвентаре заданы —
    свободы остаётся ровно две: какие три эмблемы взять и в каком порядке
    поставить (соседство меняет проценты). Перебор идёт по каждой роли каждой
    команды, результат — рейтинг пар.
    """
    if not request.inventory:
        raise HTTPException(400, "инвентарь пуст")

    rules = load_rules()
    inventory = [
        Emblem(stat=e.stat, quality=e.quality, trait=e.trait) for e in request.inventory
    ]
    unknown = [e.stat for e in inventory if e.stat not in rules.stats]
    if unknown:
        raise HTTPException(400, f"неизвестные статы: {', '.join(sorted(set(unknown)))}")

    candidates = ti_candidates(session)
    if not candidates:
        raise HTTPException(400, "игроки TI15 не размечены — выполните ingest истории")

    advisor = EmblemAdvisor()

    # Нехватку считаем по всем ролям правил, а не только по тем, где есть
    # размеченные ростеры: пользователю важно знать, что саппорта он из этого
    # инвентаря не соберёт, даже если саппортов в базе пока нет.
    gaps: dict[str, list[str]] = {}
    for role_key in rules.role_slots:
        if request.role and role_key != request.role:
            continue
        missing = advisor.inventory_gaps(inventory, role_key)
        if missing:
            gaps[role_key] = list(missing)

    histories = []
    for role_key, entries in candidates.items():
        if request.role and role_key != request.role:
            continue
        if role_key in gaps:
            continue
        for team_id, team_name, account_ids in entries:
            history = build_role_history(
                session,
                team_id,
                role_key,
                account_ids,
                since=_since(request.history_days),
            )
            history.team_name = team_name
            histories.append(history)

    fits = advisor.rank_inventory(inventory, histories, min_games=request.min_games)[
        : request.top_n
    ]

    projector = RoleProjector()
    by_key = {(h.team_id, h.role): h for h in histories}
    rows: list[schemas.InventoryFitOut] = []
    for index, fit in enumerate(fits):
        period_mean = period_ceiling = None
        if index < simulate_top:
            projection = projector.project(
                by_key[(fit.team_id, fit.role)],
                fit.banner(),
                simulations=simulations,
            )
            period_mean = round(projection.mean, 1)
            period_ceiling = round(projection.ceiling, 1)
        rows.append(
            schemas.InventoryFitOut(
                role=fit.role,
                team_id=fit.team_id,
                team_name=fit.team_name,
                player_names=list(fit.player_names),
                expected_card_points=round(fit.expected_card_points, 1),
                period_mean=period_mean,
                period_ceiling=period_ceiling,
                games=fit.games,
                unused=[
                    schemas.EmblemIn(stat=e.stat, quality=e.quality, trait=e.trait)
                    for e in fit.unused
                ],
                slots=[
                    schemas.SlotAdviceOut(
                        slot=slot.slot,
                        color=slot.color,
                        stat=slot.emblem.stat,
                        label=load_rules().stats[slot.emblem.stat].label,
                        quality=slot.emblem.quality,
                        trait=slot.emblem.trait,
                        percent=round(slot.percent, 1),
                        base_points=round(slot.base_points, 1),
                        points=round(slot.points, 1),
                    )
                    for slot in fit.slots
                ],
            )
        )

    return schemas.InventoryResponse(fits=rows, gaps=gaps)


@router.post("/fantasy/titles", response_model=list[schemas.TitleAdviceOut])
def title_advice(
    request: schemas.StatReportRequest = Body(...),
    session: Session = Depends(get_db),
) -> list[schemas.TitleAdviceOut]:
    """Какие Coaching Titles выгодны этой роли — по её же матчам."""
    history, _ = _role_history(session, request)
    return [
        schemas.TitleAdviceOut(
            key=t.key,
            label=t.label,
            bonus=t.bonus,
            condition=t.condition,
            hit_rate=round(t.hit_rate, 3) if t.hit_rate is not None else None,
            expected_bonus=(
                round(t.expected_bonus, 4) if t.expected_bonus is not None else None
            ),
            estimator=t.estimator,
            note=t.note,
            note_key=t.note_key,
            note_params=dict(t.note_params),
        )
        for t in EmblemAdvisor().title_advice(history, heroes=load_heroes())
    ]


@router.post("/fantasy/heroes", response_model=list[schemas.HeroPickOut])
def role_hero_pool(
    request: schemas.StatReportRequest = Body(...),
    session: Session = Depends(get_db),
    limit: int = Query(15, ge=1, le=50),
) -> list[schemas.HeroPickOut]:
    """Кого эта роль берёт: герои, карты, победы и кто из пары их играет.

    По этому же пулу оцениваются префиксы титулов — «Crimson» и остальные дают
    процент за героя определённого цвета, и цвет решает не вкус, а список.
    """
    history, _ = _role_history(session, request)
    return [
        schemas.HeroPickOut(
            hero_id=pick.hero_id,
            name=pick.name,
            games=pick.games,
            wins=pick.wins,
            players=[
                {"account_id": account, "games": count} for account, count in pick.players
            ],
        )
        for pick in EmblemAdvisor().hero_pool(history, heroes=load_heroes(), limit=limit)
    ]


# --- профили команд и игроков -------------------------------------------------


def _match_row_out(row) -> schemas.MatchRowOut:
    return schemas.MatchRowOut(
        match_id=row.match_id,
        start_time=row.start_time,
        duration=row.duration,
        league_name=row.league_name,
        opponent_id=row.opponent_id,
        opponent_name=row.opponent_name,
        won=row.won,
        is_parsed=row.is_parsed,
        hero_id=row.hero_id,
        hero_name=row.hero_name,
        kills=row.kills,
        deaths=row.deaths,
        assists=row.assists,
        gpm=row.gpm,
        xpm=row.xpm,
        net_worth=row.net_worth,
    )


def _split_out(split) -> schemas.SplitOut | None:
    if split is None:
        return None
    return schemas.SplitOut(key=split.key, games=split.games, wins=split.wins)


def _trends_out(trends) -> schemas.TrendsOut | None:
    if trends is None:
        return None
    return schemas.TrendsOut(
        form=_split_out(trends.form),
        baseline=_split_out(trends.baseline),
        streak=trends.streak,
        sides=[_split_out(s) for s in trends.sides],
        durations=[_split_out(s) for s in trends.durations],
    )


def _player_page_out(profile) -> schemas.PlayerPageOut:
    return schemas.PlayerPageOut(
        account_id=profile.account_id,
        name=profile.name,
        team_id=profile.team_id,
        team_name=profile.team_name,
        role=profile.role,
        position=profile.position,
        games=profile.games,
        parsed_games=profile.parsed_games,
        wins=profile.wins,
        win_rate=round(profile.win_rate, 4),
        first_game=profile.first_game,
        last_game=profile.last_game,
        averages={k: round(v, 2) for k, v in profile.averages.items()},
        fantasy_units={k: round(v, 3) for k, v in profile.fantasy_units.items()},
        heroes=[
            schemas.HeroRowOut(hero_id=h.hero_id, name=h.name, games=h.games, wins=h.wins)
            for h in profile.heroes
        ],
        matches=[_match_row_out(m) for m in profile.matches],
        trends=_trends_out(profile.trends),
        lanes=profile.lanes,
        hero_pool=(
            schemas.HeroPoolOut(
                distinct=profile.hero_pool.distinct,
                top3_share=round(profile.hero_pool.top3_share, 3),
            )
            if profile.hero_pool
            else None
        ),
        fantasy_form=(
            schemas.FantasyFormOut(
                maps=profile.fantasy_form.maps,
                mean=round(profile.fantasy_form.mean),
                median=round(profile.fantasy_form.median),
                best=round(profile.fantasy_form.best),
                p90=round(profile.fantasy_form.p90),
                spread=round(profile.fantasy_form.spread, 3),
            )
            if profile.fantasy_form
            else None
        ),
    )


@router.get("/profiles/teams", response_model=list[schemas.TeamListItemOut])
def profile_team_list(session: Session = Depends(get_db)) -> list[schemas.TeamListItemOut]:
    """Справочник команд: участники TI сверху, дальше все, у кого есть матчи."""
    return [schemas.TeamListItemOut(**row) for row in team_directory(session)]


@router.get("/profiles/players", response_model=list[schemas.PlayerListItemOut])
def profile_player_list(
    session: Session = Depends(get_db),
    ti_only: bool = Query(False, description="только размеченные игроки TI15"),
) -> list[schemas.PlayerListItemOut]:
    """Справочник игроков: ник, команда, роль, сколько карт в базе."""
    return [
        schemas.PlayerListItemOut(**row) for row in player_directory(session, ti_only=ti_only)
    ]


@router.get("/profiles/teams/{team_id}", response_model=schemas.TeamPageOut)
def profile_team(
    team_id: int,
    session: Session = Depends(get_db),
    days: int | None = Query(180, ge=7, le=3650),
    matches: int = Query(30, ge=0, le=200),
) -> schemas.TeamPageOut:
    """Полный профиль команды: рейтинг с историей, матчи, состав, средние."""
    profile = team_profile(session, team_id, days=days, match_limit=matches)
    if profile is None:
        raise HTTPException(404, f"команда {team_id} не найдена")

    return schemas.TeamPageOut(
        team_id=profile.team_id,
        name=profile.name,
        compendium_name=profile.compendium_name,
        tag=profile.tag,
        rating=round(profile.rating, 1) if profile.rating else None,
        rd=round(profile.rd, 1) if profile.rd else None,
        volatility=round(profile.volatility, 4) if profile.volatility else None,
        rating_history=[
            {"as_of": as_of.date().isoformat(), "rating": round(rating, 1), "rd": round(rd, 1)}
            for as_of, rating, rd in profile.rating_history
        ],
        games=profile.games,
        parsed_games=profile.parsed_games,
        wins=profile.wins,
        win_rate=round(profile.win_rate, 4),
        first_game=profile.first_game,
        last_game=profile.last_game,
        roster=[_player_page_out(p) for p in profile.roster],
        matches=[_match_row_out(m) for m in profile.matches],
        team_averages={k: round(v, 2) for k, v in profile.team_averages.items()},
        opponents=[
            {"team_id": team_id, "name": name, "games": games, "wins": wins}
            for team_id, name, games, wins in profile.opponents
        ],
        trends=_trends_out(profile.trends),
        opponent_rating=(
            round(profile.opponent_rating, 1) if profile.opponent_rating else None
        ),
        vs_stronger=_split_out(profile.vs_stronger),
        first_blood_rate=(
            round(profile.first_blood_rate, 3)
            if profile.first_blood_rate is not None
            else None
        ),
    )


@router.get("/profiles/players/{account_id}", response_model=schemas.PlayerPageOut)
def profile_player(
    account_id: int,
    session: Session = Depends(get_db),
    days: int | None = Query(180, ge=7, le=3650),
    matches: int = Query(25, ge=0, le=200),
) -> schemas.PlayerPageOut:
    """Полный профиль игрока: средние, герои, матчи, команда и роль."""
    profile = player_profile(session, account_id, days=days, match_limit=matches)
    if profile is None:
        raise HTTPException(404, f"игрок {account_id} не найден")
    return _player_page_out(profile)


# --- ingest -------------------------------------------------------------------


@router.post("/ingest/pro-feed", response_model=schemas.IngestResultOut)
async def ingest_feed(
    session: Session = Depends(get_db),
    days_back: int = Query(30, ge=1, le=365),
    max_pages: int = Query(10, ge=1, le=100),
) -> schemas.IngestResultOut:
    """Забрать свежие про-матчи. Расход лимита: примерно 1 запрос на матч."""
    async with _client() as client:
        result = await ingest_pro_feed(
            client, session, days_back=days_back, max_pages=max_pages
        )
    return schemas.IngestResultOut(**result)


@router.post("/ingest/team/{team_id}", response_model=schemas.IngestResultOut)
async def ingest_team(
    team_id: int,
    session: Session = Depends(get_db),
    days_back: int = Query(120, ge=7, le=730),
) -> schemas.IngestResultOut:
    async with _client() as client:
        result = await ingest_team_history(client, session, team_id, days_back=days_back)
    return schemas.IngestResultOut(**result)


@router.post("/ingest/resolve-teams")
async def ingest_resolve_teams(session: Session = Depends(get_db)) -> list[dict]:
    """Сопоставить участников TI15 с командами OpenDota (с учётом алиасов).

    Результат нужно глазами сверить: совпадение по названию неточное, поэтому
    возвращаются и способ совпадения, и активность команды.
    """
    config = load_predictions_config()
    async with _client() as client:
        resolved = await resolve_compendium_teams(
            client, session, config.team_names, config.team_aliases
        )
    return [
        {
            "compendium_name": row.compendium_name,
            "team_id": row.team_id,
            "opendota_name": row.opendota_name,
            "matched_via": row.matched_via,
            "matches": row.matches,
            "last_match_time": row.last_match_time,
            "exact": row.exact,
        }
        for row in resolved
    ]
