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
from collections import Counter
from collections.abc import Sequence
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
from app.fantasy.shrinkage import shrink_to_role_mean  # noqa: E402
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
        # Титулы вместе со списками героев: по ним страница матча проверяет, что
        # сработало бы на конкретной карте. Без списков осталась бы половина
        # титулов — те, которым хватает длительности и результата.
        "titles": {
            group: [
                {
                    "key": title["key"],
                    "label": title["label"],
                    "bonus": title["bonus"],
                    "condition": title.get("condition", ""),
                    "estimator": title.get("estimator", ""),
                    **({"heroes": title["heroes"]} if title.get("heroes") else {}),
                }
                for title in items
            ]
            for group, items in rules.titles.items()
        },
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
    predictions = load_predictions_config()
    config = predictions.group_stage
    ratings = latest_ratings(session)
    names = {t.team_id: t.compendium_name or t.name for t in session.query(Team).all()}

    from app.services.analysis import ti_team_ids

    participants = [t for t in ti_team_ids() if t in ratings]
    if len(participants) != config.teams:
        log.warning("прогноз группы пропущен: рейтингов %d из %d", len(participants), config.teams)
        return None

    simulator = SwissSimulator(
        {t: Rating(*ratings[t]) for t in participants},
        config,
        seed=1,
        first_round=predictions.first_round_for(participants),
    )
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


def _titles(advice) -> list[dict]:
    return [
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
            "note_key": t.note_key,
            "note_params": dict(t.note_params),
        }
        for t in advice
    ]


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


def export_roles(
    session,
    *,
    history_days: int,
    simulations: int,
    series: int,
    series_options: Sequence[int] = (4, 5, 6, 7),
) -> list[dict]:
    """Для каждой роли каждой команды: ценность статов, проекция, титулы.

    Браузеру этого достаточно, чтобы пересчитывать любые баннеры самому: очки
    эмблемы линейны по базовым очкам стата, а проценты считаются аддитивно.

    Коэффициент периода считается для каждого числа серий из `series_options`, а
    не только для базового: на странице ростера это переключатель, и без всех
    вариантов он бы ничего не менял. Разница существенная — в зачёт идёт лучшая
    серия периода, и каждая дополнительная серия поднимает ожидание.
    """
    from app.services.profiles import load_heroes  # noqa: PLC0415

    advisor = EmblemAdvisor(RoleProjector(seed=11))
    heroes = load_heroes()
    since = datetime.now(timezone.utc) - timedelta(days=history_days)
    candidates = ti_candidates(session)
    all_series = sorted({series, *series_options})

    rows: list[dict] = []
    # Статы копятся отдельно: сжатие к среднему по роли сравнивает команды между
    # собой, а значит применимо только когда собраны все.
    pending: list[tuple[str, list]] = []
    for role, entries in candidates.items():
        for team_id, team_name, account_ids in entries:
            history = build_role_history(session, team_id, role, account_ids, since=since)
            if not history.games:
                log.warning("%s / %s: нет разобранных матчей", team_name, role)
                continue

            values = advisor.stat_values(history, role=role)
            projections = {
                count: advisor.projector.project(
                    history,
                    neutral_banner(role),
                    simulations=simulations,
                    series_distribution={count: 1.0},
                )
                for count in all_series
            }
            projection = projections[series]
            neutral_card = advisor.projector.expected_card_score(history, neutral_banner(role))

            rows.append(
                {
                    "team_id": team_id,
                    "team_name": team_name,
                    "role": role,
                    # Кто выйдет играть. При замене это не тот, чьи карты в
                    # выборке, — расхождение расписано в substitutions.
                    "players": list(history.roster_names),
                    "substitutions": [
                        {
                            "name": s.name,
                            "replaced": s.replaced_name,
                            "games": len(history.games),
                        }
                        for s in history.substitutions
                    ],
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
                    # То же самое для каждого числа серий: переключатель на
                    # странице ростера выбирает отсюда.
                    "period_ratios": {
                        str(count): round(p.mean / neutral_card, 4) if neutral_card else 0.0
                        for count, p in projections.items()
                    },
                    "ceiling_ratios": {
                        str(count): round(p.ceiling / neutral_card, 4) if neutral_card else 0.0
                        for count, p in projections.items()
                    },
                    # Кого эта роль берёт: по этому же пулу оцениваются префиксы
                    # титулов, поэтому список и оценка едут вместе.
                    "heroes": [
                        {
                            "id": pick.hero_id,
                            "name": pick.name,
                            "games": pick.games,
                            "wins": pick.wins,
                            "players": [
                                {"account_id": account, "games": count}
                                for account, count in pick.players
                            ],
                        }
                        for pick in advisor.hero_pool(history, heroes=heroes, limit=15)
                    ],
                    "titles": _titles(advisor.title_advice(history, heroes=heroes)),
                }
            )
            pending.append((role, values))

    for row, values in zip(rows, shrink_to_role_mean(pending), strict=True):
        row["stats"] = [_stat_row(v) for v in values]

    return rows


