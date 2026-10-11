"""
app/lands/validator.py
----------------------
Validates geographic coordinates to ensure they represent active agricultural land
rather than urban zones, residential infrastructure, or barren deserts.
"""

import logging

import httpx
from fastapi import HTTPException, status

from app.connectors import modis_ndvi

logger = logging.getLogger(__name__)

# Urban and infrastructure types defined by OSM Nominatim
URBAN_CLASSES = {"building", "amenity", "shop", "office"}
URBAN_TYPES = {"residential", "commercial", "industrial", "house", "apartments", "retail"}


def _point_on_feature(lat: float, lon: float, boundingbox) -> bool:
    """
    True when the point lies inside the OSM feature's bounding box.

    Nominatim reverse returns the *nearest* feature, not the one under the point.
    Delta fields sit between scattered farmhouses and ezbas, so the nearest feature
    is routinely a house a few hundred metres away. Only a feature that actually
    covers the point says anything about the land itself.
    """
    try:
        south, north, west, east = (float(v) for v in boundingbox)
    except (TypeError, ValueError):
        return False
    return south <= lat <= north and west <= lon <= east


def validate_agricultural_land(lat: float, lon: float) -> None:
    """
    Validates that a coordinate pair likely represents farmland.
    Raises HTTPException(400) if validation fails.
    """
    logger.info("Validating agricultural suitability for lat=%s lon=%s", lat, lon)

    # ---------------------------------------------------------
    # Phase 1: Spatial Zoning Check via OpenStreetMap
    # ---------------------------------------------------------
    headers = {"User-Agent": "SmartAgriDataPlatform/1.0"}
    try:
        url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat}&lon={lon}&zoom=18&addressdetails=1"
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(url, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                osm_class = data.get("class", "").lower()
                osm_type = data.get("type", "").lower()

                # Treat "highway/residential" or "highway/unclassified" as permissible because 
                # small rural roads or irrigation paths often bisect large farms.
                is_urban = osm_class in URBAN_CLASSES or (osm_type in URBAN_TYPES and osm_class != "highway")

                if is_urban and _point_on_feature(lat, lon, data.get("boundingbox")):
                    logger.warning("Validation failed: Urban signature detected (%s/%s).", osm_class, osm_type)
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="This spot looks like a built-up area (buildings or roads), not farmland. Move the boundary onto a cultivated field."
                    )
    except httpx.RequestError as exc:
        logger.warning("Nominatim API request failed, skipping OSM validation: %s", exc)

    # ---------------------------------------------------------
    # Phase 2: Registration-time vegetation check (MODIS ORNL API; stored NDVI uses Sentinel-2)
    # ---------------------------------------------------------
    try:
        # Fetch 90 days of NDVI history (approx 6-12 records)
        records = modis_ndvi.fetch_ndvi_history(lat, lon, days=90)
        
        max_ndvi = 0.0
        if records:
            # Safely extract NDVI values, ignoring None
            ndvi_values = [
                float(r["ndvi_modis"]) for r in records 
                if r.get("ndvi_modis") is not None
            ]
            if ndvi_values:
                max_ndvi = max(ndvi_values)

        logger.info("Max historical NDVI for validation: %.3f", max_ndvi)

        # Barren ground, concrete, and cities generally peak < 0.20
        # Active or recently active farmland will exceed 0.25 at some point
        if max_ndvi < 0.25:
            logger.warning("Validation failed: Insufficient vegetation (max_ndvi=%.3f).", max_ndvi)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No crop was seen on this spot in the last 90 days, so it looks like bare or built-up land. Choose a cultivated field."
            )
            
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("MODIS validation failed (continuing securely): %s", exc)

    logger.info("Validation passed for lat=%s lon=%s", lat, lon)
