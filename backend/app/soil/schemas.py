"""soil/schemas.py — Response schemas for 3 soil intelligence endpoints."""

from typing import Any, Optional
from pydantic import BaseModel


class DepthLayerValue(BaseModel):
    depth: str
    value: Optional[float]


class SoilProperty(BaseModel):
    name: str
    unit: str
    topsoil_value: Optional[float]        # 0-5cm
    depths: list[DepthLayerValue]
    classification: Optional[str] = None  # e.g. "neutral", "loam", "low"


class SoilProfileResponse(BaseModel):
    land_id: int
    profile_available: bool
    fetched_at: Optional[str]
    texture_class: Optional[str]
    properties: list[SoilProperty]
    source: str
    fetch_status: Optional[str] = None
    fetch_attempts: Optional[int] = None
    last_fetch_error: Optional[str] = None
    trust_tier: Optional[str] = None
    retry_available: bool = False


class CropSuitabilityEntry(BaseModel):
    crop: str
    score: float                          # 0-100
    suitability: str                      # highly_suitable | suitable | ...


class SoilSuitabilityResponse(BaseModel):
    land_id: int
    profile_available: bool
    overall_best_score: Optional[float]
    top_crops: list[CropSuitabilityEntry]
    all_crops: list[CropSuitabilityEntry]
    advice: list[str]
    texture_class: Optional[str]


class SoilStatusResponse(BaseModel):
    land_id: int
    # Live time-series data (from land_soil — Open-Meteo)
    latest_moisture_pct: Optional[float]
    moisture_timestamp: Optional[str]
    # Static profile summary (from land_soil_profiles — SoilGrids)
    ph_h2o: Optional[float]
    ph_class: Optional[str]
    soc_g_per_kg: Optional[float]
    soc_class: Optional[str]
    clay_pct: Optional[float]
    sand_pct: Optional[float]
    nitrogen_g_per_kg: Optional[float]
    texture_class: Optional[str]
    suitability_score: Optional[float]
    profile_source: str
    advice: list[str]
