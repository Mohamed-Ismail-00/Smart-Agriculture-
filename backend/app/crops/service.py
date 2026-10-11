"""crops/service.py — Crop intelligence business logic (5 endpoints)."""

from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from app.cv import ndvi as ndvi_engine
from app.crops.schemas import (
    CropDetectionResponse,
    CropHealthResponse,
    CropStatusResponse,
    CropTrendResponse,
    HarvestPredictionResponse,
    NDVIPoint,
)
from app.lands import repository


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_zone_id(db: Session, land_id: int, zone_id: Optional[int] = None) -> Optional[int]:
    if zone_id is not None:
        return zone_id
    primary = repository.get_primary_crop_zone(db, land_id)
    return int(primary.zone_id) if primary is not None else None


def _get_crop_rows(db: Session, land_id: int, zone_id: Optional[int] = None):
    """Return crop rows for a land (primary zone by default), ascending by timestamp."""
    effective_zone = _resolve_zone_id(db, land_id, zone_id)
    if effective_zone is not None:
        return list(repository.list_land_crop_rows(db, land_id, zone_id=effective_zone))
    return list(repository.list_land_crop_rows(db, land_id))


def _latest_crop(db: Session, land_id: int):
    return repository.get_latest_crop_record(db, land_id)


# ---------------------------------------------------------------------------
# 1. Crop Detection
# ---------------------------------------------------------------------------

def _crop_rows_use_synthetic(db: Session, land_id: int) -> bool:
    from app.models.data_source import DataSource
    from app.models.land_crop import LandCrop

    row = (
        db.query(LandCrop, DataSource)
        .outerjoin(DataSource, LandCrop.source_id == DataSource.source_id)
        .filter(LandCrop.land_id == land_id)
        .order_by(LandCrop.timestamp.desc())
        .first()
    )
    if not row:
        return False
    _, source = row
    return bool(source and "synthetic" in (source.name or "").lower())


def _spectral_signals_from_zone(zone) -> "SpectralSignals":
    from app.crops.schemas import SpectralSignals

    meta = zone.zone_metadata or {}
    return SpectralSignals(
        profile_fit=float(meta.get("profile_fit", 0.0)),
        season_match=float(meta.get("season_match", 0.0)),
        spatial_coherence=float(meta.get("spatial_coherence", 0.0)),
        field_agreement=float(meta.get("field_agreement", 0.0)),
        separation=float(zone.separation_score) if zone.separation_score is not None else None,
        profile_margin=float(meta["profile_margin"]) if meta.get("profile_margin") is not None else None,
    )


