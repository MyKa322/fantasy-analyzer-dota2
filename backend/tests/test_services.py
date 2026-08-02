"""Тесты сервисного слоя: определение ролей, разметка участников, история роли."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.models import Base, Match, Player, PlayerMatchStat, Team, TeamRosterSlot
from app.services.analysis import (
    build_role_history,
    infer_team_roles,
    mark_ti_participants,
    ti_candidates,
    ti_team_ids,
)

NOW = datetime.now(timezone.utc)
LIQUID = 2163  # реальный team_id из конфига компендиума

# Позиции: два кора с высоким фармом, мид на центре, два саппорта с низким GPM.
ROSTER = {
    101: {"gpm": 700, "creep_score": 420, "lane_role": 1, "wards": 0},
    102: {"gpm": 560, "creep_score": 330, "lane_role": 3, "wards": 1},
    103: {"gpm": 640, "creep_score": 380, "lane_role": 2, "wards": 0},
    104: {"gpm": 300, "creep_score": 60, "lane_role": 4, "wards": 14},
    105: {"gpm": 250, "creep_score": 40, "lane_role": 5, "wards": 18},
}


def add_stat(
    session: Session,
    *,
    match_id: int,
    account_id: int,
    days_ago: float,
    gpm: float,
    team_id: int = LIQUID,
    lane_role: int = 1,
) -> None:
    """Одна строка статистики (и матч под неё, если его ещё нет)."""
    start = NOW - timedelta(days=days_ago)
    if session.get(Match, match_id) is None:
        session.add(
            Match(
                match_id=match_id,
                start_time=start,
                duration=2000,
                series_key=f"extra:{match_id}",
                radiant_team_id=team_id,
                dire_team_id=999,
                radiant_win=True,
                is_parsed=True,
            )
        )
    session.add(
        PlayerMatchStat(
            match_id=match_id,
            account_id=account_id,
            team_id=team_id,
            hero_id=1,
            is_radiant=True,
            won=True,
            lane_role=lane_role,
            start_time=start,
            stats={"gpm": gpm, "creep_score": gpm / 2, "kills": 5, "wards_placed": 1},
        )
    )


@pytest.fixture()
def session():
    engine = create_engine("sqlite://", future=True)
    Base.metadata.create_all(engine)
    with Session(engine, future=True) as session:
        seed(session)
        yield session
    engine.dispose()


@pytest.fixture()
def empty_session():
    """Чистая база — для сценариев, где стандартный ростер мешает."""
    engine = create_engine("sqlite://", future=True)
    Base.metadata.create_all(engine)
    with Session(engine, future=True) as session:
        yield session
    engine.dispose()


def seed(session: Session, *, games: int = 8, parsed: bool = True) -> None:
    session.add(Team(team_id=LIQUID, name="Team Liquid", compendium_name="Team Liquid"))
    for account_id in ROSTER:
        session.add(Player(account_id=account_id, name=f"player{account_id}"))

    for i in range(games):
        start = NOW - timedelta(days=i)
        session.add(
            Match(
                match_id=5000 + i,
                start_time=start,
                duration=2100,
                series_key=f"series:{i // 2}",
                radiant_team_id=LIQUID,
                dire_team_id=999,
                radiant_win=i % 2 == 0,
                is_parsed=parsed,
            )
        )
        for account_id, profile in ROSTER.items():
            session.add(
                PlayerMatchStat(
                    match_id=5000 + i,
                    account_id=account_id,
                    team_id=LIQUID,
                    hero_id=1,
                    is_radiant=True,
                    won=i % 2 == 0,
                    lane_role=profile["lane_role"],
                    start_time=start,
                    stats={
                        "gpm": profile["gpm"],
                        "creep_score": profile["creep_score"],
                        "kills": 6,
                        "wards_placed": profile["wards"],
                    },
                )
            )
    session.flush()


# --- определение ролей --------------------------------------------------------


def test_roles_split_into_core_mid_support(session):
    roles = infer_team_roles(session, LIQUID)
    assert set(roles) == {"core", "mid", "support"}
    assert len(roles["core"]) == 2
    assert len(roles["mid"]) == 1
    assert len(roles["support"]) == 2


def test_mid_detected_by_lane(session):
    roles = infer_team_roles(session, LIQUID)
    assert roles["mid"] == (103,)


def test_cores_detected_by_farm_priority(session):
    roles = infer_team_roles(session, LIQUID)
    assert set(roles["core"]) == {101, 102}
    assert set(roles["support"]) == {104, 105}


def test_unknown_team_gives_empty_roles(session):
    assert infer_team_roles(session, 777) == {}


def test_replaced_player_loses_the_slot_to_his_successor(empty_session):
    """Регрессия: состав отбирался по общему числу игр, и заменённый игрок
    оставался в ростере, если успел наиграть больше преемника.

    Ровно случай Team Vision: у SSS 55 карт в марте-апреле, у сменившего его
    Noticed — 50 в мае-июне, и на TI едет второй.
    """
    session = empty_session
    session.add(Team(team_id=LIQUID, name="Team Liquid", compendium_name="Team Liquid"))
    veteran, newcomer = 301, 302
    for account_id in (*ROSTER, veteran, newcomer):
        session.add(Player(account_id=account_id, name=f"p{account_id}"))

    # Старый состав: четверо постоянных плюс ветеран, много карт, но давно.
    for i in range(11):
        for account_id in (101, 102, 103, 104, veteran):
            add_stat(
                session,
                match_id=7000 + i,
                account_id=account_id,
                days_ago=60 + i,
                gpm=ROSTER.get(account_id, {"gpm": 300})["gpm"],
                lane_role=ROSTER.get(account_id, {"lane_role": 5})["lane_role"],
            )
    # Свежие матчи: на месте ветерана уже новичок, карт у него меньше.
    for i in range(8):
        for account_id in (101, 102, 103, 104, newcomer):
            add_stat(
                session,
                match_id=7100 + i,
                account_id=account_id,
                days_ago=i,
                gpm=ROSTER.get(account_id, {"gpm": 300})["gpm"],
                lane_role=ROSTER.get(account_id, {"lane_role": 5})["lane_role"],
            )
    session.flush()

    roles = infer_team_roles(session, LIQUID, min_games=2, recent_matches=8)
    squad = {a for group in roles.values() for a in group}

    assert newcomer in squad, "в ростер должен попасть тот, кто играет сейчас"
    assert veteran not in squad


def test_roster_override_replaces_automatic_pick(session, tmp_path):
    """Ручной состав из конфига важнее автоматики — на случай замены перед TI."""
    session.add(Player(account_id=401, name="standin"))
    for i in range(9):
        add_stat(session, match_id=7200 + i, account_id=401, days_ago=i, gpm=700)
    session.flush()

    override = tmp_path / "rosters.yaml"
    override.write_text(
        "overrides:\n"
        "  Team Liquid:\n"
        "    core: ['standin', 'player101']\n",
        encoding="utf-8",
    )

    from app.services import analysis

    roles = analysis.infer_team_roles(session, LIQUID)
    patched = analysis._apply_roster_override(
        session,
        LIQUID,
        "Team Liquid",
        roles,
        analysis.load_roster_overrides(override)["Team Liquid"],
    )
    assert patched["core"] == (401, 101)


def test_unknown_nickname_in_override_is_ignored(session, tmp_path, caplog):
    """Опечатка в конфиге не должна тихо привести в ростер постороннего."""
    from app.services import analysis

    roles = analysis.infer_team_roles(session, LIQUID)
    patched = analysis._apply_roster_override(
        session,
        LIQUID,
        "Team Liquid",
        roles,
        {"core": ["nosuchplayer", "player101"]},
    )
    assert patched["core"] == roles["core"]


def test_shipped_override_fixes_team_vision():
    """Конфиг в репозитории описывает актуальный состав Team Vision."""
    from app.services.analysis import load_roster_overrides

    overrides = load_roster_overrides()
    assert overrides["Team Vision"]["core"] == ["Satanic", "Noticed"]
    assert "SSS" not in str(overrides["Team Vision"])


def test_guest_core_does_not_push_out_a_regular_support(session):
    """Регрессия: чужой кор, сыгравший пару карт, вытеснял саппорта основы.

    Роли раздавались среди всех, кто попал в выборку, а сравнение шло по фарму —
    у заезжего кора он заведомо выше, чем у саппорта команды.
    """
    guest = 555
    session.add(Player(account_id=guest, name="guest_carry"))
    for i in range(3):  # всего три карты против восьми у основы
        session.add(
            PlayerMatchStat(
                match_id=5000 + i,
                account_id=guest,
                team_id=LIQUID,
                hero_id=2,
                is_radiant=True,
                won=True,
                lane_role=1,
                start_time=NOW - timedelta(days=i),
                stats={"gpm": 900, "creep_score": 600, "kills": 10, "wards_placed": 0},
            )
        )
    session.flush()

    roles = infer_team_roles(session, LIQUID, min_games=2)
    everyone = {a for group in roles.values() for a in group}

    assert guest not in everyone
    assert everyone == set(ROSTER)
    assert set(roles["support"]) == {104, 105}


# --- разметка участников ------------------------------------------------------


def test_ti_team_ids_cover_all_participants():
    teams = ti_team_ids()
    assert len(teams) == 16
    assert teams[LIQUID] == "Team Liquid"


def test_mark_participants_sets_roles(session):
    result = mark_ti_participants(session)
    assert result["Team Liquid"]["mid"] == (103,)

    mid = session.get(Player, 103)
    assert mid is not None
    assert mid.is_ti_participant is True
    assert mid.fantasy_role == "mid"
    assert mid.team_id == LIQUID


def test_mark_participants_is_idempotent(session):
    mark_ti_participants(session)
    mark_ti_participants(session)
    marked = [p for p in session.query(Player).all() if p.is_ti_participant]
    assert len(marked) == 5


def test_shared_player_does_not_erase_another_teams_roster(session):
    """Регрессия: роль хранилась одной строкой на игрока, поэтому команда,
    размеченная раньше, теряла состав, если её игрок сыграл и за другую."""
    other_team = 8255888  # BoomBoys, тоже участник TI15
    session.add(Team(team_id=other_team, name="BoomBoys", compendium_name="BoomBoys"))

    shared = 105  # саппорт Liquid, отыгравший несколько карт за вторую команду
    for i in range(6):
        match_id = 6000 + i
        start = NOW - timedelta(days=i)
        session.add(
            Match(
                match_id=match_id,
                start_time=start,
                duration=2000,
                series_key=f"other:{i}",
                radiant_team_id=other_team,
                dire_team_id=888,
                radiant_win=True,
                is_parsed=True,
            )
        )
        for account_id in (shared, 201, 202, 203, 204):
            session.add(
                PlayerMatchStat(
                    match_id=match_id,
                    account_id=account_id,
                    team_id=other_team,
                    hero_id=3,
                    is_radiant=True,
                    won=True,
                    lane_role=2 if account_id == 201 else 1,
                    start_time=start,
                    stats={"gpm": 500, "creep_score": 200, "kills": 5, "wards_placed": 3},
                )
            )
            if session.get(Player, account_id) is None:
                session.add(Player(account_id=account_id, name=f"p{account_id}"))
    session.flush()

    mark_ti_participants(session)
    candidates = ti_candidates(session)

    liquid_players = {
        account_id
        for entries in candidates.values()
        for team_id, _, account_ids in entries
        if team_id == LIQUID
        for account_id in account_ids
    }
    assert liquid_players == set(ROSTER), "состав Liquid не должен терять игроков"

    other_players = {
        account_id
        for entries in candidates.values()
        for team_id, _, account_ids in entries
        if team_id == other_team
        for account_id in account_ids
    }
    assert len(other_players) == 5
    assert shared in liquid_players and shared in other_players


def test_candidates_grouped_by_role(session):
    mark_ti_participants(session)
    candidates = ti_candidates(session)

    assert set(candidates) == {"core", "mid", "support"}
    team_id, name, account_ids = candidates["core"][0]
    assert team_id == LIQUID
    assert name == "Team Liquid"
    assert len(account_ids) == 2


# --- история роли -------------------------------------------------------------


def test_role_history_collects_games(session):
    history = build_role_history(session, LIQUID, "core", (101, 102))
    assert len(history.games) == 8
    assert history.team_name == "Team Liquid"
    assert set(history.games[0].player_stats) == {101, 102}


def test_role_history_orders_chronologically(session):
    history = build_role_history(session, LIQUID, "core", (101, 102))
    times = [g.start_time for g in history.games]
    assert times == sorted(times)


def test_role_history_respects_window(session):
    recent = build_role_history(
        session, LIQUID, "core", (101, 102), since=NOW - timedelta(days=3)
    )
    assert len(recent.games) < 8


def test_role_history_skips_unparsed_matches(session):
    for match in session.query(Match).all():
        match.is_parsed = False
    session.flush()

    history = build_role_history(session, LIQUID, "core", (101, 102))
    assert history.games == []

    # С parsed_only=False те же матчи возвращаются — но для Fantasy они не годятся.
    relaxed = build_role_history(
        session, LIQUID, "core", (101, 102), parsed_only=False
    )
    assert len(relaxed.games) == 8


def test_role_history_requires_players(session):
    with pytest.raises(ValueError, match="не заданы игроки"):
        build_role_history(session, LIQUID, "core", ())


def test_history_keeps_matches_played_under_a_previous_tag(session):
    """Коллектив переехал под новый бренд — его матчи выборке нужны.

    Iron Wing раньше играл как Tundra и 1w, LGD как HEROIC. Под новым тегом у
    них по два десятка карт, и выбрасывать прежние — значит остаться без данных.
    Признак «та же команда» — пересечение состава, а не совпадение team_id.
    """
    old_team = 555001  # тот же состав, другой team_id
    session.add(Team(team_id=old_team, name="Prev Brand"))
    for slot_role, ids in (("core", (101, 102)), ("mid", (103,)), ("support", (104, 105))):
        for account_id in ids:
            session.add(
                TeamRosterSlot(team_id=LIQUID, account_id=account_id, role=slot_role)
            )

    for i in range(5):
        for account_id in ROSTER:
            add_stat(
                session,
                match_id=8000 + i,
                account_id=account_id,
                days_ago=30 + i,
                gpm=ROSTER[account_id]["gpm"],
                team_id=old_team,
                lane_role=ROSTER[account_id]["lane_role"],
            )
    session.flush()

    history = build_role_history(session, LIQUID, "core", (101, 102))
    assert len(history.games) == 8 + 5


def test_history_drops_matches_played_for_another_squad(session):
    """Игрок перешёл из другой команды — его прежние карты к роли не относятся.

    Ровно случай Noticed: 26 карт за Team Yandex до перехода в Team Vision. Там
    были другие напарники, и «среднее по игрокам роли» считалось бы по одному
    человеку вместо двух.
    """
    for slot_role, ids in (("core", (101, 102)), ("mid", (103,)), ("support", (104, 105))):
        for account_id in ids:
            session.add(
                TeamRosterSlot(team_id=LIQUID, account_id=account_id, role=slot_role)
            )

    other_team = 555002
    session.add(Team(team_id=other_team, name="Previous Employer"))
    for i in range(6):
        # В этих картах из нынешнего состава есть только один игрок.
        add_stat(
            session,
            match_id=8100 + i,
            account_id=101,
            days_ago=40 + i,
            gpm=700,
            team_id=other_team,
        )
        for stranger in (901, 902, 903, 904):
            if session.get(Player, stranger) is None:
                session.add(Player(account_id=stranger, name=f"s{stranger}"))
            add_stat(
                session,
                match_id=8100 + i,
                account_id=stranger,
                days_ago=40 + i,
                gpm=500,
                team_id=other_team,
            )
    session.flush()

    history = build_role_history(session, LIQUID, "core", (101, 102))
    assert len(history.games) == 8, "карты в чужом составе не должны попадать в выборку"


def test_squad_overlap_can_be_disabled(session):
    """Фильтр можно отключить — например, чтобы сравнить выборки."""
    for slot_role, ids in (("core", (101, 102)), ("mid", (103,)), ("support", (104, 105))):
        for account_id in ids:
            session.add(
                TeamRosterSlot(team_id=LIQUID, account_id=account_id, role=slot_role)
            )
    other_team = 555003
    session.add(Team(team_id=other_team, name="Elsewhere"))
    for i in range(4):
        add_stat(
            session,
            match_id=8200 + i,
            account_id=101,
            days_ago=20 + i,
            gpm=700,
            team_id=other_team,
        )
    session.flush()

    filtered = build_role_history(session, LIQUID, "core", (101, 102))
    unfiltered = build_role_history(
        session, LIQUID, "core", (101, 102), min_squad_overlap=0
    )
    assert len(unfiltered.games) > len(filtered.games)


def test_no_filtering_without_a_marked_roster(session):
    """Пока состав не размечен, фильтровать не по чему — выборка берётся целиком,
    иначе анализ молча остался бы без данных."""
    other_team = 555004
    session.add(Team(team_id=other_team, name="Elsewhere"))
    for i in range(4):
        add_stat(
            session,
            match_id=8300 + i,
            account_id=101,
            days_ago=20 + i,
            gpm=700,
            team_id=other_team,
        )
    session.flush()

    history = build_role_history(session, LIQUID, "core", (101, 102))
    assert len(history.games) == 8 + 4
