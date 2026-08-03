"""Извлечение Fantasy-статов из разобранного матча OpenDota.

Маппинг проверен на реальном ответе `GET /api/matches/{id}` (версия парсера 22,
июль 2026), а не выведен из документации — часть полей в OpenDota дублируется
под разными именами, часть механик патча не трекается вовсе.

Доступность стата (`Availability`) — не декоративное поле: проекция обязана
показывать, что баннер с `madstone_collected` она оценить не может, вместо того
чтобы молча подставить ноль и занизить игрока.

ВАЖНО: у нераспарсенных матчей (`version: null` в /proMatches) нет ни вардов, ни
станов, ни тимфайтов — такие матчи в выборку для проекции брать нельзя.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class Availability(StrEnum):
    EXACT = "exact"
    """Поле есть напрямую и означает ровно то, что просит глоссарий."""

    APPROXIMATE = "approximate"
    """Считается через прокси — величина близка, но не тождественна."""

    UNAVAILABLE = "unavailable"
    """OpenDota такую механику не трекает."""


@dataclass(frozen=True, slots=True)
class StatSource:
    stat: str
    availability: Availability
    note: str = ""


# Витрина того, откуда берётся каждый стат. Используется и в UI ("почему этот
# стат не оценён"), и в тестах, чтобы список не разъезжался с кодом.
STAT_SOURCES: dict[str, StatSource] = {
    "kills": StatSource("kills", Availability.EXACT, "player.kills"),
    "deaths": StatSource("deaths", Availability.EXACT, "player.deaths"),
    "creep_score": StatSource(
        "creep_score", Availability.EXACT, "player.last_hits + player.denies"
    ),
    "gpm": StatSource("gpm", Availability.EXACT, "player.gold_per_min"),
    "tower_kills": StatSource(
        "tower_kills", Availability.EXACT, "player.tower_kills (ластхит по вышке)"
    ),
    "wards_placed": StatSource(
        "wards_placed", Availability.EXACT, "player.obs_placed (только observer)"
    ),
    "camps_stacked": StatSource(
        "camps_stacked",
        Availability.EXACT,
        "player.camps_stacked (не creeps_stacked — то число крипов, а не лагерей)",
    ),
    "runes_grabbed": StatSource("runes_grabbed", Availability.EXACT, "player.rune_pickups"),
    "smokes_used": StatSource(
        "smokes_used", Availability.EXACT, "player.item_uses.smoke_of_deceit"
    ),
    "roshan_kills": StatSource("roshan_kills", Availability.EXACT, "player.roshan_kills"),
    "teamfight_participation": StatSource(
        "teamfight_participation",
        Availability.EXACT,
        "player.teamfight_participation (доля 0..1, множится на потолок 2124)",
    ),
    "stuns": StatSource("stuns", Availability.EXACT, "player.stuns (секунды, float)"),
    "tormentor_kills": StatSource(
        "tormentor_kills",
        Availability.EXACT,
        "player.killed['npc_dota_miniboss']; objectives.CHAT_MESSAGE_MINIBOSS_KILL "
        "как фолбэк — у него ненадёжный slot",
    ),
    "first_blood": StatSource("first_blood", Availability.EXACT, "player.firstblood_claimed"),
    "courier_kills": StatSource("courier_kills", Availability.EXACT, "player.courier_kills"),
    "lotuses_grabbed": StatSource(
        "lotuses_grabbed",
        Availability.APPROXIMATE,
        "item_uses.famango + item_uses.great_famango — это ИСПОЛЬЗОВАННЫЕ лотосы; "
        "подобранный и переданный союзнику лотос сюда не попадёт",
    ),
    "madstone_collected": StatSource(
        "madstone_collected",
        Availability.UNAVAILABLE,
        "OpenDota не трекает мадстоуны; нужен STRATZ или парсинг реплея",
    ),
    "watchers_taken": StatSource(
        "watchers_taken",
        Availability.UNAVAILABLE,
        "OpenDota не трекает захват наблюдателей",
    ),
}

UNAVAILABLE_STATS = frozenset(
    k for k, v in STAT_SOURCES.items() if v.availability is Availability.UNAVAILABLE
)
APPROXIMATE_STATS = frozenset(
    k for k, v in STAT_SOURCES.items() if v.availability is Availability.APPROXIMATE
)

# Внутренние имена предметов-лотосов (Healing Lotus / Great Healing Lotus).
LOTUS_ITEMS = ("famango", "great_famango")


def _num(value: Any) -> float:
    """OpenDota местами присылает null вместо нуля."""
    if value is None:
        return 0.0
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    return 0.0


def extract_player_stats(player: Mapping[str, Any]) -> dict[str, float]:
    """Разложить объект игрока из матча OpenDota в статы Fantasy-конфига.

    Недоступные статы возвращаются нулями — сам факт недоступности выражен через
    `STAT_SOURCES`/`missing_stats`, а не через отсутствие ключа, чтобы движок
    очков работал единообразно.
    """
    item_uses: Mapping[str, Any] = player.get("item_uses") or {}
    killed: Mapping[str, Any] = player.get("killed") or {}

    return {
        "kills": _num(player.get("kills")),
        "deaths": _num(player.get("deaths")),
        "creep_score": _num(player.get("last_hits")) + _num(player.get("denies")),
        "gpm": _num(player.get("gold_per_min")),
        "madstone_collected": 0.0,
        "tower_kills": _num(player.get("tower_kills") or player.get("towers_killed")),
        "wards_placed": _num(player.get("obs_placed") or player.get("observers_placed")),
        "camps_stacked": _num(player.get("camps_stacked")),
        "runes_grabbed": _num(player.get("rune_pickups")),
        "watchers_taken": 0.0,
        "smokes_used": _num(item_uses.get("smoke_of_deceit")),
        "lotuses_grabbed": sum(_num(item_uses.get(i)) for i in LOTUS_ITEMS),
        "roshan_kills": _num(player.get("roshan_kills") or player.get("roshans_killed")),
        "teamfight_participation": _num(player.get("teamfight_participation")),
        "stuns": _num(player.get("stuns")),
        "tormentor_kills": _num(killed.get("npc_dota_miniboss")),
        "first_blood": _num(player.get("firstblood_claimed")),
        "courier_kills": _num(player.get("courier_kills")),
    }


# Версия набора данных о матче. Растёт, когда мы начинаем сохранять что-то
# новое: по ней ingest понимает, что матч уже в базе, но записан старым кодом и
# его надо перечитать. Без этого профиль игрока навсегда остался бы половинчатым
# — старые матчи никто бы не перезабрал.
STATS_VERSION = 2

# Поля профиля: в Fantasy они не участвуют, но именно из них состоит обычная
# статистика игрока — та, которую ждут на странице «сколько он фармит и как
# играет», а не «сколько очков приносит».
PROFILE_FIELDS = (
    "assists",
    "xpm",
    "net_worth",
    "hero_damage",
    "tower_damage",
    "hero_healing",
    "last_hits",
    "denies",
    "obs_placed",
    "sen_placed",
    "level",
    "gold_spent",
)


def extract_profile_stats(player: Mapping[str, Any]) -> dict[str, float]:
    """Обычная статистика игрока за карту — то, чего нет в Fantasy-наборе.

    Хранится отдельным полем, а не рядом с Fantasy-статами: у этих чисел другая
    роль. Fantasy-статы — вход движка очков, и любое лишнее поле в них рано или
    поздно попадёт в расчёт по ошибке.
    """
    return {
        "assists": _num(player.get("assists")),
        "xpm": _num(player.get("xp_per_min")),
        "net_worth": _num(player.get("net_worth") or player.get("total_gold")),
        "hero_damage": _num(player.get("hero_damage")),
        "tower_damage": _num(player.get("tower_damage")),
        "hero_healing": _num(player.get("hero_healing")),
        "last_hits": _num(player.get("last_hits")),
        "denies": _num(player.get("denies")),
        "obs_placed": _num(player.get("obs_placed") or player.get("observers_placed")),
        "sen_placed": _num(player.get("sen_placed") or player.get("sentries_placed")),
        "level": _num(player.get("level")),
        "gold_spent": _num(player.get("gold_spent")),
    }


def is_parsed(match: Mapping[str, Any]) -> bool:
    """Есть ли у матча разобранный реплей.

    Без него нет вардов, станов, тимфайтов и стаков — считать по такому матчу
    Fantasy-очки нельзя, это систематическое занижение.
    """
    if match.get("version") is None and "od_data" not in match:
        return False
    players = match.get("players") or []
    return any("stuns" in p and p.get("stuns") is not None for p in players)


def extract_match_stats(match: Mapping[str, Any]) -> dict[int, dict[str, float]]:
    """Статы всех игроков матча, ключ — account_id.

    Анонимные игроки (account_id отсутствует) пропускаются: сопоставить их с
    ростером всё равно невозможно.
    """
    result: dict[int, dict[str, float]] = {}
    for player in match.get("players") or []:
        account_id = player.get("account_id")
        if account_id is None:
            continue
        result[int(account_id)] = extract_player_stats(player)
    return result


def missing_stats(banner_stats: tuple[str, ...] | list[str]) -> list[str]:
    """Какие из статов баннера OpenDota не покрывает — для предупреждения в UI."""
    return [s for s in banner_stats if s in UNAVAILABLE_STATS]


def series_key(match: Mapping[str, Any]) -> str:
    """Идентификатор серии для правила «топ-2 карты одной серии».

    У OpenDota есть `series_id`, но у части матчей он нулевой — тогда серию
    склеиваем по паре команд и дате.
    """
    series_id = match.get("series_id")
    if series_id:
        return f"series:{series_id}"
    radiant = match.get("radiant_team_id") or 0
    dire = match.get("dire_team_id") or 0
    day = int(_num(match.get("start_time")) // 86400)
    lo, hi = sorted((int(radiant), int(dire)))
    return f"pair:{lo}-{hi}:day:{day}"
