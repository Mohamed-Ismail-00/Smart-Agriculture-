"""
Tests for Open-Meteo connector — both unit (mocked) and integration (real HTTP).

Unit tests: always run, no internet required.
Integration tests: marked @pytest.mark.integration, skipped by default.
  Run with: python -m pytest -m integration -v
"""

from unittest.mock import MagicMock, patch
from datetime import date, timedelta

import pytest


# ===========================================================================
# UNIT TESTS — mocked HTTP, no internet required
# ===========================================================================

class TestFetchCurrentLandClimateUnit:
    """Unit tests for fetch_current_land_climate."""

    def test_returns_all_three_fields(self):
        fake_response = {
            "current": {
                "temperature_2m": 28.5,
                "relative_humidity_2m": 62.0,
                "precipitation": 0.3,
            }
        }
        mock_resp = MagicMock()
        mock_resp.json.return_value = fake_response
        mock_resp.raise_for_status.return_value = None

        with patch("httpx.Client") as mock_client_cls:
            mock_client_cls.return_value.__enter__.return_value.get.return_value = mock_resp
            from app.connectors.open_meteo import fetch_current_land_climate
            result = fetch_current_land_climate(30.0, 31.0)

        assert result is not None
        assert result["temperature_celsius"] == pytest.approx(28.5)
        assert result["humidity_pct"] == pytest.approx(62.0)
        assert result["rainfall_mm"] == pytest.approx(0.3)

    def test_returns_none_on_http_error(self):
        import httpx
        with patch("httpx.Client") as mock_client_cls:
            mock_client_cls.return_value.__enter__.return_value.get.side_effect = httpx.HTTPError("timeout")
            from app.connectors.open_meteo import fetch_current_land_climate
            result = fetch_current_land_climate(30.0, 31.0)

        assert result is None

    def test_returns_none_when_all_fields_missing(self):
        fake_response = {"current": {}}
        mock_resp = MagicMock()
        mock_resp.json.return_value = fake_response
        mock_resp.raise_for_status.return_value = None

        with patch("httpx.Client") as mock_client_cls:
            mock_client_cls.return_value.__enter__.return_value.get.return_value = mock_resp
            from app.connectors.open_meteo import fetch_current_land_climate
            result = fetch_current_land_climate(30.0, 31.0)

        assert result is None

    def test_returns_partial_fields(self):
        """If only some fields are present, still returns them."""
        fake_response = {"current": {"temperature_2m": 35.0}}
        mock_resp = MagicMock()
        mock_resp.json.return_value = fake_response
        mock_resp.raise_for_status.return_value = None

        with patch("httpx.Client") as mock_client_cls:
            mock_client_cls.return_value.__enter__.return_value.get.return_value = mock_resp
            from app.connectors.open_meteo import fetch_current_land_climate
            result = fetch_current_land_climate(30.0, 31.0)

        assert result is not None
        assert "temperature_celsius" in result
        assert "humidity_pct" not in result


