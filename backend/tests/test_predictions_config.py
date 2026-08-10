"""Тесты конфига турнира: участники, алиасы, шкалы очков."""

from __future__ import annotations

import pytest

from app.analytics.predictions_config import PredictionsConfig, load_predictions_config


@pytest.fixture(scope="module")
def config():
    return load_predictions_config()


def test_sixteen_participants(config):
    assert len(config.team_names) == 16
    assert config.group_stage.teams == 16


def test_all_participants_resolved_to_opendota(config):
    """У каждого участника проставлен team_id — иначе его не посчитать."""
    missing = [name for name, team_id in config.team_ids.items() if team_id is None]
    assert missing == []


def test_team_ids_are_unique(config):
    ids = list(config.team_ids.values())
    assert len(set(ids)) == len(ids)


def test_renamed_organisations_have_aliases(config):
    """Команды, которые компендиум показывает под другим именем, ищутся по обоим."""
    assert "BetBoom Team" in config.search_names("BoomBoys")
    assert "L1ga Team" in config.search_names("Huligani")
    assert "PARIVISION" in config.search_names("Team Vision")
    assert "1win" in config.search_names("Iron Wing")


def test_search_names_starts_with_compendium_name(config):
    names = config.search_names("Team Spirit")
    assert names[0] == "Team Spirit"


def test_bucket_slots_sum_to_team_count(config):
    assert config.group_stage.total_slots() == config.group_stage.teams
    assert config.group_stage.slots() == {
        "4-0": 1,
        "4-1": 2,
        "elim_winner": 5,
        "elim_loser": 5,
        "1-4": 2,
        "0-4": 1,
    }


def test_points_tables_match_screens(config):
    group = config.group_stage.points
    assert group.points(1) == 30
    assert group.points(8) == 2520
    assert group.points(16) == 12000

    playoffs = config.playoffs.points
    assert playoffs.points(1) == 120
    assert playoffs.points(14) == 12000


def test_points_beyond_table_are_capped(config):
    assert config.group_stage.points.points(99) == 12000
    assert config.group_stage.points.points(0) == 0


def test_playoff_structure_is_double_elimination_for_eight(config):
    assert config.playoffs.teams == 8
    assert config.playoffs.predictions == 14


def test_swiss_format_parsed(config):
    swiss = config.group_stage.swiss
    assert swiss.wins_to_advance == 4
    assert swiss.losses_to_eliminate == 4
    assert swiss.max_rounds == 6
    assert swiss.decisive_best_of >= swiss.regular_best_of


def _config_with_first_round(tmp_path, pairs: str, *, teams: int = 4) -> "PredictionsConfig":
    names = ["A", "B", "C", "D"][:teams]
    text = f"""
version: test
group_stage:
  teams: {teams}
  buckets:
    - key: "win"
      slots: {teams // 2}
    - key: "lose"
      slots: {teams // 2}
  swiss:
    first_round:
{pairs}
  points_by_correct: {{1: 30}}
playoffs:
  predictions: 14
  points_by_correct: {{1: 120}}
teams:
"""
    for i, name in enumerate(names):
        text += f'  - name: "{name}"\n    team_id: {100 + i}\n'
    path = tmp_path / "first_round.yaml"
    path.write_text(text, encoding="utf-8")
    return PredictionsConfig.from_yaml(path)


def test_first_round_parsed_into_pairs(tmp_path):
    config = _config_with_first_round(tmp_path, '      - ["A", "B"]\n      - ["C", "D"]')
    assert config.group_stage.swiss.first_round == (("A", "B"), ("C", "D"))
    assert config.first_round_ids() == ((100, 101), (102, 103))


def test_half_a_first_round_is_rejected(tmp_path):
    """Половина пар по сетке, половина по посеву — это два разных турнира."""
    with pytest.raises(ValueError, match="1 пар"):
        _config_with_first_round(tmp_path, '      - ["A", "B"]')


def test_unknown_team_in_first_round_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="не из конфига"):
        _config_with_first_round(tmp_path, '      - ["A", "B"]\n      - ["C", "Zzz"]')


def test_team_playing_twice_in_first_round_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="дважды"):
        _config_with_first_round(tmp_path, '      - ["A", "B"]\n      - ["A", "D"]')


def test_broken_config_is_rejected(tmp_path):
    """Сумма слотов, не равная числу команд, — ошибка конфига, а не данных."""
    broken = tmp_path / "broken.yaml"
    broken.write_text(
        """
version: test
group_stage:
  teams: 16
  buckets:
    - key: "4-0"
      slots: 1
  points_by_correct: {1: 30}
playoffs:
  predictions: 14
  points_by_correct: {1: 120}
teams: []
""",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="слотов"):
        PredictionsConfig.from_yaml(broken)
