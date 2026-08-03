"""Выгрузить аналитику в JSON для статической страницы.

GitHub Pages отдаёт только файлы — питоновского бэкенда там нет. Поэтому всё,
что требует базы и симуляций (рейтинги, прогноз группы, ценность статов,
проекции), считается заранее и кладётся в один снапшот, а браузер потом
пересчитывает поверх него только математику эмблем: она аддитивная и дешёвая,
портирована в `frontend/src/engine/scoring.ts`.

    python tools/export_snapshot.py --simulations 20000

Результат: frontend/public/data/snapshot.json
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.analytics.glicko2 import Rating  # noqa: E402
from app.analytics.predictions_config import load_predictions_config  # noqa: E402
from app.analytics.simulate import (  # noqa: E402
    SwissSimulator,
    optimise_group_predictions,
)
from app.db.models import Team  # noqa: E402
from app.db.session import init_db, session_scope  # noqa: E402
from app.fantasy.advisor import EmblemAdvisor  # noqa: E402
from app.fantasy.presets import neutral_banner  # noqa: E402
from app.fantasy.projection import RoleProjector  # noqa: E402
from app.fantasy.rules import load_rules  # noqa: E402
from app.services.analysis import (  # noqa: E402
    build_role_history,
    latest_ratings,
    ti_candidates,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(message)s")
log = logging.getLogger("snapshot")

OUTPUT = Path(__file__).resolve().parents[2] / "frontend" / "public" / "data" / "snapshot.json"


def export_rules() -> dict:
    rules = load_rules()
    from app.ingest.stat_mapping import STAT_SOURCES

    return {
        "version": rules.version,
        "source": rules.source,
        "trait_bonus_mode": rules.trait_bonus_mode,
        "banner_slots": rules.banner.slots,
        "role_slots": {role: [str(c) for c in colors] for role, colors in rules.role_slots.items()},
        "qualities": rules.qualities,
        "traits": [
            {
                "key": t.key,
                "label": t.label,
                "description": t.description,
                "condition": str(t.condition),
                "effects": [{"scope": str(e.scope), "amount": e.amount} for e in t.effects],
            }
            for t in rules.traits.values()
        ],
        "stats": [
            {
                "key": s.key,
                "label": s.label,
                "color": str(s.color),
                "kind": str(s.kind),
                "per_unit": s.per_unit,
                "base": s.base,
                "value_if_true": s.value_if_true,
                "max_points": s.max_points,
                "availability": str(STAT_SOURCES[s.key].availability),
                "note": STAT_SOURCES[s.key].note,
            }
            for s in rules.stats.values()
        ],
    }


def export_teams(session) -> list[dict]:
    ratings = latest_ratings(session)
    rows = []
    for team in session.query(Team).filter(Team.compendium_name.is_not(None)).all():
        rating = ratings.get(team.team_id)
        rows.append(
            {
                "team_id": team.team_id,
                "name": team.compendium_name or team.name,
                "opendota_name": team.name,
                "rating": round(rating[0], 1) if rating else None,
                "rd": round(rating[1], 1) if rating else None,
                "listable": Rating(*rating).is_listable() if rating else False,
            }
        )
    rows.sort(key=lambda r: -(r["rating"] or 0))
    return rows


def export_group(session, simulations: int) -> dict | None:
    config = load_predictions_config().group_stage
    ratings = latest_ratings(session)
    names = {t.team_id: t.compendium_name or t.name for t in session.query(Team).all()}

    from app.services.analysis import ti_team_ids

    participants = [t for t in ti_team_ids() if t in ratings]
    if len(participants) != config.teams:
        log.warning("прогноз группы пропущен: рейтингов %d из %d", len(participants), config.teams)
        return None

    simulator = SwissSimulator({t: Rating(*ratings[t]) for t in participants}, config, seed=1)
    result = simulator.run(simulations=simulations)
    plan = optimise_group_predictions(result, config.slots(), config.points)

    return {
        "simulations": result.simulations,
        "buckets": [
            {"key": b.key, "label": b.label, "description": b.description, "slots": b.slots}
            for b in config.buckets
        ],
        "teams": [
            {
                "team_id": team_id,
                "name": names.get(team_id, str(team_id)),
                "probabilities": {
                    key: round(float(result.probabilities[i, j]), 4)
                    for j, key in enumerate(result.bucket_keys)
                },
                "advance": round(float(result.advance_probability[i]), 4),
                "expected_series": round(result.expected_series(team_id), 2),
            }
            for i, team_id in enumerate(result.team_ids)
        ],
        "plan": [
            {"team_id": int(team), "name": names.get(int(team), str(team)), "bucket": str(bucket)}
            for team, bucket in plan.assignment.items()
        ],
        "expected_points": round(plan.expected_points, 1),
        "expected_correct": round(plan.expected_correct, 2),
        "points_percentiles": {str(k): round(v, 1) for k, v in plan.points_percentiles.items()},
    }


def _stat_row(value) -> dict:
    return {
        "stat": value.stat,
        "label": value.label,
        "color": value.color,
        "units_per_game": round(value.units_per_game, 3),
        "base_points": round(value.base_points, 1),
        "p95_points": round(value.p95_points, 1),
        "p5_points": round(value.p5_points, 1),
        "median_points": round(value.median_points, 1),
        "p75_points": round(value.p75_points, 1),
        "hit_rate": round(value.hit_rate, 3),
        "trend": round(value.trend, 3) if value.trend is not None else None,
        "availability": str(value.availability),
        "negligible": value.is_negligible,
    }


def _timeline(projector: RoleProjector, history, banner) -> list[dict]:
    """Очки за каждую карту с нейтральным баннером — форма роли во времени.

    Баннер нейтральный намеренно: строка сравнима между командами и не зависит
    от того, какие эмблемы выберет пользователь. Абсолютная величина здесь не
    так важна, как форма кривой и разброс.
    """
    base = projector.base_matrix(history)
    multipliers = projector.scorer.emblem_multipliers(banner)
    vector = np.zeros(base.shape[1])
    for emblem, multiplier in zip(banner.emblems, multipliers, strict=True):
        vector[projector._stat_index[emblem.stat]] = multiplier
    scores = base @ vector

    return [
        {
            "d": game.start_time.date().isoformat(),
            "p": round(float(score)),
            "w": None if game.won is None else int(game.won),
        }
        for game, score in zip(history.games, scores, strict=True)
    ]


def export_roles(session, *, history_days: int, simulations: int, series: int) -> list[dict]:
    """Для каждой роли каждой команды: ценность статов, проекция, титулы.

    Браузеру этого достаточно, чтобы пересчитывать любые баннеры самому: очки
    эмблемы линейны по базовым очкам стата, а проценты считаются аддитивно.
    """
    advisor = EmblemAdvisor(RoleProjector(seed=11))
    since = datetime.now(timezone.utc) - timedelta(days=history_days)
    candidates = ti_candidates(session)

    rows: list[dict] = []
    for role, entries in candidates.items():
        for team_id, team_name, account_ids in entries:
            history = build_role_history(session, team_id, role, account_ids, since=since)
            if not history.games:
                log.warning("%s / %s: нет разобранных матчей", team_name, role)
                continue

            values = advisor.stat_values(history, role=role)
            projection = advisor.projector.project(
                history,
                neutral_banner(role),
                simulations=simulations,
                series_distribution={series: 1.0},
            )
            neutral_card = advisor.projector.expected_card_score(history, neutral_banner(role))

            rows.append(
                {
                    "team_id": team_id,
                    "team_name": team_name,
                    "role": role,
                    "players": list(history.player_names),
                    "games": len(history.games),
                    "last_game": history.games[-1].start_time.date().isoformat(),
                    "stats": [_stat_row(v) for v in values],
                    # Разбивка по игрокам: среднее по паре не показывает, кто
                    # именно набирает очки и насколько роль зависит от одного.
                    "player_stats": [
                        {
                            "account_id": profile.account_id,
                            "name": profile.name,
                            "games": profile.games,
                            "stats": [
                                {
                                    "stat": v.stat,
                                    "units_per_game": round(v.units_per_game, 3),
                                    "base_points": round(v.base_points, 1),
                                    "p95_points": round(v.p95_points, 1),
                                    "hit_rate": round(v.hit_rate, 3),
                                    "trend": round(v.trend, 3) if v.trend is not None else None,
                                }
                                for v in profile.values
                                if not v.is_negligible
                            ],
                        }
                        for profile in advisor.player_values(history, role=role)
                    ],
                    "timeline": _timeline(advisor.projector, history, neutral_banner(role)),
                    # Во сколько раз счёт за период больше счёта за одну карту.
                    # Позволяет браузеру пересчитать период для любого баннера,
                    # не повторяя симуляцию.
                    "period_ratio": round(projection.mean / neutral_card, 4)
                    if neutral_card
                    else 0.0,
                    "ceiling_ratio": round(projection.ceiling / neutral_card, 4)
                    if neutral_card
                    else 0.0,
                    "titles": [
                        {
                            "key": t.key,
                            "label": t.label,
                            "bonus": t.bonus,
                            "condition": t.condition,
                            "hit_rate": round(t.hit_rate, 3) if t.hit_rate is not None else None,
                            "expected_bonus": round(t.expected_bonus, 4)
                            if t.expected_bonus is not None
                            else None,
                            "estimator": t.estimator,
                            "note": t.note,
                        }
                        for t in advisor.title_advice(history)
                    ],
                }
            )

    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--simulations", type=int, default=20_000)
    parser.add_argument("--role-simulations", type=int, default=4000)
    parser.add_argument("--history-days", type=int, default=180)
    parser.add_argument("--series", type=int, default=5)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()

    init_db()
    with session_scope() as session:
        snapshot = {
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "rules": export_rules(),
            "teams": export_teams(session),
            "group": export_group(session, args.simulations),
            "roles": export_roles(
                session,
                history_days=args.history_days,
                simulations=args.role_simulations,
                series=args.series,
            ),
        }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(snapshot, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )
    size = args.output.stat().st_size / 1024
    log.info(
        "%s: %.0f КБ, команд %d, ролей %d",
        args.output,
        size,
        len(snapshot["teams"]),
        len(snapshot["roles"]),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
