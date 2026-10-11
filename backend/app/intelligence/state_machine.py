"""
app/intelligence/state_machine.py
---------------------------------
Finite State Machine for crop growth lifecycle.
Ensures only valid transitions occur and prevents impossible states.
"""

import logging
from typing import Optional
from datetime import date

logger = logging.getLogger(__name__)

# Valid transitions per lifecycle type
ANNUAL_TRANSITIONS = {
    "bare_soil":        ["planting"],
    "planting":         ["emergence"],
    "emergence":        ["early_vegetative"],
    "early_vegetative": ["vegetative"],
    "vegetative":       ["flowering"],
    "flowering":        ["grain_fill"],
    "grain_fill":       ["maturity"],
    "maturity":         ["harvest_ready"],
    "harvest_ready":    ["harvested"],
    "harvested":        ["bare_soil", "planting"],
}

PERENNIAL_TRANSITIONS = {
    "bare_soil":        ["planting"],
    "planting":         ["emergence"],
    "emergence":        ["early_vegetative"],
    "early_vegetative": ["vegetative"],
    "vegetative":       ["mature", "flowering"],
    "flowering":        ["mature"],
    "mature":           ["harvest_ready"],
    "harvest_ready":    ["harvested"],
    "harvested":        ["regrowth"],
    "regrowth":         ["vegetative"],
}

FALLOW_TRANSITIONS = {
    "bare_soil":        ["bare_soil", "planting"],
    "fallow":           ["bare_soil", "planting"],
}

# Minimum days in each stage before allowing transition (prevents flickering)
MIN_DAYS_IN_STAGE = {
    "planting": 5,
    "emergence": 7,
    "early_vegetative": 10,
    "vegetative": 14,
    "flowering": 7,
    "grain_fill": 14,
    "maturity": 7,
    "harvest_ready": 3,
    "harvested": 5,
    "regrowth": 7,
    "mature": 7,
    "bare_soil": 3,
    "fallow": 3,
}

# NDVI thresholds that indicate specific stage transitions
NDVI_STAGE_INDICATORS = {
    "bare_soil": (0.0, 0.12),       # NDVI range for bare soil
    "emergence": (0.10, 0.25),
    "early_vegetative": (0.20, 0.40),
    "vegetative": (0.35, 0.70),
    "flowering": (0.60, 0.85),
    "grain_fill": (0.50, 0.80),
    "maturity": (0.35, 0.65),
    "harvest_ready": (0.25, 0.50),
    "harvested": (0.05, 0.30),
    "regrowth": (0.15, 0.45),
}