def get_crop_detection(db: Session, land_id: int) -> Optional[CropDetectionResponse]:
    from app.crops import user_crops as user_crop_service
    from app.crops.schemas import DetectedCropItem, SpectralSignals
    from app.crops.suggestion import CropConfidenceBand, SpectralSignals as SignalsDataclass, evaluate_crop_suggestion
    from app.trust.confidence_scorer import ConfidenceScorer
    from app.trust.types import DetectionMethod, TrustTier

    land = repository.get_land(db, land_id)
    if land is None:
        return None

    declared = user_crop_service.get_primary_declaration(db, land_id)
    zones = [z for z in repository.list_crop_zones(db, land_id) if not z.suppressed]
    latest = repository.get_latest_crop_record(db, land_id)
    ndvi_val = float(latest.ndvi_value) if latest and latest.ndvi_value is not None else 0.0
    is_synthetic = _crop_rows_use_synthetic(db, land_id)

    if not zones and not latest:
        return CropDetectionResponse(
            land_id=land_id,
            detected_crop_type=None,
            detected_crops=[],
            detection_method=DetectionMethod.UNKNOWN.value,
            trust_tier=TrustTier.UNAVAILABLE.value,
            confidence=0.0,
            confidence_band=CropConfidenceBand.LOW.value,
            requires_confirmation=True,
            display_label="Uncertain",
            is_synthetic_data=is_synthetic,
            ndvi_current=0.0,
            health="no_data",
            note="No NDVI data available yet. Run satellite task to populate.",
        )

    detected_crops: list[DetectedCropItem] = []
    for i, z in enumerate(zones):
        conf = float(z.avg_confidence) if z.avg_confidence is not None else 0.0
        sep = float(z.separation_score) if z.separation_score is not None else None
        rows = repository.list_land_crop_rows(db, land_id, zone_id=int(z.zone_id))
        ndvis = [float(r.ndvi_value) for r in rows if r.ndvi_value is not None]
        detected_crops.append(
            DetectedCropItem(
                crop_type=z.crop_type,
                confidence=round(conf, 4),
                ndvi_mean=round(sum(ndvis) / len(ndvis), 4) if ndvis else float(z.latest_ndvi or 0),
                growth_stage=z.latest_growth_stage,
                is_primary=(i == 0),
                trust_tier=z.trust_tier or TrustTier.ESTIMATED.value,
                detection_method=z.detection_method or DetectionMethod.NDVI_PROFILE_MATCH.value,
                ambiguous=bool(z.ambiguous),
                show_confidence_bar=ConfidenceScorer.should_show_confidence_bar(conf, sep),
            )
        )

    confidence_band = CropConfidenceBand.LOW.value
    requires_confirmation = True
    display_label = "Suggested"
    spectral_signals: Optional[SpectralSignals] = None

    if declared:
        primary_crop = declared.crop_type
        method = DetectionMethod.USER_CONFIRMED.value
        tier = TrustTier.VERIFIED.value
        primary_conf = 1.0
        note = f"User-confirmed crop: {primary_crop}."
        spectral = zones[0].crop_type if zones else None
        if spectral and spectral.lower() != primary_crop.lower():
            note += f" Spectral estimate suggests '{spectral}' (estimated, not confirmed)."
        requires_confirmation = False
        display_label = "Confirmed"
        confidence_band = CropConfidenceBand.HIGH.value
    else:
        primary_zone = zones[0] if zones else None
        primary = detected_crops[0] if detected_crops else None
        primary_crop = primary.crop_type if primary else None
        method = DetectionMethod.NDVI_PROFILE_MATCH.value
        tier = TrustTier.ESTIMATED.value
        primary_conf = primary.confidence if primary else 0.0
        spectral = primary_crop

        signals_dc: Optional[SignalsDataclass] = None
        if primary_zone:
            signals_dc = SignalsDataclass(**_spectral_signals_from_zone(primary_zone).model_dump())
            spectral_signals = SpectralSignals(**signals_dc.to_dict())

        secondary_crop = detected_crops[1].crop_type if len(detected_crops) > 1 else None
        evaluation = evaluate_crop_suggestion(
            crop_type=primary_crop,
            confidence=primary_conf,
            area_pct=float(primary_zone.area_pct) if primary_zone and primary_zone.area_pct else 0.0,
            ambiguous=bool(primary.ambiguous) if primary else False,
            separation=float(primary_zone.separation_score) if primary_zone and primary_zone.separation_score is not None else None,
            is_synthetic=is_synthetic,
            spectral_signals=signals_dc,
            secondary_crop=secondary_crop,
        )
        note = evaluation.note
        confidence_band = evaluation.confidence_band.value
        requires_confirmation = evaluation.requires_confirmation
        display_label = evaluation.display_label

    return CropDetectionResponse(
        land_id=land_id,
        detected_crop_type=primary_crop,
        detected_crops=detected_crops,
        detection_method=method,
        trust_tier=tier,
        declared_crop=declared.crop_type if declared else None,
        spectral_estimate=spectral if declared else None,
        confidence=primary_conf,
        confidence_band=confidence_band,
        requires_confirmation=requires_confirmation,
        display_label=display_label,
        spectral_signals=spectral_signals,
        is_synthetic_data=is_synthetic,
        ndvi_current=round(ndvi_val, 4),
        health=ndvi_engine.classify_health(ndvi_val),
        note=note,
    )


# ---------------------------------------------------------------------------
# 2. Crop Health
# ---------------------------------------------------------------------------

