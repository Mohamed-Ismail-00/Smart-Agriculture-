"""Tests for land Excel export (Phase 5)."""

import zipfile
from datetime import datetime, timezone
from decimal import Decimal

from app.lands import service
from app.models.data_source import DataSource
from app.models.land import Land
from app.models.land_climate import LandClimate
from app.models.land_crop import LandCrop


def _seed_land_with_rows(db_session) -> int:
    land = Land(
        name="Export Farm",
        latitude=Decimal("30.05"),
        longitude=Decimal("31.05"),
        area_hectares=Decimal("5"),
        status="active",
    )
    db_session.add(land)
    db_session.flush()

    ds = DataSource(name="Open-Meteo")
    crop_ds = DataSource(name="Sentinel-2 L2A (Planetary Computer)")
    db_session.add_all([ds, crop_ds])
    db_session.flush()

    db_session.add(
        LandClimate(
            land_id=land.land_id,
            timestamp=datetime(2026, 1, 10, tzinfo=timezone.utc),
            temperature_celsius=Decimal("32"),
            temperature_min_c=Decimal("18"),
            temperature_mean_c=Decimal("25"),
            source_id=ds.source_id,
        )
    )
    db_session.add(
        LandCrop(
            land_id=land.land_id,
            zone_id=7,
            ndvi_value=Decimal("0.55"),
            source_id=crop_ds.source_id,
            timestamp=datetime(2026, 1, 10, tzinfo=timezone.utc),
        )
    )
    db_session.commit()
    return land.land_id


def _xlsx_text(stream) -> str:
    stream.seek(0)
    parts: list[str] = []
    with zipfile.ZipFile(stream) as zf:
        for name in zf.namelist():
            if name.endswith(".xml"):
                parts.append(zf.read(name).decode("utf-8", errors="ignore"))
    return "\n".join(parts)


class TestExcelExport:
    def test_export_produces_workbook_with_source_columns(self, db_session):
        land_id = _seed_land_with_rows(db_session)
        stream = service.export_land_to_excel(db_session, land_id)
        assert stream is not None
        assert stream.getbuffer().nbytes > 0

        text = _xlsx_text(stream)
        assert "Open-Meteo" in text
        assert "Zone ID" in text
        assert "Data Source" in text
        assert "Data Provenance" in text
        assert "Peak Max Temperature" in text
        assert "Max Temp" in text

    def test_export_returns_none_for_missing_land(self, db_session):
        assert service.export_land_to_excel(db_session, 99999) is None