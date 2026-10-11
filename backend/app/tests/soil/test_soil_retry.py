"""Tests for SoilGrids retry logic and soil profile retry API."""

from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.connectors.soilgrids import SoilFetchResult, fetch_soil_profile
from app.models.land import Land
from app.tasks.soil_task import run_soil_profile_task


class TestSoilGridsRetry:
    def test_retries_on_timeout_then_succeeds(self):
        good_response = MagicMock()
        good_response.json.return_value = {
            "properties": {
                "layers": [
                    {
                        "name": "phh2o",
                        "unit_measure": {"d_factor": 10},
                        "depths": [{"label": "0-5cm", "values": {"mean": 78}}],
                    }
                ]
            }
        }
        good_response.raise_for_status = MagicMock()

        with patch("app.connectors.soilgrids.time.sleep"):
            with patch("httpx.Client") as client_cls:
                client = MagicMock()
                client.__enter__.return_value = client
                client.get.side_effect = [
                    httpx.TimeoutException("timeout"),
                    good_response,
                ]
                client_cls.return_value = client

                result = fetch_soil_profile(30.0, 31.0, max_attempts=2)

        assert result.status == "success"
        assert result.attempts == 2
        assert result.profile is not None

    def test_returns_timeout_after_all_attempts(self):
        with patch("app.connectors.soilgrids.time.sleep"):
            with patch("httpx.Client") as client_cls:
                client = MagicMock()
                client.__enter__.return_value = client
                client.get.side_effect = httpx.TimeoutException("timeout")
                client_cls.return_value = client

                result = fetch_soil_profile(30.0, 31.0, max_attempts=2)

        assert result.status == "timeout"
        assert result.attempts == 2
        assert result.profile is None


class TestSoilTaskPersistence:
    def test_persists_fetch_status_on_failure(self, db_session):
        land = Land(
            name="Test Farm",
            latitude=30.0,
            longitude=31.0,
            status="active",
        )
        db_session.add(land)
        db_session.commit()

        with patch(
            "app.tasks.soil_task.soilgrids.fetch_soil_profile",
            return_value=SoilFetchResult(
                profile=None,
                status="timeout",
                attempts=3,
                last_error="timed out",
            ),
        ):
            ok = run_soil_profile_task(land.land_id, db_session)

        assert ok is False
        db_session.refresh(land)
        from app.soil.repository import get_soil_profile

        profile = get_soil_profile(db_session, land.land_id)
        assert profile is not None
        assert profile.fetch_status == "timeout"
        assert profile.fetch_attempts == 3
        assert profile.trust_tier == "unavailable"