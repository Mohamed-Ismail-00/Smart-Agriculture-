"""Unit tests for polygon Open-Meteo aggregation."""

from app.connectors.open_meteo_polygon import (
    aggregate_daily_records,
    compute_temp_spread_c,
    sample_points_from_ring,
)
from app.trust.tier_resolver import TrustTierResolver
from app.trust.types import TrustTier


_RING = [
    [31.0, 30.0],
    [31.1, 30.0],
    [31.1, 30.1],
    [31.0, 30.1],
    [31.0, 30.0],
]


class TestPolygonSampling:
    def test_sample_points_returns_five_locations(self):
        points = sample_points_from_ring(_RING)
        assert len(points) == 5
        labels = {p["label"] for p in points}
        assert labels == {"centroid", "sw", "se", "ne", "nw"}

    def test_aggregate_daily_records_means_values(self):
        point_a = [
            {"date": "2026-01-01", "temperature_max_c": 30.0, "temperature_min_c": 20.0},
            {"date": "2026-01-02", "temperature_max_c": 32.0, "temperature_min_c": 22.0},
        ]
        point_b = [
            {"date": "2026-01-01", "temperature_max_c": 28.0, "temperature_min_c": 18.0},
            {"date": "2026-01-02", "temperature_max_c": 30.0, "temperature_min_c": 20.0},
        ]
        merged = aggregate_daily_records([point_a, point_b])
        assert len(merged) == 2
        by_date = {r["date"]: r for r in merged}
        assert by_date["2026-01-01"]["temperature_max_c"] == 29.0
        assert by_date["2026-01-02"]["temperature_min_c"] == 21.0

    def test_temp_spread_across_points(self):
        point_a = [{"date": "2026-01-01", "temperature_max_c": 35.0, "temperature_min_c": 25.0}]
        point_b = [{"date": "2026-01-01", "temperature_max_c": 30.0, "temperature_min_c": 20.0}]
        spread = compute_temp_spread_c([point_a, point_b])
        assert spread == 5.0

    def test_climate_aggregate_tier_estimated_when_spread_high(self):
        tier = TrustTierResolver.for_climate_aggregate(has_rows=True, temp_spread_c=4.2)
        assert tier == TrustTier.ESTIMATED

    def test_climate_aggregate_tier_observed_when_spread_low(self):
        tier = TrustTierResolver.for_climate_aggregate(has_rows=True, temp_spread_c=1.5)
        assert tier == TrustTier.OBSERVED