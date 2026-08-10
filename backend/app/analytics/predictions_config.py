"""Загрузка структуры турнира и шкал очков Predictions из YAML."""

from __future__ import annotations

from collections.abc import Container
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Self

import yaml

CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"
DEFAULT_PREDICTIONS_PATH = CONFIG_DIR / "ti15_predictions.yaml"


@dataclass(frozen=True, slots=True)
class Bucket:
    key: str
    label: str
    description: str
    slots: int


@dataclass(frozen=True, slots=True)
class SwissFormat:
    wins_to_advance: int
    losses_to_eliminate: int
    max_rounds: int
    regular_best_of: int
    decisive_best_of: int
    # Объявленные пары первого раунда, названиями команд. Пока их нет, симулятор
    # разбивает первый раунд по посеву; настоящая сетка от посева отличается, и
    # вероятности по корзинам считались бы от матчей, которых не будет.
    first_round: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True, slots=True)
class PointsTable:
    """Очки за N угаданных предсказаний."""

    by_correct: dict[int, int]

    def points(self, correct: int) -> int:
        if correct <= 0:
            return 0
        if correct in self.by_correct:
            return self.by_correct[correct]
        # За пределами таблицы — потолок.
        return self.by_correct[max(self.by_correct)]

    def as_array(self, size: int) -> list[int]:
        return [self.points(i) for i in range(size + 1)]


@dataclass(frozen=True, slots=True)
class GroupStageConfig:
    teams: int
    buckets: tuple[Bucket, ...]
    swiss: SwissFormat
    points: PointsTable

    def bucket_keys(self) -> tuple[str, ...]:
        return tuple(b.key for b in self.buckets)

    def slots(self) -> dict[str, int]:
        return {b.key: b.slots for b in self.buckets}

    def total_slots(self) -> int:
        return sum(b.slots for b in self.buckets)


@dataclass(frozen=True, slots=True)
class PlayoffConfig:
    teams: int
    predictions: int
    best_of: int
    grand_final_best_of: int
    points: PointsTable


@dataclass(frozen=True, slots=True)
class PredictionsConfig:
    version: str
    event: str
    group_stage: GroupStageConfig
    playoffs: PlayoffConfig
    team_names: tuple[str, ...]
    team_ids: dict[str, int | None]
    # Реальные названия организаций для команд, которые компендиум показывает
    # под изменённым именем (BoomBoys -> BetBoom и т.п.).
    team_aliases: dict[str, tuple[str, ...]] = field(default_factory=dict)

    def search_names(self, name: str) -> tuple[str, ...]:
        """Все названия, под которыми команду стоит искать во внешних источниках."""
        return (name, *self.team_aliases.get(name, ()))

    @classmethod
    def from_yaml(cls, path: Path | str = DEFAULT_PREDICTIONS_PATH) -> Self:
        raw: dict[str, Any] = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        group_raw = raw["group_stage"]
        swiss_raw = group_raw.get("swiss", {})
        playoff_raw = raw["playoffs"]
        teams_raw = raw.get("teams", [])

        group = GroupStageConfig(
            teams=int(group_raw["teams"]),
            buckets=tuple(
                Bucket(
                    key=b["key"],
                    label=b.get("label", b["key"]),
                    description=b.get("description", ""),
                    slots=int(b["slots"]),
                )
                for b in group_raw["buckets"]
            ),
            swiss=SwissFormat(
                wins_to_advance=int(swiss_raw.get("wins_to_advance", 4)),
                losses_to_eliminate=int(swiss_raw.get("losses_to_eliminate", 4)),
                max_rounds=int(swiss_raw.get("max_rounds", 6)),
                regular_best_of=int(swiss_raw.get("regular_best_of", 1)),
                decisive_best_of=int(swiss_raw.get("decisive_best_of", 3)),
                first_round=tuple(
                    (str(pair[0]), str(pair[1])) for pair in swiss_raw.get("first_round") or ()
                ),
            ),
            points=PointsTable({int(k): int(v) for k, v in group_raw["points_by_correct"].items()}),
        )

        playoffs = PlayoffConfig(
            teams=int(playoff_raw.get("teams", 8)),
            predictions=int(playoff_raw["predictions"]),
            best_of=int(playoff_raw.get("best_of", 3)),
            grand_final_best_of=int(playoff_raw.get("grand_final_best_of", 5)),
            points=PointsTable(
                {int(k): int(v) for k, v in playoff_raw["points_by_correct"].items()}
            ),
        )

        config = cls(
            version=raw.get("version", "unknown"),
            event=raw.get("event", ""),
            group_stage=group,
            playoffs=playoffs,
            team_names=tuple(t["name"] for t in teams_raw),
            team_ids={t["name"]: t.get("team_id") for t in teams_raw},
            team_aliases={
                t["name"]: tuple(t.get("aliases") or ()) for t in teams_raw if t.get("aliases")
            },
        )
        config.validate()
        return config

    def first_round_ids(self) -> tuple[tuple[int, int], ...]:
        """Объявленные пары первого раунда в team_id."""
        pairs: list[tuple[int, int]] = []
        for left, right in self.group_stage.swiss.first_round:
            a, b = self.team_ids.get(left), self.team_ids.get(right)
            if a is None or b is None:
                missing = left if a is None else right
                raise ValueError(f"пара первого раунда {left} — {right}: у {missing} нет team_id")
            pairs.append((int(a), int(b)))
        return tuple(pairs)

    def first_round_for(self, team_ids: Container[int]) -> tuple[tuple[int, int], ...]:
        """Пары первого раунда, если считают именно эту сетку.

        Симулятор можно позвать и на другом наборе команд — топ-16 по рейтингу
        из CLI, произвольный список из API. Тогда объявленная сетка к нему не
        относится, и первый раунд снова разбивается по посеву.
        """
        pairs = self.first_round_ids()
        if pairs and all(team in team_ids for pair in pairs for team in pair):
            return pairs
        return ()

    def validate(self) -> None:
        if self.group_stage.total_slots() != self.group_stage.teams:
            raise ValueError(
                "сумма слотов корзин "
                f"({self.group_stage.total_slots()}) не равна числу команд "
                f"({self.group_stage.teams})"
            )
        if self.team_names and len(self.team_names) != self.group_stage.teams:
            raise ValueError(
                f"в конфиге {len(self.team_names)} команд, ожидалось {self.group_stage.teams}"
            )

        first_round = self.group_stage.swiss.first_round
        if not first_round:
            return
        # Первый раунд либо расписан целиком, либо не расписан вовсе: половина
        # пар по сетке, половина по посеву — это не «уточнение», а смесь двух
        # разных турниров.
        listed = [name for pair in first_round for name in pair]
        if len(first_round) * 2 != self.group_stage.teams:
            raise ValueError(
                f"в первом раунде {len(first_round)} пар на {self.group_stage.teams} команд"
            )
        unknown = sorted(set(listed) - set(self.team_names)) if self.team_names else []
        if unknown:
            raise ValueError(f"в первом раунде команды не из конфига: {', '.join(unknown)}")
        repeated = sorted({name for name in listed if listed.count(name) > 1})
        if repeated:
            raise ValueError(f"в первом раунде команда встречается дважды: {', '.join(repeated)}")


@lru_cache(maxsize=4)
def load_predictions_config(
    path: Path | str = DEFAULT_PREDICTIONS_PATH,
) -> PredictionsConfig:
    return PredictionsConfig.from_yaml(path)
