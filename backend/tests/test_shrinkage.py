"""Тесты поправки на размер выборки при сравнении ролей между собой."""

from __future__ import annotations

import pytest

from dataclasses import replace

from app.fantasy.advisor import StatValue
from app.fantasy.shrinkage import shrink_to_role_mean


def value(
    stat: str = "kills",
    *,
    base: float,
    games: int,
    std: float = 300.0,
) -> StatValue:
    return StatValue(
        stat=stat,
        label=stat,
        color="red",
        units_per_game=base / 100.0,
        base_points=base,
        p95_points=base * 1.5,
        p5_points=base * 0.5,
        median_points=base * 0.95,
        p75_points=base * 1.2,
        std_points=std,
        availability="exact",
        games=games,
    )


# Поле как в жизни: пятнадцать команд с сотней карт, укладывающиеся в 2%
# друг от друга, и один лидер с отрывом в 7,5% — мид Team Resilience.
LEADER = 1075.0


def field(*, leader_games: int, leader_base: float = LEADER, n: int = 15) -> list:
    entries = [("mid", [value(base=1000.0 + i * 2, games=100, std=100.0)]) for i in range(n)]
    entries.append(("mid", [value(base=leader_base, games=leader_games, std=100.0)]))
    return entries


def lead(values: list[float]) -> float:
    """Насколько лидер оторвался от лучшего в поле, в долях."""
    return values[-1] / max(values[:-1]) - 1.0


def test_a_lead_built_on_a_small_sample_is_erased():
    """Ровно та ситуация, из-за которой всё затевалось.

    Мид Team Resilience с 29 картами стоял на 7,5% выше поля, где остальные
    укладывались в 2% друг от друга. Такой отрыв на такой выборке неотличим от
    разброса — после поправки от него не должно остаться почти ничего.
    """
    entries = field(leader_games=29)
    before = [values[0].base_points for _, values in entries]
    after = [values[0].base_points for values in shrink_to_role_mean(entries)]

    assert lead(before) > 0.045
    assert lead(after) < 0.005, "отрыв держался на выборке, а не на игре"


def test_the_same_lead_survives_on_a_large_sample():
    """Поправка бьёт не по величине отрыва, а по его ненадёжности.

    Тот же отрыв на 500 картах — уже не шум, и срезать его нельзя: иначе метод
    просто занижал бы всех подряд и ничего не различал.
    """
    after = [values[0].base_points for values in shrink_to_role_mean(field(leader_games=500))]

    assert lead(after) > 0.01
    assert after.index(max(after)) == len(after) - 1, "выборке в 500 карт положено верить"


def test_teams_with_a_long_history_barely_move():
    entries = field(leader_base=1600.0, leader_games=100)
    adjusted = shrink_to_role_mean(entries)

    for (_, before), after in zip(entries[:-1], adjusted[:-1], strict=False):
        shift = abs(after[0].base_points - before[0].base_points) / before[0].base_points
        assert shift < 0.05


def test_differences_that_are_pure_noise_collapse_to_the_mean():
    """Разброс между командами не больше шума измерения — значит его нет.

    Тогда честный ответ «все примерно одинаковы», а не выдуманный рейтинг.
    """
    entries = [
        ("mid", [value(base=1000.0 + shift, games=10, std=900.0)])
        for shift in (-90, -40, 0, 40, 90)
    ]
    adjusted = shrink_to_role_mean(entries)

    points = [values[0].base_points for values in adjusted]
    assert max(points) - min(points) < 1.0


def test_roles_are_compared_only_within_themselves():
    """У мида и саппорта разные слоты: подтягивать одного к другому нельзя."""
    entries = [
        ("mid", [value(base=2000.0, games=100)]),
        ("mid", [value(base=2100.0, games=100)]),
        ("mid", [value(base=1900.0, games=100)]),
        ("support", [value(base=200.0, games=100)]),
        ("support", [value(base=210.0, games=100)]),
        ("support", [value(base=190.0, games=100)]),
    ]
    adjusted = shrink_to_role_mean(entries)

    assert all(values[0].base_points > 1500 for values in adjusted[:3])
    assert all(values[0].base_points < 500 for values in adjusted[3:])


def test_a_field_too_small_to_judge_is_left_alone():
    """Две команды — разброс между ними оценить не по чему, лучше не трогать."""
    entries = [
        ("mid", [value(base=1000.0, games=10)]),
        ("mid", [value(base=2000.0, games=200)]),
    ]
    adjusted = shrink_to_role_mean(entries)

    assert [v[0].base_points for v in adjusted] == [1000.0, 2000.0]


