"""Tests for scheduled land monitoring pipeline (Phase 5)."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import patch

import pytest

from app.models.land import Land
from app.models.land_climate import LandClimate
from app.pipeline import land_monitoring_pipeline


_POLYGON = {
    "type": "Polygon",
    "coordinates": [[[31.0, 30.0], [31.1, 30.0], [31.1, 30.1], [31.0, 30.1]]],
}


def _seed_land(db_session, *, interval_days: int = 16, status: str = "active") -> Land:
    land = Land(
        name="Monitor Farm",
        latitude=Decimal("30.05"),
        longitude=Decimal("31.05"),
        area_hectares=Decimal("10"),
        status=status,
        monitoring_interval_days=interval_days,
        boundary_polygon=_POLYGON,
    )
    db_session.add(land)
    db_session.commit()
    db_session.refresh(land)
    return land


class TestMonitoringDueCheck:
    def test_land_without_climate_is_due(self, db_session):
        land = _seed_land(db_session)
        assert land_monitoring_pipeline._is_due_for_monitoring(db_session, land.land_id, 16)

    def test_recent_climate_is_not_due(self, db_session):
        land = _seed_land(db_session)
        db_session.add(
            LandClimate(
                land_id=land.land_id,
                timestamp=datetime.now(timezone.utc) - timedelta(days=2),
                temperature_celsius=Decimal("28"),
            )
        )
        db_session.commit()
        assert not land_monitoring_pipeline._is_due_for_monitoring(db_session, land.land_id, 16)

    def test_stale_climate_is_due(self, db_session):
        land = _seed_land(db_session)
        db_session.add(
            LandClimate(
                land_id=land.land_id,
                timestamp=datetime.now(timezone.utc) - timedelta(days=20),
                temperature_celsius=Decimal("28"),
            )
        )
        db_session.commit()
        assert land_monitoring_pipeline._is_due_for_monitoring(db_session, land.land_id, 16)


class TestRunMonitoringCycle:
    @patch("app.pipeline.land_monitoring_pipeline._refresh_single_land", return_value=True)
    def test_explicit_land_ids_always_processed(self, mock_refresh, db_session):
        land = _seed_land(db_session)
        result = land_monitoring_pipeline.run_monitoring_cycle(db_session, [land.land_id])
        assert result == [land.land_id]
        mock_refresh.assert_called_once_with(db_session, land.land_id)

    @patch("app.pipeline.land_monitoring_pipeline._refresh_single_land", return_value=True)
    def test_skips_not_due_lands_when_auto_selecting(self, mock_refresh, db_session):
        land = _seed_land(db_session, interval_days=16)
        db_session.add(
            LandClimate(
                land_id=land.land_id,
                timestamp=datetime.now(timezone.utc) - timedelta(days=1),
                temperature_celsius=Decimal("25"),
            )
        )
        db_session.commit()

        result = land_monitoring_pipeline.run_monitoring_cycle(db_session)
        assert result == []
        mock_refresh.assert_not_called()

    @patch("app.pipeline.land_monitoring_pipeline._refresh_single_land", return_value=True)
    def test_processes_due_lands_when_auto_selecting(self, mock_refresh, db_session):
        land = _seed_land(db_session, interval_days=7)
        db_session.add(
            LandClimate(
                land_id=land.land_id,
                timestamp=datetime.now(timezone.utc) - timedelta(days=10),
                temperature_celsius=Decimal("25"),
            )
        )
        db_session.commit()

        result = land_monitoring_pipeline.run_monitoring_cycle(db_session)
        assert result == [land.land_id]
        mock_refresh.assert_called_once_with(db_session, land.land_id)

    @patch("app.pipeline.land_monitoring_pipeline._refresh_single_land", return_value=False)
    def test_does_not_return_failed_land(self, mock_refresh, db_session):
        land = _seed_land(db_session)
        result = land_monitoring_pipeline.run_monitoring_cycle(db_session, [land.land_id])
        assert result == []