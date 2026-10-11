"""
Tests for Sentinel-2 Planetary Computer Integration.
"""

from unittest.mock import patch
import httpx
import pytest

from app.connectors import sentinel
from app.tasks import sentinel_task
from app.models.land_image import LandImage

# ---------------------------------------------------------------------------
# Mocks
# ---------------------------------------------------------------------------

_STAC_MOCK_RESPONSE = {
    "features": [
        {
            "id": "S2B_MSIL2A_TEST_ID",
            "collection": "sentinel-2-l2a",
            "properties": {
                "datetime": "2024-01-01T12:00:00Z",
                "eo:cloud_cover": 1.5,
            }
        }
    ]
}

_BBOX = [31.0, 30.0, 31.05, 30.05]
_POLYGON = {
    "type": "Polygon",
    "coordinates": [[
        [31.0, 30.0], [31.05, 30.0], [31.05, 30.05], [31.0, 30.05], [31.0, 30.0]
    ]]
}


class MockResponse:
    def __init__(self, json_data, status_code):
        self.json_data = json_data
        self.status_code = status_code

    def json(self):
        return self.json_data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("Error", request=None, response=self)

# ---------------------------------------------------------------------------
# 1. Connector Tests
# ---------------------------------------------------------------------------

class TestSentinelConnector:
    @patch("httpx.Client.post")
    def test_fetch_sentinel_visual_urls_success(self, mock_post):
        mock_post.return_value = MockResponse(_STAC_MOCK_RESPONSE, 200)
        
        result = sentinel.fetch_sentinel_visual_urls(_BBOX)
        
        assert result is not None
        assert result["date"] == "2024-01-01T12:00:00Z"
        assert result["cloud_cover_pct"] == 1.5
        assert "S2B_MSIL2A_TEST_ID" in result["true_color_url"]
        assert "S2B_MSIL2A_TEST_ID" in result["ndvi_url"]
        assert "format=png" in result["true_color_url"]
        assert "format=png" in result["ndvi_url"]

    @patch("httpx.Client.post")
    def test_fetch_sentinel_empty_features(self, mock_post):
        mock_post.return_value = MockResponse({"features": []}, 200)
        result = sentinel.fetch_sentinel_visual_urls(_BBOX)
        assert result is None

    @patch("httpx.Client.post")
    def test_fetch_sentinel_http_error(self, mock_post):
        mock_post.return_value = MockResponse({}, 500)
        result = sentinel.fetch_sentinel_visual_urls(_BBOX)
        assert result is None


# ---------------------------------------------------------------------------
# 2. Task Tests
# ---------------------------------------------------------------------------

@pytest.fixture
def test_land_for_sentinel(client, db_session):
    """Register a basic land to attach images to."""
    with patch(
        "app.pipeline.land_discovery_pipeline.open_meteo_polygon.fetch_polygon_historical_climate",
        return_value=([], None),
    ), \
         patch("app.tasks.satellite_task.modis_ndvi.fetch_ndvi_history"), \
         patch("app.tasks.soil_task.soilgrids.fetch_soil_profile"), \
         patch("app.tasks.sentinel_task.sentinel.fetch_sentinel_visual_urls"):

        resp = client.post("/api/v1/lands/discover", json={
            "name": "Sentinel Farm",
            "geometry": _POLYGON,
        })
    assert resp.status_code == 202
    return resp.json()["land_id"]


class TestSentinelTask:
    def test_task_inserts_two_images(self, test_land_for_sentinel, db_session):
        # Setup mock connector return
        mock_result = {
            "source": "ESA Sentinel-2 via Planetary Computer",
            "date": "2024-01-01T12:00:00Z",
            "cloud_cover_pct": 1.5,
            "true_color_url": "https://example.com/true_color.png",
            "ndvi_url": "https://example.com/ndvi.png"
        }
        
        with patch("app.tasks.sentinel_task.sentinel.fetch_sentinel_visual_urls", return_value=mock_result):
            success = sentinel_task.run_sentinel_visual_fetch(test_land_for_sentinel, db_session)
            
        assert success is True
        
        # Verify DB insertion
        images = db_session.execute(
            __import__("sqlalchemy").select(LandImage).where(LandImage.land_id == test_land_for_sentinel)
        ).scalars().all()
        
        assert len(images) == 2
        
        types = {img.image_type for img in images}
        assert "sentinel_true_color" in types
        assert "sentinel_ndvi" in types
        
        for img in images:
            assert float(img.cloud_cover_pct) == 1.5
            assert "https://example.com/" in img.image_path


# ---------------------------------------------------------------------------
# 3. API Test (GET /lands/{id}/images)
# ---------------------------------------------------------------------------

class TestLandsImageAPI:
    def test_get_images_returns_gallery(self, client, db_session, test_land_for_sentinel):
        # Manually seed images
        img1 = LandImage(
            land_id=test_land_for_sentinel,
            image_path="https://example.com/true_color.png",
            image_type="sentinel_true_color",
            cloud_cover_pct=1.5
        )
        img2 = LandImage(
            land_id=test_land_for_sentinel,
            image_path="https://example.com/ndvi.png",
            image_type="sentinel_ndvi",
            cloud_cover_pct=1.5
        )
        db_session.add_all([img1, img2])
        db_session.commit()
        
        resp = client.get(f"/api/v1/lands/{test_land_for_sentinel}/images")
        assert resp.status_code == 200
        
        body = resp.json()
        assert body["land_id"] == test_land_for_sentinel
        assert len(body["images"]) == 2
        
        types = {img["image_type"] for img in body["images"]}
        assert types == {"sentinel_true_color", "sentinel_ndvi"}