class TestFetchSoilAndET0Unit:
    """Unit tests for fetch_soil_and_et0."""

    def _make_mock_client(self, et0_resp: dict, soil_resp: dict):
        """Creates a mock httpx.Client that returns different responses per call."""
        mock_et0 = MagicMock()
        mock_et0.json.return_value = et0_resp
        mock_et0.raise_for_status.return_value = None

        mock_soil = MagicMock()
        mock_soil.json.return_value = soil_resp
        mock_soil.raise_for_status.return_value = None

        mock_session = MagicMock()
        mock_session.get.side_effect = [mock_et0, mock_soil]
        return mock_session

    def test_returns_et0_and_soil_moisture(self):
        from datetime import date, timedelta
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        et0_resp = {
            "daily": {
                "time": [yesterday],
                "et0_fao_evapotranspiration": [4.5],
            }
        }
        # hourly: 24 values for one day; index 12 = noon = 0.25 m³/m³
        soil_resp = {
            "hourly": {
                "soil_moisture_0_to_7cm": [0.20] * 12 + [0.25] + [0.20] * 11,
            }
        }
        mock_session = self._make_mock_client(et0_resp, soil_resp)

        with patch("httpx.Client") as mock_client_cls:
            mock_client_cls.return_value.__enter__.return_value = mock_session
            from app.connectors.open_meteo import fetch_soil_and_et0
            result = fetch_soil_and_et0(30.0, 31.0, days=1)

        assert result is not None
        assert result["et0_mm_per_day"] == pytest.approx(4.5)
        assert result["soil_moisture_pct"] == pytest.approx(25.0)  # 0.25 × 100
        assert "date" in result

    def test_returns_none_on_http_error(self):
        import httpx
        with patch("httpx.Client") as mock_client_cls:
            mock_client_cls.return_value.__enter__.return_value.get.side_effect = httpx.HTTPError("timeout")
            from app.connectors.open_meteo import fetch_soil_and_et0
            result = fetch_soil_and_et0(30.0, 31.0)

        assert result is None

    def test_returns_none_when_all_values_null(self):
        from datetime import date, timedelta
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        et0_resp = {"daily": {"time": [yesterday], "et0_fao_evapotranspiration": [None]}}
        # All soil values null
        soil_resp = {"hourly": {"soil_moisture_0_to_7cm": [None] * 24}}

        mock_session = self._make_mock_client(et0_resp, soil_resp)
        with patch("httpx.Client") as mock_client_cls:
            mock_client_cls.return_value.__enter__.return_value = mock_session
            from app.connectors.open_meteo import fetch_soil_and_et0
            result = fetch_soil_and_et0(30.0, 31.0)

        assert result is None

    def test_soil_moisture_converts_volumetric_to_percent(self):
        """0.40 m³/m³ at noon should become 40.0%."""
        from datetime import date, timedelta
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        et0_resp = {"daily": {"time": [yesterday], "et0_fao_evapotranspiration": [None]}}
        soil_resp = {
            "hourly": {
                "soil_moisture_0_to_7cm": [0.30] * 12 + [0.40] + [0.30] * 11,
            }
        }
        mock_session = self._make_mock_client(et0_resp, soil_resp)
        with patch("httpx.Client") as mock_client_cls:
            mock_client_cls.return_value.__enter__.return_value = mock_session
            from app.connectors.open_meteo import fetch_soil_and_et0
            result = fetch_soil_and_et0(30.0, 31.0)

        assert result is not None
        assert result["soil_moisture_pct"] == pytest.approx(40.0)


class TestFetchHistoricalClimateUnit:
    """Unit tests for fetch_historical_climate."""

    def test_returns_list_of_daily_records(self):
        from app.connectors.open_meteo import fetch_historical_climate
        daily_resp = {
            "daily": {
                "time": ["2026-04-01", "2026-04-02"],
                "temperature_2m_max": [32.0, 34.0],
                "temperature_2m_min": [18.0, 19.0],
                "precipitation_sum": [0.0, 2.5],
                "et0_fao_evapotranspiration": [5.1, 5.8],
            }
        }
        # 2 days × 24 hours = 48 hourly values; noon = indices 12 and 36
        soil_hourly = [0.22] * 12 + [0.22] + [0.22] * 11 + [0.20] * 12 + [0.20] + [0.20] * 11
        hourly_resp = {"hourly": {"soil_moisture_0_to_7cm": soil_hourly}}

        mock_daily = MagicMock()
        mock_daily.json.return_value = daily_resp
        mock_daily.raise_for_status.return_value = None

        mock_hourly = MagicMock()
        mock_hourly.json.return_value = hourly_resp
        mock_hourly.raise_for_status.return_value = None

        mock_session = MagicMock()
        mock_session.get.side_effect = [mock_daily, mock_hourly]

        with patch("httpx.Client") as mock_client_cls:
            mock_client_cls.return_value.__enter__.return_value = mock_session
            result = fetch_historical_climate(30.0, 31.0, days=2)

        assert result is not None
        assert len(result) == 2
        assert result[0]["date"] == "2026-04-01"
        assert result[0]["temperature_max_c"] == pytest.approx(32.0)
        assert result[0]["soil_moisture_pct"] == pytest.approx(22.0)  # 0.22 × 100
        assert result[1]["soil_moisture_pct"] == pytest.approx(20.0)  # 0.20 × 100

    def test_returns_none_on_error(self):
        import httpx
        with patch("httpx.Client") as mock_client_cls:
            mock_client_cls.return_value.__enter__.return_value.get.side_effect = httpx.HTTPError("timeout")
            from app.connectors.open_meteo import fetch_historical_climate
            result = fetch_historical_climate(30.0, 31.0)
        assert result is None


# ===========================================================================
# UNIT TESTS — Discovery pipeline with new soil/ET₀ step mocked
# ===========================================================================

