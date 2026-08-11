"""Фичи уровня матча.

Всё, что описывает карту целиком: темп, размен, длительность, драфт. Это вход
для анализа команд — и для модели прогноза, которой рейтинга мало.
"""

from __future__ import annotations

from collections.abc import Mapping

from app.core import CanonicalMatch
from app.features.registry import match_feature, safe_ratio


@match_feature("shape", "duration_min", "radiant_win", "first_blood_min")
def shape(match: CanonicalMatch) -> Mapping[str, float]:
    """Форма карты: сколько шла, чем кончилась, когда пролилась первая кровь."""
    out: dict[str, float] = {}
    if match.duration:
        out["duration_min"] = match.duration / 60.0
    if match.radiant_win is not None:
        out["radiant_win"] = float(match.radiant_win)
    if match.first_blood_time is not None:
        # Может быть отрицательной: первая кровь до стартового горна — редкий,
        # но реальный случай, и обнулять его нельзя, на нём висит титул.
        out["first_blood_min"] = match.first_blood_time / 60.0
    return out


@match_feature(
    "tempo",
    "total_kills",
    "kill_diff",
    "kills_per_min",
)
def tempo(match: CanonicalMatch) -> Mapping[str, float]:
    """Темп размена: сколько убийств на карте и в чью пользу.

    Разница убийств берётся со знаком «в пользу Radiant», как и всё остальное в
    этом слое: одна сторона отсчёта на весь набор избавляет от разнобоя, где
    половина фич про Radiant, а половина про «победителя».
    """
    radiant = sum(p.fantasy.get("kills", 0.0) for p in match.players if p.is_radiant)
    dire = sum(p.fantasy.get("kills", 0.0) for p in match.players if not p.is_radiant)

    if not any(p.fantasy for p in match.players):
        return {}

    out: dict[str, float] = {
        "total_kills": radiant + dire,
        "kill_diff": radiant - dire,
    }
    per_min = safe_ratio(radiant + dire, match.duration / 60.0 if match.duration else None)
    if per_min is not None:
        out["kills_per_min"] = per_min
    return out


@match_feature(
    "economy",
    "networth_diff",
    "networth_total",
    "gpm_diff",
)
def economy(match: CanonicalMatch) -> Mapping[str, float]:
    """Экономический разрыв на конец карты.

    Это итог, а не траектория: поминутный график золота живёт только в реплее.
    Итог всё равно полезен — по нему видно, была игра разгромом или дожимом.
    """
    if not any(p.profile for p in match.players):
        return {}

    def side(is_radiant: bool, key: str, source: str = "profile") -> float:
        return sum(
            getattr(p, source).get(key, 0.0) for p in match.players if p.is_radiant is is_radiant
        )

    radiant_nw, dire_nw = side(True, "net_worth"), side(False, "net_worth")
    radiant_gpm = side(True, "gpm", "fantasy")
    dire_gpm = side(False, "gpm", "fantasy")

    out: dict[str, float] = {}
    if radiant_nw or dire_nw:
        out["networth_diff"] = radiant_nw - dire_nw
        out["networth_total"] = radiant_nw + dire_nw
    if radiant_gpm or dire_gpm:
        out["gpm_diff"] = radiant_gpm - dire_gpm
    return out


@match_feature("draft", "draft_known", "picks", "bans")
def draft(match: CanonicalMatch) -> Mapping[str, float]:
    """Полнота драфта.

    Пока это только «знаем ли мы драфт вообще»: содержательные фичи по героям
    требуют справочника ролей и мет-статистики, а тайминги пиков — реплея.
    Флаг нужен уже сейчас, чтобы модель могла отличить матч без драфта от матча,
    где драфта не было видно.
    """
    if not match.draft:
        return {"draft_known": 0.0}
    return {
        "draft_known": 1.0,
        "picks": float(sum(1 for p in match.draft if p.is_pick)),
        "bans": float(sum(1 for p in match.draft if not p.is_pick)),
    }
