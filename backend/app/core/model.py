"""Канонический матч: форма, в которой матч видят все анализаторы.

Смысл слоя — развязать источник и потребителя. Сейчас OpenDota-специфичная форма
JSON протекает всюду: `services/profiles.py` знает про `player_slot`, `fantasy/`
разбирает те же словари по-своему, а `analytics/` собирает третью проекцию тех же
матчей. Каждый новый источник данных в такой схеме означает правку в трёх местах,
и расходятся они молча.

Здесь матч описан один раз и без следов источника. OpenDota и разбор реплея —
два адаптера, которые складываются в эту форму; всё, что считает метрики, читает
только её. Провенанс при этом не теряется: у каждого стата остаётся пометка,
откуда он взялся (`core/provenance.py`).

Структуры неизменяемые: канонический матч — это факт о прошедшей игре, и код,
который «немного поправит» его по дороге, — источник расхождений между вкладками.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from app.core.provenance import Provenance, Source, describe

# Наборы полей и версия схемы наследуются из существующего маппинга: канонический
# слой меняет форму данных, а не состав статов.
from app.ingest.stat_mapping import PROFILE_FIELDS, STAT_SOURCES, STATS_VERSION

__all__ = [
    "CanonicalMatch",
    "DraftPick",
    "PlayerGame",
    "TeamGame",
    "FANTASY_STATS",
    "PROFILE_FIELDS",
    "STATS_VERSION",
]

FANTASY_STATS: tuple[str, ...] = tuple(STAT_SOURCES)


@dataclass(frozen=True, slots=True)
class DraftPick:
    """Один ход в драфте.

    OpenDota отдаёт порядок пиков и банов, но не отдаёт таймингов и остатка
    резервного времени — они есть только в реплее. Поэтому `time` и
    `reserve_time` необязательные: их отсутствие означает «источник не знает»,
    а не «ноль секунд».
    """

    order: int
    is_pick: bool
    hero_id: int
    is_radiant: bool
    time: int | None = None
    reserve_time: int | None = None


@dataclass(frozen=True, slots=True)
class PlayerGame:
    """Игрок в одной карте.

    `fantasy` и `profile` намеренно раздельные, как и в БД: `fantasy` — вход
    движка очков, и любое лишнее поле в нём рано или поздно попадёт в расчёт по
    ошибке.
    """

    account_id: int | None
    hero_id: int | None
    player_slot: int
    is_radiant: bool
    team_id: int | None
    won: bool | None
    lane_role: int | None
    fantasy: dict[str, float] = field(default_factory=dict)
    profile: dict[str, float] = field(default_factory=dict)
    provenance: dict[str, Provenance] = field(default_factory=dict)

    @property
    def is_identified(self) -> bool:
        """Есть ли у игрока account_id.

        Анонимных нельзя сопоставить с ростером, поэтому в агрегаты они не идут —
        но в матче остаются: без них не сойдётся состав команды.
        """
        return self.account_id is not None

    def source_of(self, stat: str) -> Source:
        """Из какого источника пришёл конкретный стат."""
        entry = self.provenance.get(stat)
        return entry.source if entry else Source.OPENDOTA

    def usable(self, stat: str) -> bool:
        """Измерено ли значение на самом деле (а не подставлено нулём)."""
        entry = self.provenance.get(stat)
        return entry.is_usable if entry else False


@dataclass(frozen=True, slots=True)
class TeamGame:
    """Команда в одной карте — то, что нужно рейтингам и анализу команд.

    Отдельная структура, а не вычисление на месте: сторона, результат и состав
    нужны в `analytics/` без разбора списка игроков заново, а состав ещё и
    задаёт ключ для учёта замен в рейтинге.
    """

    team_id: int | None
    is_radiant: bool
    won: bool | None
    account_ids: tuple[int, ...]

    @property
    def roster_key(self) -> str:
        """Отпечаток состава: по его смене видно, что рейтинг относится уже к
        другой команде, даже если тег и team_id прежние."""
        return ",".join(str(a) for a in sorted(self.account_ids))


@dataclass(frozen=True, slots=True)
class CanonicalMatch:
    """Матч, независимый от источника."""

    match_id: int
    start_time: datetime
    duration: int
    series_key: str
    sources: frozenset[Source]
    players: tuple[PlayerGame, ...]
    league_id: int | None = None
    league_name: str | None = None
    series_type: int | None = None
    radiant_team_id: int | None = None
    dire_team_id: int | None = None
    radiant_win: bool | None = None
    patch: int | None = None
    first_blood_time: int | None = None
    is_lan: bool | None = None
    draft: tuple[DraftPick, ...] = ()
    stats_version: int = STATS_VERSION

    @property
    def has_detail(self) -> bool:
        """Есть ли у матча разбор — свой или чужой.

        Без него нет вардов, станов и тимфайтов, и брать такой матч в выборку для
        проекции нельзя: это систематическое занижение.
        """
        return bool(self.sources)

    @property
    def from_replay(self) -> bool:
        return Source.REPLAY in self.sources

    @property
    def by_account(self) -> dict[int, PlayerGame]:
        """Игроки по account_id; анонимные пропущены."""
        return {p.account_id: p for p in self.players if p.account_id is not None}

    @property
    def teams(self) -> tuple[TeamGame, TeamGame]:
        """Обе стороны карты. Порядок фиксирован: Radiant, затем Dire."""
        return (self._team(is_radiant=True), self._team(is_radiant=False))

    def _team(self, *, is_radiant: bool) -> TeamGame:
        members = [p for p in self.players if p.is_radiant is is_radiant]
        team_id = self.radiant_team_id if is_radiant else self.dire_team_id
        won = None if self.radiant_win is None else (self.radiant_win is is_radiant)
        return TeamGame(
            team_id=team_id,
            is_radiant=is_radiant,
            won=won,
            account_ids=tuple(p.account_id for p in members if p.account_id is not None),
        )

    def opponent_of(self, team_id: int) -> int | None:
        """Соперник команды в этой карте."""
        if team_id == self.radiant_team_id:
            return self.dire_team_id
        if team_id == self.dire_team_id:
            return self.radiant_team_id
        return None

    def provenance_of(self, stat: str) -> Provenance:
        """Происхождение стата на уровне матча.

        Берётся у первого игрока, у которого оно записано: адаптер заполняет
        провенанс одинаково для всех десяти, потому что источник у карты общий.
        """
        for player in self.players:
            entry = player.provenance.get(stat)
            if entry is not None:
                return entry
        source = max(self.sources, default=Source.OPENDOTA)
        return describe(stat, source)
