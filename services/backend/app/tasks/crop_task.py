import logging
import numpy as np
from datetime import datetime
from sqlalchemy.orm import Session

from app.lands import repository
from app.cv import ndvi as ndvi_engine
from app.connectors import sentinel
from app.cv import indices
from app.cv import timeseries
from app.crops.identification import (
    build_tile_labels,
    identify_zones_from_labels,
    load_crop_profiles,
    visible_zones,
)
from app.trust.provenance_service import ProvenanceService
from app.trust.tier_resolver import TrustTierResolver
from app.trust.types import DetectionMethod, TrustTier

logger = logging.getLogger(__name__)


def run_crop_detection_task(land_id: int, db: Session, days: int = 90) -> None:
    """
    Analyzes historical Sentinel-2 data at the tile level.
    Extracts time-series features per pixel, runs the ML model per pixel,
    and aggregates to detect true multi-crop fields.
    """
    logger.info("Running pixel-level crop detection task for land_id=%s", land_id)

    # 1. Fetch raw Sentinel-2 history
    land = repository.get_land(db, land_id)
    if land is None:
        return
        
    lat, lon = float(land.latitude), float(land.longitude)
    
    # Use the precise polygon bounding box instead of a tiny hardcoded square
    from app.lands.geometry import compute_bounding_box
    if land.boundary_polygon and "coordinates" in land.boundary_polygon:
        ring = land.boundary_polygon["coordinates"][0]
        bbox = compute_bounding_box(ring)
    else:
        # Fallback to compute_bbox_from_area
        from app.connectors.sentinel import compute_bbox_from_area
        bbox = compute_bbox_from_area(lat, lon, float(land.area_hectares) if land.area_hectares else 10.0)

    try:
        timeseries_data = sentinel.fetch_sentinel_timeseries(bbox=bbox, days=days)
    except Exception as exc:
        logger.exception(
            "Sentinel timeseries failed for land_id=%s — using synthetic fallback: %s",
            land_id,
            exc,
        )
        timeseries_data = {"dates": []}
    dates = timeseries_data.get("dates") or []
    
    use_synthetic = False
    if not dates or len(dates) < 3:
        logger.warning("No/insufficient Sentinel-2 records for land_id=%s — using synthetic NDVI fallback so charts appear immediately", land_id)
        use_synthetic = True
        # Generate synthetic dates and NDVI curves (last ~12 months, ~ biweekly)
        from datetime import datetime, timedelta
        import numpy as _np  # local alias to avoid shadowing
        now = datetime.utcnow()
        synth_dates = [now - timedelta(days=16*i) for i in range(23, -1, -1)]  # ~ 24 points, ~1 year
        dates = synth_dates
        T = len(dates)
        H, W = 5, 5  # small fake grid for aggregation
        # Realistic NDVI curve per "tile": rise in season, peak ~0.7-0.85 then decline
        base_ndvi = _np.linspace(0.25, 0.78, T) + _np.sin(_np.linspace(0, 3.14, T)) * 0.12
        base_ndvi = _np.clip(base_ndvi, 0.15, 0.92)
        b04 = _np.random.default_rng(42).normal(0.15, 0.03, (T, H, W))  # dummy red
        b08 = base_ndvi.reshape(T,1,1) + _np.random.default_rng(43).normal(0, 0.04, (T, H, W))  # NIR ~ NDVI proxy
        b08 = _np.clip(b08, 0.1, 0.95)
        b02 = _np.random.default_rng(44).normal(0.12, 0.02, (T, H, W))
        b03 = _np.random.default_rng(45).normal(0.18, 0.03, (T, H, W))
        b11 = _np.random.default_rng(46).normal(0.25, 0.05, (T, H, W))
        # recompute ndvi_arr etc below will use these

    if not use_synthetic:
        b02 = timeseries_data["B02"]
        b03 = timeseries_data["B03"]
        b04 = timeseries_data["B04"]
        b08 = timeseries_data["B08"]
        b11 = timeseries_data["B11"]

    T, H, W = b08.shape
    if T < 3:
        logger.warning("Still insufficient data after fallback for land_id=%s", land_id)
        return

    # 2. Compute vegetation indices
    ndvi_arr = indices.compute_ndvi(b08, b04)
    evi_arr = indices.compute_evi(b08, b04, b02)
    ndwi_arr = indices.compute_ndwi(b08, b11)
    savi_arr = indices.compute_savi(b08, b04)
    gndvi_arr = indices.compute_gndvi(b08, b03)

    # 3. Extract 10 statistical features per tile for each index
    ndvi_features = timeseries.extract_timeseries_features(ndvi_arr, dates)
    evi_features = timeseries.extract_timeseries_features(evi_arr, dates)
    ndwi_features = timeseries.extract_timeseries_features(ndwi_arr, dates)
    savi_features = timeseries.extract_timeseries_features(savi_arr, dates)
    gndvi_features = timeseries.extract_timeseries_features(gndvi_arr, dates)

    # 4. Flatten and Run ML on every single tile
    N = H * W
    X_pred = np.zeros((N, 8))
    X_pred[:, 0] = ndvi_features["max"].flatten()
    X_pred[:, 1] = ndvi_features["mean"].flatten()
    X_pred[:, 2] = ndvi_features["std"].flatten()
    X_pred[:, 3] = ndvi_features["peak_month"].flatten()
    X_pred[:, 4] = evi_features["max"].flatten()
    X_pred[:, 5] = ndwi_features["max"].flatten()
    X_pred[:, 6] = savi_features["max"].flatten()
    X_pred[:, 7] = gndvi_features["max"].flatten()

    logger.info("Identifying crops for %d tiles via ndvi_profile_match", N)

    crop_profiles = load_crop_profiles()
    pixel_crop_classes, crop_counts = build_tile_labels(ndvi_features, crop_profiles)
    if not crop_counts:
        crop_counts = {"Unknown": N}
        pixel_crop_classes[:] = "Unknown"

    pixel_crop_classes_2d = pixel_crop_classes.reshape((H, W))
    zone_candidates = identify_zones_from_labels(
        pixel_crop_classes_2d,
        crop_counts,
        ndvi_arr,
        ndvi_features,
        crop_profiles,
        dates,
    )
    zones_to_create = visible_zones(zone_candidates)

    from app.models.crop_zone import CropZone
    from app.models.land_crop import LandCrop

    db.query(CropZone).filter(CropZone.land_id == land_id).delete()
    db.query(LandCrop).filter(LandCrop.land_id == land_id).delete()
    db.flush()

    if use_synthetic:
        ds = repository.get_or_create_data_source(db, "Synthetic NDVI (fallback)")
    else:
        ds = repository.get_or_create_data_source(db, "Sentinel-2 L2A (Planetary Computer)")
    source_id = int(ds.source_id)
    source_name = ds.name
    ndvi_tier = TrustTierResolver.for_ndvi(is_synthetic=use_synthetic, has_value=True)

    inserted_history = 0

    for zone_spec in zones_to_create:
        zone_mask = pixel_crop_classes_2d == zone_spec.crop_type

        def masked_median(arr_3d):
            medians = np.zeros(T)
            for t in range(T):
                vals = arr_3d[t][zone_mask]
                vals = vals[~np.isnan(vals)]
                # NaN = the zone was fully cloud-masked on this date (no observation)
                medians[t] = float(np.nanmedian(vals)) if len(vals) > 0 else np.nan
            return medians

        zone_ndvi = masked_median(ndvi_arr)
        zone_dvi = masked_median(indices.compute_dvi(b08, b04))
        zone_evi = masked_median(evi_arr)
        zone_ndwi = masked_median(ndwi_arr)
        zone_savi = masked_median(savi_arr)
        zone_gndvi = masked_median(gndvi_arr)

        observed = ~np.isnan(zone_ndvi)
        latest_ndvi = zone_ndvi[observed][-1] if observed.any() else 0.0
        growth_stage = ndvi_engine.estimate_growth_stage(latest_ndvi, dates[-1].month)

        zone = CropZone(
            land_id=land_id,
            crop_type=zone_spec.crop_type,
            area_pct=zone_spec.area_pct,
            status="active",
            avg_confidence=zone_spec.confidence,
            latest_ndvi=float(latest_ndvi),
            latest_growth_stage=growth_stage,
            detection_method=zone_spec.detection_method,
            trust_tier=TrustTier.ESTIMATED.value,
            separation_score=zone_spec.separation_score,
            ambiguous=zone_spec.ambiguous,
            suppressed=zone_spec.suppressed,
            zone_metadata=zone_spec.zone_metadata,
        )
        db.add(zone)
        db.flush()
        zone_id = int(zone.zone_id)

        for t in range(T):
            if not observed[t]:
                continue
            dt = dates[t]
            row = repository.insert_land_crop_snapshot(
                db, land_id,
                timestamp=dt,
                ndvi_value=float(zone_ndvi[t]),
                dvi_value=float(zone_dvi[t]),
                evi_value=float(zone_evi[t]),
                ndwi_value=float(zone_ndwi[t]),
                savi_value=float(zone_savi[t]),
                gndvi_value=float(zone_gndvi[t]),
                growth_stage=ndvi_engine.estimate_growth_stage(zone_ndvi[t], dt.month),
                confidence=zone_spec.confidence,
                source_id=source_id,
                zone_id=zone_id,
                crop_type=zone_spec.crop_type,
            )
            row.trust_tier = ndvi_tier.value
            row.is_synthetic = use_synthetic
            inserted_history += 1

    ProvenanceService.record(
        db,
        land_id=land_id,
        metric="crop_type",
        trust_tier=TrustTier.ESTIMATED.value,
        confidence=zones_to_create[0].confidence if zones_to_create else None,
        source_id=source_id,
        source_name=source_name,
        spatial_scope="polygon_bbox",
        derivation={
            "method": DetectionMethod.NDVI_PROFILE_MATCH.value,
            "scene_count": T,
            "synthetic": use_synthetic,
            "zones": [
                {
                    "crop_type": z.crop_type,
                    "confidence": z.confidence,
                    "separation_score": z.separation_score,
                    "ambiguous": z.ambiguous,
                }
                for z in zone_candidates
            ],
        },
        qa_flags=["synthetic_fallback"] if use_synthetic else ["sentinel_l2a"],
    )

    backfilled = repository.backfill_image_ndvi_means(db, land_id)
    db.commit()
    logger.info(
        "Successfully updated crop intelligence: %d timeseries rows, %d image NDVI backfills for land_id=%s",
        inserted_history, backfilled, land_id,
    )