def get_crop_health(db: Session, land_id: int) -> Optional[CropHealthResponse]:
    from app.crops.schemas import ZoneHealthItem
    from app.cv.ndvi import _CROP_PROFILES

    land = repository.get_land(db, land_id)
    if land is None:
        return None

    # --- Build per-zone health items ---
    zones = [z for z in repository.list_crop_zones(db, land_id) if not z.suppressed]
    zone_items = []
    total_score = 0
    total_weight = 0

    for z in zones:
        ndvi_val = float(z.latest_ndvi) if z.latest_ndvi is not None else 0.0
        health = ndvi_engine.classify_health(ndvi_val)
        score = ndvi_engine.health_score(ndvi_val, crop_type=z.crop_type, growth_stage=z.latest_growth_stage)

        expected_range = None
        is_below = False
        profile = _CROP_PROFILES.get(z.crop_type.lower(), {}) if z.crop_type else {}
        if profile:
            ndvi_min = profile.get("ndvi_min_healthy", 0.35)
            ndvi_peak = profile.get("ndvi_peak", 0.70)
            expected_range = {"min": ndvi_min, "max": ndvi_peak}
            is_below = ndvi_val < ndvi_min

        if health in ("bare_soil", "very_sparse"):
            advice = "Very low vegetation. Verify irrigation and check for crop failure."
        elif health == "stressed":
            advice = "Crop shows stress signs. Check water supply and soil conditions."
        elif health == "developing":
            advice = "Crop is developing normally. Monitor for continued growth."
        elif health in ("healthy", "very_healthy"):
            advice = "Crop health is good. Continue current management practices."
        else:
            advice = "Dense canopy detected. Monitor for over-growth or flooding."

        zone_items.append(ZoneHealthItem(
            zone_id=int(z.zone_id),
            crop_type=z.crop_type,
            ndvi_current=round(ndvi_val, 4),
            health_status=health,
            health_score=score,
            ndvi_expected_range=expected_range,
            is_below_expected=is_below,
            advice=advice,
        ))

        weight = float(z.area_pct) if z.area_pct else 1.0
        total_score += score * weight
        total_weight += weight

    # --- Fallback to legacy if no zones exist ---
    if not zone_items:
        latest = _latest_crop(db, land_id)
        if latest is None:
            return CropHealthResponse(
                land_id=land_id,
                ndvi_current=0.0,
                health_status="no_data",
                health_score=0,
                advice="Register land and run satellite task to collect NDVI data.",
                overall_health_status="no_data",
                overall_health_score=0,
            )
        ndvi_val = float(latest.ndvi_value) if latest.ndvi_value is not None else 0.0
        health = ndvi_engine.classify_health(ndvi_val)
        score = ndvi_engine.health_score(ndvi_val, crop_type=latest.crop_type, growth_stage=latest.growth_stage)
        return CropHealthResponse(
            land_id=land_id,
            ndvi_current=round(ndvi_val, 4),
            health_status=health,
            health_score=score,
            advice="Health based on latest NDVI observation.",
            overall_health_status=health,
            overall_health_score=score,
        )

    # --- Compute overall weighted scores ---
    overall_score = int(total_score / total_weight) if total_weight > 0 else 0
    if overall_score >= 80: overall_status = "very_healthy"
    elif overall_score >= 60: overall_status = "healthy"
    elif overall_score >= 40: overall_status = "developing"
    elif overall_score >= 20: overall_status = "stressed"
    else: overall_status = "bare_soil"

    # Use primary zone for backward-compat top-level fields
    primary = zone_items[0]

    return CropHealthResponse(
        land_id=land_id,
        # Backward-compat fields from primary zone
        ndvi_current=primary.ndvi_current,
        health_status=overall_status,
        health_score=overall_score,
        ndvi_expected_range=primary.ndvi_expected_range,
        is_below_expected=primary.is_below_expected,
        advice=primary.advice,
        # New per-zone fields
        overall_health_status=overall_status,
        overall_health_score=overall_score,
        zones=zone_items,
    )


