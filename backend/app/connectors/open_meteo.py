"""
Open-Meteo public API — current conditions, soil moisture, and ET₀ at exact coordinates.

Docs: https://open-meteo.com/en/docs
No API key required; respect fair use and rate limits in production.

Data fetched:
  - Current: temperature, humidity, precipitation
  - Daily (last 7 days): ET₀, soil moisture 0-7cm, max/min temp, rainfall sum
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

OPEN_METEO_FORECAST = "https://api.open-meteo.com/v1/forecast"
OPEN_METEO_ARCHIVE = "https://archive-api.open-meteo.com/v1/archive"

# Open-Meteo archive API has a short publication lag; 2 days is typically safe.
ARCHIVE_LAG_DAYS = 2


# ---------------------------------------------------------------------------
# Current conditions (used by discovery pipeline)
# ---------------------------------------------------------------------------

def fetch_current_land_climate(
    latitude: float,
    longitude: float,
    timeout_seconds: float = 12.0,
) -> Optional[dict[str, Any]]:
    """
    Return a dict for `land_climate` insertion:
      - temperature_celsius (float)
      - humidity_pct (float)
      - rainfall_mm (float)

    Returns None on HTTP error or missing payload.
    """
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "current": "temperature_2m,relative_humidity_2m,precipitation",
        "timezone": "UTC",
    }
    try:
        with httpx.Client(timeout=timeout_seconds) as client:
            resp = client.get(OPEN_METEO_FORECAST, params=params)
            resp.raise_for_status()
            data = resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("Open-Meteo current request failed: %s", exc)
        return None

    current = data.get("current") or {}
    temp = current.get("temperature_2m")
    humidity = current.get("relative_humidity_2m")
    precip = current.get("precipitation")

    if temp is None and humidity is None and precip is None:
        logger.warning("Open-Meteo returned no usable current fields")
        return None

    out: dict[str, Any] = {}
    if temp is not None:
        out["temperature_celsius"] = float(temp)
    if humidity is not None:
        out["humidity_pct"] = float(humidity)
    if precip is not None:
        out["rainfall_mm"] = float(precip)
    return out


# ---------------------------------------------------------------------------
# Soil moisture + ET₀ (used by discovery & monitoring pipeline)
# ---------------------------------------------------------------------------

def fetch_soil_and_et0(
    latitude: float,
    longitude: float,
    days: int = 7,
    timeout_seconds: float = 15.0,
) -> Optional[dict[str, Any]]:
    """
    Fetch the most recent soil moisture (hourly → noon reading) and
    reference evapotranspiration (daily) from Open-Meteo Historical Archive API.

    Returns the LATEST available day's values as:
      - soil_moisture_pct  (float, 0-100 mapped from 0-1 volumetric)
      - et0_mm_per_day     (float, mm/day)
      - date               (str, YYYY-MM-DD)

    Returns None on error or missing data.

    Note: soil_moisture_0_to_7cm is only available as an HOURLY variable;
          et0_fao_evapotranspiration is only available as a DAILY variable.
          We make two separate API calls and merge the results.
    """
    end_date = date.today() - timedelta(days=ARCHIVE_LAG_DAYS)
    start_date = end_date - timedelta(days=days - 1)
    start_str = start_date.isoformat()
    end_str = end_date.isoformat()

    out: dict[str, Any] = {"date": end_str}

    # ---- Call 1: daily ET₀ ----
    try:
        params_daily = {
            "latitude": latitude,
            "longitude": longitude,
            "start_date": start_str,
            "end_date": end_str,
            "daily": "et0_fao_evapotranspiration",
            "timezone": "UTC",
        }
        with httpx.Client(timeout=timeout_seconds) as client:
            resp = client.get(OPEN_METEO_ARCHIVE, params=params_daily)
            resp.raise_for_status()
            data = resp.json()

        daily = data.get("daily") or {}
        et0_values = daily.get("et0_fao_evapotranspiration") or []
        # Use the last valid ET₀ value
        for val in reversed(et0_values):
            if val is not None:
                out["et0_mm_per_day"] = float(val)
                break
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("Open-Meteo ET₀ request failed: %s", exc)

    # ---- Call 2: hourly soil moisture → take noon (12:00) reading of last day ----
    try:
        params_hourly = {
            "latitude": latitude,
            "longitude": longitude,
            "start_date": end_str,   # just yesterday
            "end_date": end_str,
            "hourly": "soil_moisture_0_to_7cm",
            "timezone": "UTC",
        }
        with httpx.Client(timeout=timeout_seconds) as client:
            resp = client.get(OPEN_METEO_ARCHIVE, params=params_hourly)
            resp.raise_for_status()
            data = resp.json()

        hourly = data.get("hourly") or {}
        soil_values = hourly.get("soil_moisture_0_to_7cm") or []
        # Index 12 = 12:00 noon reading; fallback to any non-null value
        noon_idx = 12
        if noon_idx < len(soil_values) and soil_values[noon_idx] is not None:
            out["soil_moisture_pct"] = round(float(soil_values[noon_idx]) * 100, 2)
        else:
            for val in soil_values:
                if val is not None:
                    out["soil_moisture_pct"] = round(float(val) * 100, 2)
                    break
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("Open-Meteo soil moisture request failed: %s", exc)

    if len(out) <= 1:  # only "date" key — no real data
        logger.warning("Open-Meteo archive returned no usable soil/ET₀ data for lat=%s lon=%s", latitude, longitude)
        return None

    return out


# ---------------------------------------------------------------------------
# Historical climate (last N days) — used for stress analysis in Phase 4
# ---------------------------------------------------------------------------

def fetch_historical_climate(
    latitude: float,
    longitude: float,
    days: int = 30,
    timeout_seconds: float = 15.0,
) -> Optional[list[dict[str, Any]]]:
    """
    Fetch daily climate records for the last `days` days.

    Each record:
      - date                  (str, YYYY-MM-DD)
      - temperature_max_c     (float)
      - temperature_min_c     (float)
      - rainfall_mm           (float)
      - et0_mm                (float)

    Soil moisture is fetched hourly (noon reading) in a second call and merged.
    Returns None on error.
    """
    end_date = date.today() - timedelta(days=ARCHIVE_LAG_DAYS)
    start_date = end_date - timedelta(days=days - 1)
    start_str = start_date.isoformat()
    end_str = end_date.isoformat()

    # ---- Daily call: temperatures, humidity, rainfall, ET₀ ----
    params_daily = {
        "latitude": latitude,
        "longitude": longitude,
        "start_date": start_str,
        "end_date": end_str,
        "daily": "temperature_2m_max,temperature_2m_min,relative_humidity_2m_mean,precipitation_sum,et0_fao_evapotranspiration",
        "timezone": "UTC",
    }
    try:
        with httpx.Client(timeout=timeout_seconds) as client:
            resp = client.get(OPEN_METEO_ARCHIVE, params=params_daily)
            resp.raise_for_status()
            data = resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("Open-Meteo historical request failed: %s", exc)
        return None

    daily = data.get("daily") or {}
    dates = daily.get("time") or []
    t_max = daily.get("temperature_2m_max") or []
    t_min = daily.get("temperature_2m_min") or []
    h_mean = daily.get("relative_humidity_2m_mean") or []
    rain = daily.get("precipitation_sum") or []
    et0 = daily.get("et0_fao_evapotranspiration") or []

    records = []
    for i, day in enumerate(dates):
        rec: dict[str, Any] = {"date": day}
        if i < len(t_max) and t_max[i] is not None:
            rec["temperature_max_c"] = float(t_max[i])
        if i < len(t_min) and t_min[i] is not None:
            rec["temperature_min_c"] = float(t_min[i])
        if i < len(h_mean) and h_mean[i] is not None:
            rec["humidity_pct"] = float(h_mean[i])
        if i < len(rain) and rain[i] is not None:
            rec["rainfall_mm"] = float(rain[i])
        if i < len(et0) and et0[i] is not None:
            rec["et0_mm"] = float(et0[i])
        records.append(rec)

    # ---- Hourly call: soil moisture → noon reading per day ----
    try:
        params_hourly = {
            "latitude": latitude,
            "longitude": longitude,
            "start_date": start_str,
            "end_date": end_str,
            "hourly": "soil_moisture_0_to_7cm",
            "timezone": "UTC",
        }
        with httpx.Client(timeout=timeout_seconds) as client:
            resp = client.get(OPEN_METEO_ARCHIVE, params=params_hourly)
            resp.raise_for_status()
            data = resp.json()

        hourly = data.get("hourly") or {}
        soil_values = hourly.get("soil_moisture_0_to_7cm") or []
        # Hourly data: 24 readings per day; noon = index (day_index × 24 + 12)
        for day_idx, rec in enumerate(records):
            noon_idx = day_idx * 24 + 12
            if noon_idx < len(soil_values) and soil_values[noon_idx] is not None:
                rec["soil_moisture_pct"] = round(float(soil_values[noon_idx]) * 100, 2)
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("Open-Meteo hourly soil moisture request failed: %s (continuing)", exc)

    return records if records else None
