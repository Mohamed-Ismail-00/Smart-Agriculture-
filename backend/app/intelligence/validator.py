import logging
from typing import Optional

logger = logging.getLogger(__name__)

class ConsistencyValidator:
    """
    Post-prediction validator that cross-checks all fields in a zone's intelligence
    and fixes impossible states.
    """
    
    def __init__(self, crop_profiles: dict):
        self.crop_profiles = crop_profiles
    
    def validate(self, zone: dict) -> list[str]:
        """
        Run all validation rules on a zone intelligence dict.
        May MODIFY the zone in-place to fix contradictions.
        Returns list of warnings/corrections applied.
        """
        warnings = []
        
        rules = [
            self._rule_harvested_but_ndvi_rising,
            self._rule_harvest_ready_but_low_ndvi,
            self._rule_early_veg_but_high_ndvi,
            self._rule_stress_vs_health,
            self._rule_confidence_threshold,
            self._rule_ndvi_vs_health_score,
            self._rule_bare_soil_with_growth,
            self._rule_flowering_but_ndvi_too_low,
        ]
        
        for rule in rules:
            result = rule(zone)
            if result:
                warnings.append(result)
        
        return warnings
    
    def _rule_harvested_but_ndvi_rising(self, zone: dict) -> Optional[str]:
        """IF harvested AND ndvi_trend == 'improving' → change to 'regrowth' for perennials"""
        if zone.get("growth_stage") == "harvested" and zone.get("ndvi_trend") == "improving":
            crop = zone.get("crop_type", "").lower()
            profile = self.crop_profiles.get(crop, {})
            lifecycle = profile.get("lifecycle", "annual")
            
            if lifecycle == "perennial":
                zone["growth_stage"] = "regrowth"
                return f"Corrected: harvested + rising NDVI → regrowth (perennial {crop})"
            else:
                zone["growth_stage"] = "bare_soil"
                return f"Corrected: harvested + rising NDVI → bare_soil (annual {crop}, possible replanting)"
        return None
    
    def _rule_harvest_ready_but_low_ndvi(self, zone: dict) -> Optional[str]:
        """IF harvest_ready AND ndvi < 0.20 → already harvested"""
        if zone.get("growth_stage") == "harvest_ready" and zone.get("ndvi_current", 1.0) < 0.20:
            zone["growth_stage"] = "harvested"
            zone["harvest_status"] = "completed"
            return f"Corrected: harvest_ready + NDVI {zone.get('ndvi_current'):.2f} < 0.20 → harvested"
        return None
    
    def _rule_early_veg_but_high_ndvi(self, zone: dict) -> Optional[str]:
        """IF early_vegetative AND ndvi > 0.65 → upgrade to vegetative or flowering"""
        ndvi = zone.get("ndvi_current", 0)
        if zone.get("growth_stage") == "early_vegetative" and ndvi > 0.65:
            if ndvi > 0.75:
                zone["growth_stage"] = "flowering"
                return f"Corrected: early_vegetative + NDVI {ndvi:.2f} > 0.75 → flowering"
            else:
                zone["growth_stage"] = "vegetative"
                return f"Corrected: early_vegetative + NDVI {ndvi:.2f} > 0.65 → vegetative"
        return None
    
    def _rule_stress_vs_health(self, zone: dict) -> Optional[str]:
        """IF stress_level == 'high' AND health_score > 80 → reduce stress"""
        if zone.get("stress_level") == "high" and zone.get("health_score", 0) > 80:
            zone["stress_level"] = "low"
            return f"Corrected: stress=high contradicts health_score={zone.get('health_score')} → stress=low"
        if zone.get("stress_level") == "none" and zone.get("health_score", 100) < 40:
            zone["stress_level"] = "moderate"
            return f"Corrected: stress=none contradicts health_score={zone.get('health_score')} → stress=moderate"
        return None
    
    def _rule_confidence_threshold(self, zone: dict) -> Optional[str]:
        """IF any confidence < 0.60 → set needs_review = True"""
        confidences = [
            zone.get("crop_confidence", 1.0),
            zone.get("growth_stage_confidence", 1.0),
            zone.get("harvest_confidence", 1.0),
            zone.get("stress_confidence", 1.0),
        ]
        min_conf = min(confidences)
        if min_conf < 0.60:
            zone["needs_review"] = True
            return f"Low confidence ({min_conf:.2f}) — marked for manual review"
        return None
    
    def _rule_ndvi_vs_health_score(self, zone: dict) -> Optional[str]:
        """Ensure health_score is consistent with NDVI"""
        ndvi = zone.get("ndvi_current", 0)
        health = zone.get("health_score", 0)
        # Don't check post-harvest zones
        if zone.get("growth_stage") in ("harvested", "bare_soil"):
            return None
        
        expected_health = min(100, max(0, int(ndvi * 120)))  # rough NDVI->health mapping
        if abs(health - expected_health) > 30:
            zone["health_score"] = expected_health
            return f"Corrected: health_score {health} inconsistent with NDVI {ndvi:.2f} → {expected_health}"
        return None
    
    def _rule_bare_soil_with_growth(self, zone: dict) -> Optional[str]:
        """IF bare_soil AND ndvi > 0.30 → something is growing"""
        if zone.get("growth_stage") == "bare_soil" and zone.get("ndvi_current", 0) > 0.30:
            zone["growth_stage"] = "early_vegetative"
            return f"Corrected: bare_soil + NDVI {zone.get('ndvi_current'):.2f} > 0.30 → early_vegetative"
        return None
    
    def _rule_flowering_but_ndvi_too_low(self, zone: dict) -> Optional[str]:
        """IF flowering AND ndvi < 0.35 → can't be flowering"""
        if zone.get("growth_stage") == "flowering" and zone.get("ndvi_current", 1.0) < 0.35:
            zone["growth_stage"] = "maturity"
            return f"Corrected: flowering + NDVI {zone.get('ndvi_current'):.2f} < 0.35 → maturity (declining)"
        return None
