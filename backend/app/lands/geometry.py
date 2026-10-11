"""
lands/geometry.py
-----------------
Pure Python geometry utilities for GeoJSON polygon processing.

No external dependencies — works in tests, production, and pipelines.

GeoJSON coordinate convention: [longitude, latitude] (x, y)
"""

from __future__ import annotations

import math
from typing import Optional


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

# GeoJSON ring: list of [lng, lat] pairs
Ring = list[list[float]]


# ---------------------------------------------------------------------------
# Polygon utilities
# ---------------------------------------------------------------------------

def close_ring(ring: Ring) -> Ring:
    """
    Ensure the first and last coordinate of the ring are identical.
    GeoJSON spec requires closed rings.
    """
    if not ring:
        return ring
    if ring[0] != ring[-1]:
        return ring + [ring[0]]
    return ring


def validate_polygon(ring: Ring) -> None:
    """
    Raise ValueError if the polygon ring is invalid:
    - fewer than 3 unique points
    - coordinates out of range
    """
    unique = [p for i, p in enumerate(ring) if p not in ring[:i]]
    if len(unique) < 3:
        raise ValueError(
            f"Polygon must have at least 3 unique points, got {len(unique)}"
        )
    for point in ring:
        if len(point) < 2:
            raise ValueError("Each coordinate must have at least 2 values [lng, lat]")
        lng, lat = point[0], point[1]
        if not (-180 <= lng <= 180):
            raise ValueError(f"Longitude {lng} out of range [-180, 180]")
        if not (-90 <= lat <= 90):
            raise ValueError(f"Latitude {lat} out of range [-90, 90]")


def compute_centroid(ring: Ring) -> tuple[float, float]:
    """
    Compute the centroid of a polygon ring using the Shoelace formula.

    Returns (latitude, longitude) — note the swapped order for storage
    since our DB columns are (latitude, longitude) but GeoJSON is [lng, lat].
    """
    closed = close_ring(ring)
    n = len(closed) - 1  # exclude repeated closing point

    cx = cy = area_signed = 0.0
    for i in range(n):
        x0, y0 = closed[i][0], closed[i][1]
        x1, y1 = closed[i + 1][0], closed[i + 1][1]
        cross = x0 * y1 - x1 * y0
        area_signed += cross
        cx += (x0 + x1) * cross
        cy += (y0 + y1) * cross

    if abs(area_signed) < 1e-12:
        # Degenerate polygon — fall back to simple average
        avg_lng = sum(p[0] for p in ring) / len(ring)
        avg_lat = sum(p[1] for p in ring) / len(ring)
        return round(avg_lat, 8), round(avg_lng, 8)

    factor = 1.0 / (3.0 * area_signed)
    centroid_lng = cx * factor
    centroid_lat = cy * factor
    return round(centroid_lat, 8), round(centroid_lng, 8)


def compute_area_hectares(ring: Ring) -> float:
    """
    Compute approximate area of a polygon ring in hectares.

    Uses the Shoelace formula on geographic coordinates projected to metres
    using an equirectangular approximation (accurate within ~1% for
    small fields < 100 km across).

    1 hectare = 10,000 m²
    """
    closed = close_ring(ring)
    n = len(closed) - 1

    # Compute centroid latitude for the equirectangular projection
    avg_lat = sum(p[1] for p in ring) / len(ring)
    lat_rad = math.radians(avg_lat)

    # Degrees to metres conversion at centroid latitude
    meters_per_deg_lat = 111_320.0
    meters_per_deg_lng = 111_320.0 * math.cos(lat_rad)

    # Shoelace formula in projected metres
    area_m2 = 0.0
    for i in range(n):
        x0 = closed[i][0] * meters_per_deg_lng
        y0 = closed[i][1] * meters_per_deg_lat
        x1 = closed[i + 1][0] * meters_per_deg_lng
        y1 = closed[i + 1][1] * meters_per_deg_lat
        area_m2 += x0 * y1 - x1 * y0

    area_m2 = abs(area_m2) / 2.0
    return round(area_m2 / 10_000.0, 4)  # convert m² → hectares


def circle_to_polygon(
    center_lat: float,
    center_lng: float,
    radius_km: float,
    num_points: int = 64,
) -> Ring:
    """
    Convert a circle (center + radius) to a GeoJSON polygon ring.

    Returns a closed ring of `num_points` coordinate pairs in
    [longitude, latitude] order (GeoJSON standard).

    Uses equirectangular approximation — accurate for radii < 100 km.
    """
    if radius_km <= 0:
        raise ValueError("radius_km must be positive")

    lat_rad = math.radians(center_lat)
    # Degrees per km at this latitude
    km_per_deg_lat = 111.32
    km_per_deg_lng = 111.32 * math.cos(lat_rad)

    coords: Ring = []
    for i in range(num_points):
        angle = 2 * math.pi * i / num_points
        dlat = radius_km * math.sin(angle) / km_per_deg_lat
        dlng = radius_km * math.cos(angle) / km_per_deg_lng
        coords.append([
            round(center_lng + dlng, 8),
            round(center_lat + dlat, 8),
        ])

    return close_ring(coords)


def compute_bounding_box(ring: Ring) -> list[float]:
    """
    Compute the bounding box of a polygon ring.
    
    Returns a list: [min_lon, min_lat, max_lon, max_lat]
    """
    if not ring:
        raise ValueError("Cannot compute bounding box for an empty ring")
        
    min_lon = min(p[0] for p in ring)
    max_lon = max(p[0] for p in ring)
    min_lat = min(p[1] for p in ring)
    max_lat = max(p[1] for p in ring)
    
    return [min_lon, min_lat, max_lon, max_lat]