def _split(split) -> dict:
    return {"key": split.key, "games": split.games, "wins": split.wins}


def _trends(trends) -> dict | None:
    """Разрезы выборки в JSON. Ключи короткие — их читает не человек, а страница."""
    if trends is None:
        return None
    return {
        "form": _split(trends.form),
        "baseline": _split(trends.baseline),
        "streak": trends.streak,
        "sides": [_split(s) for s in trends.sides],
        "durations": [_split(s) for s in trends.durations],
    }


def _match_rows(rows) -> list[dict]:
    out = []
    for row in rows:
        entry = {
            "id": row.match_id,
            "d": row.start_time.date().isoformat(),
            "dur": row.duration,
            "opp": row.opponent_name,
            "opp_id": row.opponent_id,
            "won": None if row.won is None else int(row.won),
            "parsed": int(row.is_parsed),
        }
        if row.league_name:
            entry["league"] = row.league_name
        if row.hero_name:
            entry["hero"] = row.hero_name
        for key, value in (
            ("k", row.kills),
            ("d_", row.deaths),
            ("a", row.assists),
            ("gpm", row.gpm),
            ("xpm", row.xpm),
            ("nw", row.net_worth),
        ):
            if value is not None:
                entry[key] = round(float(value))
        out.append(entry)
    return out


def _team_heroes(profile, limit: int = 15) -> list[dict]:
    """Пул героев команды: чьи это герои, видно по разбивке на игроков."""
    games: Counter[int] = Counter()
    wins: Counter[int] = Counter()
    names: dict[int, str] = {}
    by_player: dict[int, Counter[int]] = {}
    for player in profile.roster:
        for hero in player.heroes:
            games[hero.hero_id] += hero.games
            wins[hero.hero_id] += hero.wins
            names[hero.hero_id] = hero.name
            by_player.setdefault(hero.hero_id, Counter())[player.account_id] += hero.games

    return [
        {
            "id": hero_id,
            "name": names.get(hero_id, str(hero_id)),
            "games": count,
            "wins": wins[hero_id],
            "players": [
                {"account_id": account, "games": played}
                for account, played in by_player[hero_id].most_common()
            ],
        }
        for hero_id, count in games.most_common(limit)
    ]


def _player_page(profile, advisor=None, heroes=None) -> dict:
    titles = []
    if advisor is not None and profile.history is not None and profile.history.games:
        titles = _titles(
            advisor.title_advice(
                profile.history,
                heroes=heroes,
                account_ids=(profile.account_id,),
            )
        )[:8]

    return {
        "account_id": profile.account_id,
        "name": profile.name,
        "titles": titles,
        "team_id": profile.team_id,
        "team_name": profile.team_name,
        "role": profile.role,
        "games": profile.games,
        "parsed_games": profile.parsed_games,
        "wins": profile.wins,
        "first_game": profile.first_game.date().isoformat() if profile.first_game else None,
        "last_game": profile.last_game.date().isoformat() if profile.last_game else None,
        "averages": {k: round(v, 2) for k, v in profile.averages.items()},
        "fantasy_units": {k: round(v, 3) for k, v in profile.fantasy_units.items()},
        "heroes": [
            {"id": h.hero_id, "name": h.name, "games": h.games, "wins": h.wins}
            for h in profile.heroes
        ],
        "matches": _match_rows(profile.matches),
        "trends": _trends(profile.trends),
        "lanes": profile.lanes,
        "hero_pool": (
            {
                "distinct": profile.hero_pool.distinct,
                "top3_share": round(profile.hero_pool.top3_share, 3),
            }
            if profile.hero_pool
            else None
        ),
        "fantasy_form": (
            {
                "maps": profile.fantasy_form.maps,
                "mean": round(profile.fantasy_form.mean),
                "median": round(profile.fantasy_form.median),
                "best": round(profile.fantasy_form.best),
                "p90": round(profile.fantasy_form.p90),
                "spread": round(profile.fantasy_form.spread, 3),
            }
            if profile.fantasy_form
            else None
        ),
    }


