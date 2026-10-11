"""Discovery pipeline should keep lands when optional steps fail."""

from decimal import Decimal
from unittest.mock import patch

import pytest

from app.lands import repository
from app.models.land import Land
from app.pipeline.land_discovery_pipeline import execute
from app.tests.conftest import POLYGON_CLIMATE_MOCK_META, POLYGON_CLIMATE_MOCK_RECORDS


def _seed_land(db_session) -> int:
    land = Land(
        name="Resilience Farm",
        latitude=Decimal("30.05"),
        longitude=Decimal("31.05"),
        area_hectares=Decimal("12"),
        status="processing",
        boundary_polygon={
            "type": "Polygon",
            "coordinates": [[[31.0, 30.0], [31.1, 30.0], [31.1, 30.1], [31.0, 30.1], [31.0, 30.0]]],
        },
    )
    db_session.add(land)
    db_session.commit()
    db_session.refresh(land)
    return int(land.land_id)


class TestDiscoveryResilience:
    def test_keeps_land_when_optional_steps_fail(self, db_session):
        land_id = _seed_land(db_session)

        with patch(
            "app.pipeline.land_discovery_pipeline.open_meteo_polygon.fetch_polygon_historical_climate",
            return_value=(POLYGON_CLIMATE_MOCK_RECORDS, POLYGON_CLIMATE_MOCK_META),
        ), patch(
            "app.tasks.sentinel_task.run_sentinel_visual_fetch",
            side_effect=RuntimeError("sentinel down"),
        ), patch("app.tasks.soil_task.run_soil_profile_task", return_value=False), \
             patch("app.tasks.crop_task.run_crop_detection_task"), \
             patch("app.ai.land_analyst.run_ai_land_analysis", side_effect=RuntimeError("no groq key")):
            execute(land_id, db_session)

        land = repository.get_land(db_session, land_id)
        assert land is not None
        assert land.status == "active_partial"
        warnings = (land.metadata_ or {}).get("pipeline_warnings") or []
        assert "satellite_imagery" in warnings
        assert "ai_analysis" in warnings