def refresh_crop_health(db: Session, land_id: int) -> Optional[CropHealthResponse]:
    """
    Recompute crop-zone intelligence and persist updates to crop_zones.
    Use this for explicit refresh; GET /crop-health remains read-only.
    """
    land = repository.get_land(db, land_id)
    if land is None:
        return None

    from app.intelligence.engine import CropIntelligenceEngine

    engine = CropIntelligenceEngine()
    engine.analyze_land(land_id, db, run_pipeline=False, persist=True)
    db.commit()
    return get_crop_health(db, land_id)


# ---------------------------------------------------------------------------
# 3. Crop Status (growth stage + trend)
# ---------------------------------------------------------------------------

def get_crop_status(db: Session, land_id: int, zone_id: Optional[int] = None) -> Optional[CropStatusResponse]:
    land = repository.get_land(db, land_id)
    if land is None:
        return None

    effective_zone = _resolve_zone_id(db, land_id, zone_id)
    latest = repository.get_latest_crop_record(db, land_id, zone_id=effective_zone)
    if latest is None:
        return CropStatusResponse(
            land_id=land_id,
            growth_stage="unknown",
            ndvi_current=0.0,
            trend="insufficient_data",
            trend_slope=0.0,
            last_updated="never",
            monitoring_interval_days=int(land.monitoring_interval_days),
        )

    rows = _get_crop_rows(db, land_id, zone_id=effective_zone)
    ndvi_series = [float(r.ndvi_value) for r in rows if r.ndvi_value is not None]

    ndvi_val = float(latest.ndvi_value) if latest.ndvi_value is not None else 0.0
    trend = ndvi_engine.compute_trend(ndvi_series)
    slope = ndvi_engine.compute_trend_slope(ndvi_series)

    return CropStatusResponse(
        land_id=land_id,
        growth_stage=latest.growth_stage or "unknown",
        ndvi_current=round(ndvi_val, 4),
        trend=trend,
        trend_slope=round(slope, 6),
        last_updated=latest.timestamp.isoformat(),
        monitoring_interval_days=int(land.monitoring_interval_days),
    )


# ---------------------------------------------------------------------------
# 4. Crop Trend (NDVI time-series)
# ---------------------------------------------------------------------------

def get_crop_trend(
    db: Session,
    land_id: int,
    days: int = 90,
    zone_id: Optional[int] = None,
) -> Optional[CropTrendResponse]:
    land = repository.get_land(db, land_id)
    if land is None:
        return None

    effective_zone = _resolve_zone_id(db, land_id, zone_id)
    rows = _get_crop_rows(db, land_id, zone_id=effective_zone)

    # Filter to last `days` worth of data
    from datetime import datetime, timezone, timedelta
    cutoff_aware = datetime.now(timezone.utc) - timedelta(days=days)
    cutoff_naive = cutoff_aware.replace(tzinfo=None)
    rows = [
        r for r in rows
        if (r.timestamp.tzinfo is not None and r.timestamp >= cutoff_aware)
        or (r.timestamp.tzinfo is None and r.timestamp >= cutoff_naive)
    ]

    if not rows:
        return CropTrendResponse(
            land_id=land_id,
            days_analyzed=days,
            ndvi_series=[],
            trend="insufficient_data",
            trend_slope=0.0,
            min_ndvi=0.0,
            max_ndvi=0.0,
            mean_ndvi=0.0,
            anomaly_detected=False,
        )

    ndvi_series = [float(r.ndvi_value) for r in rows if r.ndvi_value is not None]
    points = [
        NDVIPoint(
            date=r.timestamp.strftime("%Y-%m-%d"),
            ndvi=round(float(r.ndvi_value), 4) if r.ndvi_value is not None else 0.0,
            health=ndvi_engine.classify_health(float(r.ndvi_value) if r.ndvi_value else 0.0),
            growth_stage=r.growth_stage or "unknown",
        )
        for r in rows
    ]

    trend = ndvi_engine.compute_trend(ndvi_series)
    slope = ndvi_engine.compute_trend_slope(ndvi_series)
    anomaly = ndvi_engine.detect_anomaly(ndvi_series)

    return CropTrendResponse(
        land_id=land_id,
        days_analyzed=days,
        ndvi_series=points,
        trend=trend,
        trend_slope=round(slope, 6),
        min_ndvi=round(min(ndvi_series), 4) if ndvi_series else 0.0,
        max_ndvi=round(max(ndvi_series), 4) if ndvi_series else 0.0,
        mean_ndvi=round(sum(ndvi_series) / len(ndvi_series), 4) if ndvi_series else 0.0,
        anomaly_detected=anomaly,
    )


