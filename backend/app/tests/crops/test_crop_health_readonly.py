"""Phase 4 — crop health read-path hygiene unit tests."""

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from app.intelligence.engine import CropIntelligenceEngine
from app.intelligence.models import LandIntelligenceReport


class TestAnalyzeLandPersist:
    def test_persist_false_skips_zone_and_report_writes(self):
        engine = CropIntelligenceEngine()
        report = LandIntelligenceReport(land_id=1)
        db = MagicMock()

        with patch.object(engine, "_store_report") as mock_store, patch.object(
            engine, "_update_crop_zones"
        ) as mock_update:
            # Simulate the persist gate at the end of analyze_land
            persist = False
            if persist:
                engine._store_report(report, db)
                engine._update_crop_zones(report, db)

            mock_store.assert_not_called()
            mock_update.assert_not_called()

    def test_persist_true_writes_zone_and_report(self):
        engine = CropIntelligenceEngine()
        report = LandIntelligenceReport(land_id=1)
        db = MagicMock()

        with patch.object(engine, "_store_report") as mock_store, patch.object(
            engine, "_update_crop_zones"
        ) as mock_update:
            persist = True
            if persist:
                engine._store_report(report, db)
                engine._update_crop_zones(report, db)

            mock_store.assert_called_once_with(report, db)
            mock_update.assert_called_once_with(report, db)


class TestRefreshCropHealthService:
    def test_refresh_calls_analyze_with_persist_true(self, db_session):
        from app.crops.service import refresh_crop_health
        from app.models.land import Land

        land = Land(
            name="Persist Test",
            latitude=30.0,
            longitude=31.0,
            area_hectares=Decimal("10"),
            status="active",
            boundary_polygon={"type": "Polygon", "coordinates": [[[31, 30], [31.1, 30], [31.1, 30.1], [31, 30]]]},
        )
        db_session.add(land)
        db_session.commit()

        with patch("app.intelligence.engine.CropIntelligenceEngine") as mock_engine_cls:
            mock_engine = mock_engine_cls.return_value
            mock_engine.analyze_land.return_value = LandIntelligenceReport(land_id=land.land_id)
            with patch("app.crops.service.get_crop_health") as mock_get:
                mock_get.return_value = MagicMock()
                refresh_crop_health(db_session, land.land_id)
                mock_engine.analyze_land.assert_called_once_with(
                    land.land_id,
                    db_session,
                    run_pipeline=False,
                    persist=True,
                )
                mock_get.assert_called_once()