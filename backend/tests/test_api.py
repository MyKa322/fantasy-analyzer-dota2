"""Сквозные тесты API на временной базе."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import Base, Match, Team, TeamRosterSlot
from app.db.session import get_db
from app.ingest.pipeline import upsert_match
from app.main import app

FIXTURE = Path(__file__).parent / "fixtures" / "match_8922016200.json"
NOW = datetime.now(timezone.utc)


@pytest.fixture()
def session_factory():
    # StaticPool + check_same_thread: TestClient обрабатывает запросы в отдельном
    # потоке, а обычный пул выдал бы ему собственную (пустую) in-memory базу.
    engine = create_engine(
        "sqlite://",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine, expire_on_commit=False, future=True)
    engine.dispose()


@pytest.fixture()
def client(session_factory):
    def override_get_db():
        session = session_factory()
        try:
            yield session
            session.commit()
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    # TestClient без контекстного менеджера не запускает lifespan — а он поднял бы
    # планировщик и создал настоящий файл базы рядом с проектом.
    yield TestClient(app)
    app.dependency_overrides.clear()


def seed_tournament(session: Session, *, teams: int = 16, days: int = 60) -> list[int]:
    """Синтетический турнир: команды с явной иерархией силы играют круговой цикл."""
    team_ids = list(range(1, teams + 1))
    for team_id in team_ids:
        session.add(
            Team(team_id=team_id, name=f"Team {team_id}", compendium_name=f"Team {team_id}")
        )

    match_id = 1
    start = NOW - timedelta(days=days)
    for round_index in range(6):
        for i in range(0, teams, 2):
            radiant, dire = team_ids[i], team_ids[(i + 1 + round_index) % teams]
            if radiant == dire:
                continue
            session.add(
                Match(
                    match_id=match_id,
                    start_time=start + timedelta(days=round_index * 7),
                    duration=2000,
                    series_key=f"series:{match_id}",
                    radiant_team_id=radiant,
                    dire_team_id=dire,
                    radiant_win=radiant < dire,  # меньший id = сильнее
                    is_parsed=False,
                )
            )
            match_id += 1
    session.commit()
    return team_ids


# --- конфигурация -------------------------------------------------------------


def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok"}


def test_fantasy_rules_endpoint_exposes_ti15_numbers(client):
    payload = client.get("/api/config/fantasy").json()
    assert payload["version"] == "TI15"
    kills = next(s for s in payload["stats"] if s["key"] == "kills")
    assert kills["per_unit"] == 107.0
    assert payload["qualities"]["tier_5"] == 1.5
    assert {t["key"] for t in payload["traits"]} == {
        "fractal",
        "benevolent",
        "vampiric",
        "unique",
        "friendly",
    }


def test_fantasy_rules_flag_unavailable_stats(client):
    payload = client.get("/api/config/fantasy").json()
    unavailable = {s["stat"] for s in payload["sources"] if s["availability"] == "unavailable"}
    assert unavailable == {"madstone_collected", "watchers_taken"}


def test_predictions_config_endpoint(client):
    payload = client.get("/api/config/predictions").json()
    assert len(payload["teams"]) == 16
    assert "Team Spirit" in payload["teams"]
    assert sum(b["slots"] for b in payload["buckets"]) == 16
    assert len(payload["bracket_slots"]) == 14


# --- команды и рейтинги -------------------------------------------------------


def test_teams_empty_by_default(client):
    assert client.get("/api/teams").json() == []


def test_group_prediction_requires_ratings(client):
    response = client.get("/api/predictions/group")
    assert response.status_code == 400
    assert "рейтинг" in response.json()["detail"].lower()


def test_rating_history_requires_recompute(client):
    assert client.get("/api/teams/1/rating-history").status_code == 404


def test_full_prediction_flow(client, session_factory):
    with session_factory() as session:
        seed_tournament(session)

    recompute = client.post("/api/ratings/recompute").json()
    assert recompute["teams"] == 16
    assert recompute["snapshots"] > 0

    teams = client.get("/api/teams").json()
    assert len(teams) == 16
    assert teams[0]["rating"] > teams[-1]["rating"]

    history = client.get(f"/api/teams/{teams[0]['team_id']}/rating-history").json()
    assert len(history["points"]) > 0

    group = client.get("/api/predictions/group", params={"simulations": 400, "seed": 1}).json()
    assert group["simulations"] == 400
    assert len(group["teams"]) == 16
    assert len(group["plan"]) == 16
    assert group["expected_points"] > 0
    # Сильнейшая команда проходит чаще слабейшей.
    assert group["teams"][0]["advance"] > group["teams"][-1]["advance"]
    # Вероятности по корзинам нормированы.
    for team in group["teams"]:
        assert sum(team["probabilities"].values()) == pytest.approx(1.0, abs=0.01)


def test_bracket_prediction_flow(client, session_factory):
    with session_factory() as session:
        seed_tournament(session)
    client.post("/api/ratings/recompute")

    response = client.get(
        "/api/predictions/bracket",
        params=[("simulations", 400), ("seed", 2)] + [("team_ids", i) for i in range(1, 9)],
    )
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["plan"]) == 14
    assert sum(payload["champion_probability"].values()) == pytest.approx(1.0, abs=0.01)


def test_bracket_requires_eight_teams(client, session_factory):
    with session_factory() as session:
        seed_tournament(session)
    client.post("/api/ratings/recompute")

    response = client.get(
        "/api/predictions/bracket",
        params=[("team_ids", i) for i in range(1, 5)],
    )
    assert response.status_code == 400


# --- fantasy ------------------------------------------------------------------


def test_roles_endpoint_requires_data(client):
    assert client.get("/api/fantasy/roles/999").status_code == 404


def test_projection_flow_on_real_match(client, session_factory):
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    with session_factory() as session:
        # Один и тот же матч под несколькими id — минимальная история для проекции.
        for offset in range(6):
            clone = dict(payload)
            clone["match_id"] = payload["match_id"] + offset
            clone["start_time"] = payload["start_time"] + offset * 3600
            clone["series_id"] = payload["series_id"] + offset // 2
            upsert_match(session, clone)
        session.commit()

    roles = client.get("/api/fantasy/roles/10207962").json()
    assert set(roles["roles"]) == {"core", "mid", "support"}
    assert len(roles["roles"]["core"]) == 2
    assert len(roles["roles"]["mid"]) == 1

    response = client.post(
        "/api/fantasy/project",
        json={
            "team_id": 10207962,
            "role": "core",
            "simulations": 500,
            "history_days": 3650,
            "banner": {
                "emblems": [
                    {"stat": "kills", "quality": "tier_3", "trait": "benevolent"},
                    {"stat": "gpm", "quality": "tier_4"},
                ]
            },
        },
    )
    assert response.status_code == 200, response.text
    projection = response.json()
    assert projection["mean"] > 0
    assert projection["floor_p5"] <= projection["median"] <= projection["ceiling_p95"]
    assert projection["games_used"] > 0
    assert projection["unavailable_stats"] == []


def test_projection_reports_unavailable_stats(client, session_factory):
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    with session_factory() as session:
        upsert_match(session, payload)
        session.commit()

    response = client.post(
        "/api/fantasy/project",
        json={
            "team_id": 10207962,
            "role": "mid",
            "simulations": 200,
            "history_days": 3650,
            "banner": {"emblems": [{"stat": "madstone_collected", "quality": "tier_5"}]},
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["unavailable_stats"] == ["madstone_collected"]


def test_banner_optimisation_flow(client, session_factory):
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    with session_factory() as session:
        for offset in range(4):
            clone = dict(payload)
            clone["match_id"] = payload["match_id"] + offset
            clone["start_time"] = payload["start_time"] + offset * 3600
            upsert_match(session, clone)
        session.commit()

    response = client.post(
        "/api/fantasy/optimise-banner",
        json={
            "team_id": 10207962,
            "role": "support",
            "history_days": 3650,
            "slots": 2,
            "shortlist": 6,
            "simulations": 300,
            "top_n": 3,
            "available_emblems": [
                {"stat": "wards_placed", "quality": "tier_4"},
                {"stat": "camps_stacked", "quality": "tier_3"},
                {"stat": "kills", "quality": "tier_1"},
            ],
        },
    )
    assert response.status_code == 200, response.text
    options = response.json()
    assert 1 <= len(options) <= 3
    assert options[0]["mean"] >= options[-1]["mean"]
    assert len(options[0]["emblems"]) == 2


# --- анализатор эмблем --------------------------------------------------------


def seed_role_history(session_factory, *, copies: int = 8) -> None:
    """Несколько копий реального матча — минимальная история для анализа."""
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    with session_factory() as session:
        for offset in range(copies):
            clone = dict(payload)
            clone["match_id"] = payload["match_id"] + offset
            clone["start_time"] = payload["start_time"] + offset * 3600
            clone["series_id"] = payload["series_id"] + offset // 2
            upsert_match(session, clone)
        session.commit()


def test_stat_report_returns_role_colours_only(client, session_factory):
    seed_role_history(session_factory)
    response = client.post(
        "/api/fantasy/stat-report",
        json={"team_id": 10207962, "role": "support", "history_days": 3650},
    )
    assert response.status_code == 200, response.text
    stats = response.json()
    assert stats
    colours = {s["color"] for s in stats}
    assert colours <= {"blue", "green"}  # у саппорта нет красных слотов
    assert stats[0]["base_points"] >= stats[-1]["base_points"]


def test_best_banner_respects_slot_colours(client, session_factory):
    seed_role_history(session_factory)
    response = client.post(
        "/api/fantasy/best-banner",
        json={
            "team_id": 10207962,
            "role": "core",
            "history_days": 3650,
            "simulate": False,
            "top_n": 2,
        },
    )
    assert response.status_code == 200, response.text
    advices = response.json()
    assert len(advices) == 2
    assert [s["color"] for s in advices[0]["slots"]] == ["red", "red", "green"]
    assert advices[0]["expected_card_points"] >= advices[1]["expected_card_points"]
    assert all(s["percent"] >= 100 for s in advices[0]["slots"])


def test_best_banner_can_be_restricted_to_rolled_options(client, session_factory):
    seed_role_history(session_factory)
    response = client.post(
        "/api/fantasy/best-banner",
        json={
            "team_id": 10207962,
            "role": "mid",
            "history_days": 3650,
            "simulate": False,
            "top_n": 1,
            "qualities": ["tier_1", "tier_2"],
            "traits": [None, "vampiric"],
        },
    )
    assert response.status_code == 200, response.text
    slots = response.json()[0]["slots"]
    assert {s["quality"] for s in slots} <= {"tier_1", "tier_2"}
    assert {s["trait"] for s in slots} <= {None, "vampiric"}
    assert [s["color"] for s in slots] == ["red", "blue", "green"]


def test_evaluate_swap_reports_delta(client, session_factory):
    seed_role_history(session_factory)
    response = client.post(
        "/api/fantasy/evaluate-swap",
        json={
            "team_id": 10207962,
            "role": "core",
            "history_days": 3650,
            "slot": 0,
            "banner": {
                "emblems": [
                    {"stat": "gpm", "quality": "tier_1"},
                    {"stat": "kills", "quality": "tier_1"},
                    {"stat": "stuns", "quality": "tier_1"},
                ]
            },
            "candidate": {"stat": "gpm", "quality": "tier_5"},
        },
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["delta"] > 0
    assert result["after"] > result["before"]


def test_titles_endpoint_estimates_from_data(client, session_factory):
    seed_role_history(session_factory)
    response = client.post(
        "/api/fantasy/titles",
        json={"team_id": 10207962, "role": "core", "history_days": 3650},
    )
    assert response.status_code == 200, response.text
    titles = {t["key"]: t for t in response.json()}
    assert titles["decisive"]["expected_bonus"] is not None
    # Условия вне наших данных честно помечены, а не выдуманы.
    assert titles["tormented"]["expected_bonus"] is None
    assert titles["tormented"]["note"]


def test_stat_ranking_requires_marked_players(client):
    assert client.get("/api/fantasy/stat-ranking/wards_placed").status_code == 400


def test_stat_ranking_rejects_unknown_stat(client, session_factory):
    seed_role_history(session_factory)
    with session_factory() as session:
        session.add(
            TeamRosterSlot(team_id=10207962, account_id=87063175, role="core")
        )
        session.commit()
    assert client.get("/api/fantasy/stat-ranking/nonsense").status_code in (400, 404)


def test_projection_rejects_unknown_role(client):
    response = client.post(
        "/api/fantasy/project",
        json={
            "team_id": 1,
            "role": "jungle",
            "banner": {"emblems": [{"stat": "kills", "quality": "tier_1"}]},
        },
    )
    assert response.status_code == 400


# --- разбивка по игрокам и свой инвентарь --------------------------------------


def seed_ti_role_history(session_factory, *, copies: int = 8) -> tuple[int, list[int]]:
    """Тот же матч, но за команду-участницу TI15: без этого её нет в кандидатах.

    Возвращает id команды и account_id её игроков — рейтинг инвентаря идёт по
    размеченным ростерам, а не по всем, кто попал в базу.
    """
    from app.services.analysis import ti_team_ids

    team_id = next(iter(ti_team_ids()))
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    payload["radiant_team_id"] = team_id
    payload["radiant_team"] = {"team_id": team_id, "name": "TI Team", "tag": "TI"}
    accounts = [p["account_id"] for p in payload["players"] if p["isRadiant"]]

    with session_factory() as session:
        for offset in range(copies):
            clone = dict(payload)
            clone["match_id"] = payload["match_id"] + offset
            clone["start_time"] = payload["start_time"] + offset * 3600
            clone["series_id"] = payload["series_id"] + offset // 2
            upsert_match(session, clone)
        session.commit()
    return team_id, accounts


def test_player_report_splits_the_role(client, session_factory):
    seed_role_history(session_factory)
    response = client.post(
        "/api/fantasy/players",
        json={"team_id": 10207962, "role": "core", "history_days": 3650},
    )
    assert response.status_code == 200, response.text
    profiles = response.json()
    assert len(profiles) == 2  # core duo
    for profile in profiles:
        assert profile["games"] > 0
        assert profile["values"]
        assert {v["color"] for v in profile["values"]} <= {"red", "green"}


def test_stat_report_carries_pinpoint_numbers(client, session_factory):
    seed_role_history(session_factory)
    stats = client.post(
        "/api/fantasy/stat-report",
        json={"team_id": 10207962, "role": "support", "history_days": 3650},
    ).json()
    wards = next(s for s in stats if s["stat"] == "wards_placed")
    assert wards["hit_rate"] > 0
    assert wards["p5_points"] <= wards["median_points"] <= wards["p95_points"]
    assert wards["median_points"] <= wards["p75_points"] <= wards["p95_points"]


def test_inventory_ranks_pairs_for_the_emblems_you_own(client, session_factory):
    team_id, accounts = seed_ti_role_history(session_factory)
    with session_factory() as session:
        for account_id in accounts[:2]:
            session.add(
                TeamRosterSlot(team_id=team_id, account_id=account_id, role="support")
            )
        session.commit()

    response = client.post(
        "/api/fantasy/inventory",
        json={
            "history_days": 3650,
            "min_games": 1,
            "inventory": [
                {"stat": "wards_placed", "quality": "tier_4", "trait": "benevolent"},
                {"stat": "camps_stacked", "quality": "tier_2", "trait": None},
                {"stat": "stuns", "quality": "tier_3", "trait": None},
                {"stat": "gpm", "quality": "tier_5", "trait": None},
            ],
        },
        params={"simulate_top": 1, "simulations": 300},
    )
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["fits"], payload
    fit = payload["fits"][0]
    assert fit["role"] == "support"
    assert [s["color"] for s in fit["slots"]] == ["blue", "blue", "green"]
    assert fit["expected_card_points"] > 0
    assert fit["period_mean"] is not None  # первому в списке считается период
    # Красная эмблема саппорту не подходит и остаётся в запасе.
    assert [e["stat"] for e in fit["unused"]] == ["gpm"]
    # Роли, на которые инвентаря не хватает, названы явно.
    assert "core" in payload["gaps"] and payload["gaps"]["core"]


def test_inventory_rejects_empty_and_unknown(client, session_factory):
    assert (
        client.post("/api/fantasy/inventory", json={"inventory": []}).status_code == 400
    )
    seed_ti_role_history(session_factory, copies=2)
    response = client.post(
        "/api/fantasy/inventory",
        json={"inventory": [{"stat": "nonsense", "quality": "tier_3"}]},
    )
    assert response.status_code == 400
    assert "nonsense" in response.json()["detail"]
