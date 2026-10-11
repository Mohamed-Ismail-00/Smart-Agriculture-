"""Tests for trust tier resolver and confidence scorer."""

from app.trust.confidence_scorer import ConfidenceScorer
from app.trust.provenance_service import _trust_tier_value
from app.trust.tier_resolver import TrustTierResolver
from app.trust.types import TrustTier


class TestTrustTierResolver:
    def test_ndvi_observed_when_real(self):
        assert TrustTierResolver.for_ndvi(is_synthetic=False, has_value=True) == TrustTier.OBSERVED

    def test_ndvi_estimated_when_synthetic(self):
        assert TrustTierResolver.for_ndvi(is_synthetic=True, has_value=True) == TrustTier.ESTIMATED

    def test_crop_verified_when_user_confirmed(self):
        assert (
            TrustTierResolver.for_crop_label(user_confirmed=True, has_label=True)
            == TrustTier.VERIFIED
        )

    def test_climate_aggregate_estimated_on_high_spread(self):
        assert (
            TrustTierResolver.for_climate_aggregate(has_rows=True, temp_spread_c=4.0)
            == TrustTier.ESTIMATED
        )


class TestProvenanceTierValue:
    def test_enum_serializes_to_value_not_repr(self):
        assert _trust_tier_value(TrustTier.ESTIMATED) == "estimated"
        assert len(_trust_tier_value(TrustTier.ESTIMATED)) <= 16


class TestConfidenceScorer:
    def test_giza_like_low_separation_suppresses_secondary(self):
        sep = ConfidenceScorer.separation_score(0.349, 0.362)
        assert ConfidenceScorer.should_suppress_secondary_zone(sep)

    def test_confidence_bar_hidden_for_low_separation(self):
        assert not ConfidenceScorer.should_show_confidence_bar(0.85, separation_score=0.013)

    def test_profile_fit_penalizes_mismatch(self):
        fit = ConfidenceScorer.profile_fit(0.55, 0.65)
        assert 0.5 < fit < 1.0