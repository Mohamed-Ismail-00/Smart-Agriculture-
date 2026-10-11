import numpy as np
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

@dataclass
class HarvestEvent:
    date: date
    ndvi_before: float
    ndvi_after: float
    drop_magnitude: float
    confidence: float
    harvest_number: int  # 1st, 2nd, 3rd cut for perennials

@dataclass
class HarvestPrediction:
    estimated_date: date
    days_remaining: int
    confidence: float
    based_on: str  # "crop_profile" | "historical_pattern" | "ndvi_trajectory"

class HarvestDetector:
    """
    Detects harvest events from NDVI time-series drops.
    Also predicts future harvest windows based on crop profiles.
    """
    
    def __init__(self, crop_profiles: dict):
        self.crop_profiles = crop_profiles
    
    def detect_harvest_events(
        self,
        ndvi_series: list[float],
        dates: list[str],
        crop_type: str,
    ) -> list[HarvestEvent]:
        """
        Detect actual harvest events from NDVI drops.
        
        Algorithm:
        1. Compute first differences of (smoothed) NDVI
        2. Find points where NDVI drops exceed the crop's harvest_ndvi_drop threshold
        3. Verify drop is sustained (not just noise/cloud)
        4. For perennial crops, detect multiple cuts
        """
        if len(ndvi_series) < 3 or len(dates) != len(ndvi_series):
            return []
        
        profile = self.crop_profiles.get(crop_type.lower(), {})
        drop_threshold = profile.get("harvest_ndvi_drop", 0.25)
        if drop_threshold <= 0:
            drop_threshold = 0.25
        
        events = []
        harvest_count = 0
        arr = np.array(ndvi_series)
        
        # Compute first differences
        diffs = np.diff(arr)
        
        i = 0
        while i < len(diffs):
            # Look for significant drop
            if diffs[i] < -drop_threshold:
                # Check if sustained (next value doesn't bounce back)
                sustained = True
                if i + 1 < len(diffs):
                    # If next step recovers more than 50% of drop, it's noise
                    if diffs[i + 1] > abs(diffs[i]) * 0.5:
                        sustained = False
                
                if sustained:
                    harvest_count += 1
                    ndvi_before = float(arr[i])
                    ndvi_after = float(arr[i + 1])
                    drop_mag = ndvi_before - ndvi_after
                    
                    # Confidence based on drop magnitude and sustainability
                    # Ensure drop_threshold is > 0 before dividing
                    if drop_threshold > 0:
                        conf = min(1.0, drop_mag / drop_threshold) * 0.9
                    else:
                        conf = 0.5
                        
                    if i + 2 < len(arr) and arr[i + 2] < arr[i] * 0.6:
                        conf = min(1.0, conf + 0.1)  # Extra confidence if still low
                    
                    try:
                        event_date = datetime.strptime(dates[i + 1], "%Y-%m-%d").date()
                    except (ValueError, IndexError):
                        event_date = date.today()
                    
                    events.append(HarvestEvent(
                        date=event_date,
                        ndvi_before=round(ndvi_before, 4),
                        ndvi_after=round(ndvi_after, 4),
                        drop_magnitude=round(drop_mag, 4),
                        confidence=round(conf, 2),
                        harvest_number=harvest_count,
                    ))
                    
                    # Skip ahead past the drop recovery period
                    i += 3
                    continue
            i += 1
        
        return events
    
    def predict_next_harvest(
        self,
        last_harvest: Optional[HarvestEvent],
        crop_type: str,
        ndvi_current: float,
        ndvi_trend: str,
        current_growth_stage: str,
    ) -> Optional[HarvestPrediction]:
        """
        Predict next harvest window based on:
        - Last harvest date + crop regrowth profile (perennial)
        - Current growth stage + crop calendar (annual)
        - NDVI trajectory
        """
        profile = self.crop_profiles.get(crop_type.lower(), {})
        lifecycle = profile.get("lifecycle", "annual")
        today = date.today()
        
        if lifecycle == "fallow":
            return None
        
        # For perennial crops with known last harvest
        if lifecycle == "perennial" and last_harvest:
            regrowth_days = profile.get("regrowth_days", 30)
            # Time from harvest to next harvest ≈ regrowth + maturation
            growth_stages = profile.get("growth_stages", {})
            veg_days = growth_stages.get("vegetative", 20)
            total_cycle = regrowth_days + veg_days
            
            est_date = last_harvest.date + timedelta(days=total_cycle)
            days_remaining = (est_date - today).days

            return HarvestPrediction(
                estimated_date=est_date,
                days_remaining=days_remaining,
                confidence=0.70 if days_remaining > 0 else 0.85,
                based_on="crop_profile",
            )
        
        # For annual crops, estimate from growth stage
        if lifecycle == "annual":
            growth_stages = profile.get("growth_stages", {})
            stage_order = ["emergence", "early_vegetative", "vegetative", "flowering", "grain_fill", "maturity"]
            
            if current_growth_stage in ("harvested", "bare_soil", "planting"):
                return None  # No harvest to predict
            
            # Sum remaining stage durations
            remaining_days = 0
            found_current = False
            for stage in stage_order:
                if stage == current_growth_stage:
                    found_current = True
                    # Estimate we're halfway through current stage
                    remaining_days += growth_stages.get(stage, 14) // 2
                    continue
                if found_current:
                    remaining_days += growth_stages.get(stage, 14)
            
            if not found_current:
                remaining_days = 45  # Default fallback
            
            est_date = today + timedelta(days=remaining_days)
            
            return HarvestPrediction(
                estimated_date=est_date,
                days_remaining=remaining_days,
                confidence=0.60 if remaining_days > 60 else 0.75,
                based_on="crop_profile",
            )
        
        return None