class GrowthStateMachine:
    """
    Finite State Machine for crop growth lifecycle.
    Ensures only valid transitions occur and prevents impossible states.
    """
    
    def __init__(self, crop_profiles: dict):
        self.crop_profiles = crop_profiles
    
    def get_lifecycle_type(self, crop_type: str) -> str:
        """Get lifecycle type from crop profiles."""
        key = crop_type.lower()
        profile = self.crop_profiles.get(key, {})
        return profile.get("lifecycle", "annual")
    
    def get_transitions(self, lifecycle: str) -> dict:
        """Get valid transitions for a lifecycle type."""
        if lifecycle == "perennial":
            return PERENNIAL_TRANSITIONS
        elif lifecycle == "fallow":
            return FALLOW_TRANSITIONS
        return ANNUAL_TRANSITIONS
    
    def is_valid_transition(self, current: str, proposed: str, lifecycle: str) -> bool:
        """Check if a transition is valid."""
        transitions = self.get_transitions(lifecycle)
        valid_next = transitions.get(current, [])
        return proposed in valid_next
    
    def determine_stage(
        self,
        current_stage: Optional[str],
        ndvi_current: float,
        ndvi_previous: Optional[float],
        ndvi_peak: float,
        crop_type: str,
        days_in_current_stage: int = 0,
    ) -> tuple:  # Returns (new_stage, confidence, reason)
        """
        Determine the correct growth stage based on:
        - Current state (previous stage)
        - NDVI values (current and trajectory)
        - Valid transitions for the crop's lifecycle
        - Minimum days in stage (anti-flicker)
        
        Returns: (stage: str, confidence: float, reason: str)
        """
        lifecycle = self.get_lifecycle_type(crop_type)
        transitions = self.get_transitions(lifecycle)
        
        # If no current stage, determine from NDVI alone
        if not current_stage:
            return self._infer_initial_stage(ndvi_current, crop_type)
        
        # Check minimum days in current stage
        min_days = MIN_DAYS_IN_STAGE.get(current_stage, 5)
        if days_in_current_stage < min_days:
            return (current_stage, 0.7, f"Minimum {min_days} days in {current_stage} not reached")
        
        # Determine candidate next stage from NDVI trajectory
        ndvi_trend = "stable"
        if ndvi_previous is not None:
            diff = ndvi_current - ndvi_previous
            if diff > 0.03:
                ndvi_trend = "rising"
            elif diff < -0.03:
                ndvi_trend = "falling"
        
        candidate = self._propose_next_stage(current_stage, ndvi_current, ndvi_trend, ndvi_peak, lifecycle)
        
        # Validate transition
        if candidate == current_stage:
            return (current_stage, 0.8, "No transition warranted")
        
        if self.is_valid_transition(current_stage, candidate, lifecycle):
            confidence = self._compute_transition_confidence(current_stage, candidate, ndvi_current)
            return (candidate, confidence, f"Valid transition: {current_stage} -> {candidate}")
        
        # Invalid transition — stay in current stage and log
        logger.warning(
            "Blocked invalid transition %s -> %s for %s (lifecycle=%s)",
            current_stage, candidate, crop_type, lifecycle
        )
        return (current_stage, 0.5, f"Blocked invalid: {current_stage} -> {candidate}")
    
    def _infer_initial_stage(self, ndvi: float, crop_type: str) -> tuple:
        """Determine stage from NDVI alone when no history exists."""
        if ndvi < 0.12:
            return ("bare_soil", 0.8, "Initial: NDVI < 0.12")
        elif ndvi < 0.25:
            return ("emergence", 0.6, "Initial: NDVI 0.12-0.25")
        elif ndvi < 0.40:
            return ("early_vegetative", 0.6, "Initial: NDVI 0.25-0.40")
        elif ndvi < 0.60:
            return ("vegetative", 0.7, "Initial: NDVI 0.40-0.60")
        elif ndvi < 0.75:
            return ("flowering", 0.6, "Initial: NDVI 0.60-0.75")
        else:
            return ("mature", 0.6, "Initial: NDVI >= 0.75")
    
    def _propose_next_stage(self, current: str, ndvi: float, trend: str, ndvi_peak: float, lifecycle: str) -> str:
        """Propose the most likely next stage based on NDVI dynamics."""
        # Large sudden drop = harvest event
        if current in ("maturity", "harvest_ready", "mature") and ndvi < 0.30 and trend == "falling":
            return "harvested"
        
        # Post-harvest rising NDVI = regrowth (perennial) or new planting
        if current == "harvested" and trend == "rising":
            if lifecycle == "perennial":
                return "regrowth"
            return "bare_soil"  # will transition to planting
        
        # Rising NDVI in early stages = progressing forward
        if trend == "rising":
            transitions = self.get_transitions(lifecycle)
            valid_next = transitions.get(current, [])
            if valid_next:
                return valid_next[0]  # First valid next stage
        
        # Falling NDVI in late stages = approaching harvest
        if trend == "falling" and current in ("flowering", "grain_fill"):
            transitions = self.get_transitions(lifecycle)
            valid_next = transitions.get(current, [])
            if valid_next:
                return valid_next[0]
        
        # NDVI below bare soil threshold
        if ndvi < 0.12 and current not in ("harvested", "bare_soil"):
            return "harvested" if current in ("maturity", "harvest_ready", "mature") else current
        
        return current  # Stay in current stage
    
    def _compute_transition_confidence(self, from_stage: str, to_stage: str, ndvi: float) -> float:
        """Compute confidence for a transition based on how well NDVI matches the target stage."""
        expected_range = NDVI_STAGE_INDICATORS.get(to_stage, (0, 1))
        ndvi_min, ndvi_max = expected_range
        
        if ndvi_min <= ndvi <= ndvi_max:
            return 0.90  # NDVI is in expected range for target stage
        elif abs(ndvi - ndvi_min) < 0.10 or abs(ndvi - ndvi_max) < 0.10:
            return 0.70  # Close to expected range
        else:
            return 0.50  # NDVI doesn't match well, but transition is structurally valid