class TestDiscoveryPipelineWithSoilET0:
    """Verify that discovery now also writes soil + water rows from real connectors."""

    _POLYGON = {
        "type": "Polygon",
        "coordinates": [[
            [31.0, 30.0], [31.1, 30.0], [31.1, 30.1], [31.0, 30.1],
        ]],
    }

    def test_discovery_writes_soil_and_water_rows(self, client, db_session):
        """
        When fetch_soil_and_et0 returns data, discovery should write to land_soil
        and land_water in addition to land_climate.
        """
        from app.lands import repository as repo

        from app.tests.conftest import POLYGON_CLIMATE_MOCK_META

        polygon_records = [{
            "date": "2026-04-24",
            "temperature_max_c": 25.0,
            "temperature_min_c": 18.0,
            "humidity_pct": 60.0,
            "rainfall_mm": 0.0,
            "et0_mm": 5.2,
            "soil_moisture_pct": 28.5,
        }]

        with patch(
            "app.pipeline.land_discovery_pipeline.open_meteo_polygon.fetch_polygon_historical_climate",
            return_value=(polygon_records, POLYGON_CLIMATE_MOCK_META),
        ):

            resp = client.post(
                "/api/v1/lands/discover",
                json={"name": "Delta Farm", "geometry": self._POLYGON},
            )
        assert resp.status_code == 202
        land_id = resp.json()["land_id"]

        # land_climate should have 1 row
        climate_rows = repo.list_land_climate_rows(db_session, land_id)
        assert len(climate_rows) == 1

        # land_soil should have 1 row with real moisture
        soil_rows = repo.list_land_soil_rows(db_session, land_id)
        assert len(soil_rows) == 1
        assert float(soil_rows[0].moisture_pct) == pytest.approx(28.5)

        # land_water should have 1 row with ET₀ as crop_water_requirement_mm
        water_rows = repo.list_land_water_rows(db_session, land_id)
        assert len(water_rows) == 1
        assert float(water_rows[0].crop_water_requirement_mm) == pytest.approx(5.2)

    def test_discovery_still_completes_when_soil_connector_fails(self, client, db_session):
        """Pipeline should not fail if the soil connector returns None."""
        from app.tests.conftest import POLYGON_CLIMATE_MOCK_META

        polygon_records = [{
            "date": "2026-04-24",
            "temperature_max_c": 25.0,
            "temperature_min_c": 18.0,
            "humidity_pct": 60.0,
            "rainfall_mm": 0.0,
        }]

        with patch(
            "app.pipeline.land_discovery_pipeline.open_meteo_polygon.fetch_polygon_historical_climate",
            return_value=(polygon_records, POLYGON_CLIMATE_MOCK_META),
        ):
            resp = client.post(
                "/api/v1/lands/discover",
                json={"name": "Test Fallback", "geometry": self._POLYGON},
            )

        assert resp.status_code == 202
        land_id = resp.json()["land_id"]
        from app.models.land import Land
        land = db_session.get(Land, land_id)
        assert land is not None


# ===========================================================================
# INTEGRATION TESTS — Real HTTP calls to Open-Meteo
# Run manually: python -m pytest app/tests/connectors/ -m integration -v
# ===========================================================================

@pytest.mark.integration
class TestOpenMeteoIntegration:
    """
    Real HTTP calls — skipped unless you run with: pytest -m integration
    These tests verify the API shape hasn't changed (not exact values).
    Uses Nile Delta coordinates (30.0444, 31.2357).
    """

    def test_fetch_current_climate_returns_real_data(self):
        from app.connectors.open_meteo import fetch_current_land_climate
        result = fetch_current_land_climate(30.0444, 31.2357)
        assert result is not None, "Open-Meteo returned None — check connectivity"
        assert "temperature_celsius" in result
        temp = result["temperature_celsius"]
        assert -30 < temp < 60, f"Unrealistic temperature: {temp}"

    def test_fetch_soil_et0_returns_real_data(self):
        from app.connectors.open_meteo import fetch_soil_and_et0
        result = fetch_soil_and_et0(30.0444, 31.2357, days=7)
        assert result is not None, "Open-Meteo archive returned None — check connectivity"
        assert "date" in result
        # At least one of ET₀ or soil moisture should be present
        has_data = "et0_mm_per_day" in result or "soil_moisture_pct" in result
        assert has_data, f"Expected ET₀ or soil moisture, got: {result}"
        if "et0_mm_per_day" in result:
            assert 0 <= result["et0_mm_per_day"] <= 20, f"Unrealistic ET₀: {result['et0_mm_per_day']}"
        if "soil_moisture_pct" in result:
            assert 0 <= result["soil_moisture_pct"] <= 100, f"Unrealistic soil moisture: {result['soil_moisture_pct']}"

    def test_fetch_historical_climate_returns_30_days(self):
        from app.connectors.open_meteo import fetch_historical_climate
        result = fetch_historical_climate(30.0444, 31.2357, days=30)
        assert result is not None
        # Should return close to 30 records (may be slightly fewer due to archive lag)
        assert len(result) >= 25, f"Expected ~30 records, got {len(result)}"
        # Each record should have a date
        for rec in result:
            assert "date" in rec
