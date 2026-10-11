"""
Phase 1 tests: Foundation & Data Layer.

Covers:
- Extended model columns (LandCrop, LandWater, LandSoil, LandImage new fields)
- New LandAlert model
- Repository functions for all domain tables
- Time-series API for water / crops / soil (previously returned empty [])
- Image list API endpoint
"""

from datetime import datetime, timezone, timedelta

from unittest.mock import patch
from decimal import Decimal

import pytest

from app.lands import repository
from app.models.land import Land
from app.models.land_alert import LandAlert
from app.models.land_crop import LandCrop
from app.models.land_image import LandImage
from app.models.land_soil import LandSoil
from app.models.land_water import LandWater


# ---------------------------------------------------------------------------
# Mock fixture — prevent real Open-Meteo HTTP in any test that triggers discovery
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _mock_open_meteo():
    from app.tests.conftest import POLYGON_CLIMATE_MOCK_META, POLYGON_CLIMATE_MOCK_RECORDS

    with patch(
        "app.pipeline.land_discovery_pipeline.open_meteo_polygon.fetch_polygon_historical_climate",
        return_value=(POLYGON_CLIMATE_MOCK_RECORDS, POLYGON_CLIMATE_MOCK_META),
    ):
        yield


# ---------------------------------------------------------------------------
# Helper: create a land and return its id
# ---------------------------------------------------------------------------

def _create_land(db) -> int:
    land = repository.create_land(
        db, name="Test Plot", latitude=Decimal("30.0"),
        longitude=Decimal("31.0"), description=None, user_id=None,
    )
    db.commit()
    db.refresh(land)
    return int(land.land_id)


# ===================================================================
# A. MODEL COLUMN TESTS — verify new columns can be written and read
# ===================================================================

class TestLandCropColumns:
    def test_growth_stage_column_exists(self, db_session):
        land_id = _create_land(db_session)
        row = repository.insert_land_crop_snapshot(
            db_session, land_id,
            crop_type="wheat", ndvi_value=0.65,
            growth_stage="vegetative", ndvi_trend="improving", confidence=0.88,
        )
        db_session.commit()
        db_session.refresh(row)
        assert row.growth_stage == "vegetative"
        assert row.ndvi_trend == "improving"
        assert float(row.confidence) == pytest.approx(0.88, abs=0.01)

    def test_crop_columns_nullable(self, db_session):
        land_id = _create_land(db_session)
        row = repository.insert_land_crop_snapshot(db_session, land_id)
        db_session.commit()
        db_session.refresh(row)
        assert row.growth_stage is None
        assert row.ndvi_trend is None
        assert row.confidence is None


class TestLandWaterColumns:
    def test_water_requirement_columns(self, db_session):
        land_id = _create_land(db_session)
        row = repository.insert_land_water_snapshot(
            db_session, land_id,
            estimated_water_usage_liters=5000.0,
            irrigation_status="adequate",
            crop_water_requirement_mm=5.5,
            water_efficiency_ratio=0.0012,
        )
        db_session.commit()
        db_session.refresh(row)
        assert float(row.crop_water_requirement_mm) == pytest.approx(5.5, abs=0.01)
        assert float(row.water_efficiency_ratio) == pytest.approx(0.0012, abs=0.001)


class TestLandSoilColumns:
    def test_soil_quality_columns(self, db_session):
        land_id = _create_land(db_session)
        row = repository.insert_land_soil_snapshot(
            db_session, land_id,
            moisture_pct=35.0, soil_type="clay",
            ph_level=6.5, organic_matter_pct=3.2, suitability_score=78.0,
        )
        db_session.commit()
        db_session.refresh(row)
        assert float(row.ph_level) == pytest.approx(6.5, abs=0.1)
        assert float(row.organic_matter_pct) == pytest.approx(3.2, abs=0.1)
        assert float(row.suitability_score) == pytest.approx(78.0, abs=0.1)


class TestLandImageColumns:
    def test_ndvi_mean_and_cloud_cover(self, db_session):
        land_id = _create_land(db_session)
        row = repository.insert_land_image(
            db_session, land_id,
            image_path="data/images/lands/1/2026-01-01_ndvi.png",
            image_type="ndvi",
            ndvi_mean=0.72, cloud_cover_pct=15.5,
        )
        db_session.commit()
        db_session.refresh(row)
        assert float(row.ndvi_mean) == pytest.approx(0.72, abs=0.01)
        assert float(row.cloud_cover_pct) == pytest.approx(15.5, abs=0.1)


# ===================================================================
# B. LAND ALERT MODEL TESTS
# ===================================================================

