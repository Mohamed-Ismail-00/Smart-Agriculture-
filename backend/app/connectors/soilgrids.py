"""
connectors/soilgrids.py
-----------------------
ISRIC SoilGrids v2.0 REST API connector.

API docs:  https://rest.isric.org/soilgrids/v2.0/docs
Auth:      None required
License:   CC BY 4.0

Properties fetched (all at 3 topsoil depths: 0-5cm, 5-15cm, 15-30cm):
  phh2o   → pH (H₂O),  mapped pH×10  → divide by 10 → actual pH
  soc     → Soil Organic Carbon (dg/kg) → divide by 10 → g/kg
  clay    → Clay content (g/kg)  → divide by 10 → %
  sand    → Sand content (g/kg)  → divide by 10 → %
  silt    → Silt content (g/kg)  → divide by 10 → %
  bdod    → Bulk Density (cg/cm³) → divide by 100 → kg/dm³
  nitrogen→ Total N (cg/kg) → divide by 100 → g/kg
  cec     → Cation Exchange Capacity (mmol(c)/kg) → divide by 10 → cmol(c)/kg

Scale factors (d_factor) are read from the API response itself.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

ISRIC_BASE = "https://rest.isric.org/soilgrids/v2.0/properties/query"

PROPERTIES = ["phh2o", "soc", "clay", "sand", "silt", "bdod", "nitrogen", "cec"]
DEPTHS = ["0-5cm", "5-15cm", "15-30cm"]

RETRY_BACKOFF_SECONDS = (5, 15, 45)
MAX_ATTEMPTS = 3
DEFAULT_TIMEOUT = 45.0


@dataclass
class SoilFetchResult:
    profile: Optional[dict[str, Any]]
    status: str
    attempts: int
    last_error: Optional[str] = None


def fetch_soil_profile(
    lat: float,
    lon: float,
    timeout: float = DEFAULT_TIMEOUT,
    *,
    max_attempts: int = MAX_ATTEMPTS,
) -> SoilFetchResult:
    """
    Fetch ISRIC SoilGrids soil property profile with retries.

    Returns SoilFetchResult with status: success | timeout | error | empty.
    """
    last_error: Optional[str] = None
    attempts = 0

    for attempt in range(max_attempts):
        attempts = attempt + 1
        try:
            profile = _fetch_once(lat, lon, timeout=timeout)
            if profile is None:
                last_error = "SoilGrids returned no usable data"
                status = "empty"
            else:
                return SoilFetchResult(
                    profile=profile,
                    status="success",
                    attempts=attempts,
                )
        except httpx.TimeoutException as exc:
            last_error = str(exc)
            status = "timeout"
            logger.warning(
                "SoilGrids timeout attempt=%s/%s lat=%s lon=%s",
                attempts,
                max_attempts,
                lat,
                lon,
            )
        except (httpx.HTTPError, ValueError) as exc:
            last_error = str(exc)
            status = "error"
            logger.warning(
                "SoilGrids request failed attempt=%s/%s: %s",
                attempts,
                max_attempts,
                exc,
            )

        if attempt < max_attempts - 1:
            delay = RETRY_BACKOFF_SECONDS[min(attempt, len(RETRY_BACKOFF_SECONDS) - 1)]
            time.sleep(delay)

    return SoilFetchResult(
        profile=None,
        status=status,
        attempts=attempts,
        last_error=last_error,
    )


def _fetch_once(
    lat: float,
    lon: float,
    timeout: float,
) -> Optional[dict[str, Any]]:
    result: dict[str, dict[str, Optional[float]]] = {}
    any_value = False

    # Chunk properties to avoid SoilGrids API timeouts (chunk by 1 for maximum safety)
    chunk_size = 1
    with httpx.Client(timeout=timeout) as client:
        for i in range(0, len(PROPERTIES), chunk_size):
            chunk_props = PROPERTIES[i:i + chunk_size]
            params: list[tuple[str, str]] = []
            params.append(("lon", str(lon)))
            params.append(("lat", str(lat)))
            for prop in chunk_props:
                params.append(("property", prop))
            for depth in DEPTHS:
                params.append(("depth", depth))
            params.append(("value", "mean"))

            # Retry per chunk to avoid restarting the whole process
            chunk_success = False
            for attempt in range(3):
                try:
                    resp = client.get(ISRIC_BASE, params=params, follow_redirects=True)
                    resp.raise_for_status()
                    data = resp.json()
                    
                    layers = data.get("properties", {}).get("layers", [])
                    if layers:
                        for layer in layers:
                            name = layer.get("name")
                            d_factor = layer.get("unit_measure", {}).get("d_factor", 1) or 1
                            if not name:
                                continue
                            depth_vals: dict[str, Optional[float]] = {}
                            for depth_entry in layer.get("depths", []):
                                label = depth_entry.get("label")
                                raw = depth_entry.get("values", {}).get("mean")
                                if label is None:
                                    continue
                                if raw is not None:
                                    depth_vals[label] = round(raw / d_factor, 4)
                                    any_value = True
                                else:
                                    depth_vals[label] = None
                            result[name] = depth_vals
                    chunk_success = True
                    break
                except httpx.TimeoutException:
                    if attempt == 2:
                        logger.warning("SoilGrids chunk timeout after 3 attempts for lat=%s lon=%s chunk=%s", lat, lon, chunk_props)
                        raise
                    time.sleep(2)
                except httpx.HTTPError:
                    if attempt == 2:
                        raise
                    time.sleep(2)

    if not any_value:
        logger.warning("SoilGrids all-null response for lat=%s lon=%s", lat, lon)
        return None

    texture = _texture_class(
        clay_pct=_top_value(result, "clay"),
        sand_pct=_top_value(result, "sand"),
    )

    return {
        "lat": lat,
        "lon": lon,
        "properties": result,
        "texture_class": texture,
        "source": "ISRIC-SoilGrids-v2",
    }


def _top_value(props: dict, name: str) -> Optional[float]:
    """Return the 0-5cm (topsoil) value for a property."""
    return props.get(name, {}).get("0-5cm")


def _texture_class(clay_pct: Optional[float], sand_pct: Optional[float]) -> str:
    """
    USDA soil texture triangle simplified to 6 classes.
    Thresholds are approximate and cover the major agricultural classes.
    """
    if clay_pct is None or sand_pct is None:
        return "unknown"
    silt_pct = max(0.0, 100.0 - clay_pct - sand_pct)

    if clay_pct >= 40:
        return "clay"
    elif clay_pct >= 27 and sand_pct < 45:
        return "clay_loam"
    elif clay_pct >= 20 and silt_pct >= 28:
        return "silty_clay_loam"
    elif sand_pct >= 70 and clay_pct < 15:
        return "sandy_loam"
    elif silt_pct >= 50:
        return "silt_loam"
    else:
        return "loam"