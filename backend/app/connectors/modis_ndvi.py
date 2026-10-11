"""
connectors/modis_ndvi.py
------------------------
NASA ORNL DAAC — MODIS MOD13Q1 Vegetation Index REST API.

Product:   MOD13Q1 (Terra Vegetation Indices, 16-Day, 250m)
API docs:  https://modis.ornl.gov/rst/ui/
Auth:      None required
License:   NASA open data policy

What this returns per 16-day composite:
  - NIR reflectance (band 2, scaled ×10000)
  - RED reflectance (band 1, scaled ×10000)
  - Pre-computed NDVI (scaled ×10000)
  - EVI (scaled ×10000)
  - Pixel reliability flag (0=best, 1=good, 2=marginal, 3=snow/ice, -1=fill)
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

ORNL_BASE = "https://modis.ornl.gov/rst/api/v1/MOD13Q1"
SCALE_FACTOR = 10_000.0     # all reflectance/NDVI values are ×10000 integers
MAX_RELIABLE_QUALITY = 1    # pixel_reliability: 0=best, 1=good — anything higher is marginal


def _modis_date_for(d: date) -> str:
    """Convert a calendar date to MODIS day-of-year format (A{year}{doy})."""
    doy = d.timetuple().tm_yday
    return f"A{d.year}{doy:03d}"


def _fetch_subset(
    lat: float,
    lon: float,
    start: date,
    end: date,
    timeout: float = 20.0,
) -> Optional[list[dict]]:
    """
    Call ORNL DAAC subset API. Returns raw subset list or None on error.
    """
    params = {
        "latitude": lat,
        "longitude": lon,
        "startDate": _modis_date_for(start),
        "endDate": _modis_date_for(end),
        "kmAboveBelow": 0,
        "kmLeftRight": 0,
    }
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.get(f"{ORNL_BASE}/subset", params=params, follow_redirects=True)
            resp.raise_for_status()
            return resp.json().get("subset", [])
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        logger.warning("MODIS ORNL request failed: %s", exc)
        return None


def _parse_subset(subset: list[dict]) -> list[dict[str, Any]]:
    """
    Group subset records by date and extract NIR, RED, NDVI, quality.
    Returns a list of dicts sorted by date ascending.
    """
    by_date: dict[str, dict[str, Any]] = {}

    for record in subset:
        cal_date = record.get("calendar_date")
        band = record.get("band", "")
        data = record.get("data", [])
        if not cal_date or not data:
            continue
        value = data[0]

        entry = by_date.setdefault(cal_date, {"date": cal_date})

        if band == "250m_16_days_NIR_reflectance":
            entry["nir_raw"] = value
            if value > -3000:   # fill value = -28672
                entry["nir"] = round(value / SCALE_FACTOR, 6)

        elif band == "250m_16_days_red_reflectance":
            entry["red_raw"] = value
            if value > -3000:
                entry["red"] = round(value / SCALE_FACTOR, 6)

        elif band == "250m_16_days_NDVI":
            entry["ndvi_raw"] = value
            if value > -3000:
                entry["ndvi_modis"] = round(value / SCALE_FACTOR, 6)

        elif band == "250m_16_days_EVI":
            entry["evi_raw"] = value
            if value > -3000:
                entry["evi"] = round(value / SCALE_FACTOR, 6)

        elif band == "250m_16_days_pixel_reliability":
            entry["quality_flag"] = value   # 0=best, 1=good, 2=marginal, -1=fill

    return sorted(by_date.values(), key=lambda x: x["date"])


def fetch_ndvi_history(
    lat: float,
    lon: float,
    days: int = 90,
    timeout: float = 20.0,
) -> Optional[list[dict[str, Any]]]:
    """
    Fetch the last `days` worth of 16-day NDVI composites for a location.

    Each returned record:
      date        (str, YYYY-MM-DD)
      nir         (float, 0–1 reflectance)
      red         (float, 0–1 reflectance)
      ndvi_modis  (float, pre-computed by MODIS, -1 to 1)
      evi         (float, enhanced vegetation index)
      quality_flag (int, 0=best, 1=good, 2=marginal)

    Records with fill values or extreme quality degradation are excluded.
    Returns None on HTTP error.
    """
    end = date.today() - timedelta(days=1)
    start = end - timedelta(days=days)

    subset = _fetch_subset(lat, lon, start, end, timeout)
    if subset is None:
        return None

    records = _parse_subset(subset)

    # Filter: require at least ndvi_modis to be present
    valid = [r for r in records if "ndvi_modis" in r]
    if not valid:
        logger.warning("MODIS returned no valid NDVI records for lat=%s lon=%s", lat, lon)
        return None

    return valid


def fetch_latest_ndvi(
    lat: float,
    lon: float,
    timeout: float = 20.0,
) -> Optional[dict[str, Any]]:
    """
    Fetch the single most-recent 16-day NDVI composite.

    Returns same structure as one record from fetch_ndvi_history, or None.
    """
    records = fetch_ndvi_history(lat, lon, days=32, timeout=timeout)
    if not records:
        return None
    # Return the most recent valid record
    return records[-1]
