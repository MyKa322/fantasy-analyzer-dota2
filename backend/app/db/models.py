"""Схема БД: матчи, игроки, статы и история рейтингов.

Одна база на оба модуля анализа — Predictions и Fantasy читают одни и те же
матчи, просто агрегируют их по-разному.

Набор Fantasy-статов Valve меняет между турнирами, поэтому статы игрока хранятся
одним JSON-полем, а не колонкой на стат: иначе каждый патч компендиума означал
бы миграцию схемы.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Team(Base):
    __tablename__ = "teams"

    team_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), index=True)
    tag: Mapped[str | None] = mapped_column(String(32), nullable=True)
    logo_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    # Название из конфига компендиума, если команда — участник TI15.
    compendium_name: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    players: Mapped[list["Player"]] = relationship(back_populates="team")
    ratings: Mapped[list["TeamRating"]] = relationship(
        back_populates="team", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Team {self.team_id} {self.name!r}>"


class Player(Base):
    __tablename__ = "players"

    account_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str | None] = mapped_column(String(128), index=True)
    team_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("teams.team_id"), nullable=True, index=True
    )
    # core / mid / support — роль в терминах компендиума, не позиция 1-5.
    fantasy_role: Mapped[str | None] = mapped_column(String(16), nullable=True, index=True)
    # Позиция 1-5 по данным о лейне, если удалось определить.
    position: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_ti_participant: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    team: Mapped[Team | None] = relationship(back_populates="players")
    stats: Mapped[list["PlayerMatchStat"]] = relationship(back_populates="player")

    def __repr__(self) -> str:
        return f"<Player {self.account_id} {self.name!r}>"


class Match(Base):
    __tablename__ = "matches"

    match_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    duration: Mapped[int] = mapped_column(Integer, default=0)
    league_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    league_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    # series_id OpenDota бывает нулевым — тогда ключ склеивается из пары команд и дня.
    series_key: Mapped[str] = mapped_column(String(64), index=True)
    series_type: Mapped[int | None] = mapped_column(Integer, nullable=True)
    radiant_team_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    dire_team_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    radiant_win: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    patch: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    # Разобран ли реплей: без этого нет вардов, станов и тимфайтов.
    is_parsed: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    is_lan: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    player_stats: Mapped[list["PlayerMatchStat"]] = relationship(
        back_populates="match", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("ix_matches_teams_time", "radiant_team_id", "dire_team_id", "start_time"),)

    def __repr__(self) -> str:
        return f"<Match {self.match_id} @{self.start_time:%Y-%m-%d}>"


class PlayerMatchStat(Base):
    __tablename__ = "player_match_stats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    match_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("matches.match_id", ondelete="CASCADE"), index=True
    )
    account_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("players.account_id"), index=True
    )
    team_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    hero_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    is_radiant: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    won: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    lane_role: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Fantasy-статы в терминах конфига компендиума: {"kills": 8.0, "gpm": 712.0, ...}
    stats: Mapped[dict] = mapped_column(JSON, default=dict)
    # Денормализованное время матча — чтобы фильтровать окно без join.
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

    match: Mapped[Match] = relationship(back_populates="player_stats")
    player: Mapped[Player] = relationship(back_populates="stats")

    __table_args__ = (
        UniqueConstraint("match_id", "account_id", name="uq_player_match"),
        Index("ix_stats_account_time", "account_id", "start_time"),
    )

    def __repr__(self) -> str:
        return f"<PlayerMatchStat m={self.match_id} p={self.account_id}>"


class TeamRating(Base):
    """Снимок рейтинга команды на момент времени.

    Храним историю, а не одно текущее значение: тренд рейтинга — то, что рисует
    дашборд, и то, по чему видно эффект замены игрока.
    """

    __tablename__ = "team_ratings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    team_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("teams.team_id"), index=True)
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    rating: Mapped[float] = mapped_column(Float)
    rd: Mapped[float] = mapped_column(Float)
    volatility: Mapped[float] = mapped_column(Float)
    matches_played: Mapped[int] = mapped_column(Integer, default=0)
    # Метка прогона пересчёта — рейтинги всегда считаются с нуля хронологически,
    # чтобы исключить утечку будущего в исторические значения.
    run_id: Mapped[str] = mapped_column(String(64), index=True)

    team: Mapped[Team] = relationship(back_populates="ratings")

    __table_args__ = (
        UniqueConstraint("team_id", "as_of", "run_id", name="uq_rating_snapshot"),
    )

    def __repr__(self) -> str:
        return f"<TeamRating {self.team_id} {self.rating:.0f}±{self.rd:.0f}>"


class TeamRosterSlot(Base):
    """Кто занимает роль компендиума в конкретной команде.

    Отдельная таблица, а не поле у игрока: составы пересекаются (игрок успевает
    сыграть за две команды периода), и одна строка на игрока молча затирала бы
    разметку той команды, которую обработали раньше.
    """

    __tablename__ = "team_roster_slots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    team_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("teams.team_id"), index=True)
    account_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("players.account_id"), index=True
    )
    role: Mapped[str] = mapped_column(String(16), index=True)
    games: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (
        UniqueConstraint("team_id", "account_id", name="uq_roster_slot"),
    )

    def __repr__(self) -> str:
        return f"<TeamRosterSlot {self.team_id} {self.role} {self.account_id}>"


class IngestState(Base):
    """Курсоры инкрементального забора данных."""

    __tablename__ = "ingest_state"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str | None] = mapped_column(String(256), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
