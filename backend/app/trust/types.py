"""Trust tier and detection method constants."""

from enum import Enum


class TrustTier(str, Enum):
    VERIFIED = "verified"
    OBSERVED = "observed"
    ESTIMATED = "estimated"
    UNAVAILABLE = "unavailable"


class DetectionMethod(str, Enum):
    USER_CONFIRMED = "user_confirmed"
    USER_DECLARED_MIX = "user_declared_mix"
    NDVI_PROFILE_MATCH = "ndvi_profile_match"
    ML_SPECTRAL = "ml_spectral"
    MIXED_VEGETATION = "mixed_vegetation"
    UNKNOWN = "unknown"


# Display thresholds (plan KD-4, KD-5)
SEPARATION_SUPPRESS_THRESHOLD = 0.05
SEPARATION_DISPLAY_THRESHOLD = 0.15
MIN_CROP_CONFIDENCE_DISPLAY = 0.35