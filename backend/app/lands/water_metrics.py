"""Derived irrigation metrics from Open-Meteo ET₀ and soil moisture."""

from typing import Optional


def estimate_daily_water_liters(et0_mm: float, area_hectares: float) -> float:
    """FAO: 1 mm over 1 ha = 10 m³ = 10,000 L of crop water need."""
    return et0_mm * area_hectares * 10_000


def derive_irrigation_status(
    soil_moisture_pct: Optional[float],
    et0_mm: Optional[float],
) -> str:
    """
    Classify irrigation need from volumetric soil moisture and reference ET₀.

    Status values align with AI analyst schema:
    adequate | needed_soon | overdue | excessive
    """
    if soil_moisture_pct is None:
        if et0_mm is not None and et0_mm >= 8:
            return "needed_soon"
        if et0_mm is not None:
            return "adequate"
        return "unknown"

    sm = float(soil_moisture_pct)
    et0 = float(et0_mm or 0)

    if sm >= 55:
        return "excessive"
    if sm < 18 or (sm < 25 and et0 >= 6):
        return "overdue"
    if sm < 28 or (sm < 35 and et0 >= 7):
        return "needed_soon"
    return "adequate"