"""Map data sources and methods to trust tiers."""

from __future__ import annotations

from typing import Optional

from app.trust.types import DetectionMethod, TrustTier


class TrustTierResolver:
    """Server-side tier assignment — never accept tiers from clients."""

    @staticmethod
    def for_ndvi(*, is_synthetic: bool, has_value: bool) -> TrustTier:
        if not has_value:
            return TrustTier.UNAVAILABLE
        if is_synthetic:
            return TrustTier.ESTIMATED
        return TrustTier.OBSERVED

    @staticmethod
    def for_climate(*, has_rows: bool) -> TrustTier:
        return TrustTier.OBSERVED if has_rows else TrustTier.UNAVAILABLE

    @staticmethod
    def for_climate_aggregate(
        *,
        has_rows: bool,
        temp_spread_c: Optional[float] = None,
    ) -> TrustTier:
        if not has_rows:
            return TrustTier.UNAVAILABLE
        if temp_spread_c is not None and temp_spread_c > 3.0:
            return TrustTier.ESTIMATED
        return TrustTier.OBSERVED

    @staticmethod
    def for_soil_moisture(*, has_rows: bool) -> TrustTier:
        return TrustTier.OBSERVED if has_rows else TrustTier.UNAVAILABLE

    @staticmethod
    def for_soil_profile(*, fetch_status: Optional[str], has_data: bool) -> TrustTier:
        if fetch_status in ("timeout", "error", "empty") or not has_data:
            return TrustTier.UNAVAILABLE
        return TrustTier.OBSERVED

    @staticmethod
    def for_crop_label(
        *,
        user_confirmed: bool,
        detection_method: Optional[str] = None,
        has_label: bool = True,
    ) -> TrustTier:
        if user_confirmed:
            return TrustTier.VERIFIED
        if not has_label:
            return TrustTier.UNAVAILABLE
        if detection_method in (
            DetectionMethod.USER_CONFIRMED.value,
            DetectionMethod.USER_DECLARED_MIX.value,
        ):
            return TrustTier.VERIFIED
        return TrustTier.ESTIMATED

    @staticmethod
    def user_facing_label(tier: TrustTier) -> str:
        return {
            TrustTier.VERIFIED: "Confirmed",
            TrustTier.OBSERVED: "Observed",
            TrustTier.ESTIMATED: "Estimated",
            TrustTier.UNAVAILABLE: "No data",
        }.get(tier, "Unknown")