class TestLandAlertModel:
    def test_create_and_read_alert(self, db_session):
        land_id = _create_land(db_session)
        alert = repository.insert_land_alert(
            db_session, land_id,
            alert_type="ndvi_drop",
            severity="high",
            message="NDVI dropped 20% in 5 days",
            payload={"ndvi_before": 0.7, "ndvi_after": 0.5},
        )
        db_session.commit()
        db_session.refresh(alert)
        assert alert.alert_type == "ndvi_drop"
        assert alert.severity == "high"
        assert alert.resolved_at is None

    def test_list_alerts_unresolved(self, db_session):
        land_id = _create_land(db_session)
        repository.insert_land_alert(
            db_session, land_id, alert_type="heat_stress",
            severity="medium", message="Temperature above 40C for 3 days",
        )
        repository.insert_land_alert(
            db_session, land_id, alert_type="drought",
            severity="low", message="No rainfall for 14 days",
        )
        db_session.commit()
        alerts = repository.list_land_alerts(db_session, land_id, unresolved_only=True)
        assert len(alerts) == 2


# ===================================================================
# C. REPOSITORY QUERY TESTS
# ===================================================================

class TestCropRepository:
    def test_list_crop_rows_ordered(self, db_session):
        land_id = _create_land(db_session)
        repository.insert_land_crop_snapshot(db_session, land_id, ndvi_value=0.3, crop_type="wheat")
        repository.insert_land_crop_snapshot(db_session, land_id, ndvi_value=0.5, crop_type="wheat")
        db_session.commit()
        rows = repository.list_land_crop_rows(db_session, land_id)
        assert len(rows) == 2
        # ordered by timestamp asc
        assert float(rows[0].ndvi_value) < float(rows[1].ndvi_value)

    def test_get_latest_crop_record(self, db_session):
        # Use explicit timestamps to guarantee ordering in SQLite
        now = datetime.now(timezone.utc)
        land_id = _create_land(db_session)
        r1 = repository.insert_land_crop_snapshot(db_session, land_id, ndvi_value=0.3)
        r1.timestamp = now - timedelta(seconds=10)
        r2 = repository.insert_land_crop_snapshot(db_session, land_id, ndvi_value=0.7)
        r2.timestamp = now
        db_session.commit()
        latest = repository.get_latest_crop_record(db_session, land_id)
        assert latest is not None
        assert float(latest.ndvi_value) == pytest.approx(0.7, abs=0.01)

    def test_get_latest_crop_record_empty(self, db_session):
        land_id = _create_land(db_session)
        db_session.commit()
        assert repository.get_latest_crop_record(db_session, land_id) is None


class TestWaterRepository:
    def test_list_water_rows(self, db_session):
        land_id = _create_land(db_session)
        repository.insert_land_water_snapshot(
            db_session, land_id,
            estimated_water_usage_liters=1000.0, irrigation_status="overuse",
        )
        db_session.commit()
        rows = repository.list_land_water_rows(db_session, land_id)
        assert len(rows) == 1
        assert rows[0].irrigation_status == "overuse"

    def test_get_latest_water_record(self, db_session):
        now = datetime.now(timezone.utc)
        land_id = _create_land(db_session)
        r1 = repository.insert_land_water_snapshot(db_session, land_id, estimated_water_usage_liters=500.0)
        r1.timestamp = now - timedelta(seconds=10)
        r2 = repository.insert_land_water_snapshot(db_session, land_id, estimated_water_usage_liters=800.0)
        r2.timestamp = now
        db_session.commit()
        latest = repository.get_latest_water_record(db_session, land_id)
        assert latest is not None
        assert float(latest.estimated_water_usage_liters) == pytest.approx(800.0, abs=1)


class TestSoilRepository:
    def test_list_soil_rows(self, db_session):
        land_id = _create_land(db_session)
        repository.insert_land_soil_snapshot(
            db_session, land_id, moisture_pct=40.0, soil_type="loam", ph_level=7.0,
        )
        db_session.commit()
        rows = repository.list_land_soil_rows(db_session, land_id)
        assert len(rows) == 1
        assert rows[0].soil_type == "loam"


class TestImageRepository:
    def test_list_images_with_filter(self, db_session):
        land_id = _create_land(db_session)
        repository.insert_land_image(
            db_session, land_id, image_path="/img/1.png", image_type="true_color",
        )
        repository.insert_land_image(
            db_session, land_id, image_path="/img/2.png", image_type="ndvi",
        )
        db_session.commit()
        all_imgs = repository.list_land_images(db_session, land_id)
        assert len(all_imgs) == 2
        ndvi_only = repository.list_land_images(db_session, land_id, image_type="ndvi")
        assert len(ndvi_only) == 1
        assert ndvi_only[0].image_type == "ndvi"

    def test_get_land_image_by_id(self, db_session):
        land_id = _create_land(db_session)
        img = repository.insert_land_image(
            db_session, land_id, image_path="/img/test.png", image_type="ndvi",
        )
        db_session.commit()
        fetched = repository.get_land_image(db_session, int(img.id))
        assert fetched is not None
        assert fetched.image_path == "/img/test.png"


# ===================================================================
# D. API TESTS — Time-series for water / crops / soil
# ===================================================================