def export_profiles(
    session,
    *,
    days: int,
    min_games: int,
    ti_matches: int,
    other_matches: int,
) -> dict:
    """Страницы команд и игроков для статического режима.

    Полностью выгружаются участники TI15 и их составы — это то, ради чего
    страница существует. Остальные команды и игроки из базы (соперники по
    квалификациям, стенд-ины) выгружаются короче: средние, герои и несколько
    последних матчей. Без порога по числу карт снапшот распух бы вдвое ради
    профилей, где две игры и никакой статистики.
    """
    from app.services.profiles import (  # noqa: PLC0415
        load_heroes,
        player_directory,
        player_profile,
        team_directory,
        team_profile,
    )

    heroes = load_heroes()
    if not heroes:
        log.warning("справочник героев пуст — выполните `cli.py ingest-heroes`")
    advisor = EmblemAdvisor(RoleProjector(seed=13))

    teams_out: list[dict] = []
    for entry in team_directory(session):
        is_ti = bool(entry["is_ti"])
        if not is_ti and int(entry["games"]) < min_games:
            continue
        profile = team_profile(
            session,
            int(entry["team_id"]),
            days=days,
            match_limit=ti_matches if is_ti else other_matches,
            roster_limit=8 if is_ti else 5,
            heroes=heroes,
        )
        if profile is None or not profile.games:
            continue
        teams_out.append(
            {
                "team_id": profile.team_id,
                "name": profile.name,
                "tag": profile.tag,
                "is_ti": is_ti,
                "rating": round(profile.rating, 1) if profile.rating else None,
                "rd": round(profile.rd, 1) if profile.rd else None,
                "games": profile.games,
                "parsed_games": profile.parsed_games,
                "wins": profile.wins,
                "first_game": profile.first_game.date().isoformat()
                if profile.first_game
                else None,
                "last_game": profile.last_game.date().isoformat()
                if profile.last_game
                else None,
                "team_averages": {k: round(v, 2) for k, v in profile.team_averages.items()},
                "opponents": [
                    {"team_id": team_id, "name": name, "games": games, "wins": wins}
                    for team_id, name, games, wins in profile.opponents
                ],
                # История рейтинга прореживается: точек бывает под сотню, а на
                # графике шириной в панель разница не видна.
                "rating_history": [
                    {"d": as_of.date().isoformat(), "r": round(rating, 1), "rd": round(rd, 1)}
                    for as_of, rating, rd in profile.rating_history[::2]
                ],
                "trends": _trends(profile.trends),
                "opponent_rating": (
                    round(profile.opponent_rating, 1) if profile.opponent_rating else None
                ),
                "vs_stronger": _split(profile.vs_stronger) if profile.vs_stronger else None,
                "first_blood_rate": (
                    round(profile.first_blood_rate, 3)
                    if profile.first_blood_rate is not None
                    else None
                ),
                "roster": [p.account_id for p in profile.roster],
                # Пул героев команды — сумма выборов всего состава за период.
                "heroes": _team_heroes(profile),
                "matches": _match_rows(profile.matches),
            }
        )

    ti_teams = {t["team_id"] for t in teams_out if t["is_ti"]}
    players_out: list[dict] = []
    for entry in player_directory(session):
        is_ti = bool(entry["is_ti"]) or entry["team_id"] in ti_teams
        if not is_ti and int(entry["games"]) < min_games:
            continue
        profile = player_profile(
            session,
            int(entry["account_id"]),
            days=days,
            match_limit=ti_matches if is_ti else other_matches,
            hero_limit=12 if is_ti else 6,
            heroes=heroes,
        )
        if profile is None or not profile.games:
            continue
        # Титулы считаем только участникам: их выбирают в состав, а соперник по
        # квалификации попал в базу заодно с матчами, и восемь строк на каждого
        # из четырёхсот весят больше, чем стоят.
        players_out.append(
            _player_page(profile, advisor=advisor if is_ti else None, heroes=heroes)
        )

    log.info("профили: команд %d, игроков %d", len(teams_out), len(players_out))
    return {"days": days, "min_games": min_games, "teams": teams_out, "players": players_out}


