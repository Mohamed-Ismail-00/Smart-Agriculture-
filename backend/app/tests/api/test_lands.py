"""Tests for land discovery (GeoJSON polygon), Open-Meteo climate snapshot, and timeseries."""

from decimal import Decimal
from unittest.mock import patch

import pytest

from app.lands.geometry import circle_to_polygon
from app.models.land import Land
from app.models.user import User
from app.tests.conftest import POLYGON_CLIMATE_MOCK_META, POLYGON_CLIMATE_MOCK_RECORDS, make_token

# Shared minimal polygon for tests that only care about land_id
_MINIMAL_POLYGON = {
    "type": "Polygon",
    "coordinates": [[
        [31.0, 30.0], [31.1, 30.0], [31.1, 30.1], [31.0, 30.1],
    ]],
}

_UNKNOWN_PUBLIC_ID = "00000000-0000-0000-0000-000000000099"


@pytest.fixture
def lands_auth(db_session):
    user = User(email="lands-test@local", role="admin")
    db_session.add(user)
    db_session.commit()
    token = make_token(user.user_id, "admin")
    return {"user_id": user.user_id, "headers": {"Authorization": f"Bearer {token}"}}


@pytest.fixture(autouse=True)
def _mock_discovery_deps():
    """Avoid real HTTP and flaky validation during discovery tests."""
    with patch(
        "app.lands.validator.modis_ndvi.fetch_ndvi_history",
        return_value=[{"ndvi_modis": 0.55}],
    ), patch(
        "app.pipeline.land_discovery_pipeline.open_meteo_polygon.fetch_polygon_historical_climate",
        return_value=(POLYGON_CLIMATE_MOCK_RECORDS, POLYGON_CLIMATE_MOCK_META),
    ), patch("app.tasks.sentinel_task.run_sentinel_visual_fetch"), \
         patch("app.tasks.soil_task.run_soil_profile_task", return_value=True), \
         patch("app.tasks.crop_task.run_crop_detection_task"), \
         patch("app.ai.land_analyst.run_ai_land_analysis"):
        yield


def test_discover_land_returns_202(client, db_session, lands_auth):
    resp = client.post(
        "/api/v1/lands/discover",
        json={"name": "Nile Delta Plot 1", "geometry": _MINIMAL_POLYGON},
        headers=lands_auth["headers"],
    )
    assert resp.status_code == 202
    body = resp.json()
    assert body["status"] == "processing"
    land_id = body["land_id"]
    land = db_session.get(Land, land_id)
    assert land is not None
    assert land.name == "Nile Delta Plot 1"


def test_timeseries_unknown_land(client, db_session, lands_auth):
    resp = client.get(
        f"/api/v1/lands/{_UNKNOWN_PUBLIC_ID}/timeseries",
        headers=lands_auth["headers"],
    )
    assert resp.status_code == 404


def test_timeseries_climate_returns_points_after_discovery(client, db_session, lands_auth):
    from app.lands import repository
    from app.pipeline.land_discovery_pipeline import insert_historical_environment_records

    discover = client.post(
        "/api/v1/lands/discover",
        json={"name": "Test", "geometry": _MINIMAL_POLYGON},
        headers=lands_auth["headers"],
    )
    assert discover.status_code == 202
    body = discover.json()
    public_id = body["public_id"]
    land_id = body["land_id"]

    land = db_session.get(Land, land_id)
    ds = repository.get_or_create_data_source(db_session, "Open-Meteo")
    insert_historical_environment_records(
        db_session,
        land,
        POLYGON_CLIMATE_MOCK_RECORDS,
        None,
        source_id=int(ds.source_id),
    )
    repository.update_land_climate_sampling_metadata(db_session, land_id, POLYGON_CLIMATE_MOCK_META)
    db_session.commit()

    resp = client.get(
        f"/api/v1/lands/{public_id}/timeseries?metric=climate",
        headers=lands_auth["headers"],
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["land_id"] == land_id
    assert data["metric"] == "climate"
    assert len(data["points"]) == 1
    pt = data["points"][0]
    assert pt["value"] == 22.5
    assert pt["payload"]["humidity_pct"] == 55.0
    assert pt["payload"]["rainfall_mm"] == 0.1
    assert pt["payload"]["spatial_sample"]["spatial_scope"] == "polygon_mean"


def test_timeseries_climate_empty_when_connector_returns_none(client, db_session, lands_auth):
    with patch(
        "app.pipeline.land_discovery_pipeline.open_meteo_polygon.fetch_polygon_historical_climate",
        return_value=(None, None),
    ):
        discover = client.post(
            "/api/v1/lands/discover",
            json={"name": "No weather", "geometry": _MINIMAL_POLYGON},
            headers=lands_auth["headers"],
        )
    assert discover.status_code == 202
    public_id = discover.json()["public_id"]
    resp = client.get(
        f"/api/v1/lands/{public_id}/timeseries?metric=climate",
        headers=lands_auth["headers"],
    )
    assert resp.status_code == 200
    assert resp.json()["points"] == []


def test_circle_to_polygon_produces_closed_ring():
    ring = circle_to_polygon(30.0, 31.0, radius_km=1.0, num_points=8)
    assert ring[0] == ring[-1]
    assert len(ring) == 9