class TestTimeSeriesWaterAPI:
    def test_water_timeseries_returns_data(self, client, db_session):
        land_id = _create_land(db_session)
        repository.update_land_status(db_session, land_id, "active")
        repository.insert_land_water_snapshot(
            db_session, land_id,
            estimated_water_usage_liters=2500.0, irrigation_status="adequate",
            crop_water_requirement_mm=5.0,
        )
        db_session.commit()
        resp = client.get(f"/api/v1/lands/{land_id}/timeseries?metric=water")
        assert resp.status_code == 200
        data = resp.json()
        assert data["metric"] == "water"
        assert len(data["points"]) == 1
        pt = data["points"][0]
        assert pt["value"] == pytest.approx(2500.0, abs=1)
        assert pt["payload"]["irrigation_status"] == "adequate"
        assert pt["payload"]["crop_water_requirement_mm"] == pytest.approx(5.0, abs=0.1)


class TestTimeSeriesCropsAPI:
    def test_crops_timeseries_returns_data(self, client, db_session):
        land_id = _create_land(db_session)
        repository.update_land_status(db_session, land_id, "active")
        repository.insert_land_crop_snapshot(
            db_session, land_id,
            crop_type="wheat", ndvi_value=0.65,
            growth_stage="vegetative", ndvi_trend="improving", confidence=0.88,
        )
        db_session.commit()
        resp = client.get(f"/api/v1/lands/{land_id}/timeseries?metric=crops")
        assert resp.status_code == 200
        data = resp.json()
        assert data["metric"] == "crops"
        assert len(data["points"]) == 1
        pt = data["points"][0]
        assert pt["value"] == pytest.approx(0.65, abs=0.01)
        assert pt["payload"]["crop_type"] == "wheat"
        assert pt["payload"]["growth_stage"] == "vegetative"
        assert pt["payload"]["ndvi_trend"] == "improving"
        assert pt["payload"]["confidence"] == pytest.approx(0.88, abs=0.01)


class TestTimeSeriesSoilAPI:
    def test_soil_timeseries_returns_data(self, client, db_session):
        land_id = _create_land(db_session)
        repository.update_land_status(db_session, land_id, "active")
        repository.insert_land_soil_snapshot(
            db_session, land_id,
            moisture_pct=35.0, soil_type="clay", ph_level=6.5,
            organic_matter_pct=3.2, suitability_score=78.0,
        )
        db_session.commit()
        resp = client.get(f"/api/v1/lands/{land_id}/timeseries?metric=soil")
        assert resp.status_code == 200
        data = resp.json()
        assert data["metric"] == "soil"
        assert len(data["points"]) == 1
        pt = data["points"][0]
        assert pt["value"] == pytest.approx(35.0, abs=1)
        assert pt["payload"]["soil_type"] == "clay"
        assert pt["payload"]["ph_level"] == pytest.approx(6.5, abs=0.1)
        assert pt["payload"]["suitability_score"] == pytest.approx(78.0, abs=1)


# ===================================================================
# E. API TESTS — Image list endpoint
# ===================================================================

class TestImageListAPI:
    def test_images_endpoint_returns_data(self, client, db_session):
        land_id = _create_land(db_session)
        repository.update_land_status(db_session, land_id, "active")
        repository.insert_land_image(
            db_session, land_id,
            image_path="data/images/lands/1/2026-01-01_true.png",
            image_type="true_color", ndvi_mean=None, cloud_cover_pct=10.0,
        )
        repository.insert_land_image(
            db_session, land_id,
            image_path="data/images/lands/1/2026-01-01_ndvi.png",
            image_type="ndvi", ndvi_mean=0.72, cloud_cover_pct=10.0,
        )
        db_session.commit()
        resp = client.get(f"/api/v1/lands/{land_id}/images")
        assert resp.status_code == 200
        data = resp.json()
        assert data["land_id"] == land_id
        assert len(data["images"]) == 2

    def test_images_endpoint_filter_by_type(self, client, db_session):
        land_id = _create_land(db_session)
        repository.update_land_status(db_session, land_id, "active")
        repository.insert_land_image(
            db_session, land_id, image_path="/a.png", image_type="true_color",
        )
        repository.insert_land_image(
            db_session, land_id, image_path="/b.png", image_type="ndvi",
        )
        db_session.commit()
        resp = client.get(f"/api/v1/lands/{land_id}/images?image_type=ndvi")
        assert resp.status_code == 200
        assert len(resp.json()["images"]) == 1
        assert resp.json()["images"][0]["image_type"] == "ndvi"

    def test_images_endpoint_unknown_land_returns_404(self, client, db_session):
        resp = client.get("/api/v1/lands/9999/images")
        assert resp.status_code == 404

    def test_images_endpoint_empty_land_returns_empty_list(self, client, db_session):
        land_id = _create_land(db_session)
        db_session.commit()
        resp = client.get(f"/api/v1/lands/{land_id}/images")
        assert resp.status_code == 200
        assert resp.json()["images"] == []
