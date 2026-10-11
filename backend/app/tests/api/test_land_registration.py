"""
Tests for POST /lands/discover (GeoJSON polygon) and GET /lands/{id}.
"""

from unittest.mock import patch
from decimal import Decimal

import pytest

from app.lands import repository
from app.models.land import Land


# Suppress real HTTP in all tests in this module
@pytest.fixture(autouse=True)
def _mock_connectors():
    from app.tests.conftest import POLYGON_CLIMATE_MOCK_META, POLYGON_CLIMATE_MOCK_RECORDS

    with patch(
        "app.pipeline.land_discovery_pipeline.open_meteo_polygon.fetch_polygon_historical_climate",
        return_value=(POLYGON_CLIMATE_MOCK_RECORDS, POLYGON_CLIMATE_MOCK_META),
    ):
        yield


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# A simple square around the Nile Delta ([lng, lat] GeoJSON order)
NILE_DELTA_POLYGON = {
    "type": "Polygon",
    "coordinates": [[
        [31.0, 30.0],
        [31.1, 30.0],
        [31.1, 30.1],
        [31.0, 30.1],
        [31.0, 30.0],   # closed
    ]],
}

TRIANGLE_POLYGON = {
    "type": "Polygon",
    "coordinates": [[
        [31.0, 30.0],
        [31.2, 30.0],
        [31.1, 30.2],
    ]],
}


# ===========================================================================
# POST /lands/discover — polygon input
# ===========================================================================

class TestLandDiscoverWithPolygon:
    def test_returns_202_with_land_id(self, client, db_session):
        resp = client.post("/api/v1/lands/discover", json={
            "name": "Nile Delta Farm",
            "geometry": NILE_DELTA_POLYGON,
        })
        assert resp.status_code == 202
        body = resp.json()
        assert body["status"] == "processing"
        assert "land_id" in body
        assert isinstance(body["land_id"], int)

    def test_boundary_polygon_stored_in_db(self, client, db_session):
        resp = client.post("/api/v1/lands/discover", json={
            "name": "Geometry Test",
            "geometry": NILE_DELTA_POLYGON,
        })
        land_id = resp.json()["land_id"]
        land = db_session.get(Land, land_id)
        assert land is not None
        assert land.boundary_polygon is not None
        assert land.boundary_polygon["type"] == "Polygon"

    def test_centroid_computed_from_polygon(self, client, db_session):
        resp = client.post("/api/v1/lands/discover", json={
            "name": "Centroid Test",
            "geometry": NILE_DELTA_POLYGON,
        })
        land_id = resp.json()["land_id"]
        land = db_session.get(Land, land_id)
        # Centroid of square [31.0–31.1, 30.0–30.1] ≈ (30.05, 31.05)
        assert float(land.latitude) == pytest.approx(30.05, abs=0.02)
        assert float(land.longitude) == pytest.approx(31.05, abs=0.02)

    def test_area_hectares_computed_and_stored(self, client, db_session):
        resp = client.post("/api/v1/lands/discover", json={
            "name": "Area Test",
            "geometry": NILE_DELTA_POLYGON,
        })
        land_id = resp.json()["land_id"]
        land = db_session.get(Land, land_id)
        assert land.area_hectares is not None
        # 0.1° × 0.1° square at 30°N:
        # 0.1° lat ≈ 11.1 km, 0.1° lng ≈ 9.6 km → area ≈ 107 km² = 10,700 ha
        assert 5_000 < float(land.area_hectares) < 15_000

    def test_open_ring_is_automatically_closed(self, client, db_session):
        """Backend should close the ring even if frontend didn't send closing point."""
        resp = client.post("/api/v1/lands/discover", json={
            "name": "Open Ring Farm",
            "geometry": TRIANGLE_POLYGON,  # not closed
        })
        assert resp.status_code == 202
        land_id = resp.json()["land_id"]
        land = db_session.get(Land, land_id)
        ring = land.boundary_polygon["coordinates"][0]
        assert ring[0] == ring[-1], "Ring should be auto-closed"

    def test_with_description(self, client, db_session):
        resp = client.post("/api/v1/lands/discover", json={
            "name": "Farm With Desc",
            "description": "Test description",
            "geometry": NILE_DELTA_POLYGON,
        })
        assert resp.status_code == 202

    def test_circle_polygon_from_frontend(self, client, db_session):
        """Simulate auto-circle mode: frontend sends a 64-point circle polygon."""
        from app.lands.geometry import circle_to_polygon
        ring = circle_to_polygon(30.0444, 31.2357, radius_km=2.5, num_points=64)
        geojson = {"type": "Polygon", "coordinates": [ring]}
        resp = client.post("/api/v1/lands/discover", json={
            "name": "2.5km Circle Farm",
            "geometry": geojson,
        })
        assert resp.status_code == 202
        land_id = resp.json()["land_id"]
        land = db_session.get(Land, land_id)
        # Centroid should be close to input center
        assert float(land.latitude) == pytest.approx(30.0444, abs=0.1)
        assert float(land.longitude) == pytest.approx(31.2357, abs=0.1)
        # Area ≈ π × 2.5² × 100 ≈ 1963 ha
        assert 1500 < float(land.area_hectares) < 2500


# ===========================================================================
# POST /lands/discover — validation errors
# ===========================================================================

class TestLandDiscoverValidation:
    def test_missing_geometry_returns_422(self, client, db_session):
        resp = client.post("/api/v1/lands/discover", json={"name": "No Geometry"})
        assert resp.status_code == 422

    def test_wrong_geometry_type_returns_422(self, client, db_session):
        resp = client.post("/api/v1/lands/discover", json={
            "name": "Wrong Type",
            "geometry": {"type": "Point", "coordinates": [31.0, 30.0]},
        })
        assert resp.status_code == 422

    def test_too_few_points_returns_422(self, client, db_session):
        resp = client.post("/api/v1/lands/discover", json={
            "name": "Too Few",
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[31.0, 30.0], [31.1, 30.0]]],  # only 2 unique
            },
        })
        assert resp.status_code == 422

    def test_missing_name_returns_422(self, client, db_session):
        resp = client.post("/api/v1/lands/discover", json={
            "geometry": NILE_DELTA_POLYGON,
        })
        assert resp.status_code == 422


# ===========================================================================
# GET /lands/{id}
# ===========================================================================

class TestGetLandDetail:
    def test_returns_land_with_geometry(self, client, db_session):
        create = client.post("/api/v1/lands/discover", json={
            "name": "Detail Test Farm",
            "geometry": NILE_DELTA_POLYGON,
        })
        land_id = create.json()["land_id"]

        resp = client.get(f"/api/v1/lands/{land_id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["land_id"] == land_id
        assert body["name"] == "Detail Test Farm"
        assert body["boundary_polygon"] is not None
        assert body["boundary_polygon"]["type"] == "Polygon"
        assert body["area_hectares"] is not None
        assert body["area_hectares"] > 0
        assert "latitude" in body
        assert "longitude" in body

    def test_unknown_land_returns_404(self, client, db_session):
        resp = client.get("/api/v1/lands/99999")
        assert resp.status_code == 404
