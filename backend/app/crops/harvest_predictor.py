"""Unified harvest prediction from NDVI peaks, growth stage, and harvest events."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Optional

from app.cv.ndvi import predict_harvest_window
from app.intelligence.harvest_detector import HarvestDetector


def _parse_date(value: str) -> Optional[date]:
    try:
        return datetime.strptime(value[:10], "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def days_until_harvest(harvest_start: date, *, today: Optional[date] = None) -> int:
    """Days from today until harvest start (negative = past due)."""
    ref = today or date.today()
    return (harvest_start - ref).days


def finalize_prediction(raw: dict, *, today: Optional[date] = None) -> dict:
    """Recompute days_to_harvest from dates so responses stay current."""
    result = dict(raw)
    start = _parse_date(result.get("estimated_harvest_start", ""))
    if start is not None:
        result["days_to_harvest"] = days_until_harvest(start, today=today)
    return result


def _ndvi_trend(ndvi_series: list[float]) -> str:
    if len(ndvi_series) < 2:
        return "stable"
    delta = ndvi_series[-1] - ndvi_series[-2]
    if delta > 0.03:
        return "rising"
    if delta < -0.03:
        return "falling"
    return "stable"


def predict_from_growth_stage(
    ndvi_series: list[float],
    dates: list[str],
    crop_type: str,
    growth_stage: Optional[str],
    crop_profiles: dict,
) -> Optional[dict]:
    """Growth-stage + harvest-event trajectory (always anchored to today)."""
    if len(ndvi_series) < 2:
        return None

    detector = HarvestDetector(crop_profiles)
    events = detector.detect_harvest_events(ndvi_series, dates, crop_type or "unknown")
    last_event = events[-1] if events else None
    stage = growth_stage or "vegetative"

    prediction = detector.predict_next_harvest(
        last_harvest=last_event,
        crop_type=crop_type or "unknown",
        ndvi_current=ndvi_series[-1],
        ndvi_trend=_ndvi_trend(ndvi_series),
        current_growth_stage=stage,
    )
    if prediction is None:
        return None

    harvest_start = prediction.estimated_date
    harvest_end = harvest_start + timedelta(days=7)
    confidence = "high" if prediction.confidence >= 0.75 else "medium" if prediction.confidence >= 0.6 else "low"

    return {
        "peak_ndvi": round(max(ndvi_series), 4),
        "peak_date": dates[ndvi_series.index(max(ndvi_series))],
        "estimated_harvest_start": harvest_start.isoformat(),
        "estimated_harvest_end": harvest_end.isoformat(),
        "days_to_harvest": days_until_harvest(harvest_start),
        "confidence": confidence,
        "method": prediction.based_on,
    }


def predict_zone_harvest(
    ndvi_series: list[float],
    dates: list[str],
    crop_type: str,
    growth_stage: Optional[str],
    crop_profiles: dict,
) -> Optional[dict]:
    """
    Combine NDVI-peak calendar with growth-stage trajectory.
    Prefers the estimate closest to today that is still in the future.
    """
    if len(ndvi_series) < 3:
        return None

    peak_pred = predict_harvest_window(ndvi_series, dates, crop_type)
    stage_pred = predict_from_growth_stage(
        ndvi_series, dates, crop_type, growth_stage, crop_profiles
    )

    candidates = [p for p in (peak_pred, stage_pred) if p]
    if not candidates:
        return None

    today = date.today()

    def score(pred: dict) -> tuple:
        start = _parse_date(pred.get("estimated_harvest_start", ""))
        if start is None:
            return (3, 9999)
        days = days_until_harvest(start, today=today)
        # Prefer future estimates; among past, prefer stage-based (more current)
        if days >= 0:
            return (0, days)
        method_rank = 0 if pred.get("method") else 1
        return (1, method_rank, abs(days))

    best = min(candidates, key=score)
    result = finalize_prediction(best, today=today)

    # Recent harvest: NDVI collapsed and window long past
    if (
        result.get("days_to_harvest", 0) < -14
        and ndvi_series[-1] < 0.25
    ):
        result["harvest_status"] = "completed"
        result["confidence"] = "high"
        result["note_suffix"] = "NDVI indicates harvest likely completed."
    elif result.get("days_to_harvest", 0) < 0:
        result["harvest_status"] = "overdue"
        result["note_suffix"] = "Estimated window has passed; verify field conditions."
    elif result.get("days_to_harvest", 0) <= 14:
        result["harvest_status"] = "approaching"
    else:
        result["harvest_status"] = "scheduled"

    return result