def test_derived_numbers_move_with_the_estimate():
    """Очки поехали, а «за карту» осталось — таблица начала бы себе противоречить."""
    entries = field(leader_base=1600.0, leader_games=29)
    before = entries[-1][1][0]
    after = shrink_to_role_mean(entries)[-1][0]

    scale = after.base_points / before.base_points
    assert after.units_per_game == pytest.approx(before.units_per_game * scale)
    assert after.p95_points == pytest.approx(before.p95_points * scale)
    assert after.median_points == pytest.approx(before.median_points * scale)
    assert after.p5_points == pytest.approx(before.p5_points * scale)


def test_descriptive_fields_are_not_touched():
    """Число карт и доля карт со статом — это факты, а не оценки."""
    entries = field(leader_base=1600.0, leader_games=29)
    after = shrink_to_role_mean(entries)[-1][0]

    assert after.games == 29
    assert after.stat == "kills"
    assert after.availability == "exact"


def test_shape_and_order_are_preserved():
    entries = [
        ("mid", [value("kills", base=900.0, games=40), value("gpm", base=1200.0, games=40)]),
        ("mid", [value("kills", base=950.0, games=90), value("gpm", base=1100.0, games=90)]),
        ("mid", [value("kills", base=980.0, games=95), value("gpm", base=1150.0, games=95)]),
    ]
    adjusted = shrink_to_role_mean(entries)

    assert len(adjusted) == 3
    for values in adjusted:
        assert {v.stat for v in values} == {"kills", "gpm"}
        assert values == sorted(values, key=lambda v: -v.base_points)


# --- эффективный размер выборки -----------------------------------------------
#
# `base_points` — взвешенное по свежести среднее, и его точность задаётся не
# числом карт, а `n_eff = (Σw)²/Σw²`. Подстановка числа карт занижала стандартную
# ошибку примерно вдвое и недожимала как раз маленькие выборки.


def test_effective_games_wins_over_the_raw_count():
    """При равном числе карт сильнее сжимается тот, у кого меньше n_eff.

    Обе команды отыграли по 100 карт, но у лидера они собраны в узкое окно, и
    взвешенное среднее опирается всего на 20 из них. Поправка обязана считать по
    ним, а не по номиналу.
    """
    honest = [("mid", [value(base=1000.0 + i * 2, games=100, std=100.0)]) for i in range(15)]

    leader = value(base=LEADER, games=100, std=100.0)
    by_count = shrink_to_role_mean([*honest, ("mid", [leader])])[-1][0]

    thin = replace(leader, effective_games=20.0)
    by_effective = shrink_to_role_mean([*honest, ("mid", [thin])])[-1][0]

    field_best = max(v[0].base_points for _, v in honest)
    assert by_effective.base_points < by_count.base_points
    assert by_effective.base_points < field_best


def test_raw_count_is_the_fallback_when_effective_is_unset():
    """Значения, посчитанные без весов, не должны потерять поправку вовсе.

    У них `effective_games` нулевой, и делить на ноль нельзя: сжатие обязано
    продолжить работать по числу карт.
    """
    entries = field(leader_games=29)
    assert all(v[0].effective_games == 0.0 for _, v in entries)

    after = [values[0].base_points for values in shrink_to_role_mean(entries)]
    assert lead(after) < 0.02


def test_stat_values_report_effective_games_below_the_map_count():
    """Сквозная проверка: advisor обязан отдавать n_eff меньше числа карт.

    Веса экспоненциальные, поэтому равенство возможно только если все карты
    сыграны в один момент — на истории в несколько месяцев этого не бывает.
    """
    from datetime import datetime, timedelta, timezone

    from app.fantasy.advisor import EmblemAdvisor
    from app.fantasy.projection import RoleGame, RoleHistory

    now = datetime(2026, 8, 11, tzinfo=timezone.utc)
    games = [
        RoleGame(
            match_id=i,
            start_time=now - timedelta(days=4 * i),
            series_key=f"series:{i}",
            player_stats={1: {"kills": 5.0}, 2: {"kills": 4.0}},
            won=True,
        )
        for i in range(30)
    ]
    history = RoleHistory(
        team_id=1, role="mid", account_ids=(1, 2), player_names=("a", "b"), games=games
    )

    values = EmblemAdvisor().stat_values(history, role="mid", now=now)

    assert values
    effective = values[0].effective_games
    assert 0 < effective < len(games)
    # Полураспад 30 дней на окне в 120 — эффективная выборка примерно вдвое меньше.
    assert effective < len(games) * 0.75
