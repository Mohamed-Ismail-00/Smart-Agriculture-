"""
cv/ndvi.py
----------
Pure Python NDVI computation and agricultural intelligence.

No external dependencies — all logic is deterministic and testable.

NDVI formula: (NIR - RED) / (NIR + RED)
Range: -1.0 to 1.0
  < 0.1  → bare soil / water / urban
  0.1–0.2 → very sparse vegetation
  0.2–0.4 → sparse / stressed crops
  0.4–0.6 → moderate / developing crops
  0.6–0.8 → dense / healthy vegetation
  > 0.8  → very dense canopy
"""

from __future__ import annotations

import json
import math
import os
from datetime import date
from typing import Optional

# ---------------------------------------------------------------------------
# Load crop profiles reference once at module level
# ---------------------------------------------------------------------------
_PROFILES_PATH = os.path.join(
    os.path.dirname(__file__), "..", "data", "reference", "crop_profiles.json"
)

def _load_profiles() -> dict:
    try:
        with open(_PROFILES_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

_CROP_PROFILES: dict = _load_profiles()


# ---------------------------------------------------------------------------
# NDVI calculation
# ---------------------------------------------------------------------------

def compute_ndvi(nir: float, red: float) -> float:
    """
    Compute NDVI from raw NIR and RED reflectance values.

    Args:
        nir: Near-infrared reflectance (0–1)
        red: Red reflectance (0–1)

    Returns:
        NDVI value clipped to [-1.0, 1.0]. Returns 0.0 if bands are both zero.
    """
    denominator = nir + red
    if abs(denominator) < 1e-9:
        return 0.0
    ndvi = (nir - red) / denominator
    return max(-1.0, min(1.0, round(ndvi, 6)))


# ---------------------------------------------------------------------------
# Health classification
# ---------------------------------------------------------------------------

# FAO-aligned NDVI thresholds for agricultural land
_HEALTH_THRESHOLDS = [
    (0.10, "bare_soil"),
    (0.20, "very_sparse"),
    (0.35, "stressed"),
    (0.50, "developing"),
    (0.65, "healthy"),
    (0.80, "very_healthy"),
    (1.01, "dense_canopy"),
]


def classify_health(ndvi: float) -> str:
    """
    Map NDVI value to a human-readable health classification.

    Returns one of:
      bare_soil | very_sparse | stressed | developing | healthy | very_healthy | dense_canopy
    """
    for threshold, label in _HEALTH_THRESHOLDS:
        if ndvi < threshold:
            return label
    return "dense_canopy"


def health_score(ndvi: float, crop_type: Optional[str] = None, growth_stage: Optional[str] = None) -> int:
    """Convert NDVI to a 0–100 score for dashboard display."""
    # Fallow or harvested land shouldn't be penalized as 'poor health'.
    if growth_stage in ("harvested", "harvest_ready", "fallow/bare soil", "bare_soil") or crop_type == "fallow/bare soil":
        if ndvi < 0.25:
            return 80  # Good health for intentionally bare land
            
    # Clamp to [0, 1] range for scoring (negative NDVI = water/bare, score 0)
    normalized = max(0.0, min(1.0, ndvi))
    score = round(normalized * 120)
    
    if crop_type and crop_type.lower() in _CROP_PROFILES:
        profile = _CROP_PROFILES[crop_type.lower()]
        peak = profile.get("ndvi_peak", 0.7)
        if ndvi >= peak * 0.85:
            score = max(score, 85)
            
    return max(0, min(100, score))


# ---------------------------------------------------------------------------
# Growth stage estimation
# ---------------------------------------------------------------------------

# Fallback growth stage thresholds when crop type is unknown
_GENERIC_GROWTH_STAGES = [
    (0.15, "planting"),
    (0.35, "early_vegetative"),
    (0.55, "vegetative"),
    (0.70, "flowering"),
    (0.65, "grain_fill"),       # NDVI slightly drops during grain fill
    (0.45, "maturity"),
    (0.25, "harvest_ready"),
]


def estimate_growth_stage(
    ndvi: float,
    month: int,
    crop_type: Optional[str] = None,
    ndvi_series: Optional[list[float]] = None,
) -> str:
    """
    Estimate the growth stage from NDVI value, month, and optional time-series.

    Strategy:
    1. If we have a time-series, find peak NDVI to anchor the stages
    2. Use crop-specific NDVI thresholds from crop_profiles.json if available
    3. Fall back to generic thresholds

    Returns one of:
      planting | early_vegetative | vegetative | flowering | grain_fill | maturity | harvest_ready
    """
    # Get crop profile NDVI peak if available
    if crop_type and crop_type.lower() in _CROP_PROFILES:
        profile = _CROP_PROFILES[crop_type.lower()]
        ndvi_peak = profile.get("ndvi_peak", 0.7)
    else:
        ndvi_peak = 0.7

    # If we have a series, use relative position (before/after peak)
    if ndvi_series and len(ndvi_series) >= 3:
        peak_idx = ndvi_series.index(max(ndvi_series))
        current_idx = len(ndvi_series) - 1
        peak_ndvi = ndvi_series[peak_idx]

        if current_idx < peak_idx * 0.3:
            return "planting"
        elif current_idx < peak_idx * 0.6:
            return "early_vegetative"
        elif current_idx < peak_idx:
            return "vegetative"
        elif ndvi >= peak_ndvi * 0.95:
            return "flowering"
        elif ndvi >= peak_ndvi * 0.80:
            return "grain_fill"
        elif ndvi >= peak_ndvi * 0.55:
            return "maturity"
        else:
            return "harvest_ready"

    # Simple NDVI threshold fallback
    if ndvi < 0.15:
        return "planting"
    elif ndvi < 0.35:
        return "early_vegetative"
    elif ndvi < 0.55:
        return "vegetative"
    elif ndvi < ndvi_peak * 0.95:
        return "flowering"
    elif ndvi < ndvi_peak * 0.75:
        return "grain_fill"
    elif ndvi < ndvi_peak * 0.50:
        return "maturity"
    else:
        return "harvest_ready"


# ---------------------------------------------------------------------------
# Trend analysis
# ---------------------------------------------------------------------------

def compute_trend(ndvi_series: list[float]) -> str:
    """
    Compute NDVI trend from a time-series using simple linear regression.

    Returns:
      improving        → slope > +0.005 per step
      stable           → slope between -0.005 and +0.005
      declining        → slope < -0.005 per step
      insufficient_data → fewer than 3 points
    """
    if len(ndvi_series) < 3:
        return "insufficient_data"

    n = len(ndvi_series)
    x_mean = (n - 1) / 2.0
    y_mean = sum(ndvi_series) / n

    numerator = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(ndvi_series))
    denominator = sum((i - x_mean) ** 2 for i in range(n))

    if abs(denominator) < 1e-9:
        return "stable"

    slope = numerator / denominator

    if slope > 0.005:
        return "improving"
    elif slope < -0.005:
        return "declining"
    else:
        return "stable"