# ---------------------------------------------------------------------------
# 5. Harvest Prediction
# ---------------------------------------------------------------------------

def get_harvest_prediction(db: Session, land_id: int) -> Optional[HarvestPredictionResponse]:
    from app.crops.harvest_predictor import finalize_prediction, predict_zone_harvest
    from app.crops.schemas import ZoneHarvestItem
    from app.cv.ndvi import _CROP_PROFILES

    land = repository.get_land(db, land_id)
    if land is None:
        return None

    zones = [z for z in repository.list_crop_zones(db, land_id) if not z.suppressed]
    rows = list(repository.list_land_crop_rows(db, land_id))

    zone_items: list[ZoneHarvestItem] = []

    for z in zones:
        # Filter observations belonging to this zone
        z_rows = [r for r in rows if r.zone_id == z.zone_id]

        if len(z_rows) < 3:
            zone_items.append(ZoneHarvestItem(
                zone_id=int(z.zone_id),
                crop_type=z.crop_type,
                prediction_available=False,
                confidence_level="insufficient_data",
                note=f"Need at least 3 NDVI readings for {z.crop_type}. Currently have {len(z_rows)}.",
            ))
            continue

        ndvi_values = [float(r.ndvi_value) for r in z_rows if r.ndvi_value is not None]
        dates = [r.timestamp.strftime("%Y-%m-%d") for r in z_rows if r.ndvi_value is not None]
        latest_stage = z_rows[-1].growth_stage if z_rows else z.latest_growth_stage
        prediction = predict_zone_harvest(
            ndvi_values, dates, z.crop_type, latest_stage, _CROP_PROFILES
        )

        if prediction is None:
            zone_items.append(ZoneHarvestItem(
                zone_id=int(z.zone_id),
                crop_type=z.crop_type,
                prediction_available=False,
                confidence_level="insufficient_data",
                note=f"Could not compute harvest for {z.crop_type} from available data.",
            ))
            continue

        prediction = finalize_prediction(prediction)
        note = f"Based on {len(ndvi_values)} NDVI observations for {z.crop_type}."
        if prediction.get("note_suffix"):
            note = f"{note} {prediction['note_suffix']}"

        zone_items.append(ZoneHarvestItem(
            zone_id=int(z.zone_id),
            crop_type=z.crop_type,
            prediction_available=True,
            peak_ndvi=prediction["peak_ndvi"],
            peak_date=prediction["peak_date"],
            estimated_harvest_start=prediction["estimated_harvest_start"],
            estimated_harvest_end=prediction["estimated_harvest_end"],
            days_to_harvest=prediction["days_to_harvest"],
            confidence_level=prediction["confidence"],
            note=note,
        ))

    # --- Fallback: legacy single-crop prediction if no zones ---
    if not zone_items:
        if len(rows) < 3:
            return HarvestPredictionResponse(
                land_id=land_id,
                prediction_available=False,
                confidence_level="insufficient_data",
                note=f"Need at least 3 NDVI readings. Currently have {len(rows)}.",
            )
        ndvi_values = [float(r.ndvi_value) for r in rows if r.ndvi_value is not None]
        dates = [r.timestamp.strftime("%Y-%m-%d") for r in rows if r.ndvi_value is not None]
        crop_type = rows[-1].crop_type if rows else None
        latest_stage = rows[-1].growth_stage if rows else None
        prediction = predict_zone_harvest(
            ndvi_values, dates, crop_type, latest_stage, _CROP_PROFILES
        )
        if prediction:
            prediction = finalize_prediction(prediction)
            note = f"Based on {len(ndvi_values)} NDVI observations."
            if prediction.get("note_suffix"):
                note = f"{note} {prediction['note_suffix']}"
            return HarvestPredictionResponse(
                land_id=land_id,
                prediction_available=True,
                peak_ndvi=prediction["peak_ndvi"],
                peak_date=prediction["peak_date"],
                estimated_harvest_start=prediction["estimated_harvest_start"],
                estimated_harvest_end=prediction["estimated_harvest_end"],
                days_to_harvest=prediction["days_to_harvest"],
                confidence_level=prediction["confidence"],
                note=note,
            )
        return HarvestPredictionResponse(
            land_id=land_id,
            prediction_available=False,
            confidence_level="insufficient_data",
            note="Could not compute harvest prediction.",
        )

    # Use nearest upcoming harvest across zones for top-level summary
    available = [z for z in zone_items if z.prediction_available and z.days_to_harvest is not None]
    if available:
        primary = min(
            available,
            key=lambda z: z.days_to_harvest if z.days_to_harvest >= 0 else 10_000 + abs(z.days_to_harvest),
        )
    else:
        primary = next((z for z in zone_items if z.prediction_available), zone_items[0])

    response = HarvestPredictionResponse(
        land_id=land_id,
        prediction_available=primary.prediction_available,
        peak_ndvi=primary.peak_ndvi,
        peak_date=primary.peak_date,
        estimated_harvest_start=primary.estimated_harvest_start,
        estimated_harvest_end=primary.estimated_harvest_end,
        days_to_harvest=primary.days_to_harvest,
        confidence_level=primary.confidence_level,
        note=primary.note,
        zones=zone_items,
    )
    # Always recompute days from dates at response time
    if response.estimated_harvest_start:
        finalized = finalize_prediction(response.model_dump())
        response.days_to_harvest = finalized.get("days_to_harvest")
    return response


