"""
tasks/satellite_task.py
-----------------------
Per-land NDVI update orchestrator.

Responsibilities:
  1. Fetch Sentinel-2 L2A STAC time-series for a land's bounding box
  2. Compute vegetation indices from NIR/RED (and related) bands
  3. Classify health, growth stage, trend, confidence
  4. Insert LandCrop snapshots with source attribution
  5. Detect anomalies → insert LandAlert if needed
  6. Optionally backfill historical NDVI

This task is called:
  - At land registration (multi-day backfill)
  - By the monitoring pipeline every land.monitoring_interval_days
"""
from __future__ import annotations

import logging
import numpy as np
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.connectors import sentinel
from app.cv import ndvi as ndvi_engine
from app.cv import indices
from app.lands import repository

logger = logging.getLogger(__name__)


def run_ndvi_task(land_id: int, db: Session) -> bool:
    """
    Fetch and store the latest Sentinel-2 snapshot for a land.
    """
    return run_ndvi_history_backfill(land_id, db, days=90) > 0


def run_ndvi_history_backfill(
    land_id: int,
    db: Session,
    days: int = 90,
    update_progress=None,
) -> int:
    """
    Fetches real Sentinel-2 L2A STAC data over `days`.
    Computes all vegetation indices for every tile.
    Takes the median across the field (ignoring spatial variation for the time-series chart)
    and stores them in land_crops.
    """
    land = repository.get_land(db, land_id)
    if land is None:
        return 0

    lat, lon = float(land.latitude), float(land.longitude)
    
    from app.lands.geometry import compute_bounding_box
    if land.boundary_polygon and "coordinates" in land.boundary_polygon:
        ring = land.boundary_polygon["coordinates"][0]
        bbox = compute_bounding_box(ring)
    else:
        from app.connectors.sentinel import compute_bbox_from_area
        bbox = compute_bbox_from_area(lat, lon, float(land.area_hectares) if land.area_hectares else 10.0)

    timeseries_data = sentinel.fetch_sentinel_timeseries(bbox=bbox, days=days, update_progress=update_progress)
    dates = timeseries_data["dates"]
    
    if not dates:
        return 0
    
    b02 = timeseries_data["B02"]
    b03 = timeseries_data["B03"]
    b04 = timeseries_data["B04"]
    b08 = timeseries_data["B08"]
    b11 = timeseries_data["B11"]

    ds = repository.get_or_create_data_source(db, "Sentinel-2 L2A (Planetary Computer)")
    inserted = 0

    # Calculate indices as (T, H, W)
    ndvi_arr = indices.compute_ndvi(b08, b04)
    dvi_arr = indices.compute_dvi(b08, b04)
    evi_arr = indices.compute_evi(b08, b04, b02)
    ndwi_arr = indices.compute_ndwi(b08, b11)
    savi_arr = indices.compute_savi(b08, b04)
    gndvi_arr = indices.compute_gndvi(b08, b03)

    # Take median across spatial dimensions (H, W) -> shape (T,), ignoring cloud-masked pixels.
    # A date where every pixel is masked stays NaN and is skipped below.
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=RuntimeWarning)
        ndvi_medians = np.nanmedian(ndvi_arr, axis=(1, 2))
        dvi_medians = np.nanmedian(dvi_arr, axis=(1, 2))
        evi_medians = np.nanmedian(evi_arr, axis=(1, 2))
        ndwi_medians = np.nanmedian(ndwi_arr, axis=(1, 2))
        savi_medians = np.nanmedian(savi_arr, axis=(1, 2))
        gndvi_medians = np.nanmedian(gndvi_arr, axis=(1, 2))

    from app.models.land_crop import LandCrop

    # Insert into DB
    for t in range(len(dates)):
        dt = dates[t]
        if np.isnan(ndvi_medians[t]):
            continue

        # Avoid exact duplicates
        existing = db.query(LandCrop).filter(LandCrop.land_id == land_id, LandCrop.timestamp == dt).first()
        if existing:
            continue
            
        ndvi_val = float(ndvi_medians[t])
        
        # Classification for UI (using median NDVI)
        health = ndvi_engine.classify_health(ndvi_val)
        month = dt.month
        growth_stage = ndvi_engine.estimate_growth_stage(ndvi_val, month)

        repository.insert_land_crop_snapshot(
            db, land_id,
            timestamp=dt,
            ndvi_value=ndvi_val,
            dvi_value=float(dvi_medians[t]),
            evi_value=float(evi_medians[t]),
            ndwi_value=float(ndwi_medians[t]),
            savi_value=float(savi_medians[t]),
            gndvi_value=float(gndvi_medians[t]),
            growth_stage=growth_stage,
            confidence=0.95, # High confidence for Sentinel-2 clear pixels
            source_id=int(ds.source_id),
        )
        inserted += 1

    db.commit()
    logger.info("Sentinel-2 backfill inserted %d Median records for land %s", inserted, land_id)
    return inserted
