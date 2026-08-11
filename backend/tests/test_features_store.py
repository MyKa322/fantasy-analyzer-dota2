"""Тесты материализации фич в базу.

Главное здесь — пересчёт по версии. Механизм скопирован с `STATS_VERSION` в
ingest именно потому, что там он уже спас базу от «половина матчей в старом
формате навсегда»; тест фиксирует, что он работает и для фич.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.core.db_adapter import from_db
from app.core.provenance import Source
from app.db.models import Base, Match, MatchFeature, Player, PlayerMatchFeature, PlayerMatchStat
from app.features import materialize
from app.features.registry import FEATURES_VERSION

NOW = datetime.now(timezone.utc)
RADIANT, DIRE = 11, 22


@pytest.fixture()
def session() -> Session:
    engine = create_engine("sqlite://", future=True)
    Base.metadata.create_all(engine)
    with Session(engine, future=True) as s:
        yield s


def seed_match(session: Session, *, match_id: int = 900, days_ago: float = 1.0) -> None:
    """Одна карта с десятью игроками и правдоподобными статами."""
    start = NOW - timedelta(days=days_ago)
    session.add(
        Match(
            match_id=match_id,
            start_time=start,
            duration=2400,
            series_key=f"series:{match_id}",
            radiant_team_id=RADIANT,
            dire_team_id=DIRE,
            radiant_win=True,
            is_parsed=True,
            stats_version=3,
        )
    )
    for slot in range(10):
        account_id = 1000 + slot
        is_radiant = slot < 5
        # Игроки общие для всех карт — вторая карта не должна их переcоздавать.
        if session.get(Player, account_id) is None:
            session.add(Player(account_id=account_id, name=f"p{slot}"))
        session.add(
            PlayerMatchStat(
                match_id=match_id,
                account_id=account_id,
                team_id=RADIANT if is_radiant else DIRE,
                hero_id=slot + 1,
                is_radiant=is_radiant,
                won=is_radiant,
                lane_role=1,
                stats={
                    "kills": float(slot),
                    "deaths": 2.0,
                    "creep_score": 100.0 + slot,
                    "gpm": 400.0 + slot,
                    "wards_placed": 3.0,
                    "camps_stacked": 1.0,
                    "runes_grabbed": 2.0,
                    "stuns": 5.0,
                },
                profile={
                    "assists": 4.0,
                    "net_worth": 10_000.0 + 100 * slot,
                    "hero_damage": 20_000.0,
                    "xpm": 500.0,
                },
                start_time=start,
                source=Source.OPENDOTA.value,
            )
        )
    session.flush()


def test_materialize_writes_both_tables(session):
    seed_match(session)
    result = materialize(session)

    assert result.matches == 1
    assert result.players == 10
    assert session.scalar(select(MatchFeature.match_id)) == 900
    assert len(list(session.scalars(select(PlayerMatchFeature)))) == 10


def test_materialize_is_idempotent(session):
    seed_match(session)
    materialize(session)
    second = materialize(session)

    # Второй прогон не находит устаревших строк и ничего не пишет.
    assert second.matches == 0
    assert second.skipped_up_to_date == 1
    assert len(list(session.scalars(select(PlayerMatchFeature)))) == 10


def test_version_bump_triggers_recompute(session, monkeypatch):
    """Строка, посчитанная старой версией, обязана быть переписана."""
    seed_match(session)
    materialize(session)

    row = session.scalar(select(MatchFeature))
    row.features_version = FEATURES_VERSION - 1
    row.features = {"stale": 1.0}
    session.flush()

    result = materialize(session)

    assert result.matches == 1
    refreshed = session.scalar(select(MatchFeature))
    assert refreshed.features_version == FEATURES_VERSION
    assert "stale" not in refreshed.features
    assert "duration_min" in refreshed.features


def test_force_recomputes_current_rows(session):
    seed_match(session)
    materialize(session)
    forced = materialize(session, force=True)
    assert forced.matches == 1


def test_since_window_limits_work(session):
    seed_match(session, match_id=900, days_ago=1.0)
    seed_match(session, match_id=901, days_ago=400.0)

    result = materialize(session, since=NOW - timedelta(days=30))

    assert result.matches == 1
    assert session.scalar(select(MatchFeature.match_id)) == 900


def test_no_duplicate_rows_on_repeated_force(session):
    seed_match(session)
    materialize(session)
    materialize(session, force=True)
    materialize(session, force=True)

    rows = list(session.scalars(select(PlayerMatchFeature)))
    assert len(rows) == 10  # уникальный ключ (match_id, account_id) держит


def test_db_adapter_round_trips_stats(session):
    """Канонический матч из базы должен нести те же статы, что записаны."""
    seed_match(session)
    match_row = session.get(Match, 900)
    stats = list(session.scalars(select(PlayerMatchStat).where(PlayerMatchStat.match_id == 900)))

    canonical = from_db(match_row, stats)

    assert len(canonical.players) == 10
    assert canonical.radiant_team_id == RADIANT
    assert canonical.sources == frozenset({Source.OPENDOTA})
    by_account = canonical.by_account
    assert by_account[1003].fantasy["kills"] == 3.0
    assert by_account[1003].profile["net_worth"] == 10_300.0
    assert by_account[1003].source_of("kills") is Source.OPENDOTA


def test_db_adapter_reports_replay_provenance(session):
    """Точечное отклонение по стату должно быть видно в провенансе."""
    seed_match(session)
    stat = session.scalar(select(PlayerMatchStat).where(PlayerMatchStat.account_id == 1000))
    stat.stats = {**stat.stats, "madstone_collected": 12.0}
    stat.stat_sources = {"madstone_collected": Source.REPLAY.value}
    session.flush()

    canonical = from_db(
        session.get(Match, 900),
        list(session.scalars(select(PlayerMatchStat).where(PlayerMatchStat.match_id == 900))),
    )
    player = canonical.by_account[1000]

    assert player.source_of("madstone_collected") is Source.REPLAY
    assert player.usable("madstone_collected")
    # Остальные статы остались опендотовскими.
    assert player.source_of("kills") is Source.OPENDOTA
    assert Source.REPLAY in canonical.sources
