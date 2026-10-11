"""
Tests for all 5 crop intelligence API endpoints.
Pre-seeds LandCrop rows directly for deterministic tests.
"""

from datetime import datetime, timezone, timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest

from app.models.user import User
from app.models.land import Land
from app.models.land_crop import LandCrop
from app.models.crop_zone import CropZone
from app.tests.conftest import make_token


# ---------------------------------------------------------------------------
# Polygon for land creation
# ---------------------------------------------------------------------------
_POLYGON = {
    "type": "Polygon",
    "coordinates": [[
        [31.0, 30.0], [31.1, 30.0], [31.1, 30.1], [31.0, 30.1],
    ]],
}

_UNKNOWN_PUBLIC_ID = "00000000-0000-0000-0000-000000000099"


@pytest.fixture
def crop_auth(db_session):
    user = User(email="crop-test@local", role="admin")
    db_session.add(user)
    db_session.commit()
    token = make_token(user.user_id, "admin")
    return {"user_id": user.user_id, "headers": {"Authorization": f"Bearer {token}"}}


def _create_land(db_session, user_id: int, name: str) -> Land:
    land = Land(
        user_id=user_id,
        name=name,
        latitude=Decimal("30.0500"),
        longitude=Decimal("31.0500"),
        area_hectares=Decimal("10"),
        status="active",
        boundary_polygon=_POLYGON,
    )
    db_session.add(land)
    db_session.commit()
    db_session.refresh(land)
    return land


@pytest.fixture
def land_id_with_history(db_session, crop_auth):
    """Land with seeded NDVI history (returns internal land_id)."""
    land = _create_land(db_session, crop_auth["user_id"], "Crop Test Farm")

    ndvi_values = [0.20, 0.35, 0.52, 0.68, 0.65, 0.45]
    growth_stages = ["planting", "early_vegetative", "vegetative",
                     "flowering", "grain_fill", "maturity"]
    base_time = datetime.now(timezone.utc) - timedelta(days=90)

    for i, (ndvi, stage) in enumerate(zip(ndvi_values, growth_stages)):
        db_session.add(LandCrop(
            land_id=land.land_id,
            ndvi_value=Decimal(str(ndvi)),
            growth_stage=stage,
            ndvi_trend="improving" if i < 3 else "declining",
            confidence=Decimal("0.85"),
            timestamp=base_time + timedelta(days=i * 16),
        ))

    db_session.commit()
    return land.land_id


@pytest.fixture
def land_public_id_with_history(db_session, crop_auth, land_id_with_history):
    land = db_session.get(Land, land_id_with_history)
    return str(land.public_id)


@pytest.fixture
def empty_land_id(db_session, crop_auth):
    land = _create_land(db_session, crop_auth["user_id"], "Empty Land")
    return land.land_id


@pytest.fixture
def empty_land_public_id(db_session, crop_auth, empty_land_id):
    land = db_session.get(Land, empty_land_id)
    return str(land.public_id)


# ===========================================================================
# 1. Crop Detection
# ===========================================================================

