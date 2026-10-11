"""
tests/conftest.py
-----------------
Shared test fixtures for all test modules.

Uses SQLite in-memory so tests run WITHOUT Docker / MySQL.

The entire stack is wired together:
  - In-memory SQLite creates all tables via Base.metadata.create_all()
  - The FastAPI get_db() dependency is overridden to use the test session
  - Each test function gets a fresh isolated database state

`DATABASE_URL` is set before importing the app so `SessionLocal()` (used by
BackgroundTasks in land discovery) hits the same engine as fixtures.
"""

import os

os.environ["DATABASE_URL"] = "sqlite://"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import sessionmaker


@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(element, compiler, **kw):
    """Allow PostgreSQL JSONB columns in SQLite test schema."""
    return "JSON"

import app.db.session as db_session_module

db_session_module._engine = None
db_session_module._SessionLocal = None

from app.db.base import Base  # ensures all models are registered
from app.core.dependencies import get_db
from app.core import security
from app.db.session import get_engine
from app.main import app

# ---------------------------------------------------------------------------
# Test database — shared in-memory SQLite (no Docker / no pymysql required)
# ---------------------------------------------------------------------------

test_engine = get_engine()
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="function", autouse=False)
def db_session():
    """
    Provides a fresh SQLite session per test.
    Tables are created before each test and dropped afterwards.
    """
    Base.metadata.create_all(bind=test_engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=test_engine)


@pytest.fixture(scope="function")
def client(db_session):
    """
    FastAPI TestClient with get_db overridden to use the test SQLite session.
    Each test gets a clean database state.
    """
    def _override_get_db():
        try:
            yield db_session
        finally:
            pass  # session lifecycle managed by db_session fixture

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Helper: create a valid JWT token for a given user_id and role
# ---------------------------------------------------------------------------

def make_token(user_id: int, role: str = "viewer") -> str:
    """Create a valid test JWT token with the given user_id and role."""
    return security.create_access_token(data={"sub": str(user_id)})


# ---------------------------------------------------------------------------
# Open-Meteo polygon sampling mocks (discovery pipeline)
# ---------------------------------------------------------------------------

POLYGON_CLIMATE_MOCK_RECORDS = [
    {
        "date": "2026-04-24",
        "temperature_max_c": 22.5,
        "temperature_min_c": 18.0,
        "humidity_pct": 55.0,
        "rainfall_mm": 0.1,
        "et0_mm": 5.0,
        "soil_moisture_pct": 28.0,
    }
]

POLYGON_CLIMATE_MOCK_META = {
    "spatial_scope": "polygon_mean",
    "sample_count": 5,
    "temp_spread_c": 0.5,
    "high_spread": False,
    "large_field_warning": False,
    "aggregate_trust_tier": "observed",
    "points": [],
    "updated_at": "2026-04-24T00:00:00+00:00",
}


def patch_polygon_climate_mock(*, records=None, spatial_meta=None):
    """Context manager patching polygon historical fetch in discovery pipeline."""
    from contextlib import contextmanager
    from unittest.mock import patch

    recs = records if records is not None else POLYGON_CLIMATE_MOCK_RECORDS
    meta = spatial_meta if spatial_meta is not None else POLYGON_CLIMATE_MOCK_META

    @contextmanager
    def _cm():
        with patch(
            "app.pipeline.land_discovery_pipeline.open_meteo_polygon.fetch_polygon_historical_climate",
            return_value=(recs, meta),
        ):
            yield

    return _cm()
