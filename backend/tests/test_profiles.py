"""Тесты профилей команд и игроков."""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import Base, Player, TeamRating, TeamRosterSlot
from app.ingest.pipeline import upsert_match
from app.ingest.stat_mapping import STATS_VERSION, extract_profile_stats
from app.services.profiles import (
    GameRow,
    _fantasy_form,
    _hero_pool,
    _trends,
    load_heroes,
    player_directory,
    player_profile,
    team_directory,
    team_profile,
)

FIXTURE = Path(__file__).parent / "fixtures" / "match_8922016200.json"
NOW = datetime.now(timezone.utc)


@pytest.fixture()
def session() -> Session:
    engine = create_engine("sqlite://", future=True)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    with factory() as active:
        yield active
    engine.dispose()


def seed(session: Session, *, copies: int = 6) -> dict:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    for offset in range(copies):
        clone = dict(payload)
        clone["match_id"] = payload["match_id"] + offset
        clone["start_time"] = payload["start_time"] + offset * 3600
        clone["series_id"] = payload["series_id"] + offset // 2
        upsert_match(session, clone)
    session.commit()
    return payload


# --- обычная статистика -------------------------------------------------------


def test_profile_stats_extracted_from_match(session):
    payload = seed(session, copies=1)
    radiant = next(p for p in payload["players"] if p["isRadiant"])
    profile = extract_profile_stats(radiant)

    assert profile["assists"] == float(radiant["assists"])
    assert profile["xpm"] == float(radiant["xp_per_min"])
    assert profile["net_worth"] == float(radiant["net_worth"])
    # Добивания есть и в Fantasy-наборе (внутри creep_score), и здесь — но
    # отдельно, потому что в профиле их читают как есть.
    assert profile["last_hits"] == float(radiant["last_hits"])


def test_match_records_stats_version(session):
    seed(session, copies=1)
    from app.db.models import Match

    match = session.scalars(session.query(Match).statement).first()
    assert match.stats_version == STATS_VERSION


def test_reingest_skips_only_current_version(session):
    """Матч, записанный старым кодом, должен перезабираться, а свежий — нет."""
    from app.db.models import Match
    from app.ingest.pipeline import ingest_matches

    payload = seed(session, copies=2)
    ids = [payload["match_id"], payload["match_id"] + 1]

    # Первый помечаем как записанный предыдущей версией набора полей.
    old = session.get(Match, ids[0])
    old.stats_version = STATS_VERSION - 1
    session.commit()

    class FakeClient:
        def __init__(self) -> None:
            self.asked: list[int] = []

        async def matches(self, match_ids, **_):
            self.asked = list(match_ids)
            return [], list(match_ids)

    client = FakeClient()
    import asyncio

    asyncio.run(ingest_matches(client, session, ids))
    assert client.asked == [ids[0]]


# --- профиль игрока -----------------------------------------------------------


def test_player_profile_collects_everything(session):
    payload = seed(session)
    player = next(p for p in payload["players"] if p["isRadiant"])
    account_id = player["account_id"]
    heroes = {int(player["hero_id"]): "Тестовый герой"}

    profile = player_profile(session, account_id, days=None, heroes=heroes)
    assert profile is not None
    assert profile.games == 6
    assert profile.parsed_games == 6
    assert profile.wins in range(0, 7)
    assert profile.averages["assists"] > 0
    assert profile.fantasy_units["gpm"] > 0
    assert profile.heroes and profile.heroes[0].games == 6
    assert profile.matches and profile.matches[0].hero_name == "Тестовый герой"
    # Матчи идут от свежих к старым — так их и читают.
    assert profile.matches[0].start_time >= profile.matches[-1].start_time


def test_player_profile_uses_roster_team_over_stale_field(session):
    """Роль и команда берутся из размеченного ростера, а не из поля игрока."""
    payload = seed(session)
    account_id = next(p["account_id"] for p in payload["players"] if p["isRadiant"])
    player = session.get(Player, account_id)
    player.team_id = 999999  # устаревшее поле, игрок давно перешёл
    session.add(TeamRosterSlot(team_id=10207962, account_id=account_id, role="support"))
    session.commit()

    profile = player_profile(session, account_id, days=None)
    assert profile.team_id == 10207962
    assert profile.role == "support"


def test_unknown_player_returns_none(session):
    assert player_profile(session, 4242, days=None) is None


