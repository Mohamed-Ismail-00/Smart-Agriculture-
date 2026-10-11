"""
Crop identification from Sentinel NDVI time-series (rule-based profile matching).

Extracted from crop_task.py — does not call ML predict_crop (deprecated until ground truth).
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from app.trust.confidence_scorer import ConfidenceScorer
from app.trust.types import DetectionMethod, SEPARATION_SUPPRESS_THRESHOLD

logger = logging.getLogger(__name__)

_PROFILES_PATH = os.path.join(
    os.path.dirname(__file__), "..", "data", "reference", "crop_profiles.json"
)


@dataclass
class ZoneIdentification:
    crop_type: str
    area_pct: float
    tile_count: int
    avg_ndvi_peak: float
    confidence: float
    separation_score: float | None = None
    ambiguous: bool = False
    suppressed: bool = False
    detection_method: str = DetectionMethod.NDVI_PROFILE_MATCH.value
    zone_metadata: dict[str, Any] = field(default_factory=dict)


def load_crop_profiles() -> dict[str, Any]:
    try:
        with open(_PROFILES_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        logger.error("Failed to load crop profiles: %s", exc)
        return {}


def _eligible_profile_entries(
    tile_peak_month: int,
    profiles: dict[str, Any],
) -> list[dict[str, Any]]:
    annuals = []
    perennials = []
    for crop_name, profile in profiles.items():
        if crop_name == "fallow/bare soil":
            continue
        entry = {
            "name": crop_name,
            "peak": profile.get("ndvi_peak", 0.7),
            "months": profile.get("typical_season_months", []),
        }
        if profile.get("lifecycle") == "perennial":
            perennials.append(entry)
        else:
            annuals.append(entry)

    eligible = perennials + [c for c in annuals if not c["months"] or tile_peak_month in c["months"]]
    return eligible or (perennials + annuals)


def profile_fit_margin(
    tile_ndvi_max: float,
    tile_peak_month: int,
    profiles: dict[str, Any],
    winner: str,
) -> float:
    """Gap between best and second-best NDVI profile fit (higher = more distinct match)."""
    eligible = _eligible_profile_entries(tile_peak_month, profiles)
    if len(eligible) < 2:
        return 1.0

    fits = sorted(
        (
            ConfidenceScorer.profile_fit(tile_ndvi_max, c["peak"]),
            c["name"],
        )
        for c in eligible
    )
    best_fit, best_name = fits[-1]
    second_fit = fits[-2][0]
    if best_name != winner:
        winner_fit = next(
            (ConfidenceScorer.profile_fit(tile_ndvi_max, c["peak"]) for c in eligible if c["name"] == winner),
            best_fit,
        )
        return max(0.0, winner_fit - second_fit)
    return max(0.0, best_fit - second_fit)


def classify_tile_crop(
    tile_ndvi_max: float,
    tile_peak_month: int,
    profiles: dict[str, Any],
) -> str:
    if tile_ndvi_max < 0.25:
        return "fallow/bare soil"

    eligible = _eligible_profile_entries(tile_peak_month, profiles)
    if not eligible:
        return "Unknown"
    return min(eligible, key=lambda c: abs(c["peak"] - tile_ndvi_max))["name"]


def build_tile_labels(
    ndvi_features: dict[str, np.ndarray],
    profiles: dict[str, Any],
) -> tuple[np.ndarray, dict[str, int]]:
    flat_max = ndvi_features["max"].flatten()
    flat_peak = ndvi_features["peak_month"].flatten().astype(int)
    n = flat_max.size
    labels = np.empty(n, dtype=object)
    counts: dict[str, int] = {}

    for i in range(n):
        crop = classify_tile_crop(float(flat_max[i]), int(flat_peak[i]), profiles)
        labels[i] = crop
        counts[crop] = counts.get(crop, 0) + 1

    return labels, counts


def validate_zone_separation(
    primary_mean_ndvi: float,
    secondary_mean_ndvi: float,
) -> tuple[float, bool, bool]:
    sep = ConfidenceScorer.separation_score(primary_mean_ndvi, secondary_mean_ndvi)
    ambiguous = sep < SEPARATION_SUPPRESS_THRESHOLD
    suppress = ConfidenceScorer.should_suppress_secondary_zone(sep)
    return sep, ambiguous, suppress


def field_agreement_ratio(labels_2d: np.ndarray, crop_type: str) -> float:
    total = labels_2d.size
    if total == 0:
        return 0.0
    return float(np.sum(labels_2d == crop_type)) / total


def identify_zones_from_labels(
    labels_2d: np.ndarray,
    crop_counts: dict[str, int],
    ndvi_arr: np.ndarray,
    ndvi_features: dict[str, np.ndarray],
    profiles: dict[str, Any],
    dates: list,
) -> list[ZoneIdentification]:
    total = sum(crop_counts.values()) or 1
    sorted_crops = sorted(crop_counts.items(), key=lambda x: x[1], reverse=True)
    zones: list[ZoneIdentification] = []
    field_labels = labels_2d.flatten().tolist()

    for crop_type, count in sorted_crops:
        area_pct = (count / total) * 100.0
        if area_pct < 5.0 and len(sorted_crops) > 1:
            continue

        mask = labels_2d == crop_type
        peak_vals = ndvi_arr[:, mask]
        mean_ndvi = float(np.nanmean(peak_vals)) if peak_vals.size else 0.0
        tile_peak_month = int(np.median(ndvi_features["peak_month"][mask])) if mask.any() else 1

        profile = profiles.get(crop_type, {})
        ndvi_peak_observed = float(np.nanmax(peak_vals)) if peak_vals.size else mean_ndvi
        ndvi_peak_profile = float(profile.get("ndvi_peak", 0.7))
        typical_months = profile.get("typical_season_months", [])
        fit = ConfidenceScorer.profile_fit(ndvi_peak_observed, ndvi_peak_profile)
        season = ConfidenceScorer.season_match(tile_peak_month, typical_months)
        coherence = ConfidenceScorer.spatial_coherence(field_labels)
        agreement = field_agreement_ratio(labels_2d, crop_type)
        margin = profile_fit_margin(ndvi_peak_observed, tile_peak_month, profiles, crop_type)

        confidence = ConfidenceScorer.compute_crop_confidence(
            ndvi_peak_observed=ndvi_peak_observed,
            ndvi_peak_profile=ndvi_peak_profile,
            peak_month=tile_peak_month,
            typical_season_months=typical_months,
            tile_labels=field_labels,
        )

        zones.append(
            ZoneIdentification(
                crop_type=crop_type,
                area_pct=round(area_pct, 2),
                tile_count=count,
                avg_ndvi_peak=mean_ndvi,
                confidence=confidence,
                zone_metadata={
                    "peak_month": tile_peak_month,
                    "ndvi_peak_observed": ndvi_peak_observed,
                    "profile_fit": round(fit, 4),
                    "season_match": round(season, 4),
                    "spatial_coherence": round(coherence, 4),
                    "field_agreement": round(agreement, 4),
                    "profile_margin": round(margin, 4),
                },
            )
        )

    zones.sort(key=lambda z: z.area_pct, reverse=True)

    if len(zones) >= 2:
        sep, ambiguous, suppress = validate_zone_separation(
            zones[0].avg_ndvi_peak,
            zones[1].avg_ndvi_peak,
        )
        zones[1].separation_score = sep
        zones[1].ambiguous = ambiguous
        zones[1].suppressed = suppress
        if suppress:
            zones[1].zone_metadata["suppression_reason"] = f"separation_score={sep:.4f}"
        zones[0].separation_score = sep
        zones[0].ambiguous = ambiguous

        primary = zones[0]
        meta = primary.zone_metadata
        primary.confidence = ConfidenceScorer.compute_crop_confidence(
            ndvi_peak_observed=meta["ndvi_peak_observed"],
            ndvi_peak_profile=float(profiles.get(primary.crop_type, {}).get("ndvi_peak", 0.7)),
            peak_month=meta["peak_month"],
            typical_season_months=profiles.get(primary.crop_type, {}).get("typical_season_months", []),
            tile_labels=field_labels,
            separation_score=sep,
        )

    return zones


def visible_zones(zones: list[ZoneIdentification]) -> list[ZoneIdentification]:
    """Zones shown in API/UI — suppressed secondaries hidden unless primary only."""
    if not zones:
        return []
    visible = [zones[0]]
    for z in zones[1:]:
        if not z.suppressed:
            visible.append(z)
    return visible