def export_head_to_head(session, *, days: int) -> dict:
    """Личные встречи: все матчи между парами команд за период.

    Отдельным файлом, а не полем в профиле: страница матча спрашивает ровно один
    вопрос — «сколько раз эти двое уже играли и чем кончалось», — и тащить ради
    него двухмегабайтные профили незачем. Ключ пары — два id по возрастанию,
    поэтому порядок команд в матче на поиск не влияет.
    """
    from sqlalchemy import select  # noqa: PLC0415

    from app.db.models import Match  # noqa: PLC0415

    since = datetime.now(timezone.utc) - timedelta(days=days)
    names = {
        team.team_id: team.compendium_name or team.name for team in session.scalars(select(Team))
    }

    pairs: dict[str, list[dict]] = {}
    used: set[int] = set()
    query = (
        select(Match)
        .where(Match.start_time >= since)
        .where(Match.radiant_team_id.is_not(None))
        .where(Match.dire_team_id.is_not(None))
        .order_by(Match.start_time.desc())
    )
    for match in session.scalars(query):
        low, high = sorted((int(match.radiant_team_id), int(match.dire_team_id)))
        if low == high:
            continue
        winner = None
        if match.radiant_win is not None:
            winner = match.radiant_team_id if match.radiant_win else match.dire_team_id
        row = {
            "id": match.match_id,
            "d": match.start_time.date().isoformat(),
            "r": int(match.radiant_team_id),
            "w": int(winner) if winner else None,
            "dur": match.duration,
        }
        if match.league_name:
            row["league"] = match.league_name
        pairs.setdefault(f"{low}:{high}", []).append(row)
        used.update((low, high))

    log.info("личных встреч: пар %d, матчей %d", len(pairs), sum(len(v) for v in pairs.values()))
    return {
        "days": days,
        "teams": {str(team_id): names[team_id] for team_id in sorted(used) if team_id in names},
        "pairs": pairs,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--simulations", type=int, default=20_000)
    parser.add_argument("--role-simulations", type=int, default=4000)
    parser.add_argument("--history-days", type=int, default=180)
    parser.add_argument("--series", type=int, default=5)
    parser.add_argument(
        "--profile-min-games",
        type=int,
        default=10,
        help="порог по картам для команд и игроков вне TI15",
    )
    parser.add_argument("--profile-matches", type=int, default=15)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()

    init_db()
    with session_scope() as session:
        from app.services.profiles import (  # noqa: PLC0415
            load_heroes as _load_heroes,
            load_items as _load_items,
        )

        snapshot = {
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "rules": export_rules(),
            # Справочник героев целиком: в матче OpenDota лежит только hero_id, а
            # странице матча нужны и название, и проверка титулов по списку.
            "heroes": {str(hero_id): name for hero_id, name in sorted(_load_heroes().items())},
            # То же с предметами: в слотах инвентаря лежат id, а иконки названы
            # внутренним именем предмета.
            "items": _load_items(),
            "teams": export_teams(session),
            "group": export_group(session, args.simulations),
            "roles": export_roles(
                session,
                history_days=args.history_days,
                simulations=args.role_simulations,
                series=args.series,
            ),
        }
        profiles = export_profiles(
            session,
            days=args.history_days,
            min_games=args.profile_min_games,
            ti_matches=args.profile_matches,
            other_matches=max(5, args.profile_matches // 2),
        )
        head_to_head = export_head_to_head(session, days=args.history_days)

    # Снапшот без команд формально валиден, но страница по нему пустая: не из
    # чего выбрать в анализаторе эмблем и некого показать в профилях. Такое уже
    # уезжало в деплой незаметно, поэтому лучше уронить прогон, чем опубликовать.
    problems = []
    if not snapshot["teams"]:
        problems.append("в выгрузке нет ни одной команды-участницы")
    if not snapshot["roles"]:
        problems.append("в выгрузке нет ни одной роли")
    if problems:
        log.error("снапшот не записан: %s", "; ".join(problems))
        log.error(
            "участники размечаются командой `python tools/cli.py ingest-ti` — "
            "она проставляет и названия компендиума, и составы по ролям"
        )
        return 1

    args.output.parent.mkdir(parents=True, exist_ok=True)
    write(args.output, snapshot)
    log.info(
        "%s: %.0f КБ, команд %d, ролей %d",
        args.output,
        args.output.stat().st_size / 1024,
        len(snapshot["teams"]),
        len(snapshot["roles"]),
    )

    # Профили лежат отдельным файлом: они втрое тяжелее аналитики, а нужны
    # только на вкладке «Профили». Грузить их вместе со стартовой страницей —
    # платить два мегабайта за то, что большинство не откроет.
    profiles_path = args.output.with_name("profiles.json")
    write(profiles_path, profiles)
    log.info(
        "%s: %.0f КБ, команд %d, игроков %d",
        profiles_path,
        profiles_path.stat().st_size / 1024,
        len(profiles["teams"]),
        len(profiles["players"]),
    )

    # Личные встречи — третий файл по той же причине: их спрашивает страница
    # матча, а она не грузит ни профили, ни половину снапшота.
    h2h_path = args.output.with_name("head_to_head.json")
    write(h2h_path, head_to_head)
    log.info(
        "%s: %.0f КБ, пар %d",
        h2h_path,
        h2h_path.stat().st_size / 1024,
        len(head_to_head["pairs"]),
    )
    return 0


def write(path: Path, payload: dict) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )


if __name__ == "__main__":
    raise SystemExit(main())
