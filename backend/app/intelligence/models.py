"""
app/intelligence/models.py
--------------------------
Dataclass models for the Crop Intelligence Engine output.
These represent the single source of truth for all crop analytics.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional


@dataclass
class HarvestRecord:
    """A detected or predicted harvest event."""
    date: Optional[date] = None
    ndvi_before: Optional[float] = None
    ndvi_after: Optional[float] = None
    confidence: float = 0.0
    harvest_number: int = 1
    is_detected: bool = False   # True = detected from NDVI drop, False = predicted


@dataclass
class StressAssessment:
    """Stress assessment for a crop zone."""
    level: str = "none"          # none | low | moderate | high | critical
    stress_type: Optional[str] = None  # water | nutrient | heat | unknown
    confidence: float = 0.0


@dataclass
class ZoneIntelligence:
    """
    Complete intelligence for a single crop zone.
    This is the ONLY structure any downstream system should read for crop decisions.
    """
    zone_id: int = 0
    crop_type: str = "Unknown"
    crop_confidence: float = 0.0
    area_pct: float = 0.0
    area_hectares: Optional[float] = None

    # Growth stage (from state machine)
    growth_stage: str = "unknown"
    growth_stage_confidence: float = 0.0
    days_in_stage: int = 0

    # Harvest intelligence
    harvest_status: str = "not_harvested"   # not_harvested | approaching | completed
    harvest_confidence: float = 0.0
    last_harvest_date: Optional[date] = None
    next_harvest_est: Optional[date] = None
    next_harvest_days: Optional[int] = None
    harvest_count: int = 0                  # total harvests detected (for perennials)

    # Health & stress
    health_score: int = 0                   # 0–100
    stress: StressAssessment = field(default_factory=StressAssessment)

    # Spectral
    ndvi_current: float = 0.0
    ndvi_trend: str = "stable"              # improving | stable | declining
    ndvi_peak: Optional[float] = None

    # Yield
    expected_yield_tons: Optional[float] = None

    # Validation
    flags: list[str] = field(default_factory=list)
    needs_review: bool = False              # True if any confidence < 0.60

    def to_dict(self) -> dict:
        """Serialize to dict for API/JSON output."""
        return {
            "zone_id": self.zone_id,
            "crop_type": self.crop_type,
            "crop_confidence": self.crop_confidence,
            "area_pct": self.area_pct,
            "area_hectares": self.area_hectares,
            "growth_stage": self.growth_stage,
            "growth_stage_confidence": self.growth_stage_confidence,
            "days_in_stage": self.days_in_stage,
            "harvest_status": self.harvest_status,
            "harvest_confidence": self.harvest_confidence,
            "last_harvest_date": self.last_harvest_date.isoformat() if self.last_harvest_date else None,
            "next_harvest_est": self.next_harvest_est.isoformat() if self.next_harvest_est else None,
            "next_harvest_days": self.next_harvest_days,
            "harvest_count": self.harvest_count,
            "health_score": self.health_score,
            "stress": {
                "level": self.stress.level,
                "type": self.stress.stress_type,
                "confidence": self.stress.confidence,
            },
            "ndvi_current": self.ndvi_current,
            "ndvi_trend": self.ndvi_trend,
            "ndvi_peak": self.ndvi_peak,
            "expected_yield_tons": self.expected_yield_tons,
            "flags": self.flags,
            "needs_review": self.needs_review,
        }


@dataclass
class LandIntelligenceReport:
    """
    The complete intelligence report for a land.
    Produced by the CropIntelligenceEngine — the single source of truth.
    """
    land_id: int = 0
    report_date: datetime = field(default_factory=datetime.utcnow)
    zones: list[ZoneIntelligence] = field(default_factory=list)
    overall_health: int = 0
    overall_confidence: float = 0.0
    data_quality_score: float = 0.0
    validator_warnings: list[str] = field(default_factory=list)

    # Weather summary (for LLM context)
    weather_summary: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Serialize to dict for API/JSON output and DB storage."""
        return {
            "land_id": self.land_id,
            "report_date": self.report_date.isoformat(),
            "zones": [z.to_dict() for z in self.zones],
            "overall_health": self.overall_health,
            "overall_confidence": self.overall_confidence,
            "data_quality_score": self.data_quality_score,
            "validator_warnings": self.validator_warnings,
            "weather_summary": self.weather_summary,
        }

    @property
    def primary_zone(self) -> Optional[ZoneIntelligence]:
        """Return the zone with the largest area percentage."""
        if not self.zones:
            return None
        return max(self.zones, key=lambda z: z.area_pct)
