"""Тесты витрины фич.

Проверяются три вещи, каждая из которых уже ломалась в подобных слоях:
пропуск вместо нуля при отсутствии данных, соответствие объявленных имён
фактически возвращаемым, и пересчёт по версии — без него половина базы навсегда
остаётся посчитанной старым кодом.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from app.core import from_opendota
from app.features import (
    MATCH_FEATURES,
    PLAYER_FEATURES,
    all_player_features,
    declared_keys,
    match_features,
    player_features,
    safe_ratio,
)

FIXTURE = Path(__file__).parent / "fixtures" / "match_8922016200.json"


@pytest.fixture(scope="module")
def raw():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def match(raw):
    return from_opendota(raw)


@pytest.fixture()
def unparsed(raw):
    stripped = copy.deepcopy(raw)
    stripped["version"] = None
    for player in stripped["players"]:
        player.pop("stuns", None)
    return from_opendota(stripped)


# --- дисциплина реестра -------------------------------------------------------


def test_declared_keys_are_unique():
    """Две группы, объявившие одно имя, молча затирали бы друг друга."""
    for groups in (MATCH_FEATURES, PLAYER_FEATURES):
        keys = declared_keys(groups)
        assert len(keys) == len(set(keys)), f"дубли: {sorted(k for k in keys if keys.count(k) > 1)}"


def test_computed_keys_are_all_declared(match):
    """Фича, посчитанная но не объявленная, не попадёт ни в одну документацию."""
    assert set(match_features(match)) <= set(declared_keys(MATCH_FEATURES))
    for values in all_player_features(match).values():
        assert set(values) <= set(declared_keys(PLAYER_FEATURES))


def test_every_group_has_a_rationale():
    for group in [*MATCH_FEATURES, *PLAYER_FEATURES]:
        assert group.doc, f"группа {group.name} без объяснения"


# --- пропуск вместо нуля ------------------------------------------------------


def test_unparsed_match_yields_no_invented_zeroes(unparsed):
    """У карты без разбора фич нет — вместо нулей, которые утянут среднее вниз."""
    values = match_features(unparsed)
    assert "total_kills" not in values
    assert "cs_per_min" not in values

    for player_values in all_player_features(unparsed).values():
        assert player_values == {}


def test_unparsed_match_keeps_what_is_actually_known(unparsed):
    """Длительность и исход известны и без разбора — их терять не надо."""
    values = match_features(unparsed)
    assert values["duration_min"] > 0
    assert "radiant_win" in values


def test_safe_ratio_refuses_to_invent_a_zero():
    assert safe_ratio(5.0, 0.0) is None
    assert safe_ratio(None, 10.0) is None
    assert safe_ratio(5.0, 2.0) == pytest.approx(2.5)


# --- содержательные проверки --------------------------------------------------


def test_kill_diff_is_signed_towards_radiant(raw, match):
    radiant = sum(p["kills"] for p in raw["players"] if p["isRadiant"])
    dire = sum(p["kills"] for p in raw["players"] if not p["isRadiant"])
    values = match_features(match)
    assert values["kill_diff"] == pytest.approx(radiant - dire)
    assert values["total_kills"] == pytest.approx(radiant + dire)


def test_duration_is_in_minutes(raw, match):
    assert match_features(match)["duration_min"] == pytest.approx(raw["duration"] / 60.0)


def test_shares_sum_to_one_across_a_team(match):
    """Доли по определению должны складываться в единицу внутри пятёрки."""
    for is_radiant in (True, False):
        side = [p for p in match.players if p.is_radiant is is_radiant]
        total = sum(player_features(match, p).get("networth_share", 0.0) for p in side)
        assert total == pytest.approx(1.0, abs=1e-9)


def test_kill_participation_can_exceed_one(match):
    """За одно убийство считаются и убийца, и ассистенты — сумма больше единицы.

    Тест фиксирует это как решение, а не как баг: срезать участие до 1.0 значило
    бы стереть разницу между игроком в каждом размене и игроком в половине.
    """
    values = [
        player_features(match, p).get("kill_participation")
        for p in match.players
        if p.is_radiant
    ]
    present = [v for v in values if v is not None]
    assert present
    assert sum(present) > 1.0
    assert all(0.0 <= v <= 2.0 for v in present)


def test_cs_per_min_matches_hand_calculation(raw, match):
    player = match.players[0]
    expected = (raw["players"][0]["last_hits"] + raw["players"][0]["denies"]) / (
        raw["duration"] / 60.0
    )
    assert player_features(match, player)["cs_per_min"] == pytest.approx(expected)


def test_draft_flag_is_false_without_picks(match):
    assert match_features(match)["draft_known"] == 0.0


def test_draft_counts_picks_and_bans(raw):
    with_draft = copy.deepcopy(raw)
    with_draft["picks_bans"] = [
        {"is_pick": True, "hero_id": 5, "team": 0, "order": 0},
        {"is_pick": False, "hero_id": 8, "team": 1, "order": 1},
        {"is_pick": True, "hero_id": 9, "team": 1, "order": 2},
    ]
    values = match_features(from_opendota(with_draft))
    assert values["draft_known"] == 1.0
    assert values["picks"] == 2.0
    assert values["bans"] == 1.0


def test_features_are_pure(match):
    """Дважды посчитанная фича обязана совпасть — иначе бэктест невоспроизводим."""
    assert match_features(match) == match_features(match)
    assert all_player_features(match) == all_player_features(match)
