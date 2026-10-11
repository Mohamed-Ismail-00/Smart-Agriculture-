"""Tests for environment refresh helpers (Phase 2)."""

from app.pipeline.land_discovery_pipeline import (
    _climate_mean_temp,
    parse_refresh_sections,
)


class TestClimateMeanTemp:
    def test_computes_average(self):
        assert _climate_mean_temp(30.0, 18.0) == 24.0

    def test_returns_none_when_missing(self):
        assert _climate_mean_temp(None, 18.0) is None
        assert _climate_mean_temp(30.0, None) is None


class TestParseRefreshSections:
    def test_default_all_when_empty(self):
        assert parse_refresh_sections(None) == {"environment", "satellite", "crops"}

    def test_parses_subset(self):
        assert parse_refresh_sections("environment,crops") == {"environment", "crops"}

    def test_ignores_unknown(self):
        assert parse_refresh_sections("environment,foo") == {"environment"}

    def test_fallback_when_all_invalid(self):
        assert parse_refresh_sections("foo,bar") == {"environment", "satellite", "crops"}