# ---------------------------------------------------------------------------
# 6. NDVI Weekly Comparison (progress tracking)
# ---------------------------------------------------------------------------

def get_ndvi_comparison(db: Session, land_id: int, weeks: int = 8) -> Optional[dict]:
    """Return NDVI image snapshots over the last N weeks for side-by-side comparison."""
    from app.crops.schemas import NdviSnapshot, NdviComparisonResponse

    land = repository.get_land(db, land_id)
    if land is None:
        return None

    primary = repository.get_primary_crop_zone(db, land_id)
    primary_zone_id = int(primary.zone_id) if primary else None
    imgs = repository.list_land_images(db, land_id, image_type="ndvi")
    snapshots = []
    for img in imgs:
        ndvi_val = float(img.ndvi_mean) if img.ndvi_mean is not None else None
        if ndvi_val is None:
            joined = repository.find_crop_ndvi_near_date(
                db, land_id, img.timestamp, zone_id=primary_zone_id
            )
            ndvi_val = joined if joined is not None else 0.0
        snapshots.append(NdviSnapshot(
            date=img.timestamp.strftime("%Y-%m-%d"),
            ndvi=ndvi_val,
        ))

    # Compute simple trend
    if len(snapshots) >= 2:
        first_ndvi = snapshots[0].ndvi
        last_ndvi = snapshots[-1].ndvi
        if first_ndvi > 0:
            change_pct = round(((last_ndvi - first_ndvi) / first_ndvi) * 100, 1)
        else:
            change_pct = 0.0
        trend = "improving" if last_ndvi > first_ndvi else ("declining" if last_ndvi < first_ndvi else "stable")
    else:
        change_pct = None
        trend = "insufficient_data"

    return NdviComparisonResponse(
        land_id=land_id,
        snapshots=snapshots[-weeks:],  # last N weeks
        trend=trend,
        change_pct=change_pct,
    )