def compute_trend_slope(ndvi_series: list[float]) -> float:
    """Return the linear regression slope (NDVI units per 16-day period)."""
    if len(ndvi_series) < 2:
        return 0.0
    n = len(ndvi_series)
    x_mean = (n - 1) / 2.0
    y_mean = sum(ndvi_series) / n
    num = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(ndvi_series))
    den = sum((i - x_mean) ** 2 for i in range(n))
    return round(num / den, 6) if abs(den) > 1e-9 else 0.0


# ---------------------------------------------------------------------------
# Confidence scoring
# ---------------------------------------------------------------------------

def compute_confidence(quality_flags: list[int]) -> float:
    """
    Convert MODIS pixel_reliability flags to a 0–1 confidence score.

    MODIS flags:
      0 = best quality      → weight 1.0
      1 = good quality      → weight 0.8
      2 = marginal quality  → weight 0.4
      3 = snow/ice          → weight 0.1
      -1 = fill value       → weight 0.0

    Returns the average weighted score for all valid flags.
    """
    weights = {0: 1.0, 1: 0.8, 2: 0.4, 3: 0.1, -1: 0.0}
    if not quality_flags:
        return 0.5   # unknown
    scores = [weights.get(f, 0.0) for f in quality_flags]
    return round(sum(scores) / len(scores), 4)


# ---------------------------------------------------------------------------
# Anomaly detection
# ---------------------------------------------------------------------------

def detect_anomaly(
    ndvi_series: list[float],
    drop_threshold: float = 0.15,
) -> bool:
    """
    Return True if the latest NDVI value drops more than `drop_threshold`
    below the mean of previous readings.

    Requires at least 3 values (1 current + 2 historical).
    """
    if len(ndvi_series) < 3:
        return False
    history_mean = sum(ndvi_series[:-1]) / len(ndvi_series[:-1])
    current = ndvi_series[-1]
    return (history_mean - current) > drop_threshold


# ---------------------------------------------------------------------------
# Harvest prediction
# ---------------------------------------------------------------------------

def predict_harvest_window(
    ndvi_series: list[float],
    dates: list[str],
    crop_type: Optional[str] = None,
) -> Optional[dict]:
    """
    Estimate harvest window based on NDVI peak detection.

    Approach:
    - Find peak NDVI date (flowering/pollination)
    - Use crop calendar from crop_profiles.json to estimate days to maturity
    - Return estimated harvest start/end dates

    Returns None if insufficient data.
    """
    if len(ndvi_series) < 3 or len(dates) != len(ndvi_series):
        return None

    # Prefer peak within the trailing observation window (handles ongoing seasons)
    try:
        from datetime import datetime as _dt
        latest_date = _dt.strptime(dates[-1], "%Y-%m-%d").date()
        cutoff = latest_date - __import__("datetime").timedelta(days=120)
        window_indices = [
            i for i, d in enumerate(dates)
            if _dt.strptime(d, "%Y-%m-%d").date() >= cutoff
        ]
    except (ValueError, IndexError):
        window_indices = list(range(len(ndvi_series)))

    if not window_indices:
        window_indices = list(range(len(ndvi_series)))

    peak_idx = max(window_indices, key=lambda i: ndvi_series[i])
    peak_date_str = dates[peak_idx]
    peak_ndvi = ndvi_series[peak_idx]

    # Days from peak to harvest from crop profiles
    days_to_maturity = 45   # default fallback
    if crop_type and crop_type.lower() in _CROP_PROFILES:
        profile = _CROP_PROFILES[crop_type.lower()]
        # grain_fill + maturity duration as proxy
        grain_days = profile.get("growth_stages", {}).get("grain_fill", 30)
        maturity_days = profile.get("growth_stages", {}).get("maturity", 15)
        days_to_maturity = grain_days + maturity_days

    try:
        from datetime import datetime
        peak_date = datetime.strptime(peak_date_str, "%Y-%m-%d").date()
        harvest_start = peak_date + __import__("datetime").timedelta(days=days_to_maturity)
        harvest_end = harvest_start + __import__("datetime").timedelta(days=14)
        return {
            "peak_ndvi": round(peak_ndvi, 4),
            "peak_date": peak_date_str,
            "estimated_harvest_start": harvest_start.isoformat(),
            "estimated_harvest_end": harvest_end.isoformat(),
            "days_to_harvest": (harvest_start - date.today()).days,
            "confidence": "medium" if len(ndvi_series) >= 5 else "low",
        }
    except (ValueError, AttributeError):
        return None
