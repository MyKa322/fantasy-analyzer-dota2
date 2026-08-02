"""Тесты записи матчей в базу (SQLite в памяти)."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db.models import Base, Match, Player, PlayerMatchStat, Team
from app.ingest.pipeline import upsert_match

FIXTURE = Path(__file__).parent / "fixtures" / "match_8922016200.json"


@pytest.fixture(scope="module")
def match_payload():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


@pytest.fixture()
def session():
    engine = create_engine("sqlite://", future=True)
    Base.metadata.create_all(engine)
    with Session(engine, future=True) as session:
        yield session
    engine.dispose()


def test_match_and_stats_written(session, match_payload):
    upsert_match(session, match_payload)
    session.flush()

    match = session.get(Match, 8922016200)
    assert match is not None
    assert match.is_parsed
    assert match.league_id == 19917
    assert match.series_key == "series:1126029"
    assert match.radiant_win is False
    assert session.scalar(select(Match.duration)) == 2029

    stats = session.scalars(select(PlayerMatchStat)).all()
    assert len(stats) == 10
    assert all(s.start_time == match.start_time for s in stats)


def test_teams_and_players_created(session, match_payload):
    upsert_match(session, match_payload)
    session.flush()

    teams = {t.team_id: t.name for t in session.scalars(select(Team))}
    assert teams == {10207962: "Midas Club", 10207961: "Rune Eaters"}
    assert session.scalar(select(Player.name).where(Player.account_id == 87063175)) == "Lelis"


def test_player_side_and_result_recorded(session, match_payload):
    upsert_match(session, match_payload)
    session.flush()

    stat = session.scalar(
        select(PlayerMatchStat).where(PlayerMatchStat.account_id == 87063175)
    )
    assert stat is not None
    assert stat.is_radiant is True
    assert stat.team_id == 10207962
    # radiant_win = False, игрок за Radiant -> поражение
    assert stat.won is False
    assert stat.stats["kills"] == 6


def test_upsert_is_idempotent(session, match_payload):
    upsert_match(session, match_payload)
    session.flush()
    upsert_match(session, match_payload)
    session.flush()

    assert len(session.scalars(select(Match)).all()) == 1
    assert len(session.scalars(select(PlayerMatchStat)).all()) == 10


def test_reingest_updates_changed_values(session, match_payload):
    upsert_match(session, match_payload)
    session.flush()

    updated = copy.deepcopy(match_payload)
    updated["players"][0]["kills"] = 99
    upsert_match(session, updated)
    session.flush()

    stat = session.scalar(
        select(PlayerMatchStat).where(PlayerMatchStat.account_id == 87063175)
    )
    assert stat is not None and stat.stats["kills"] == 99


def test_unparsed_match_stored_without_player_stats(session, match_payload):
    unparsed = copy.deepcopy(match_payload)
    unparsed["version"] = None
    for player in unparsed["players"]:
        player.pop("stuns", None)

    row = upsert_match(session, unparsed)
    session.flush()

    assert row.is_parsed is False
    # Матч всё ещё годится для рейтинга команд, но статов игроков в нём нет.
    assert row.radiant_win is False
    assert session.scalars(select(PlayerMatchStat)).all() == []


def test_late_parse_backfills_stats(session, match_payload):
    """Матч сначала пришёл нераспарсенным, потом доехал разбор реплея."""
    unparsed = copy.deepcopy(match_payload)
    unparsed["version"] = None
    for player in unparsed["players"]:
        player.pop("stuns", None)
    upsert_match(session, unparsed)
    session.flush()
    assert session.scalars(select(PlayerMatchStat)).all() == []

    upsert_match(session, match_payload)
    session.flush()

    match = session.get(Match, 8922016200)
    assert match is not None and match.is_parsed
    assert len(session.scalars(select(PlayerMatchStat)).all()) == 10


def test_anonymous_player_is_skipped(session, match_payload):
    payload = copy.deepcopy(match_payload)
    payload["players"][0]["account_id"] = None
    upsert_match(session, payload)
    session.flush()

    assert len(session.scalars(select(PlayerMatchStat)).all()) == 9
