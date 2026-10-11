"""
db/session.py
-------------
SQLAlchemy engine and session factory.

Engine is created lazily on first call to get_engine() so that:
- Test suite can import the whole app without psycopg2 being installed locally.
- Tests override get_db() via dependency injection, bypassing PostgreSQL entirely.
"""

import os
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

# ---------------------------------------------------------------------------
# Connection URL — read from environment (set in .env.backend via Docker)
# ---------------------------------------------------------------------------

DB_USER = os.getenv("POSTGRES_USER", "agri_user")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "agri_pass")
DB_HOST = os.getenv("POSTGRES_HOST", "postgres")
DB_PORT = os.getenv("POSTGRES_PORT", "5432")
DB_NAME = os.getenv("POSTGRES_DB", "agriculture")

_default_url = f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# ---------------------------------------------------------------------------
# Lazy engine + session factory
# ---------------------------------------------------------------------------

_engine = None
_SessionLocal = None


def get_engine():
    """Return (creating if necessary) the SQLAlchemy engine."""
    global _engine
    if _engine is None:
        url = os.getenv("DATABASE_URL", _default_url)
        engine_kwargs: dict = {"echo": False}
        if url.startswith("sqlite"):
            engine_kwargs["connect_args"] = {"check_same_thread": False}
            # In-memory SQLite shared across threads (FastAPI BackgroundTasks + TestClient).
            if url in ("sqlite://", "sqlite:///:memory:"):
                from sqlalchemy.pool import StaticPool

                engine_kwargs["poolclass"] = StaticPool
        _engine = create_engine(url, **engine_kwargs)
    return _engine


def get_session_factory():
    """Return (creating if necessary) the sessionmaker bound to the engine."""
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=get_engine(),
        )
    return _SessionLocal


# Keep backward-compatible names used across the codebase
@property
def engine():
    return get_engine()


# SessionLocal is used directly in health.py and conftest — expose lazily
class _LazySessionLocal:
    """Proxy that creates the real SessionLocal on first __call__."""

    def __call__(self, *args, **kwargs):
        return get_session_factory()(*args, **kwargs)

    def __getattr__(self, name):
        return getattr(get_session_factory(), name)


SessionLocal = _LazySessionLocal()
