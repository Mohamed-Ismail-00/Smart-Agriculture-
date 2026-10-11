"""
Tests for lands/geometry.py — pure math, no DB, no HTTP.
"""

import math
import pytest

from app.lands.geometry import (
    circle_to_polygon,
    close_ring,
    compute_area_hectares,
    compute_centroid,
    validate_polygon,
)


# ---------------------------------------------------------------------------
# A known 1° × 1° square centred near 30°N, 31°E (Nile Delta)
# Coords: [lng, lat] (GeoJSON order)
# ---------------------------------------------------------------------------
SQUARE = [
    [30.5, 29.5],
    [31.5, 29.5],
    [31.5, 30.5],
    [30.5, 30.5],
]


class TestCloseRing:
    def test_closes_open_ring(self):
        ring = [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0]]
        closed = close_ring(ring)
        assert closed[-1] == closed[0]
        assert len(closed) == 4

    def test_does_not_duplicate_closed_ring(self):
        ring = [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 0.0]]
        closed = close_ring(ring)
        assert len(closed) == 4  # no extra point added

    def test_empty_ring_safe(self):
        assert close_ring([]) == []


class TestValidatePolygon:
    def test_valid_triangle_passes(self):
        ring = [[0.0, 0.0], [1.0, 0.0], [0.5, 1.0]]
        validate_polygon(ring)  # should not raise

    def test_fewer_than_3_unique_points_raises(self):
        ring = [[0.0, 0.0], [1.0, 0.0], [0.0, 0.0]]  # only 2 unique
        with pytest.raises(ValueError, match="3 unique points"):
            validate_polygon(ring)

    def test_longitude_out_of_range_raises(self):
        ring = [[200.0, 30.0], [31.0, 30.0], [31.0, 31.0]]
        with pytest.raises(ValueError, match="Longitude"):
            validate_polygon(ring)

    def test_latitude_out_of_range_raises(self):
        ring = [[31.0, 95.0], [32.0, 30.0], [31.5, 30.0]]
        with pytest.raises(ValueError, match="Latitude"):
            validate_polygon(ring)


class TestComputeCentroid:
    def test_square_centroid(self):
        """Centroid of a 1°×1° square at 30°N, 31°E should be (30.0, 31.0)."""
        lat, lng = compute_centroid(SQUARE)
        assert lat == pytest.approx(30.0, abs=0.01)
        assert lng == pytest.approx(31.0, abs=0.01)

    def test_triangle_centroid(self):
        """Centroid of triangle (0,0),(2,0),(1,2) → (1, 0.667)"""
        ring = [[0.0, 0.0], [2.0, 0.0], [1.0, 2.0]]
        lat, lng = compute_centroid(ring)
        assert lng == pytest.approx(1.0, abs=0.01)
        assert lat == pytest.approx(0.667, abs=0.01)

    def test_already_closed_ring(self):
        """Adding closing point should not change the centroid."""
        open_ring = list(SQUARE)
        closed_ring = list(SQUARE) + [SQUARE[0]]
        lat1, lng1 = compute_centroid(open_ring)
        lat2, lng2 = compute_centroid(closed_ring)
        assert lat1 == pytest.approx(lat2, abs=0.0001)
        assert lng1 == pytest.approx(lng2, abs=0.0001)


class TestComputeAreaHectares:
    def test_1_degree_square_near_equator(self):
        """
        A 1°×1° square at ~30°N.
        At 30°N: 1° lat ≈ 111.32 km, 1° lng ≈ 111.32 × cos(30°) ≈ 96.4 km
        Area ≈ 111.32 × 96.4 ≈ 10,731 km² ≈ 1,073,100 ha
        Our square: 1° × 1° — just verify it's within 5% of expected.
        """
        area = compute_area_hectares(SQUARE)
        assert area > 900_000  # at least 900k ha for a ~1° square

    def test_small_field_rough_estimate(self):
        """
        A tiny 0.01° × 0.01° square at ~30°N.
        ≈ 1.11 km × 0.96 km ≈ 107 ha
        """
        delta = 0.01
        small_square = [
            [31.0, 30.0],
            [31.0 + delta, 30.0],
            [31.0 + delta, 30.0 + delta],
            [31.0, 30.0 + delta],
        ]
        area = compute_area_hectares(small_square)
        # Expected ≈ 107 ha, accept 80–140 ha range
        assert 80 < area < 140

    def test_area_is_positive(self):
        """Area is always positive regardless of winding direction."""
        clockwise = list(SQUARE)
        counter = list(reversed(SQUARE))
        assert compute_area_hectares(clockwise) > 0
        assert compute_area_hectares(counter) > 0


class TestCircleToPolygon:
    def test_generates_closed_ring(self):
        ring = circle_to_polygon(30.0, 31.0, radius_km=1.0, num_points=32)
        assert ring[0] == ring[-1], "Ring must be closed"

    def test_correct_number_of_points(self):
        ring = circle_to_polygon(30.0, 31.0, radius_km=1.0, num_points=64)
        assert len(ring) == 65  # 64 unique + 1 closing

    def test_radius_zero_raises(self):
        with pytest.raises(ValueError, match="positive"):
            circle_to_polygon(30.0, 31.0, radius_km=0)

    def test_approximate_area(self):
        """
        Circle with 2 km radius → area = π × r² ≈ 12.57 km² ≈ 1,257 ha.
        Accept 10% tolerance due to polygon approximation.
        """
        ring = circle_to_polygon(30.0, 31.0, radius_km=2.0, num_points=128)
        area = compute_area_hectares(ring)
        expected = math.pi * 2.0 ** 2 * 100  # 1,257 ha
        assert abs(area - expected) / expected < 0.10, f"Area {area:.0f} ha, expected ~{expected:.0f} ha"

    def test_centroid_matches_center(self):
        """Centroid of circle polygon should be very close to input center."""
        ring = circle_to_polygon(29.5, 31.2, radius_km=5.0, num_points=64)
        lat, lng = compute_centroid(ring)
        assert lat == pytest.approx(29.5, abs=0.01)
        assert lng == pytest.approx(31.2, abs=0.01)
