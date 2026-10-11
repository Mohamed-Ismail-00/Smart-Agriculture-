"""
Tests for cv/ndvi.py — pure math, no DB, no HTTP.
All functions are deterministic, so no mocking needed.
"""

import pytest
from app.cv.ndvi import (
    classify_health,
    compute_confidence,
    compute_ndvi,
    compute_trend,
    compute_trend_slope,
    detect_anomaly,
    health_score,
    predict_harvest_window,
    estimate_growth_stage,
)


class TestComputeNDVI:
    def test_healthy_vegetation(self):
        """NIR=0.40, RED=0.20 → NDVI = (0.40-0.20)/(0.40+0.20) = 0.333"""
        result = compute_ndvi(0.40, 0.20)
        assert result == pytest.approx(0.333, abs=0.001)

    def test_modis_scaled_values(self):
        """MODIS returns raw ints. After /10000: NIR=0.1792, RED=0.1427 → ~0.1133"""
        nir = 1792 / 10000
        red = 1427 / 10000
        result = compute_ndvi(nir, red)
        # Pre-computed MODIS value was 1133/10000 = 0.1133
        assert result == pytest.approx(0.1133, abs=0.001)

    def test_bare_soil(self):
        """Equal NIR and RED → NDVI = 0"""
        assert compute_ndvi(0.3, 0.3) == pytest.approx(0.0, abs=0.001)

    def test_dense_vegetation(self):
        """High NIR, low RED → NDVI close to 1"""
        result = compute_ndvi(0.90, 0.05)
        assert result > 0.85

    def test_water_negative_ndvi(self):
        """Water: RED > NIR → negative NDVI"""
        result = compute_ndvi(0.05, 0.20)
        assert result < 0.0

    def test_clipped_to_minus_one(self):
        assert compute_ndvi(0.0, 1.0) >= -1.0

    def test_clipped_to_plus_one(self):
        assert compute_ndvi(1.0, 0.0) <= 1.0

    def test_both_zero_returns_zero(self):
        assert compute_ndvi(0.0, 0.0) == pytest.approx(0.0)


class TestClassifyHealth:
    @pytest.mark.parametrize("ndvi,expected", [
        (-0.1, "bare_soil"),
        (0.05, "bare_soil"),
        (0.15, "very_sparse"),
        (0.28, "stressed"),
        (0.45, "developing"),
        (0.58, "healthy"),
        (0.72, "very_healthy"),
        (0.85, "dense_canopy"),
    ])
    def test_classification_thresholds(self, ndvi, expected):
        assert classify_health(ndvi) == expected


class TestHealthScore:
    def test_zero_for_negative_ndvi(self):
        assert health_score(-0.5) == 0

    def test_100_for_max_ndvi(self):
        assert health_score(1.0) == 100

    def test_proportional(self):
        assert health_score(0.5) == 50


class TestComputeTrend:
    def test_improving(self):
        series = [0.20, 0.30, 0.42, 0.55, 0.65]
        assert compute_trend(series) == "improving"

    def test_declining(self):
        series = [0.70, 0.58, 0.45, 0.32, 0.20]
        assert compute_trend(series) == "declining"

    def test_stable(self):
        series = [0.50, 0.51, 0.49, 0.50, 0.51]
        assert compute_trend(series) == "stable"

    def test_insufficient_data(self):
        assert compute_trend([0.5, 0.6]) == "insufficient_data"

    def test_single_point(self):
        assert compute_trend([0.5]) == "insufficient_data"


class TestComputeTrendSlope:
    def test_positive_slope(self):
        slope = compute_trend_slope([0.30, 0.40, 0.50])
        assert slope > 0

    def test_negative_slope(self):
        slope = compute_trend_slope([0.60, 0.50, 0.40])
        assert slope < 0

    def test_flat_is_zero(self):
        slope = compute_trend_slope([0.50, 0.50, 0.50])
        assert slope == pytest.approx(0.0, abs=0.001)


class TestComputeConfidence:
    def test_all_best_quality(self):
        assert compute_confidence([0, 0, 0]) == pytest.approx(1.0)

    def test_all_good(self):
        assert compute_confidence([1, 1, 1]) == pytest.approx(0.8)

    def test_mixed_quality(self):
        result = compute_confidence([0, 1, 2])
        # (1.0 + 0.8 + 0.4) / 3 = 0.733
        assert result == pytest.approx(0.733, abs=0.01)

    def test_fill_values_zero_weight(self):
        assert compute_confidence([-1, -1]) == pytest.approx(0.0)

    def test_empty_returns_neutral(self):
        assert compute_confidence([]) == pytest.approx(0.5)


class TestDetectAnomaly:
    def test_detects_significant_drop(self):
        series = [0.65, 0.67, 0.64, 0.66, 0.30]   # last one drops sharply
        assert detect_anomaly(series, drop_threshold=0.15) is True

    def test_no_anomaly_on_gradual_decline(self):
        series = [0.65, 0.62, 0.59, 0.56, 0.53]
        assert detect_anomaly(series, drop_threshold=0.15) is False

    def test_insufficient_data_returns_false(self):
        assert detect_anomaly([0.5, 0.2]) is False


class TestEstimateGrowthStage:
    def test_low_ndvi_is_planting(self):
        assert estimate_growth_stage(0.08, month=3) == "planting"

    def test_medium_ndvi_is_vegetative(self):
        stage = estimate_growth_stage(0.45, month=5)
        assert stage in ("early_vegetative", "vegetative")

    def test_high_ndvi_is_flowering_or_later(self):
        stage = estimate_growth_stage(0.68, month=6)
        assert stage in ("vegetative", "flowering", "grain_fill", "harvest_ready")


class TestPredictHarvestWindow:
    def test_returns_none_when_too_few_points(self):
        result = predict_harvest_window([0.5, 0.6], ["2026-01-01", "2026-01-17"])
        assert result is None

    def test_returns_prediction_with_enough_data(self):
        ndvi_values = [0.2, 0.4, 0.65, 0.72, 0.55, 0.35, 0.20]
        dates = [
            "2026-01-01", "2026-01-17", "2026-02-02",
            "2026-02-18", "2026-03-06", "2026-03-22", "2026-04-07",
        ]
        result = predict_harvest_window(ndvi_values, dates)
        assert result is not None
        assert "peak_ndvi" in result
        assert "estimated_harvest_start" in result
        assert result["peak_ndvi"] > 0

    def test_mismatched_lengths_returns_none(self):
        result = predict_harvest_window([0.5, 0.6, 0.7], ["2026-01-01"])
        assert result is None
