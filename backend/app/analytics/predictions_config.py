"""Загрузка структуры турнира и шкал очков Predictions из YAML."""

from __future__ import annotations

import re
from collections.abc import Container
from dataclasses import dataclass, field
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any, Self

import yaml


def _first_date(raw: object) -> date | None:
    """Первая дата из строки вида «2026-08-13 .. 2026-08-23»."""
    if isinstance(raw, date):
        return raw
    found = re.search(r"\d{4}-\d{2}-\d{2}", str(raw or ""))
    return date.fromisoformat(found.group()) if found else None

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
    # Объявленные пары четвертьфиналов верхней сетки, названиями команд. Пока их
    # нет, сетка разводится по посеву — как и первый раунд Swiss.
    upper_quarterfinals: tuple[tuple[str, str], ...] = ()
    # Первый день плей-офф: по нему серии сетки отличаются от серий группы.
    starts: date | None = None


@dataclass(frozen=True, slots=True)
class FantasyStage:
    """Период Fantasy: свой состав, своё число серий, свой момент закрепления."""

    key: str
    label: str
    starts: date | None
    locks: date | None


@dataclass(frozen=True, slots=True)
class PredictionsConfig:
    version: str
    event: str
    group_stage: GroupStageConfig
    playoffs: PlayoffConfig
    team_names: tuple[str, ...]
    team_ids: dict[str, int | None]
    # Периоды Fantasy по порядку: групповой этап, затем основной.
    fantasy_stages: tuple[FantasyStage, ...] = ()
    # Первый день турнира. По нему матчи группового этапа отличаются от
    # квалификаций и товарищеских: команды те же, а сетка — только начиная
    # с этой даты.
    starts: date | None = None
    # Реальные названия организаций для команд, которые компендиум показывает
    # под изменённым именем (BoomBoys -> BetBoom и т.п.).
    team_aliases: dict[str, tuple[str, ...]] = field(default_factory=dict)
    # Прежние профили того же коллектива — только чтобы догрузить их матчи.
    # Ни в рейтинг, ни в прогноз эти id не идут: что взять в выборку роли,
    # решает пересечение состава, а не тег команды.
    team_previous_ids: dict[str, tuple[int, ...]] = field(default_factory=dict)

    def ingest_team_ids(self) -> dict[int, str]:
        """Все team_id, чьи матчи нужно держать в базе: {team_id: название}.

        Нынешний профиль и прежние — под одним названием: догрузка по ним
        одинаковая, а различать их дальше по коду незачем.
        """
        result: dict[int, str] = {}
        for name, team_id in self.team_ids.items():
            if team_id is not None:
                result[int(team_id)] = name
            for previous in self.team_previous_ids.get(name, ()):
                result.setdefault(previous, name)
        return result

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
            upper_quarterfinals=tuple(
                (str(pair[0]), str(pair[1]))
                for pair in playoff_raw.get("upper_quarterfinals") or ()
            ),
            starts=_first_date(playoff_raw.get("starts")),
        )

        config = cls(
            version=raw.get("version", "unknown"),
            event=raw.get("event", ""),
            starts=_first_date(raw.get("dates")),
            group_stage=group,
            playoffs=playoffs,
            fantasy_stages=tuple(
                FantasyStage(
                    key=str(stage["key"]),
                    label=str(stage.get("label", stage["key"])),
                    starts=_first_date(stage.get("starts")),
                    locks=_first_date(stage.get("locks")),
                )
                for stage in raw.get("fantasy_stages") or ()
            ),
            team_names=tuple(t["name"] for t in teams_raw),
            team_ids={t["name"]: t.get("team_id") for t in teams_raw},
            team_aliases={
                t["name"]: tuple(t.get("aliases") or ()) for t in teams_raw if t.get("aliases")
            },
            team_previous_ids={
                t["name"]: tuple(int(i) for i in t["previous_ids"])
                for t in teams_raw
                if t.get("previous_ids")
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

    def quarterfinal_ids(self) -> tuple[tuple[int, int], ...]:
        """Объявленные четвертьфиналы верхней сетки в team_id."""
        pairs: list[tuple[int, int]] = []
        for left, right in self.playoffs.upper_quarterfinals:
            a, b = self.team_ids.get(left), self.team_ids.get(right)
            if a is None or b is None:
                missing = left if a is None else right
                raise ValueError(f"пара плей-офф {left} — {right}: у {missing} нет team_id")
            pairs.append((int(a), int(b)))
        return tuple(pairs)

    def playoff_team_ids(self) -> dict[int, str]:
        """Восемь команд объявленной сетки: {team_id: название}."""
        names = {team_id: name for name, team_id in self.team_ids.items()}
        return {
            team: names.get(team, str(team))
            for pair in self.quarterfinal_ids()
            for team in pair
        }

    def fantasy_stage(self, key: str) -> FantasyStage | None:
        return next((s for s in self.fantasy_stages if s.key == key), None)

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

        # Первый раунд либо расписан целиком, либо не расписан вовсе: половина
        # пар по сетке, половина по посеву — это не «уточнение», а смесь двух
        # разных турниров. То же с сеткой плей-офф.
        self._validate_pairs(
            self.group_stage.swiss.first_round, self.group_stage.teams, "первом раунде"
        )
        self._validate_pairs(
            self.playoffs.upper_quarterfinals, self.playoffs.teams, "сетке плей-офф"
        )

    def _validate_pairs(
        self, pairs: tuple[tuple[str, str], ...], teams: int, what: str
    ) -> None:
        if not pairs:
            return
        listed = [name for pair in pairs for name in pair]
        if len(pairs) * 2 != teams:
            raise ValueError(f"в {what} {len(pairs)} пар на {teams} команд")
        unknown = sorted(set(listed) - set(self.team_names)) if self.team_names else []
        if unknown:
            raise ValueError(f"в {what} команды не из конфига: {', '.join(unknown)}")
        repeated = sorted({name for name in listed if listed.count(name) > 1})
        if repeated:
            raise ValueError(f"в {what} команда встречается дважды: {', '.join(repeated)}")


@lru_cache(maxsize=4)
def load_predictions_config(
    path: Path | str = DEFAULT_PREDICTIONS_PATH,
) -> PredictionsConfig:
    return PredictionsConfig.from_yaml(path)
