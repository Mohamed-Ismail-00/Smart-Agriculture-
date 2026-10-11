from datetime import date, timedelta

import pytest

from app.crops.harvest_predictor import (
    days_until_harvest,
    finalize_prediction,
    predict_zone_harvest,
)


class TestDaysUntilHarvest:
    def test_future_date(self):
        future = date.today() + timedelta(days=10)
        assert days_until_harvest(future) == 10

    def test_past_date(self):
        past = date.today() - timedelta(days=5)
        assert days_until_harvest(past) == -5


class TestFinalizePrediction:
    def test_recalculates_days_from_start(self):
        start = (date.today() + timedelta(days=21)).isoformat()
        raw = {
            "estimated_harvest_start": start,
            "days_to_harvest": 999,
        }
        result = finalize_prediction(raw)
        assert result["days_to_harvest"] == 21


class TestPredictZoneHarvest:
    def test_returns_prediction_with_enough_points(self):
        today = date.today()
        dates = [(today - timedelta(days=30 - i)).isoformat() for i in range(30)]
        ndvi = [0.3 + (i / 30) * 0.4 for i in range(30)]
        result = predict_zone_harvest(ndvi, dates, "wheat", "vegetative", {})
        assert result is not None
        assert "estimated_harvest_start" in result
        assert "days_to_harvest" in result

    def test_insufficient_points_returns_none(self):
        assert predict_zone_harvest([0.4, 0.5], ["2026-01-01", "2026-01-17"], "wheat", "vegetative", {}) is None