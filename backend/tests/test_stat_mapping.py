"""Тесты разбора матча OpenDota в Fantasy-статы.

Фикстура `match_8922016200.json` — реальный разобранный матч (парсер v22),
урезанный до нужных полей скриптом `tools/make_fixture.py`.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from app.fantasy.rules import load_rules
from app.ingest.stat_mapping import (
    STAT_SOURCES,
    UNAVAILABLE_STATS,
    Availability,
    extract_match_stats,
    extract_player_stats,
    is_parsed,
    missing_stats,
    series_key,
)

FIXTURE = Path(__file__).parent / "fixtures" / "match_8922016200.json"


@pytest.fixture(scope="module")
def match():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


@pytest.fixture()
def first_player(match):
    return copy.deepcopy(match["players"][0])


def test_fixture_is_parsed(match):
    assert is_parsed(match)


def test_unparsed_match_detected(match):
    unparsed = copy.deepcopy(match)
    unparsed["version"] = None
    for player in unparsed["players"]:
        player.pop("stuns", None)
    assert not is_parsed(unparsed)


def test_every_config_stat_has_a_source():
    """Конфиг очков и маппинг не должны разъезжаться."""
    rules = load_rules()
    assert set(STAT_SOURCES) == set(rules.stats)


def test_extracted_keys_cover_all_config_stats(first_player):
    rules = load_rules()
    assert set(extract_player_stats(first_player)) == set(rules.stats)


def test_real_player_values(first_player):
    stats = extract_player_stats(first_player)
    assert stats["kills"] == 6
    assert stats["deaths"] == 10
    assert stats["creep_score"] == 53 + 15
    assert stats["gpm"] == 322
    assert stats["wards_placed"] == 9
    assert stats["camps_stacked"] == 2  # не creeps_stacked (там 5 крипов)
    assert stats["runes_grabbed"] == 5
    assert stats["smokes_used"] == 3
    assert stats["stuns"] == pytest.approx(26.700497)
    assert stats["teamfight_participation"] == pytest.approx(0.7222222)
    assert stats["first_blood"] == 0
    assert stats["tower_kills"] == 0
    assert stats["roshan_kills"] == 0


def test_camps_stacked_not_confused_with_creeps_stacked(match):
    """Разные вещи: лагерей 2, крипов в них 5. Глоссарий платит за лагеря."""
    player = match["players"][0]
    assert player["camps_stacked"] != player["creeps_stacked"]
    assert extract_player_stats(player)["camps_stacked"] == player["camps_stacked"]


def test_first_blood_claimed_by_exactly_one_player(match):
    claims = [extract_player_stats(p)["first_blood"] for p in match["players"]]
    assert sum(claims) == 1


def test_tormentor_taken_from_killed_dict(first_player):
    first_player["killed"] = {"npc_dota_miniboss": 2}
    assert extract_player_stats(first_player)["tormentor_kills"] == 2


def test_lotuses_sum_both_item_variants(first_player):
    first_player["item_uses"] = {"famango": 3, "great_famango": 1}
    assert extract_player_stats(first_player)["lotuses_grabbed"] == 4


def test_unavailable_stats_are_zero_not_missing(first_player):
    stats = extract_player_stats(first_player)
    for key in UNAVAILABLE_STATS:
        assert stats[key] == 0.0


def test_unavailable_set_matches_expectation():
    """Если OpenDota однажды добавит эти поля — тест напомнит обновить маппинг."""
    assert UNAVAILABLE_STATS == {"madstone_collected", "watchers_taken"}
    assert STAT_SOURCES["lotuses_grabbed"].availability is Availability.APPROXIMATE


def test_missing_stats_reports_only_unsupported():
    banner = ("kills", "gpm", "madstone_collected", "watchers_taken")
    assert missing_stats(banner) == ["madstone_collected", "watchers_taken"]


def test_nulls_are_treated_as_zero(first_player):
    first_player["kills"] = None
    first_player["stuns"] = None
    first_player["item_uses"] = None
    stats = extract_player_stats(first_player)
    assert stats["kills"] == 0.0
    assert stats["stuns"] == 0.0
    assert stats["smokes_used"] == 0.0


def test_extract_match_stats_indexes_by_account(match):
    by_account = extract_match_stats(match)
    assert len(by_account) == 10
    assert 87063175 in by_account
    assert by_account[87063175]["kills"] == 6


def test_anonymous_players_skipped(match):
    anonymised = copy.deepcopy(match)
    anonymised["players"][0]["account_id"] = None
    assert len(extract_match_stats(anonymised)) == 9


# --- ключ серии ---------------------------------------------------------------


def test_series_key_uses_series_id(match):
    assert series_key(match) == "series:1126029"


def test_series_key_falls_back_to_team_pair(match):
    without_series = copy.deepcopy(match)
    without_series["series_id"] = 0
    key = series_key(without_series)
    assert key.startswith("pair:")
    assert "day:" in key


def test_series_key_fallback_is_side_independent(match):
    """Одна и та же пара команд должна дать один ключ независимо от сторон."""
    a = copy.deepcopy(match)
    a["series_id"] = 0
    b = copy.deepcopy(a)
    b["radiant_team_id"], b["dire_team_id"] = a["dire_team_id"], a["radiant_team_id"]
    assert series_key(a) == series_key(b)
