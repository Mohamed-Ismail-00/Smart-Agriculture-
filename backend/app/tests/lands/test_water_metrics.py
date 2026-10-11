import pytest

from app.lands.water_metrics import derive_irrigation_status, estimate_daily_water_liters


class TestEstimateDailyWaterLiters:
    def test_fao_conversion(self):
        # 5 mm ET₀ over 10 ha → 500 m³ → 500,000 L
        assert estimate_daily_water_liters(5.0, 10.0) == pytest.approx(500_000.0)

    def test_small_field(self):
        # 8 mm over 0.5 ha → 40 m³ → 40,000 L
        assert estimate_daily_water_liters(8.0, 0.5) == pytest.approx(40_000.0)


class TestDeriveIrrigationStatus:
    def test_adequate_moisture(self):
        assert derive_irrigation_status(35.0, 5.0) == "adequate"

    def test_needed_soon_low_moisture(self):
        assert derive_irrigation_status(22.0, 5.0) == "needed_soon"

    def test_overdue_very_dry(self):
        assert derive_irrigation_status(15.0, 5.0) == "overdue"

    def test_overdue_dry_with_high_et0(self):
        assert derive_irrigation_status(22.0, 7.0) == "overdue"

    def test_excessive_wet(self):
        assert derive_irrigation_status(60.0, 3.0) == "excessive"

    def test_no_soil_high_et0(self):
        assert derive_irrigation_status(None, 9.0) == "needed_soon"

    def test_no_soil_moderate_et0(self):
        assert derive_irrigation_status(None, 5.0) == "adequate"

    def test_no_data(self):
        assert derive_irrigation_status(None, None) == "unknown"