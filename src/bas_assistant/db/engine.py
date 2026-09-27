"""SQLAlchemy engine, session factory, and declarative base.

The engine is created once, lazily, from ``Settings().database_url``. Importing
this module never touches the database; nothing connects until ``get_session``
is called.
"""

from __future__ import annotations

from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from bas_assistant.settings import Settings


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    """Return the process-wide engine, built from environment settings."""
    return create_engine(Settings().database_url, pool_pre_ping=True)


@lru_cache(maxsize=1)
def _session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), expire_on_commit=False)


def get_session() -> Iterator[Session]:
    """FastAPI dependency: yield one session per request, always closed."""
    session = _session_factory()()
    try:
        yield session
    finally:
        session.close()
