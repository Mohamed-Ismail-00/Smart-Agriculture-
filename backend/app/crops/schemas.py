"""crops/schemas.py — Response schemas for all 5 crop intelligence endpoints."""

from typing import Any, Optional
from pydantic import BaseModel


class NDVIPoint(BaseModel):
    date: str
    ndvi: float
    health: str
    growth_stage: str


class SpectralSignals(BaseModel):
    profile_fit: float
    season_match: float
    spatial_coherence: float
    field_agreement: float
    separation: Optional[float] = None
    profile_margin: Optional[float] = None


class DetectedCropItem(BaseModel):
    """A single detected crop with its confidence and metadata."""
    crop_type: str
    confidence: float                  # 0.0 – 1.0
    ndvi_mean: float
    growth_stage: Optional[str] = None
    is_primary: bool = False
    trust_tier: str = "estimated"
    detection_method: Optional[str] = None
    ambiguous: bool = False
    show_confidence_bar: bool = False


class CropDetectionResponse(BaseModel):
    land_id: int
    detected_crop_type: Optional[str]  # Primary crop (backward-compat)
    detected_crops: list[DetectedCropItem] = []  # All detected crops
    detection_method: str              # ndvi_profile_match | user_confirmed | unknown
    trust_tier: str = "estimated"
    declared_crop: Optional[str] = None
    spectral_estimate: Optional[str] = None
    confidence: float                  # Primary crop confidence
    confidence_band: str = "low"       # high | medium | low
    requires_confirmation: bool = True
    display_label: str = "Suggested"
    spectral_signals: Optional[SpectralSignals] = None
    is_synthetic_data: bool = False
    ndvi_current: float
    health: str
    note: str


class DeclaredCropRequest(BaseModel):
    crop_type: str
    notes: Optional[str] = None


class ZoneHealthItem(BaseModel):
    """Health assessment for a single crop zone."""
    zone_id: int
    crop_type: str
    ndvi_current: float
    health_status: str
    health_score: int
    ndvi_expected_range: Optional[dict[str, float]] = None
    is_below_expected: bool = False
    advice: str = ""


class CropHealthResponse(BaseModel):
    land_id: int
    # Overall (backward-compat — aggregated across all zones)
    ndvi_current: float = 0.0
    health_status: str = "no_data"
    health_score: int = 0
    ndvi_expected_range: Optional[dict[str, float]] = None
    is_below_expected: bool = False
    advice: str = ""
    # Per-zone breakdown (new)
    overall_health_status: str = "no_data"
    overall_health_score: int = 0
    zones: list[ZoneHealthItem] = []


class CropStatusResponse(BaseModel):
    land_id: int
    growth_stage: str
    ndvi_current: float
    trend: str                    # improving | stable | declining | insufficient_data
    trend_slope: float            # NDVI units per 16-day period
    last_updated: str             # ISO timestamp of latest NDVI reading
    monitoring_interval_days: int


class CropTrendResponse(BaseModel):
    land_id: int
    days_analyzed: int
    ndvi_series: list[NDVIPoint]
    trend: str
    trend_slope: float
    min_ndvi: float
    max_ndvi: float
    mean_ndvi: float
    anomaly_detected: bool


class ZoneHarvestItem(BaseModel):
    """Harvest prediction for a single crop zone."""
    zone_id: int
    crop_type: str
    prediction_available: bool = False
    peak_ndvi: Optional[float] = None
    peak_date: Optional[str] = None
    estimated_harvest_start: Optional[str] = None
    estimated_harvest_end: Optional[str] = None
    days_to_harvest: Optional[int] = None
    confidence_level: str = "insufficient_data"
    note: str = ""


class HarvestPredictionResponse(BaseModel):
    land_id: int
    # Overall (backward-compat — uses primary crop)
    prediction_available: bool = False
    peak_ndvi: Optional[float] = None
    peak_date: Optional[str] = None
    estimated_harvest_start: Optional[str] = None
    estimated_harvest_end: Optional[str] = None
    days_to_harvest: Optional[int] = None
    confidence_level: str = "insufficient_data"
    note: str = ""
    # Per-zone breakdown (new)
    zones: list[ZoneHarvestItem] = []


class NdviSnapshot(BaseModel):
    """A single NDVI measurement at a point in time."""
    date: str
    ndvi: float
    image_type: str = "ndvi"


class NdviComparisonResponse(BaseModel):
    land_id: int
    snapshots: list[NdviSnapshot] = []
    trend: str = "insufficient_data"
    change_pct: Optional[float] = None

