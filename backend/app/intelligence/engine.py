"""
app/intelligence/engine.py
--------------------------
Crop Intelligence Engine — the single source of truth for all crop analytics.

This engine is the ONLY component that makes decisions about:
- Crop type and confidence
- Growth stage (via state machine)
- Harvest status (via harvest detector)
- Stress assessment
- Health score
- Expected yield

No other component in the system should independently compute these values.
All downstream consumers (API, LLM, dashboard) read from the engine's output.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Optional

import numpy as np
from sqlalchemy.orm import Session

from app.intelligence.models import (
    LandIntelligenceReport,
    ZoneIntelligence,
    StressAssessment,
    HarvestRecord,
)

logger = logging.getLogger(__name__)

# Path to crop profiles
_PROFILES_PATH = Path(__file__).resolve().parent.parent / "data" / "reference" / "crop_profiles.json"


def _load_crop_profiles() -> dict:
    """Load crop profiles from JSON. Returns empty dict on failure."""
    try:
        with open(_PROFILES_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        logger.warning("Could not load crop profiles: %s", exc)
        return {}


class CropIntelligenceEngine:
    """
    Single source of truth for all crop intelligence.

    Pipeline:
    1. Fetch preprocessed observations (from sentinel connector)
    2. Build clean time-series (smoothed, quality-filtered)
    3. Extract features
    4. Run ML crop classification (per tile)
    5. Aggregate tiles into zones
    6. For each zone:
       a. Determine crop type + confidence
       b. Run state machine for growth stage
       c. Run harvest detector
       d. Assess stress levels
       e. Compute health score
       f. Estimate yield
    7. Run consistency validator across all zones
    8. Store and return unified LandIntelligenceReport
    """

    def __init__(self):
        self.crop_profiles = _load_crop_profiles()
        # Lazy imports to avoid circular dependencies
        self._state_machine = None
        self._harvest_detector = None
        self._validator = None

    @property
    def state_machine(self):
        if self._state_machine is None:
            from app.intelligence.state_machine import GrowthStateMachine
            self._state_machine = GrowthStateMachine(self.crop_profiles)
        return self._state_machine

    @property
    def harvest_detector(self):
        if self._harvest_detector is None:
            from app.intelligence.harvest_detector import HarvestDetector
            self._harvest_detector = HarvestDetector(self.crop_profiles)
        return self._harvest_detector

    @property
    def validator(self):
        if self._validator is None:
            from app.intelligence.validator import ConsistencyValidator
            self._validator = ConsistencyValidator(self.crop_profiles)
        return self._validator

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def analyze_land(
        self,
        land_id: int,
        db: Session,
        run_pipeline: bool = False,
        *,
        persist: bool = True,
    ) -> LandIntelligenceReport:
        """
        Run the complete intelligence pipeline for a land.
        Returns a fully validated, consistent LandIntelligenceReport.

        When ``persist=False``, zone records are not updated (read-only analysis).
        """
        from app.models.land import Land
        from app.models.land_crop import LandCrop
        from app.models.crop_zone import CropZone
        from app.models.land_climate import LandClimate
        from app.models.land_soil import LandSoil

        land = db.query(Land).filter(Land.land_id == land_id).first()
        if not land:
            logger.warning("Land %s not found", land_id)
            return LandIntelligenceReport(land_id=land_id)

        report = LandIntelligenceReport(
            land_id=land_id,
            report_date=datetime.utcnow(),
        )

        # --- Step 1: Run the ML crop detection pipeline if requested ---
        if run_pipeline:
            try:
                self._run_data_pipeline(land_id, db)
            except Exception as exc:
                logger.error("Data pipeline failed for land %s: %s", land_id, exc)
                report.validator_warnings.append(f"Data pipeline error: {exc}")

        # --- Step 2: Load all data from DB ---
        crop_zones = (
            db.query(CropZone)
            .filter(CropZone.land_id == land_id, CropZone.status == "active")
            .order_by(CropZone.area_pct.desc())
            .all()
        )

        crop_rows = (
            db.query(LandCrop)
            .filter(LandCrop.land_id == land_id)
            .order_by(LandCrop.timestamp.asc())
            .all()
        )

        # --- Step 3: Build per-zone intelligence ---
        if crop_zones:
            for cz in crop_zones:
                zone_intel = self._analyze_zone(cz, crop_rows, land)
                report.zones.append(zone_intel)
        else:
            # No zones detected — create a single fallback zone
            zone_intel = self._analyze_fallback(crop_rows, land)
            report.zones.append(zone_intel)

        # --- Step 4: Run consistency validator ---
        all_warnings = []
        for zone in report.zones:
            zone_dict = zone.to_dict()
            warnings = self.validator.validate(zone_dict)

            # Apply corrections back to the zone object
            zone.growth_stage = zone_dict.get("growth_stage", zone.growth_stage)
            zone.harvest_status = zone_dict.get("harvest_status", zone.harvest_status)
            zone.health_score = zone_dict.get("health_score", zone.health_score)
            zone.stress.level = zone_dict.get("stress_level", zone.stress.level)
            zone.needs_review = zone_dict.get("needs_review", zone.needs_review)

            zone.flags.extend(warnings)
            all_warnings.extend(warnings)

        report.validator_warnings = all_warnings

        # --- Step 5: Compute overall metrics ---
        if report.zones:
            total_area = sum(z.area_pct for z in report.zones) or 1
            report.overall_health = int(
                sum(z.health_score * z.area_pct for z in report.zones) / total_area
            )
            report.overall_confidence = round(
                sum(z.crop_confidence * z.area_pct for z in report.zones) / total_area, 2
            )

        # --- Step 6: Weather summary ---
        report.weather_summary = self._build_weather_summary(land_id, db)

        # --- Step 7: Compute data quality ---
        report.data_quality_score = self._compute_data_quality(crop_rows)

        # --- Step 8–9: Persist report + update crop zones (optional) ---
        if persist:
            self._store_report(report, db)
            self._update_crop_zones(report, db)

        logger.info(
            "Intelligence report for land %s: %d zones, overall_health=%d, confidence=%.2f, warnings=%d",
            land_id, len(report.zones), report.overall_health,
            report.overall_confidence, len(report.validator_warnings),
        )
        return report

    # ------------------------------------------------------------------
    # Per-zone analysis
    # ------------------------------------------------------------------

    def _analyze_zone(
        self, cz, crop_rows: list, land
    ) -> ZoneIntelligence:
        """Analyze a single crop zone using all available data."""
        crop_type = cz.crop_type or "Unknown"
        profile = self.crop_profiles.get(crop_type.lower(), {})

        # Filter crop rows for this zone (or fallback to all if no zone_id match)
        zone_rows = [r for r in crop_rows if r.zone_id == cz.zone_id]
        if not zone_rows:
            zone_rows = crop_rows  # fallback

        # Build NDVI time-series
        ndvi_series = [float(r.ndvi_value) for r in zone_rows if r.ndvi_value is not None]
        dates = [r.timestamp.strftime("%Y-%m-%d") for r in zone_rows if r.ndvi_value is not None]

        # Current NDVI — prefer latest observation over stale zone snapshot
        ndvi_current = (
            ndvi_series[-1] if ndvi_series else (
                float(cz.latest_ndvi) if cz.latest_ndvi else 0.0
            )
        )

        # NDVI trend
        ndvi_trend = self._compute_trend(ndvi_series)

        # NDVI peak
        ndvi_peak = max(ndvi_series) if ndvi_series else 0.0

        # Previous NDVI (for state machine)
        ndvi_previous = ndvi_series[-2] if len(ndvi_series) >= 2 else None

        # --- Growth stage via state machine ---
        previous_stage = cz.latest_growth_stage or None
        days_in_stage = self._estimate_days_in_stage(cz)

        growth_stage, growth_confidence, growth_reason = self.state_machine.determine_stage(
            current_stage=previous_stage,
            ndvi_current=ndvi_current,
            ndvi_previous=ndvi_previous,
            ndvi_peak=profile.get("ndvi_peak", 0.70),
            crop_type=crop_type,
            days_in_current_stage=days_in_stage,
        )

        # --- Harvest detection ---
        harvest_events = self.harvest_detector.detect_harvest_events(
            ndvi_series, dates, crop_type
        )

        harvest_status = "not_harvested"
        harvest_confidence = 0.5
        last_harvest_date = None
        next_harvest_est = None
        next_harvest_days = None
        harvest_count = len(harvest_events)

        if harvest_events:
            latest_event = harvest_events[-1]
            last_harvest_date = latest_event.date
            harvest_confidence = latest_event.confidence

            # Determine if the LAST event is recent (within 30 days)
            days_since = (date.today() - latest_event.date).days if latest_event.date else 999
            if days_since < 30:
                harvest_status = "completed"
            elif growth_stage in ("harvest_ready", "maturity"):
                harvest_status = "approaching"

        # Predict next harvest
        prediction = self.harvest_detector.predict_next_harvest(
            last_harvest=harvest_events[-1] if harvest_events else None,
            crop_type=crop_type,
            ndvi_current=ndvi_current,
            ndvi_trend=ndvi_trend,
            current_growth_stage=growth_stage,
        )
        if prediction:
            next_harvest_est = prediction.estimated_date
            next_harvest_days = prediction.days_remaining

        # --- Stress assessment ---
        stress = self._assess_stress(ndvi_current, ndvi_trend, ndvi_peak, profile)

        # --- Health score ---
        health_score = self._compute_health_score(
            ndvi_current, growth_stage, profile
        )

        # --- Confidence ---
        crop_confidence = float(cz.avg_confidence) if cz.avg_confidence else 0.75
        crop_confidence = self._adjust_confidence(
            crop_confidence,
            self._compute_data_quality_for_series(ndvi_series),
            len(ndvi_series),
        )

        return ZoneIntelligence(
            zone_id=cz.zone_id,
            crop_type=crop_type,
            crop_confidence=round(crop_confidence, 2),
            area_pct=float(cz.area_pct) if cz.area_pct else 0.0,
            area_hectares=float(cz.area_hectares) if cz.area_hectares else None,
            growth_stage=growth_stage,
            growth_stage_confidence=round(growth_confidence, 2),
            days_in_stage=days_in_stage,
            harvest_status=harvest_status,
            harvest_confidence=round(harvest_confidence, 2),
            last_harvest_date=last_harvest_date,
            next_harvest_est=next_harvest_est,
            next_harvest_days=next_harvest_days,
            harvest_count=harvest_count,
            health_score=health_score,
            stress=stress,
            ndvi_current=round(ndvi_current, 4),
            ndvi_trend=ndvi_trend,
            ndvi_peak=round(ndvi_peak, 4) if ndvi_peak else None,
        )

    def _analyze_fallback(self, crop_rows: list, land) -> ZoneIntelligence:
        """Create a single zone intelligence from raw crop data (no zones detected)."""
        ndvi_series = [float(r.ndvi_value) for r in crop_rows if r.ndvi_value is not None]
        dates = [r.timestamp.strftime("%Y-%m-%d") for r in crop_rows if r.ndvi_value is not None]

        ndvi_current = ndvi_series[-1] if ndvi_series else 0.0
        ndvi_trend = self._compute_trend(ndvi_series)
        ndvi_peak = max(ndvi_series) if ndvi_series else 0.0

        crop_type = "Unknown"
        if crop_rows:
            last_row = crop_rows[-1]
            crop_type = last_row.crop_type or "Unknown"

        growth_stage, growth_conf, _ = self.state_machine.determine_stage(
            current_stage=None,
            ndvi_current=ndvi_current,
            ndvi_previous=ndvi_series[-2] if len(ndvi_series) >= 2 else None,
            ndvi_peak=0.70,
            crop_type=crop_type,
        )

        harvest_events = self.harvest_detector.detect_harvest_events(
            ndvi_series, dates, crop_type
        )

        next_harvest_est = None
        next_harvest_days = None
        harvest_status = "completed" if harvest_events else "not_harvested"
        if harvest_events:
            latest_event = harvest_events[-1]
            days_since = (date.today() - latest_event.date).days if latest_event.date else 999
            if days_since >= 30:
                harvest_status = "not_harvested"

        prediction = self.harvest_detector.predict_next_harvest(
            last_harvest=harvest_events[-1] if harvest_events else None,
            crop_type=crop_type,
            ndvi_current=ndvi_current,
            ndvi_trend=ndvi_trend,
            current_growth_stage=growth_stage,
        )
        if prediction:
            next_harvest_est = prediction.estimated_date
            next_harvest_days = prediction.days_remaining

        return ZoneIntelligence(
            zone_id=0,
            crop_type=crop_type,
            crop_confidence=0.50,
            area_pct=100.0,
            area_hectares=float(land.area_hectares) if land.area_hectares else None,
            growth_stage=growth_stage,
            growth_stage_confidence=round(growth_conf, 2),
            harvest_status=harvest_status,
            harvest_count=len(harvest_events),
            last_harvest_date=harvest_events[-1].date if harvest_events else None,
            next_harvest_est=next_harvest_est,
            next_harvest_days=next_harvest_days,
            health_score=self._compute_health_score(ndvi_current, growth_stage, {}),
            stress=self._assess_stress(ndvi_current, ndvi_trend, ndvi_peak, {}),
            ndvi_current=round(ndvi_current, 4),
            ndvi_trend=ndvi_trend,
            ndvi_peak=round(ndvi_peak, 4),
            needs_review=True,
            flags=["No crop zones detected — using fallback analysis"],
        )

    # ------------------------------------------------------------------
    # Sub-routines
    # ------------------------------------------------------------------

    def _run_data_pipeline(self, land_id: int, db: Session):
        """Run the satellite data + ML pipeline (existing tasks)."""
        from app.connectors.sentinel import fetch_sentinel_timeseries
        from app.tasks.satellite_task import run_ndvi_history_backfill
        from app.tasks.crop_task import run_crop_detection_task

        # Wipe stale crop data for clean re-analysis
        from sqlalchemy import text
        db.execute(text("DELETE FROM land_crops WHERE land_id=:lid"), {"lid": land_id})
        db.commit()

        # Run existing pipelines (they write to DB)
        run_ndvi_history_backfill(land_id, db, days=90)
        run_crop_detection_task(land_id, db, days=90)

    def _compute_trend(self, ndvi_series: list[float]) -> str:
        """Compute trend from NDVI time-series."""
        if len(ndvi_series) < 3:
            return "stable"
        recent = ndvi_series[-5:]  # last 5 observations
        if len(recent) < 2:
            return "stable"
        slope = (recent[-1] - recent[0]) / len(recent)
        if slope > 0.005:
            return "improving"
        elif slope < -0.005:
            return "declining"
        return "stable"

    def _estimate_days_in_stage(self, cz) -> int:
        """Estimate how many days the zone has been in the current growth stage."""
        if cz.last_updated:
            delta = datetime.utcnow() - cz.last_updated
            return delta.days
        return 30  # default

    def _assess_stress(
        self, ndvi_current: float, ndvi_trend: str, ndvi_peak: float, profile: dict
    ) -> StressAssessment:
        """Assess crop stress based on NDVI dynamics and crop expectations."""
        ndvi_min_healthy = profile.get("ndvi_min_healthy", 0.30)

        if ndvi_current < ndvi_min_healthy * 0.6:
            level = "critical"
            confidence = 0.85
        elif ndvi_current < ndvi_min_healthy:
            level = "high"
            confidence = 0.80
        elif ndvi_trend == "declining" and ndvi_current < ndvi_peak * 0.7:
            level = "moderate"
            confidence = 0.70
        elif ndvi_trend == "declining":
            level = "low"
            confidence = 0.60
        else:
            level = "none"
            confidence = 0.85

        # Determine stress type heuristic
        stress_type = None
        if level in ("moderate", "high", "critical"):
            # Without specific spectral indices for nutrient stress,
            # default to water stress (most common in arid regions)
            stress_type = "water"

        return StressAssessment(level=level, stress_type=stress_type, confidence=confidence)

    def _compute_health_score(
        self, ndvi_current: float, growth_stage: str, profile: dict
    ) -> int:
        """Compute a 0-100 health score."""
        # Post-harvest: low NDVI is expected, not unhealthy
        if growth_stage in ("harvested", "bare_soil"):
            return 50  # neutral — not a health concern

        # Scale NDVI to 0-100, clamped
        raw_score = max(0, min(100, int(ndvi_current * 120)))

        # Adjust based on expected NDVI for crop
        ndvi_peak = profile.get("ndvi_peak", 0.70)
        if ndvi_current >= ndvi_peak * 0.85:
            raw_score = max(raw_score, 85)  # Boost if near peak
        elif ndvi_current < profile.get("ndvi_min_healthy", 0.30):
            raw_score = min(raw_score, 40)  # Cap if below healthy minimum

        return raw_score

    def _adjust_confidence(
        self, ml_confidence: float, data_quality: float, n_observations: int
    ) -> float:
        """Adjust ML confidence by data quality and observation count."""
        obs_factor = min(1.0, n_observations / 10)  # need ≥10 for full confidence
        return round(ml_confidence * max(0.5, data_quality) * obs_factor, 2)

    def _compute_data_quality(self, crop_rows: list) -> float:
        """Compute overall data quality score from observation count + spread."""
        if not crop_rows:
            return 0.0
        n = len(crop_rows)
        # More observations = higher quality, capped at 1.0 for 30+ observations
        return round(min(1.0, n / 30), 2)

    def _compute_data_quality_for_series(self, ndvi_series: list) -> float:
        """Quality score for a single NDVI series."""
        n = len(ndvi_series)
        if n == 0:
            return 0.0
        return round(min(1.0, n / 10), 2)

    def _build_weather_summary(self, land_id: int, db: Session) -> dict:
        """Build weather summary from recent climate and soil data."""
        from app.models.land_climate import LandClimate
        from app.models.land_soil import LandSoil

        summary = {}

        climate_rows = (
            db.query(LandClimate)
            .filter(LandClimate.land_id == land_id)
            .order_by(LandClimate.timestamp.desc())
            .limit(30)
            .all()
        )
        if climate_rows:
            temps = [float(r.temperature_celsius) for r in climate_rows if r.temperature_celsius is not None]
            humidity = [
                float(r.humidity_pct)
                for r in climate_rows
                if r.humidity_pct is not None
            ]
            rainfall = [
                float(r.rainfall_mm)
                for r in climate_rows
                if r.rainfall_mm is not None
            ]
            summary["avg_temp_c"] = round(sum(temps) / len(temps), 1) if temps else None
            summary["max_temp_c"] = round(max(temps), 1) if temps else None
            summary["avg_humidity_pct"] = round(sum(humidity) / len(humidity), 1) if humidity else None
            summary["total_rainfall_mm"] = round(sum(rainfall), 1) if rainfall else 0

        soil_rows = (
            db.query(LandSoil)
            .filter(LandSoil.land_id == land_id)
            .order_by(LandSoil.timestamp.desc())
            .limit(10)
            .all()
        )
        if soil_rows:
            moistures = [float(r.moisture_pct) for r in soil_rows if r.moisture_pct is not None]
            summary["avg_soil_moisture_pct"] = (
                round(sum(moistures) / len(moistures), 1) if moistures else None
            )

        return summary

    def _store_report(self, report: LandIntelligenceReport, db: Session):
        """Persist the intelligence report to the database. (Skipped: table does not exist yet)"""
        pass

    def _update_crop_zones(self, report: LandIntelligenceReport, db: Session):
        """Update CropZone records with validated intelligence from the report."""
        from app.models.crop_zone import CropZone

        for zone in report.zones:
            if zone.zone_id == 0:
                continue  # fallback zone, no DB record
            cz = db.query(CropZone).filter(CropZone.zone_id == zone.zone_id).first()
            if cz:
                cz.latest_ndvi = zone.ndvi_current
                cz.latest_growth_stage = zone.growth_stage
                cz.estimated_yield_tons = zone.expected_yield_tons
                cz.last_updated = datetime.utcnow()
                db.add(cz)

        try:
            db.flush()
        except Exception as exc:
            logger.warning("Could not update crop zones: %s", exc)
