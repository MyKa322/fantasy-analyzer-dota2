"""Подключение к БД. SQLite для личного использования, Postgres — сменой URL."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from ..settings import settings
from .models import Base

_engine: Engine | None = None
_SessionFactory: sessionmaker[Session] | None = None


def _configure_sqlite(engine: Engine) -> None:
    """WAL и внешние ключи — SQLite по умолчанию не включает ни то, ни другое."""

    @event.listens_for(engine, "connect")
    def _set_pragma(dbapi_connection, _connection_record):  # type: ignore[no-untyped-def]
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        url = settings.database_url
        if url.startswith("sqlite"):
            db_path = url.split("///", 1)[-1]
            if db_path and db_path != ":memory:":
                Path(db_path).parent.mkdir(parents=True, exist_ok=True)
            _engine = create_engine(url, future=True, connect_args={"check_same_thread": False})
            _configure_sqlite(_engine)
        else:
            _engine = create_engine(url, future=True, pool_pre_ping=True)
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    global _SessionFactory
    if _SessionFactory is None:
        _SessionFactory = sessionmaker(bind=get_engine(), expire_on_commit=False, future=True)
    return _SessionFactory


@contextmanager
def session_scope() -> Iterator[Session]:
    """Транзакция: коммит при успехе, откат при исключении."""
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db() -> Iterator[Session]:
    """Зависимость FastAPI."""
    with session_scope() as session:
        yield session


# Колонки, добавленные к уже существующим таблицам. Полноценные миграции для
# личной SQLite-базы — лишний слой, но и терять накопленную историю матчей
# из-за одного нового поля нельзя: `create_all` существующие таблицы не трогает.
_ADDED_COLUMNS: tuple[tuple[str, str, str], ...] = (
    ("matches", "stats_version", "INTEGER DEFAULT 0"),
    ("matches", "first_blood_time", "INTEGER"),
    ("player_match_stats", "profile", "JSON"),
    # Провенанс: откуда взят каждый стат. Значение по умолчанию — opendota,
    # потому что всё, что уже лежит в базе, добыто именно оттуда.
    ("matches", "replay_parsed", "BOOLEAN DEFAULT 0"),
    ("matches", "replay_version", "VARCHAR(32)"),
    ("player_match_stats", "source", "VARCHAR(16) DEFAULT 'opendota'"),
    ("player_match_stats", "stat_sources", "JSON"),
    ("player_match_stats", "parser_version", "VARCHAR(32)"),
)


# Индексы для добавленных колонок: `create_all` существующую таблицу не трогает,
# поэтому индекс к дописанной колонке нужно создать отдельно.
_ADDED_INDEXES: tuple[tuple[str, str, str], ...] = (
    ("ix_matches_replay_parsed", "matches", "replay_parsed"),
    ("ix_matches_replay_version", "matches", "replay_version"),
    ("ix_player_match_stats_source", "player_match_stats", "source"),
)


def _ensure_columns(engine: Engine) -> None:
    if not engine.url.drivername.startswith("sqlite"):
        return
    from sqlalchemy import text

    with engine.begin() as connection:
        for table, column, definition in _ADDED_COLUMNS:
            existing = {
                row[1] for row in connection.exec_driver_sql(f"PRAGMA table_info({table})")
            }
            if not existing or column in existing:
                continue
            connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {definition}"))

        for name, table, column in _ADDED_INDEXES:
            existing = {
                row[1] for row in connection.exec_driver_sql(f"PRAGMA table_info({table})")
            }
            if column not in existing:
                continue
            connection.execute(
                text(f"CREATE INDEX IF NOT EXISTS {name} ON {table} ({column})")
            )


def init_db() -> None:
    engine = get_engine()
    Base.metadata.create_all(engine)
    _ensure_columns(engine)


def reset_engine() -> None:
    """Сбросить кэшированный engine — нужно тестам и при смене DATABASE_URL."""
    global _engine, _SessionFactory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionFactory = None
