"""
Polygon-aware Open-Meteo sampling.

Samples centroid + bounding-box corners (5 points) and aggregates daily
climate/soil/ET₀ values as polygon means for trust-aligned environment data.
"""

from __future__ import annotations

import logging
import statistics
from datetime import datetime, timezone
from typing import Any, Optional

from app.connectors import open_meteo
from app.lands.geometry import compute_bounding_box, compute_centroid

logger = logging.getLogger(__name__)

TEMP_SPREAD_ESTIMATED_THRESHOLD_C = 3.0
LARGE_FIELD_HECTARES = 50.0


def extract_ring(boundary_polygon: Optional[dict]) -> Optional[list[list[float]]]:
    """Return the outer GeoJSON ring or None."""
    if not boundary_polygon or "coordinates" not in boundary_polygon:
        return None
    coords = boundary_polygon.get("coordinates") or []
    if not coords or not coords[0]:
        return None
    return coords[0]


def sample_points_from_ring(ring: list[list[float]]) -> list[dict[str, Any]]:
    """
    Build 5 sample locations: centroid + bbox corners.

    Returns list of {label, latitude, longitude}.
    """
    min_lon, min_lat, max_lon, max_lat = compute_bounding_box(ring)
    centroid_lat, centroid_lng = compute_centroid(ring)

    return [
        {"label": "centroid", "latitude": centroid_lat, "longitude": centroid_lng},
        {"label": "sw", "latitude": min_lat, "longitude": min_lon},
        {"label": "se", "latitude": min_lat, "longitude": max_lon},
        {"label": "ne", "latitude": max_lat, "longitude": max_lon},
        {"label": "nw", "latitude": max_lat, "longitude": min_lon},
    ]


def sample_points_for_land(
    *,
    boundary_polygon: Optional[dict],
    latitude: float,
    longitude: float,
) -> tuple[list[dict[str, Any]], str]:
    """Return sample points and spatial_scope (polygon_mean | centroid)."""
    ring = extract_ring(boundary_polygon)
    if ring and len(ring) >= 3:
        return sample_points_from_ring(ring), "polygon_mean"
    return [
        {"label": "centroid", "latitude": latitude, "longitude": longitude},
    ], "centroid"


def _mean_of(values: list[float]) -> Optional[float]:
    return round(statistics.mean(values), 4) if values else None


def aggregate_daily_records(
    per_point_records: list[list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    """Merge per-point daily rows into polygon-mean daily rows."""
    if not per_point_records:
        return []

    by_date: dict[str, dict[str, list[float]]] = {}
    numeric_keys = (
        "temperature_max_c",
        "temperature_min_c",
        "humidity_pct",
        "rainfall_mm",
        "et0_mm",
        "soil_moisture_pct",
    )

    for records in per_point_records:
        if not records:
            continue
        for rec in records:
            day = rec.get("date")
            if not day:
                continue
            bucket = by_date.setdefault(day, {k: [] for k in numeric_keys})
            for key in numeric_keys:
                val = rec.get(key)
                if val is not None:
                    bucket[key].append(float(val))

    aggregated: list[dict[str, Any]] = []
    for day in sorted(by_date.keys()):
        bucket = by_date[day]
        row: dict[str, Any] = {"date": day}
        for key in numeric_keys:
            mean_val = _mean_of(bucket[key])
            if mean_val is not None:
                row[key] = mean_val
        aggregated.append(row)
    return aggregated


def compute_temp_spread_c(per_point_records: list[list[dict[str, Any]]]) -> float:
    """
    Max daily spread of mean temperature across sample points (°C).
    """
    if len(per_point_records) < 2:
        return 0.0

    by_date: dict[str, list[float]] = {}
    for records in per_point_records:
        for rec in records or []:
            day = rec.get("date")
            t_max = rec.get("temperature_max_c")
            t_min = rec.get("temperature_min_c")
            if day is None or t_max is None or t_min is None:
                continue
            mean_t = (float(t_max) + float(t_min)) / 2.0
            by_date.setdefault(day, []).append(mean_t)

    if not by_date:
        return 0.0

    return round(max(max(vals) - min(vals) for vals in by_date.values() if len(vals) > 1), 2)


def build_spatial_metadata(
    *,
    points: list[dict[str, Any]],
    spatial_scope: str,
    temp_spread_c: float,
    area_hectares: Optional[float] = None,
) -> dict[str, Any]:
    """Metadata persisted on land.metadata_.climate_sampling."""
    from app.trust.tier_resolver import TrustTierResolver

    tier = TrustTierResolver.for_climate_aggregate(
        has_rows=True,
        temp_spread_c=temp_spread_c,
    )
    high_spread = temp_spread_c > TEMP_SPREAD_ESTIMATED_THRESHOLD_C
    large_field = area_hectares is not None and float(area_hectares) > LARGE_FIELD_HECTARES

    return {
        "spatial_scope": spatial_scope,
        "sample_count": len(points),
        "temp_spread_c": temp_spread_c,
        "high_spread": high_spread,
        "large_field_warning": large_field and high_spread,
        "aggregate_trust_tier": tier.value,
        "points": [
            {
                "label": p["label"],
                "latitude": p["latitude"],
                "longitude": p["longitude"],
            }
            for p in points
        ],
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


def fetch_polygon_historical_climate(
    *,
    boundary_polygon: Optional[dict],
    latitude: float,
    longitude: float,
    days: int = 30,
    area_hectares: Optional[float] = None,
) -> tuple[Optional[list[dict[str, Any]]], Optional[dict[str, Any]]]:
    """
    Fetch and aggregate historical climate for a land polygon.

    Returns (aggregated_records, spatial_metadata).
    """
    points, spatial_scope = sample_points_for_land(
        boundary_polygon=boundary_polygon,
        latitude=latitude,
        longitude=longitude,
    )

    per_point_records: list[list[dict[str, Any]]] = []
    for pt in points:
        records = open_meteo.fetch_historical_climate(
            pt["latitude"],
            pt["longitude"],
            days=days,
        )
        if records:
            per_point_records.append(records)
        else:
            logger.warning(
                "Open-Meteo polygon sample returned no data label=%s lat=%s lon=%s",
                pt["label"],
                pt["latitude"],
                pt["longitude"],
            )

    if not per_point_records:
        return None, None

    aggregated = aggregate_daily_records(per_point_records)
    if not aggregated:
        return None, None

    temp_spread = compute_temp_spread_c(per_point_records)
    spatial_meta = build_spatial_metadata(
        points=points,
        spatial_scope=spatial_scope,
        temp_spread_c=temp_spread,
        area_hectares=area_hectares,
    )
    return aggregated, spatial_meta