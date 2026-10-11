"""Crop suggestion confidence bands for smart detection UX."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional


class CropConfidenceBand(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# Tunable thresholds — high band needs strong spectral agreement across the field.
HIGH_CONFIDENCE_MIN = 0.65
HIGH_SEPARATION_MIN = 0.15
HIGH_AREA_PCT_MIN = 70.0
HIGH_MARGIN_MIN = 0.12

MEDIUM_CONFIDENCE_MIN = 0.45
MEDIUM_AREA_PCT_MIN = 50.0


@dataclass
class SpectralSignals:
    profile_fit: float
    season_match: float
    spatial_coherence: float
    field_agreement: float
    separation: Optional[float] = None
    profile_margin: Optional[float] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile_fit": round(self.profile_fit, 4),
            "season_match": round(self.season_match, 4),
            "spatial_coherence": round(self.spatial_coherence, 4),
            "field_agreement": round(self.field_agreement, 4),
            "separation": round(self.separation, 4) if self.separation is not None else None,
            "profile_margin": round(self.profile_margin, 4) if self.profile_margin is not None else None,
        }


@dataclass
class CropSuggestionEvaluation:
    confidence_band: CropConfidenceBand
    requires_confirmation: bool
    display_label: str
    note: str
    spectral_signals: Optional[SpectralSignals] = None


def evaluate_crop_suggestion(
    *,
    crop_type: Optional[str],
    confidence: float,
    area_pct: float,
    ambiguous: bool,
    separation: Optional[float],
    is_synthetic: bool,
    spectral_signals: Optional[SpectralSignals] = None,
    secondary_crop: Optional[str] = None,
) -> CropSuggestionEvaluation:
    """Classify spectral crop suggestion into UX bands."""
    if not crop_type or crop_type.lower() in ("unknown", "fallow/bare soil"):
        return CropSuggestionEvaluation(
            confidence_band=CropConfidenceBand.LOW,
            requires_confirmation=True,
            display_label="Uncertain",
            note="Could not identify a crop from satellite patterns. Please select your crop.",
            spectral_signals=spectral_signals,
        )

    margin = spectral_signals.profile_margin if spectral_signals else None

    high_ok = (
        confidence >= HIGH_CONFIDENCE_MIN
        and area_pct >= HIGH_AREA_PCT_MIN
        and not ambiguous
        and not is_synthetic
        and (separation is None or separation >= HIGH_SEPARATION_MIN)
        and (margin is None or margin >= HIGH_MARGIN_MIN)
    )

    medium_ok = (
        confidence >= MEDIUM_CONFIDENCE_MIN
        and area_pct >= MEDIUM_AREA_PCT_MIN
        and not is_synthetic
        and not ambiguous
    )

    if high_ok:
        band = CropConfidenceBand.HIGH
        display = "Likely"
        requires = False
        note = (
            f"Satellite pattern strongly matches {crop_type}. "
            "Accept to unlock verified health and harvest advice, or correct if different."
        )
    elif medium_ok:
        band = CropConfidenceBand.MEDIUM
        display = "Suggested"
        requires = True
        note = (
            f"Satellite pattern suggests {crop_type}. "
            "Confirm your crop for trusted health and harvest advice."
        )
    else:
        band = CropConfidenceBand.LOW
        display = "Uncertain"
        requires = True
        note = "Satellite pattern match is weak or mixed — please confirm your actual crop."
        if ambiguous:
            note += " Spectral pattern is ambiguous across the field."
        if is_synthetic:
            note += " Based on estimated NDVI fallback, not live satellite imagery."
        if secondary_crop and not ambiguous:
            note += f" Possible mix with {secondary_crop.split('(')[0].strip()}."

    return CropSuggestionEvaluation(
        confidence_band=band,
        requires_confirmation=requires,
        display_label=display,
        note=note,
        spectral_signals=spectral_signals,
    )