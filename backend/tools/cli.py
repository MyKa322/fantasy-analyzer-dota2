"""CLI аналитика — то же, что и API, но без поднятия сервера.

    python tools/cli.py ingest-feed --days 14
    python tools/cli.py ingest-team 2163 --days 120
    python tools/cli.py resolve-teams
    python tools/cli.py ratings
    python tools/cli.py teams
    python tools/cli.py group --simulations 20000
    python tools/cli.py roles 2163
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.analytics.glicko2 import Rating  # noqa: E402
from app.analytics.predictions_config import load_predictions_config  # noqa: E402
from app.analytics.simulate import (  # noqa: E402
    SwissSimulator,
    optimise_group_predictions,
)
from app.db.models import Team  # noqa: E402
from app.db.session import init_db, session_scope  # noqa: E402
from app.ingest.opendota import OpenDotaClient  # noqa: E402
from app.ingest.pipeline import (  # noqa: E402
    ingest_pro_feed,
    ingest_team_history,
    resolve_compendium_teams,
)
from app.services.analysis import (  # noqa: E402
    build_role_history,
    infer_team_roles,
    latest_ratings,
    mark_ti_participants,
    recompute_ratings,
    ti_candidates,
    ti_team_ids,
)
from app.settings import settings  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(message)s")


def client() -> OpenDotaClient:
    return OpenDotaClient(
        api_key=settings.opendota_api_key,
        cache_dir=settings.cache_dir,
        rate_limit_per_minute=settings.opendota_rate_limit,
    )


async def cmd_ingest_feed(args: argparse.Namespace) -> None:
    async with client() as api:
        with session_scope() as session:
            result = await ingest_pro_feed(
                api, session, days_back=args.days, max_pages=args.pages
            )
    print(f"загружено: {result}")


async def cmd_ingest_team(args: argparse.Namespace) -> None:
    async with client() as api:
        with session_scope() as session:
            result = await ingest_team_history(api, session, args.team_id, days_back=args.days)
    print(f"загружено: {result}")


async def cmd_resolve_teams(_: argparse.Namespace) -> None:
    from datetime import datetime, timezone

    config = load_predictions_config()
    async with client() as api:
        with session_scope() as session:
            resolved = await resolve_compendium_teams(
                api, session, config.team_names, config.team_aliases
            )

    print("Сверьте глазами и пропишите team_id в config/ti15_predictions.yaml:\n")
    print(f"{'Компендиум':<18}{'OpenDota':<22}{'team_id':>10}{'матчей':>8}  последний матч")
    for row in resolved:
        if row.team_id is None:
            print(f"{row.compendium_name:<18}{'— не найдена':<22}")
            continue
        last = (
            datetime.fromtimestamp(row.last_match_time, tz=timezone.utc).strftime("%Y-%m-%d")
            if row.last_match_time
            else "—"
        )
        flag = "" if row.exact else "  ~ по подстроке, проверить"
        via = f" (по «{row.matched_via}»)" if row.matched_via != row.compendium_name else ""
        print(
            f"{row.compendium_name:<18}{(row.opendota_name or '')!s:<22}"
            f"{row.team_id:>10}{row.matches:>8}  {last}{via}{flag}"
        )


async def cmd_ingest_ti(args: argparse.Namespace) -> None:
    """Загрузить историю всех участников TI15 и разметить их игроков."""
    config = load_predictions_config()
    missing = [n for n, t in config.team_ids.items() if t is None]
    if missing:
        print(f"без team_id в конфиге: {', '.join(missing)} — сначала `resolve-teams`\n")

    # Вместе с нынешними профилями обходим прежние: коллектив переезжает под
    # новый тег, и без них история команды обрывается на дате переименования.
    # Лишнего это не принесёт — что взять в выборку роли, решает пересечение
    # состава, а не тег, под которым сыграна карта.
    current = {tid for tid in config.team_ids.values() if tid is not None}
    teams = config.ingest_team_ids()
    if not teams:
        return

    totals = {"requested": 0, "parsed": 0, "unparsed": 0, "failed": 0}
    broken: list[str] = []
    async with client() as api:
        for team_id, name in teams.items():
            label = name if team_id in current else f"{name} (прежний)"
            try:
                with session_scope() as session:
                    result = await ingest_team_history(
                        api, session, team_id, days_back=args.days
                    )
            except Exception as exc:  # ошибка на одной команде не должна ронять прогон
                broken.append(f"{label}: {exc}")
                print(f"  {label:<28} ОШИБКА: {exc}", flush=True)
                continue
            for key in totals:
                totals[key] += result.get(key, 0)
            print(f"  {label:<28} {result}", flush=True)

    print(f"\nитого: {totals}")
    if api.throttle_events:
        print(f"троттлинг OpenDota сработал {api.throttle_events} раз")
    if broken:
        print("не удалось загрузить: " + "; ".join(broken))

    with session_scope() as session:
        roles = mark_ti_participants(session)
    print("\nСоставы по ролям:")
    for name, by_role in roles.items():
        parts = [f"{role}={len(ids)}" for role, ids in by_role.items()]
        flag = "" if sum(len(i) for i in by_role.values()) == 5 else "   ← состав неполный"
        print(f"  {name:<18} {', '.join(parts)}{flag}")


# Запасной источник справочника героев. `/api/heroes` у OpenDota периодически
# отвечает 522 (таймаут её origin), а сам эндпоинт собран из этого же файла —
# репозиторий констант odota и есть его исходник.
HEROES_FALLBACK_URL = "https://raw.githubusercontent.com/odota/dotaconstants/master/build/heroes.json"


async def cmd_ingest_heroes(_: argparse.Namespace) -> None:
    """Обновить справочник героев: в матче есть только hero_id, имени нет."""
    import json

    from app.services.profiles import HEROES_PATH

    try:
        async with client() as api:
            heroes = await api.heroes()
    except RuntimeError as error:
        print(f"OpenDota недоступна ({error}), беру справочник из констант odota")
        import httpx

        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as http:
            response = await http.get(HEROES_FALLBACK_URL)
            response.raise_for_status()
            payload = response.json()
        heroes = list(payload.values()) if isinstance(payload, dict) else payload

    # Внутреннее имя (`npc_dota_hero_axe`) нужно для иконок: файлы названы им.
    mapping = {
        int(h["id"]): {"name": h.get("localized_name") or h["name"], "npc": h["name"]}
        for h in heroes
    }
    HEROES_PATH.write_text(
        json.dumps(mapping, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8"
    )
    print(f"{HEROES_PATH}: {len(mapping)} героев")


# Справочник предметов: в матче лежат id слотов инвентаря, а лог покупок и
# файлы иконок названы внутренним именем. Связывает одно с другим тот же
# репозиторий констант odota, что и для героев.
ITEMS_URL = "https://raw.githubusercontent.com/odota/dotaconstants/master/build/item_ids.json"


async def cmd_ingest_items(_: argparse.Namespace) -> None:
    """Обновить справочник предметов: в слотах инвентаря лежат только id."""
    import json

    import httpx

    from app.services.profiles import ITEMS_PATH

    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as http:
        response = await http.get(ITEMS_URL)
        response.raise_for_status()
        payload = response.json()

    mapping = {str(int(item_id)): str(name) for item_id, name in payload.items()}
    ITEMS_PATH.write_text(
        json.dumps(mapping, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8"
    )
    print(f"{ITEMS_PATH}: {len(mapping)} предметов")


def cmd_backfill(args: argparse.Namespace) -> None:
    """Перечитать матчи из локального кэша ответов OpenDota — без сети.

    Нужно, когда набор сохраняемых полей расширился: тела матчей уже лежат на
    диске, и перезабирать их из API незачем. В CI кэша нет — там матчи со старым
    `stats_version` перезабираются обычным `ingest-ti`.
    """
    import json

    from app.ingest.pipeline import upsert_match
    from app.settings import settings

    cache_dir = Path(settings.cache_dir)
    files = sorted(cache_dir.glob("match_*.json"))
    if not files:
        print(f"кэш пуст: {cache_dir}")
        return

    updated = skipped = broken = 0
    with session_scope() as session:
        for index, path in enumerate(files, 1):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                broken += 1
                continue
            if not payload.get("match_id"):
                skipped += 1
                continue
            upsert_match(session, payload)
            updated += 1
            if index % 200 == 0:
                session.flush()
                print(f"  {index}/{len(files)}")

    print(f"перечитано {updated}, пропущено {skipped}, битых файлов {broken}")


def cmd_profile(args: argparse.Namespace) -> None:
    """Показать профиль команды или игрока — то же, что на странице."""
    from app.services.profiles import player_profile, team_profile

    with session_scope() as session:
        if args.kind == "team":
            profile = team_profile(session, args.id)
            if profile is None:
                print("команда не найдена")
                return
            print(profile.name if not profile.tag else f"{profile.name} [{profile.tag}]")
            rating = f"{profile.rating:.0f}±{profile.rd:.0f}" if profile.rating else "—"
            print(f"рейтинг {rating}, карт {profile.games} ({profile.wins} побед)")
            print(f"разобрано реплеев: {profile.parsed_games}")
            for player in profile.roster:
                print(
                    f"  {player.name or player.account_id:<18}{player.role or '—':<9}"
                    f"{player.games:>4} карт  {player.win_rate:>5.0%}"
                )
            print("\nпоследние матчи:")
            for row in profile.matches[:10]:
                mark = "W" if row.won else "L" if row.won is False else "?"
                print(
                    f"  {row.start_time:%Y-%m-%d} {mark} vs {row.opponent_name or '—':<18}"
                    f"{'' if row.is_parsed else ' (без реплея)'}"
                )
        else:
            profile = player_profile(session, args.id)
            if profile is None:
                print("игрок не найден")
                return
            print(f"{profile.name or profile.account_id} — {profile.team_name or '—'}")
            print(
                f"роль {profile.role or '—'}, карт {profile.games} "
                f"({profile.win_rate:.0%} побед), разобрано {profile.parsed_games}"
            )
            avg = profile.averages
            print(
                f"в среднем: {profile.fantasy_units.get('kills', 0):.1f}/"
                f"{profile.fantasy_units.get('deaths', 0):.1f}/{avg.get('assists', 0):.1f}, "
                f"GPM {profile.fantasy_units.get('gpm', 0):.0f}, XPM {avg.get('xpm', 0):.0f}"
            )
            print("герои:", ", ".join(f"{h.name} ({h.games})" for h in profile.heroes[:8]))


def cmd_roster(args: argparse.Namespace) -> None:
    """Подобрать состав Fantasy: core duo, mid и support duo из разных команд."""
    from app.fantasy.projection import RoleProjector, recommend_roster
    from app.fantasy.scoring import Banner, Emblem

    # Нейтральные баннеры: один и тот же набор статов для всех кандидатов роли,
    # иначе сравнение команд превратится в сравнение баннеров.
    from app.fantasy.presets import DEFAULT_ROLE_STATS

    default_banners = {role: list(stats) for role, stats in DEFAULT_ROLE_STATS.items()}
    if args.banner:
        stats = args.banner.split(",")
        default_banners = {role: stats for role in default_banners}

    projector = RoleProjector(seed=args.seed)
    projections: dict[str, dict[int, object]] = {}
    skipped: list[str] = []

    with session_scope() as session:
        candidates = ti_candidates(session)
        if not candidates:
            print("нет размеченных игроков — сначала `ingest-ti`")
            return

        for role, entries in candidates.items():
            banner = Banner(
                emblems=tuple(
                    Emblem(stat=s, quality="tier_3") for s in default_banners[role]
                ),
                role=role,
            )
            for team_id, team_name, account_ids in entries:
                history = build_role_history(
                    session, team_id, role, account_ids, since=None
                )
                if len(history.games) < args.min_games:
                    skipped.append(f"{team_name} / {role} ({len(history.games)} карт)")
                    continue
                projections.setdefault(role, {})[team_id] = projector.project(
                    history,
                    banner,
                    simulations=args.simulations,
                    series_distribution={args.series: 1.0},
                )

        team_names = {t.team_id: t.compendium_name or t.name for t in session.query(Team).all()}

    for role in sorted(projections):
        print(f"\n=== {role.upper()} ===")
        ranked = sorted(projections[role].items(), key=lambda kv: -kv[1].mean)
        print(f"{'Команда':<18}{'ожидание':>10}{'пол p5':>9}{'потолок p95':>13}{'карт':>6}")
        for team_id, projection in ranked:
            print(
                f"{team_names.get(team_id, team_id)!s:<18}{projection.mean:>10.0f}"
                f"{projection.floor:>9.0f}{projection.ceiling:>13.0f}{projection.games_used:>6}"
            )

    if len(projections) == 3:
        print("\n=== ЛУЧШИЕ РОСТЕРЫ (три разные команды) ===")
        for i, roster in enumerate(recommend_roster(projections, top_n=args.top), start=1):
            picks = ", ".join(
                f"{p.role}: {team_names.get(p.team_id, p.team_id)}" for p in roster.picks
            )
            print(f"{i}. {roster.expected_total:>8.0f}   {picks}")

    if skipped:
        print(f"\nпропущено (мало данных): {'; '.join(skipped)}")


def cmd_ratings(args: argparse.Namespace) -> None:
    with session_scope() as session:
        history = recompute_ratings(
            session, history_days=args.days, period_days=args.period
        )
    print(
        f"команд: {len(history.current)}, снимков: {len(history.snapshots)}, "
        f"надёжных: {len(history.listable())}"
    )


def cmd_teams(args: argparse.Namespace) -> None:
    with session_scope() as session:
        ratings = latest_ratings(session)
        teams = {t.team_id: t.name for t in session.query(Team).all()}

    rows = sorted(ratings.items(), key=lambda kv: -kv[1][0])[: args.limit]
    print(f"{'Команда':<28}{'Рейтинг':>9}{'RD':>7}")
    for team_id, (rating, rd, _) in rows:
        print(f"{teams.get(team_id, team_id)!s:<28}{rating:>9.0f}{rd:>7.0f}")


def cmd_group(args: argparse.Namespace) -> None:
    predictions = load_predictions_config()
    config = predictions.group_stage
    with session_scope() as session:
        ratings = latest_ratings(session)
        names = {
            t.team_id: t.compendium_name or t.name for t in session.query(Team).all()
        }

    if not ratings:
        print("нет рейтингов — сначала `ratings`")
        return

    # Считаем именно участников TI15, а не топ-16 всей базы.
    participants = [t for t in ti_team_ids() if t in ratings]
    if len(participants) == config.teams:
        chosen = participants
    else:
        missing = [n for t, n in ti_team_ids().items() if t not in ratings]
        print(f"без рейтинга: {', '.join(missing)} — беру топ-{config.teams} по рейтингу\n")
        chosen = sorted(ratings, key=lambda t: -ratings[t][0])[: config.teams]
    if len(chosen) < config.teams:
        print(f"нужно {config.teams} команд с рейтингом, есть {len(chosen)}")
        return

    first_round = predictions.first_round_for(chosen)
    if predictions.group_stage.swiss.first_round and not first_round:
        print("сетка первого раунда не подходит этому набору команд — раунд по посеву\n")
    simulator = SwissSimulator(
        {t: Rating(*ratings[t]) for t in chosen}, config, first_round=first_round
    )
    result = simulator.run(simulations=args.simulations)
    plan = optimise_group_predictions(result, config.slots(), config.points)

    header = f"{'Команда':<24}" + "".join(f"{b.label:>10}" for b in config.buckets) + f"{'проход':>9}"
    print(header)
    for i, team_id in enumerate(result.team_ids):
        cells = "".join(
            f"{result.probabilities[i, j] * 100:>9.1f}%" for j in range(len(result.bucket_keys))
        )
        print(f"{names.get(team_id, team_id)!s:<24}{cells}{result.advance_probability[i] * 100:>8.1f}%")

    print(f"\nОжидаемые очки плана: {plan.expected_points:.0f}")
    print(f"Угадано в среднем: {plan.expected_correct:.2f} из {config.teams}")
    for team_id, bucket in plan.assignment.items():
        print(f"  {names.get(int(team_id), team_id)!s:<24} -> {bucket}")


def cmd_roles(args: argparse.Namespace) -> None:
    with session_scope() as session:
        roles = infer_team_roles(session, args.team_id)
        if not roles:
            print(f"нет данных по команде {args.team_id}")
            return
        for role, accounts in roles.items():
            print(f"{role:<8} {list(accounts)}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Dota 2 Compendium Analyzer")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("ingest-feed", help="загрузить ленту про-матчей")
    p.add_argument("--days", type=int, default=30)
    p.add_argument("--pages", type=int, default=10)
    p.set_defaults(func=cmd_ingest_feed, is_async=True)

    p = sub.add_parser("ingest-team", help="загрузить историю команды")
    p.add_argument("team_id", type=int)
    p.add_argument("--days", type=int, default=120)
    p.set_defaults(func=cmd_ingest_team, is_async=True)

    p = sub.add_parser("resolve-teams", help="сопоставить участников TI15 с OpenDota")
    p.set_defaults(func=cmd_resolve_teams, is_async=True)

    p = sub.add_parser("ingest-ti", help="загрузить историю всех участников TI15")
    p.add_argument("--days", type=int, default=120)
    p.set_defaults(func=cmd_ingest_ti, is_async=True)

    p = sub.add_parser("ingest-heroes", help="обновить справочник героев")
    p.set_defaults(func=cmd_ingest_heroes, is_async=True)

    p = sub.add_parser("ingest-items", help="обновить справочник предметов")
    p.set_defaults(func=cmd_ingest_items, is_async=True)

    p = sub.add_parser(
        "backfill", help="перечитать матчи из локального кэша (без обращений к API)"
    )
    p.set_defaults(func=cmd_backfill, is_async=False)

    p = sub.add_parser("profile", help="профиль команды или игрока")
    p.add_argument("kind", choices=("team", "player"))
    p.add_argument("id", type=int)
    p.set_defaults(func=cmd_profile, is_async=False)

    p = sub.add_parser("roster", help="подобрать состав Fantasy из игроков TI15")
    p.add_argument("--banner", type=str, default=None, help="статы через запятую")
    p.add_argument("--simulations", type=int, default=4000)
    p.add_argument("--series", type=int, default=5, help="серий у команды за период")
    p.add_argument("--min-games", type=int, default=6, dest="min_games")
    p.add_argument("--top", type=int, default=5)
    p.add_argument("--seed", type=int, default=None)
    p.set_defaults(func=cmd_roster, is_async=False)

    p = sub.add_parser("ratings", help="пересчитать рейтинги")
    p.add_argument("--days", type=int, default=365)
    p.add_argument("--period", type=int, default=7)
    p.set_defaults(func=cmd_ratings, is_async=False)

    p = sub.add_parser("teams", help="показать рейтинг команд")
    p.add_argument("--limit", type=int, default=30)
    p.set_defaults(func=cmd_teams, is_async=False)

    p = sub.add_parser("group", help="симуляция группового этапа")
    p.add_argument("--simulations", type=int, default=20_000)
    p.set_defaults(func=cmd_group, is_async=False)

    p = sub.add_parser("roles", help="определить роли игроков команды")
    p.add_argument("team_id", type=int)
    p.set_defaults(func=cmd_roles, is_async=False)

    args = parser.parse_args()
    init_db()
    if args.is_async:
        asyncio.run(args.func(args))
    else:
        args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
