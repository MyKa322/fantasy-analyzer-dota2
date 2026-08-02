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


def init_db() -> None:
    Base.metadata.create_all(get_engine())


def reset_engine() -> None:
    """Сбросить кэшированный engine — нужно тестам и при смене DATABASE_URL."""
    global _engine, _SessionFactory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionFactory = None