class TestCropDetection:
    def test_returns_200_with_history(self, client, land_id_with_history, land_public_id_with_history, crop_auth):
        resp = client.get(
            f"/api/v1/lands/{land_public_id_with_history}/crop-detection",
            headers=crop_auth["headers"],
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["land_id"] == land_id_with_history
        assert "ndvi_current" in body
        assert body["ndvi_current"] > 0
        assert "health" in body
        assert "confidence" in body

    def test_returns_no_data_for_empty_land(self, client, empty_land_public_id, crop_auth):
        resp = client.get(
            f"/api/v1/lands/{empty_land_public_id}/crop-detection",
            headers=crop_auth["headers"],
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["detection_method"] == "unknown"
        assert body["ndvi_current"] == 0.0

    def test_unknown_land_returns_404(self, client, crop_auth):
        resp = client.get(
            f"/api/v1/lands/{_UNKNOWN_PUBLIC_ID}/crop-detection",
            headers=crop_auth["headers"],
        )
        assert resp.status_code == 404


# ===========================================================================
# 2. Crop Health
# ===========================================================================

class TestCropHealth:
    def test_returns_health_score(self, client, land_public_id_with_history, crop_auth):
        resp = client.get(
            f"/api/v1/lands/{land_public_id_with_history}/crop-health",
            headers=crop_auth["headers"],
        )
        assert resp.status_code == 200
        body = resp.json()
        assert 0 <= body["health_score"] <= 100
        assert body["health_status"] in (
            "bare_soil", "very_sparse", "stressed", "developing",
            "healthy", "very_healthy", "dense_canopy", "no_data",
        )
        assert "advice" in body

    def test_get_is_read_only_does_not_mutate_zones(self, client, db_session, land_id_with_history, land_public_id_with_history, crop_auth):
        zone = CropZone(
            land_id=land_id_with_history,
            crop_type="wheat",
            area_pct=Decimal("100"),
            latest_ndvi=Decimal("0.4500"),
            latest_growth_stage="maturity",
            estimated_yield_tons=Decimal("12.5"),
            status="active",
        )
        db_session.add(zone)
        db_session.commit()
        db_session.refresh(zone)
        before = {
            "latest_ndvi": float(zone.latest_ndvi),
            "latest_growth_stage": zone.latest_growth_stage,
            "estimated_yield_tons": float(zone.estimated_yield_tons),
        }

        with patch("app.intelligence.engine.CropIntelligenceEngine.analyze_land") as mock_analyze:
            for _ in range(3):
                resp = client.get(
                    f"/api/v1/lands/{land_public_id_with_history}/crop-health",
                    headers=crop_auth["headers"],
                )
                assert resp.status_code == 200
            mock_analyze.assert_not_called()

        db_session.refresh(zone)
        assert float(zone.latest_ndvi) == before["latest_ndvi"]
        assert zone.latest_growth_stage == before["latest_growth_stage"]
        assert float(zone.estimated_yield_tons) == before["estimated_yield_tons"]

    def test_refresh_endpoint_persists_zone_updates(self, client, db_session, land_id_with_history, land_public_id_with_history, crop_auth):
        zone = CropZone(
            land_id=land_id_with_history,
            crop_type="wheat",
            area_pct=Decimal("100"),
            latest_ndvi=Decimal("0.1000"),
            latest_growth_stage="planting",
            status="active",
        )
        db_session.add(zone)
        db_session.commit()

        resp = client.post(
            f"/api/v1/lands/{land_public_id_with_history}/crop-health/refresh",
            headers=crop_auth["headers"],
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["land_id"] == land_id_with_history
        assert "health_score" in body

        db_session.refresh(zone)
        assert zone.latest_ndvi is not None
        assert float(zone.latest_ndvi) != 0.1

    def test_unknown_land_returns_404(self, client, crop_auth):
        resp = client.get(
            f"/api/v1/lands/{_UNKNOWN_PUBLIC_ID}/crop-health",
            headers=crop_auth["headers"],
        )
        assert resp.status_code == 404

    def test_refresh_unknown_land_returns_404(self, client, crop_auth):
        resp = client.post(
            f"/api/v1/lands/{_UNKNOWN_PUBLIC_ID}/crop-health/refresh",
            headers=crop_auth["headers"],
        )
        assert resp.status_code == 404


# ===========================================================================
# 3. Crop Status
# ===========================================================================

class TestCropStatus:
    def test_returns_growth_stage_and_trend(self, client, land_public_id_with_history, crop_auth):
        resp = client.get(
            f"/api/v1/lands/{land_public_id_with_history}/crop-status",
            headers=crop_auth["headers"],
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["growth_stage"] in (
            "planting", "early_vegetative", "vegetative",
            "flowering", "grain_fill", "maturity", "harvest_ready", "unknown",
        )
        assert body["trend"] in ("improving", "stable", "declining", "insufficient_data")
        assert "trend_slope" in body
        assert "monitoring_interval_days" in body
        assert body["monitoring_interval_days"] == 16

    def test_returns_last_updated_timestamp(self, client, land_public_id_with_history, crop_auth):
        resp = client.get(
            f"/api/v1/lands/{land_public_id_with_history}/crop-status",
            headers=crop_auth["headers"],
        )
        body = resp.json()
        assert body["last_updated"] != "never"

    def test_unknown_land_returns_404(self, client, crop_auth):
        resp = client.get(
            f"/api/v1/lands/{_UNKNOWN_PUBLIC_ID}/crop-status",
            headers=crop_auth["headers"],
        )
        assert resp.status_code == 404


# ===========================================================================
# 4. Crop Trend
# ===========================================================================

class TestCropTrend:
    def test_returns_ndvi_series(self, client, land_public_id_with_history, crop_auth):
        resp = client.get(
            f"/api/v1/lands/{land_public_id_with_history}/crop-trend?days=90",
            headers=crop_auth["headers"],
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "ndvi_series" in body
        assert len(body["ndvi_series"]) >= 1
        for point in body["ndvi_series"]:
            assert "date" in point
            assert "ndvi" in point
            assert "health" in point

    def test_trend_statistics(self, client, land_public_id_with_history, crop_auth):
        resp = client.get(
            f"/api/v1/lands/{land_public_id_with_history}/crop-trend",
            headers=crop_auth["headers"],
        )
        body = resp.json()
        assert body["min_ndvi"] <= body["mean_ndvi"] <= body["max_ndvi"]

    def test_anomaly_flag_present(self, client, land_public_id_with_history, crop_auth):
        resp = client.get(
            f"/api/v1/lands/{land_public_id_with_history}/crop-trend",
            headers=crop_auth["headers"],
        )
        body = resp.json()
        assert "anomaly_detected" in body
        assert isinstance(body["anomaly_detected"], bool)

    def test_empty_series_for_no_data(self, client, empty_land_public_id, crop_auth):
        resp = client.get(
            f"/api/v1/lands/{empty_land_public_id}/crop-trend",
            headers=crop_auth["headers"],
        )
        assert resp.status_code == 200
        assert resp.json()["ndvi_series"] == []

    def test_unknown_land_returns_404(self, client, crop_auth):
        resp = client.get(
            f"/api/v1/lands/{_UNKNOWN_PUBLIC_ID}/crop-trend",
            headers=crop_auth["headers"],
        )
        assert resp.status_code == 404


# ===========================================================================
# 5. Harvest Prediction
# ===========================================================================

@pytest.fixture
def multi_zone_land_id(db_session, crop_auth):
    """Land with two crop zones and per-zone NDVI history."""
    land = _create_land(db_session, crop_auth["user_id"], "Multi Zone Farm")
    land_id = land.land_id

    zone_wheat = CropZone(
        land_id=land_id,
        crop_type="wheat",
        area_pct=Decimal("60"),
        area_hectares=Decimal("6"),
        status="active",
        avg_confidence=Decimal("0.90"),
    )
    zone_corn = CropZone(
        land_id=land_id,
        crop_type="corn",
        area_pct=Decimal("40"),
        area_hectares=Decimal("4"),
        status="active",
        avg_confidence=Decimal("0.85"),
    )
    db_session.add_all([zone_wheat, zone_corn])
    db_session.flush()

    base_time = datetime.now(timezone.utc) - timedelta(days=90)
    wheat_ndvi = [0.25, 0.40, 0.55, 0.72, 0.68, 0.50]
    corn_ndvi = [0.22, 0.38, 0.50, 0.65, 0.62, 0.48]

    for i, ndvi in enumerate(wheat_ndvi):
        db_session.add(LandCrop(
            land_id=land_id,
            zone_id=zone_wheat.zone_id,
            crop_type="wheat",
            ndvi_value=Decimal(str(ndvi)),
            growth_stage="vegetative" if i < 3 else "maturity",
            timestamp=base_time + timedelta(days=i * 16),
        ))
    for i, ndvi in enumerate(corn_ndvi):
        db_session.add(LandCrop(
            land_id=land_id,
            zone_id=zone_corn.zone_id,
            crop_type="corn",
            ndvi_value=Decimal(str(ndvi)),
            growth_stage="vegetative" if i < 3 else "maturity",
            timestamp=base_time + timedelta(days=i * 16),
        ))
    db_session.commit()
    return land_id


@pytest.fixture
def multi_zone_land_public_id(db_session, multi_zone_land_id):
    land = db_session.get(Land, multi_zone_land_id)
    return str(land.public_id)


class TestHarvestPrediction:
    def test_returns_prediction_with_enough_history(self, client, land_public_id_with_history, crop_auth):
        resp = client.get(
            f"/api/v1/lands/{land_public_id_with_history}/harvest-prediction",
            headers=crop_auth["headers"],
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["prediction_available"] is True
        assert body["peak_ndvi"] is not None
        assert body["estimated_harvest_start"] is not None
        assert body["confidence_level"] in ("high", "medium", "low")

    def test_returns_unavailable_when_no_history(self, client, empty_land_public_id, crop_auth):
        resp = client.get(
            f"/api/v1/lands/{empty_land_public_id}/harvest-prediction",
            headers=crop_auth["headers"],
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["prediction_available"] is False
        assert body["confidence_level"] == "insufficient_data"

    def test_unknown_land_returns_404(self, client, crop_auth):
        resp = client.get(
            f"/api/v1/lands/{_UNKNOWN_PUBLIC_ID}/harvest-prediction",
            headers=crop_auth["headers"],
        )
        assert resp.status_code == 404

    def test_multi_zone_returns_per_zone_predictions(self, client, multi_zone_land_public_id, crop_auth):
        resp = client.get(
            f"/api/v1/lands/{multi_zone_land_public_id}/harvest-prediction",
            headers=crop_auth["headers"],
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["prediction_available"] is True
        assert len(body["zones"]) == 2
        zone_types = {z["crop_type"] for z in body["zones"]}
        assert zone_types == {"wheat", "corn"}
        for zone in body["zones"]:
            assert zone["zone_id"] is not None
            assert zone["prediction_available"] is True
            assert zone["peak_ndvi"] is not None
            assert zone["estimated_harvest_start"] is not None