def test_player_directory_skips_players_without_matches(session):
    seed(session)
    session.add(Player(account_id=777, name="Никогда не играл"))
    session.commit()

    rows = player_directory(session)
    assert 777 not in {row["account_id"] for row in rows}
    assert all(row["games"] > 0 for row in rows)


# --- профиль команды ----------------------------------------------------------


def test_team_profile_reports_record_and_roster(session):
    seed(session)
    profile = team_profile(session, 10207962, days=None)

    assert profile is not None
    assert profile.games == 6
    assert profile.wins + (profile.games - profile.wins) == profile.games
    assert len(profile.roster) == 5
    assert profile.team_averages["kills"] > 0
    # Командные средние — сумма пятерых, поэтому больше индивидуальных.
    best_player = max(profile.roster, key=lambda p: p.fantasy_units.get("kills", 0))
    assert profile.team_averages["kills"] > best_player.fantasy_units["kills"]


def test_team_profile_counts_opponents(session):
    seed(session)
    profile = team_profile(session, 10207962, days=None)
    assert profile.opponents
    team_id, name, games, wins = profile.opponents[0]
    # Id соперника нужен странице: по нему открываются личные встречи.
    assert team_id == 10207961
    assert name
    assert games == 6
    assert 0 <= wins <= games


def test_team_profile_includes_rating_history(session):
    seed(session)
    for day in range(3):
        session.add(
            TeamRating(
                team_id=10207962,
                as_of=NOW - timedelta(days=day),
                rating=1500 + day,
                rd=100 - day,
                volatility=0.06,
                matches_played=day,
                run_id="run",
            )
        )
    session.commit()

    profile = team_profile(session, 10207962, days=None)
    assert len(profile.rating_history) == 3
    assert profile.rating is not None
    # Последний снимок прогона — текущий рейтинг.
    assert profile.rating == pytest.approx(1500.0)


def test_unknown_team_returns_none(session):
    assert team_profile(session, 4242, days=None) is None


def test_team_directory_marks_ti_participants(session):
    seed(session)
    rows = {row["team_id"]: row for row in team_directory(session)}
    assert 10207962 in rows
    assert rows[10207962]["games"] == 6
    assert rows[10207962]["is_ti"] is False  # в конфиге TI15 этой команды нет


# --- справочник героев --------------------------------------------------------


def test_hero_directory_loads(tmp_path):
    path = tmp_path / "heroes.json"
    path.write_text(json.dumps({"1": "Anti-Mage", "2": "Axe"}), encoding="utf-8")
    assert load_heroes(path) == {1: "Anti-Mage", 2: "Axe"}


def test_missing_hero_directory_is_not_fatal(tmp_path):
    # Без справочника страница должна открываться — просто с id вместо имён.
    assert load_heroes(tmp_path / "нет.json") == {}


def test_averages_skip_matches_without_profile_stats(session):
    """Карта, забранная старым кодом, не должна занижать средние нулями."""
    payload = seed(session, copies=4)
    account_id = next(p["account_id"] for p in payload["players"] if p["isRadiant"])

    from app.db.models import PlayerMatchStat

    rows = list(
        session.scalars(
            session.query(PlayerMatchStat)
            .filter(PlayerMatchStat.account_id == account_id)
            .statement
        )
    )
    assists = float(rows[0].profile["assists"])
    # Две карты из четырёх — «старого» формата, без обычной статистики.
    for row in rows[:2]:
        row.profile = {}
    session.commit()

    profile = player_profile(session, account_id, days=None)
    assert profile.games == 4
    assert profile.averages["assists"] == pytest.approx(assists)
    # Fantasy-статы есть у всех карт, их выборка не сужается.
    assert profile.fantasy_units["kills"] > 0


# --- разрезы выборки ----------------------------------------------------------


def game(days_ago: float, won: bool | None, *, minutes: int = 35, radiant: bool = True) -> GameRow:
    return GameRow(
        played_at=NOW - timedelta(days=days_ago),
        won=won,
        duration=minutes * 60,
        is_radiant=radiant,
    )


def test_streak_counts_only_the_latest_run():
    """Серия — это последние подряд идущие карты, а не лучший отрезок периода."""
    rows = [game(1, True), game(2, True), game(3, False), game(4, True), game(5, True)]
    assert _trends(rows, now=NOW).streak == 2

    losses = [game(1, False), game(2, False), game(3, False), game(4, True)]
    assert _trends(losses, now=NOW).streak == -3


