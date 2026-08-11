"""Тесты канонического слоя и провенанса.

Главное, что здесь проверяется, — адаптер не теряет данные. Канонический матч
вводится ровно затем, чтобы через него можно было пропустить всё остальное; если
он по дороге что-то съедает, слой не помогает, а вредит.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from app.core import (
    CanonicalMatch,
    Source,
    best_source,
    describe,
    from_opendota,
    merge_stats,
    unusable_stats,
)
from app.core.provenance import Availability
from app.ingest.stat_mapping import (
    STAT_SOURCES,
    extract_player_stats,
    extract_profile_stats,
    series_key,
)

FIXTURE = Path(__file__).parent / "fixtures" / "match_8922016200.json"


@pytest.fixture(scope="module")
def raw():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def match(raw) -> CanonicalMatch:
    return from_opendota(raw)


# --- адаптер не теряет данные -------------------------------------------------


def test_all_players_survive_adaptation(raw, match):
    assert len(match.players) == len(raw["players"]) == 10


def test_fantasy_stats_identical_to_direct_extraction(raw, match):
    """Канонический слой обязан отдавать ровно то же, что старый маппинг."""
    for payload, player in zip(raw["players"], match.players, strict=True):
        assert player.fantasy == extract_player_stats(payload)


def test_profile_stats_identical_to_direct_extraction(raw, match):
    for payload, player in zip(raw["players"], match.players, strict=True):
        assert player.profile == extract_profile_stats(payload)


def test_scalar_fields_survive(raw, match):
    assert match.match_id == raw["match_id"]
    assert match.duration == raw["duration"]
    assert match.radiant_win == raw["radiant_win"]
    assert match.patch == raw["patch"]
    assert match.league_id == raw["leagueid"]
    assert match.series_key == series_key(raw)
    assert match.start_time.timestamp() == raw["start_time"]


def test_sides_match_source(raw, match):
    for payload, player in zip(raw["players"], match.players, strict=True):
        assert player.is_radiant is bool(payload["isRadiant"])
        assert player.player_slot == payload["player_slot"]


# --- нераспарсенный матч ------------------------------------------------------


def test_unparsed_match_has_no_sources_and_no_stats(raw):
    unparsed = copy.deepcopy(raw)
    unparsed["version"] = None
    for player in unparsed["players"]:
        player.pop("stuns", None)

    match = from_opendota(unparsed)

    assert match.sources == frozenset()
    assert not match.has_detail
    # Пустой словарь, а не нули: нулями такая карта притворилась бы сыгранной
    # вхолостую и утянула бы вниз среднее игрока.
    assert all(p.fantasy == {} for p in match.players)
    assert all(not p.usable("kills") for p in match.players)


def test_parsed_match_reports_opendota_source(match):
    assert match.sources == frozenset({Source.OPENDOTA})
    assert match.has_detail
    assert not match.from_replay


# --- команды ------------------------------------------------------------------


def test_teams_split_by_side(raw, match):
    radiant, dire = match.teams
    assert radiant.is_radiant and not dire.is_radiant
    assert radiant.team_id == raw["radiant_team_id"]
    assert dire.team_id == raw["dire_team_id"]
    assert len(radiant.account_ids) == 5
    assert len(dire.account_ids) == 5


def test_team_won_follows_radiant_win(raw, match):
    radiant, dire = match.teams
    assert radiant.won is bool(raw["radiant_win"])
    assert dire.won is not bool(raw["radiant_win"])


def test_roster_key_is_order_independent(match):
    radiant, _ = match.teams
    shuffled = type(radiant)(
        team_id=radiant.team_id,
        is_radiant=radiant.is_radiant,
        won=radiant.won,
        account_ids=tuple(reversed(radiant.account_ids)),
    )
    assert shuffled.roster_key == radiant.roster_key


def test_opponent_lookup(raw, match):
    assert match.opponent_of(raw["radiant_team_id"]) == raw["dire_team_id"]
    assert match.opponent_of(raw["dire_team_id"]) == raw["radiant_team_id"]
    assert match.opponent_of(-1) is None


def test_by_account_skips_anonymous(raw):
    anonymised = copy.deepcopy(raw)
    anonymised["players"][0]["account_id"] = None
    match = from_opendota(anonymised)
    assert len(match.players) == 10
    assert len(match.by_account) == 9


# --- драфт --------------------------------------------------------------------


def test_draft_absent_when_source_has_none(match):
    """Фикстура урезана и `picks_bans` в ней нет — пустой драфт, а не выдуманный."""
    assert match.draft == ()


def test_draft_parsed_and_ordered(raw):
    with_draft = copy.deepcopy(raw)
    with_draft["picks_bans"] = [
        {"is_pick": True, "hero_id": 5, "team": 1, "order": 2},
        {"is_pick": False, "hero_id": 8, "team": 0, "order": 0},
        {"is_pick": True, "hero_id": 11, "team": 0, "order": 1},
    ]

    draft = from_opendota(with_draft).draft

    assert [p.order for p in draft] == [0, 1, 2]
    assert draft[0].hero_id == 8 and not draft[0].is_pick
    assert draft[0].is_radiant is True  # team 0 — Radiant
    assert draft[2].is_radiant is False  # team 1 — Dire
    # Таймингов у OpenDota нет ни у одного матча.
    assert all(p.time is None and p.reserve_time is None for p in draft)


# --- провенанс ----------------------------------------------------------------


def test_opendota_gaps_are_marked_unusable(match):
    player = match.players[0]
    assert not player.usable("madstone_collected")
    assert not player.usable("watchers_taken")
    assert player.usable("kills")
    assert player.source_of("kills") is Source.OPENDOTA


def test_replay_closes_the_gaps():
    assert describe("madstone_collected", Source.OPENDOTA).availability is Availability.UNAVAILABLE
    assert describe("madstone_collected", Source.REPLAY).availability is Availability.EXACT
    assert describe("watchers_taken", Source.REPLAY).availability is Availability.EXACT
    assert describe("lotuses_grabbed", Source.REPLAY).availability is Availability.EXACT


def test_replay_wins_ties_but_not_against_better_availability():
    both = {Source.OPENDOTA, Source.REPLAY}

    # Оба источника точны — берём свой.
    assert best_source("kills", both).source is Source.REPLAY
    # Только реплей что-то знает.
    assert best_source("madstone_collected", both).source is Source.REPLAY
    # Наша метрика участия — прокси, а поле OpenDota размечено как точное:
    # чужой прокси, совпадающий с сайтом, честнее нашего.
    assert best_source("teamfight_participation", both).source is Source.OPENDOTA


def test_merge_prefers_the_better_known_value():
    base = {"kills": 6.0, "madstone_collected": 0.0, "teamfight_participation": 0.72}
    overlay = {"kills": 6.0, "madstone_collected": 14.0, "teamfight_participation": 0.68}

    values, provenance = merge_stats(base, Source.OPENDOTA, overlay, Source.REPLAY)

    assert values["madstone_collected"] == 14.0
    assert provenance["madstone_collected"].source is Source.REPLAY
    assert values["teamfight_participation"] == 0.72
    assert provenance["teamfight_participation"].source is Source.OPENDOTA


def test_merge_keeps_stats_present_in_only_one_source():
    values, provenance = merge_stats({"kills": 3.0}, Source.OPENDOTA, {"stuns": 9.0}, Source.REPLAY)
    assert values == {"kills": 3.0, "stuns": 9.0}
    assert provenance["stuns"].source is Source.REPLAY


def test_unusable_stats_reports_per_match_not_per_source(match):
    banner = ("kills", "gpm", "madstone_collected", "watchers_taken")
    player = match.players[0]

    assert unusable_stats(player.provenance, banner) == ["madstone_collected", "watchers_taken"]

    # Тот же баннер на матче, разобранном нами, оценивается целиком.
    replayed = {s: describe(s, Source.REPLAY) for s in STAT_SOURCES}
    assert unusable_stats(replayed, banner) == []
