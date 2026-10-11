"""Tests for crop suggestion confidence bands."""

from app.crops.suggestion import (
    CropConfidenceBand,
    SpectralSignals,
    evaluate_crop_suggestion,
)


def _signals(**kwargs) -> SpectralSignals:
    defaults = {
        "profile_fit": 0.8,
        "season_match": 1.0,
        "spatial_coherence": 0.85,
        "field_agreement": 0.9,
        "separation": 0.18,
        "profile_margin": 0.2,
    }
    defaults.update(kwargs)
    return SpectralSignals(**defaults)


class TestCropSuggestion:
    def test_high_confidence_when_strong_spectral_agreement(self):
        result = evaluate_crop_suggestion(
            crop_type="winter onion",
            confidence=0.72,
            area_pct=85.0,
            ambiguous=False,
            separation=0.18,
            is_synthetic=False,
            spectral_signals=_signals(),
        )
        assert result.confidence_band == CropConfidenceBand.HIGH
        assert result.requires_confirmation is False
        assert result.display_label == "Likely"

    def test_medium_when_moderate_confidence(self):
        result = evaluate_crop_suggestion(
            crop_type="winter onion",
            confidence=0.52,
            area_pct=60.0,
            ambiguous=False,
            separation=0.08,
            is_synthetic=False,
            spectral_signals=_signals(separation=0.08, profile_margin=0.05),
        )
        assert result.confidence_band == CropConfidenceBand.MEDIUM
        assert result.requires_confirmation is True
        assert result.display_label == "Suggested"

    def test_low_when_ambiguous_or_weak(self):
        result = evaluate_crop_suggestion(
            crop_type="winter onion",
            confidence=0.42,
            area_pct=80.0,
            ambiguous=True,
            separation=0.013,
            is_synthetic=False,
            spectral_signals=_signals(separation=0.013),
        )
        assert result.confidence_band == CropConfidenceBand.LOW
        assert result.requires_confirmation is True
        assert "ambiguous" in result.note.lower()

    def test_synthetic_caps_to_medium_or_low(self):
        result = evaluate_crop_suggestion(
            crop_type="winter onion",
            confidence=0.8,
            area_pct=90.0,
            ambiguous=False,
            separation=0.2,
            is_synthetic=True,
            spectral_signals=_signals(),
        )
        assert result.confidence_band != CropConfidenceBand.HIGH
        assert "synthetic" in result.note.lower() or result.requires_confirmation is True