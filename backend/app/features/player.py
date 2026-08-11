"""Фичи уровня «игрок в карте».

Ключевая идея набора — доли, а не абсолютные числа. 700 GPM у керри и 700 GPM у
саппорта означают разное, и сравнивать игроков по сырым величинам можно только
внутри одной роли на одном патче. Доля от команды (сколько золота, урона, убийств
пришлось на игрока) сравнима куда шире: она уже нормирована на то, насколько
хорошо шла игра у всей пятёрки.

Именно этого в проекте не было: `services/profiles.py` показывает сырые средние,
и по ним нельзя отличить сильного игрока в слабой команде от слабого в сильной.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from app.core import CanonicalMatch, PlayerGame
from app.features.registry import player_feature, safe_ratio


def _teammates(match: CanonicalMatch, player: PlayerGame) -> Sequence[PlayerGame]:
    return [p for p in match.players if p.is_radiant is player.is_radiant]


def _team_sum(match: CanonicalMatch, player: PlayerGame, key: str, source: str) -> float:
    return sum(getattr(p, source).get(key, 0.0) for p in _teammates(match, player))


@player_feature("rates", "cs_per_min", "kills_per_min", "deaths_per_min", "stuns_per_min")
def rates(match: CanonicalMatch, player: PlayerGame) -> Mapping[str, float]:
    """Величины в пересчёте на минуту.

    Без этого длинная карта автоматически выглядит результативнее короткой, и
    любой рейтинг по сумме за игру превращается в рейтинг по длительности матчей.
    """
    if not player.fantasy or not match.duration:
        return {}
    minutes = match.duration / 60.0

    out: dict[str, float] = {}
    for feature_key, stat in (
        ("cs_per_min", "creep_score"),
        ("kills_per_min", "kills"),
        ("deaths_per_min", "deaths"),
        ("stuns_per_min", "stuns"),
    ):
        value = safe_ratio(player.fantasy.get(stat), minutes)
        if value is not None:
            out[feature_key] = value
    return out


@player_feature("impact", "kda", "kill_participation", "death_share")
def impact(match: CanonicalMatch, player: PlayerGame) -> Mapping[str, float]:
    """Участие в разменах относительно своей команды.

    `kill_participation` — доля командных убийств, в которых игрок поучаствовал
    (убил или ассистировал). Это основная метрика вовлечённости саппорта, которую
    сырые килы не показывают вовсе.
    """
    if not player.fantasy:
        return {}

    kills = player.fantasy.get("kills", 0.0)
    deaths = player.fantasy.get("deaths", 0.0)
    assists = player.profile.get("assists")

    out: dict[str, float] = {}

    if assists is not None:
        # Классическая KDA: деление на max(deaths, 1), иначе безсмертная карта
        # даёт бесконечность. Единица — соглашение, а не измерение.
        out["kda"] = (kills + assists) / max(deaths, 1.0)

        team_kills = _team_sum(match, player, "kills", "fantasy")
        participation = safe_ratio(kills + assists, team_kills)
        if participation is not None:
            # Может превысить 1.0: за одно убийство засчитываются и убийца, и
            # все ассистенты. Не режем — это осмысленно, так видно, что игрок
            # присутствует почти в каждом размене.
            out["kill_participation"] = participation

    team_deaths = _team_sum(match, player, "deaths", "fantasy")
    share = safe_ratio(deaths, team_deaths)
    if share is not None:
        out["death_share"] = share
    return out


@player_feature("shares", "networth_share", "damage_share", "cs_share", "xpm_share")
def shares(match: CanonicalMatch, player: PlayerGame) -> Mapping[str, float]:
    """Доля игрока в ресурсах команды.

    Эти четыре числа вместе — почти готовое определение роли: у первой позиции
    высокая доля золота и добиваний, у саппорта низкая по обеим, у мида высокая
    доля опыта при средней доле золота. Роль сейчас угадывается по лейну
    (`services/analysis.py`), и на заменах это регулярно промахивается.
    """
    if not player.profile:
        return {}

    out: dict[str, float] = {}
    for feature_key, key, source in (
        ("networth_share", "net_worth", "profile"),
        ("damage_share", "hero_damage", "profile"),
        ("cs_share", "creep_score", "fantasy"),
        ("xpm_share", "xpm", "profile"),
    ):
        own = getattr(player, source).get(key)
        total = _team_sum(match, player, key, source)
        value = safe_ratio(own, total)
        if value is not None:
            out[feature_key] = value
    return out


@player_feature("support", "wards_per_min", "camps_stacked", "runes_grabbed")
def support(match: CanonicalMatch, player: PlayerGame) -> Mapping[str, float]:
    """Работа, которая не видна в KDA.

    Варды, стаки и руны — то, чем саппорт создаёт преимущество, не получая за
    него ни золота, ни опыта. Берутся только с разобранных карт: у нераспарсенных
    этих полей нет, и ноль здесь означал бы «не ставил вардов», а не «не знаем».
    """
    if not player.fantasy:
        return {}

    out: dict[str, float] = {}
    if match.duration:
        wards = safe_ratio(player.fantasy.get("wards_placed"), match.duration / 60.0)
        if wards is not None:
            out["wards_per_min"] = wards
    for key in ("camps_stacked", "runes_grabbed"):
        value = player.fantasy.get(key)
        if value is not None:
            out[key] = float(value)
    return out