def test_streak_stops_at_a_game_without_result():
    assert _trends([game(1, True), game(2, None), game(3, True)], now=NOW).streak == 1


def test_form_window_does_not_overlap_the_baseline():
    rows = [game(5, True), game(20, False), game(45, True), game(60, True), game(200, True)]
    trends = _trends(rows, now=NOW)

    assert (trends.form.games, trends.form.wins) == (2, 1)
    # Карта 200-дневной давности не попадает ни в одно окно: базой сравнения
    # служат три месяца, иначе форму сравниваешь с прошлым составом.
    assert (trends.baseline.games, trends.baseline.wins) == (2, 2)


def test_sides_and_durations_cover_every_map():
    rows = [
        game(1, True, minutes=22, radiant=True),
        game(2, False, minutes=35, radiant=False),
        game(3, True, minutes=51, radiant=False),
    ]
    trends = _trends(rows, now=NOW)

    assert [s.games for s in trends.sides] == [1, 2]
    assert [d.key for d in trends.durations] == ["short", "mid", "long"]
    assert [d.games for d in trends.durations] == [1, 1, 1]
    assert sum(d.games for d in trends.durations) == len(rows)


def test_hero_pool_shows_concentration():
    pool = _hero_pool(Counter({1: 10, 2: 5, 3: 3, 4: 2}))
    assert pool.distinct == 4
    assert pool.top3_share == pytest.approx(18 / 20)


def test_fantasy_form_needs_a_sample():
    """По двум картам разброс не считается — лучше не показывать ничего."""
    assert _fantasy_form("core", [{"kills": 10.0}, {"kills": 8.0}]) is None


def test_fantasy_form_counts_only_stats_of_the_role():
    maps = [{"kills": 10.0, "wards_placed": 30.0} for _ in range(5)]
    form = _fantasy_form("core", maps)

    assert form is not None and form.maps == 5
    # Ставить варды кор может, но синего слота у его баннера нет — за них
    # красно-зелёная тройка очков не получит.
    kills_only = _fantasy_form("core", [{"kills": 10.0} for _ in range(5)])
    assert form.mean == pytest.approx(kills_only.mean)
    # Одинаковые карты — нулевой разброс.
    assert form.spread == pytest.approx(0.0)


def test_player_profile_carries_trends(session):
    payload = seed(session)
    account_id = next(p["account_id"] for p in payload["players"] if p["isRadiant"])
    profile = player_profile(session, account_id, days=None)

    assert profile.trends is not None
    # Все шесть карт — копии одной: одна сторона, одна длительность, один исход.
    assert abs(profile.trends.streak) == 6
    assert sum(s.games for s in profile.trends.sides) == 6
    assert sum(d.games for d in profile.trends.durations) == 6
    assert profile.hero_pool.distinct == 1
    assert profile.hero_pool.top3_share == pytest.approx(1.0)


def test_team_profile_measures_opponent_strength(session):
    seed(session)
    for team_id, rating in ((10207962, 1500.0), (10207961, 1700.0)):
        session.add(
            TeamRating(
                team_id=team_id,
                as_of=NOW,
                rating=rating,
                rd=60.0,
                volatility=0.06,
                matches_played=6,
                run_id="run",
            )
        )
    session.commit()

    profile = team_profile(session, 10207962, days=None)
    assert profile.opponent_rating == pytest.approx(1700.0)
    # Соперник сильнее — все шесть карт идут в этот разрез.
    assert profile.vs_stronger.games == 6
    assert profile.first_blood_rate is not None
    assert 0.0 <= profile.first_blood_rate <= 1.0


def test_team_averages_skip_matches_without_profile_stats(session):
    seed(session, copies=4)
    from app.db.models import PlayerMatchStat

    profile_before = team_profile(session, 10207962, days=None)

    rows = list(session.scalars(session.query(PlayerMatchStat).statement))
    stale = {row.match_id for row in rows[:20]}
    for row in rows:
        if row.match_id in stale:
            row.profile = {}
    session.commit()

    profile_after = team_profile(session, 10207962, days=None)
    assert profile_after.team_averages["assists"] == pytest.approx(
        profile_before.team_averages["assists"]
    )
    assert profile_after.team_averages["kills"] == pytest.approx(
        profile_before.team_averages["kills"]
    )
