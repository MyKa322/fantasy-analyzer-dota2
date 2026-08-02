"""Собрать компактную тестовую фикстуру из реального матча OpenDota.

Полное тело матча весит несколько мегабайт (таймсерии по золоту, лог действий,
покупки посекундно) — в репозиторий такое класть незачем. Скрипт оставляет
только те поля, на которых работает `stat_mapping`.

    python tools/make_fixture.py 8922016200
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx

FIXTURE_DIR = Path(__file__).resolve().parent.parent / "tests" / "fixtures"

MATCH_KEYS = (
    "match_id",
    "start_time",
    "duration",
    "leagueid",
    "league",
    "series_id",
    "series_type",
    "radiant_team_id",
    "dire_team_id",
    "radiant_name",
    "dire_name",
    "radiant_team",
    "dire_team",
    "radiant_win",
    "patch",
    "version",
    "region",
)

PLAYER_KEYS = (
    "account_id",
    "name",
    "personaname",
    "player_slot",
    "isRadiant",
    "hero_id",
    "kills",
    "deaths",
    "assists",
    "last_hits",
    "denies",
    "gold_per_min",
    "xp_per_min",
    "net_worth",
    "tower_kills",
    "towers_killed",
    "obs_placed",
    "observers_placed",
    "camps_stacked",
    "creeps_stacked",
    "rune_pickups",
    "roshan_kills",
    "roshans_killed",
    "courier_kills",
    "teamfight_participation",
    "stuns",
    "firstblood_claimed",
    "lane_role",
    "item_uses",
)

# Из огромного словаря убитых юнитов оставляем только то, что влияет на очки.
KILLED_KEYS = ("npc_dota_miniboss", "npc_dota_roshan", "npc_dota_courier")


def slim(match: dict) -> dict:
    result = {k: match.get(k) for k in MATCH_KEYS if k in match}
    result["objectives"] = [
        o
        for o in (match.get("objectives") or [])
        if o.get("type")
        in {"CHAT_MESSAGE_FIRSTBLOOD", "CHAT_MESSAGE_ROSHAN_KILL", "CHAT_MESSAGE_MINIBOSS_KILL"}
    ]
    players = []
    for player in match.get("players") or []:
        slim_player = {k: player.get(k) for k in PLAYER_KEYS if k in player}
        killed = player.get("killed") or {}
        slim_player["killed"] = {k: killed[k] for k in KILLED_KEYS if k in killed}
        players.append(slim_player)
    result["players"] = players
    return result


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    match_id = int(sys.argv[1])
    response = httpx.get(f"https://api.opendota.com/api/matches/{match_id}", timeout=120)
    response.raise_for_status()
    match = response.json()

    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    path = FIXTURE_DIR / f"match_{match_id}.json"
    path.write_text(json.dumps(slim(match), ensure_ascii=False, indent=1), encoding="utf-8")
    parsed = "parsed" if match.get("version") is not None else "UNPARSED"
    print(f"{path} ({path.stat().st_size / 1024:.0f} KB, {parsed})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
