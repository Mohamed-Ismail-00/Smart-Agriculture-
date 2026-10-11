"""Measurable confidence scores for derived intelligence."""

from __future__ import annotations

import math
from typing import Optional

from app.trust.types import (
    MIN_CROP_CONFIDENCE_DISPLAY,
    SEPARATION_DISPLAY_THRESHOLD,
    SEPARATION_SUPPRESS_THRESHOLD,
)


class ConfidenceScorer:
    """Compute crop identification confidence from spectral fit signals."""

    @staticmethod
    def profile_fit(ndvi_peak_observed: float, ndvi_peak_profile: float) -> float:
        delta = abs(ndvi_peak_observed - ndvi_peak_profile)
        return max(0.0, 1.0 - min(delta / 0.25, 1.0))

    @staticmethod
    def season_match(peak_month: int, typical_months: list[int]) -> float:
        if not typical_months:
            return 0.75
        return 1.0 if peak_month in typical_months else 0.5

    @staticmethod
    def spatial_coherence(tile_labels: list[str]) -> float:
        if not tile_labels:
            return 0.0
        counts: dict[str, int] = {}
        for label in tile_labels:
            counts[label] = counts.get(label, 0) + 1
        n = len(tile_labels)
        entropy = -sum((c / n) * math.log(c / n) for c in counts.values() if c > 0)
        max_entropy = math.log(len(counts)) if len(counts) > 1 else 1.0
        if max_entropy <= 0:
            return 1.0
        return max(0.0, 1.0 - entropy / max_entropy)

    @staticmethod
    def separation_score(ndvi_a: float, ndvi_b: float) -> float:
        return abs(ndvi_a - ndvi_b)

    @classmethod
    def compute_crop_confidence(
        cls,
        *,
        ndvi_peak_observed: float,
        ndvi_peak_profile: float,
        peak_month: int,
        typical_season_months: list[int],
        tile_labels: list[str],
        separation_score: Optional[float] = None,
    ) -> float:
        fit = cls.profile_fit(ndvi_peak_observed, ndvi_peak_profile)
        season = cls.season_match(peak_month, typical_season_months)
        coherence = cls.spatial_coherence(tile_labels)
        sep_component = 1.0
        if separation_score is not None:
            sep_component = max(0.0, min(separation_score / 0.10, 1.0))

        raw = (
            0.30 * fit
            + 0.20 * season
            + 0.20 * coherence
            + 0.15 * sep_component
            + 0.15 * coherence
        )
        return round(max(0.0, min(raw, 1.0)), 4)

    @staticmethod
    def should_show_confidence_bar(
        confidence: float,
        separation_score: Optional[float],
    ) -> bool:
        if separation_score is not None and separation_score < SEPARATION_DISPLAY_THRESHOLD:
            return False
        return confidence >= MIN_CROP_CONFIDENCE_DISPLAY

    @staticmethod
    def should_suppress_secondary_zone(separation_score: float) -> bool:
        return separation_score < SEPARATION_SUPPRESS_THRESHOLD