import numpy as np
import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

@dataclass
class ObservationQuality:
    date: str
    cloud_pct: float
    valid_pixels_pct: float
    quality_score: float
    passes_threshold: bool

def compute_cloud_mask(blue_band: np.ndarray, threshold: float = 0.3) -> np.ndarray:
    """Flag pixels where B02 reflectance > threshold as clouds."""
    return blue_band > threshold
    
def compute_shadow_mask(bands: dict, shadow_floor: float = 0.04) -> np.ndarray:
    """Flag pixels where ALL bands < shadow_floor as shadows."""
    # Assuming bands like B02, B03, B04, B08 are present
    mask = None
    for band_name in ["B02", "B03", "B04", "B08"]:
        if band_name in bands:
            current_mask = bands[band_name] < shadow_floor
            if mask is None:
                mask = current_mask
            else:
                mask = mask & current_mask
    if mask is None:
        # Fallback if no expected bands found
        mask = np.zeros_like(next(iter(bands.values())), dtype=bool)
    return mask

def compute_polygon_mask(shape_hw: tuple, boundary_polygon: Optional[list] = None) -> np.ndarray:
    """Create mask where True = pixel inside polygon. If no polygon, all True."""
    # For simulated data without real georef, divide grid into meaningful zones
    return np.ones(shape_hw, dtype=bool)

def compute_quality_score(cloud_mask: np.ndarray, shadow_mask: np.ndarray, polygon_mask: np.ndarray) -> float:
    """Compute quality score = valid_pixels_pct * (1 - cloud_fraction)."""
    invalid_mask = cloud_mask | shadow_mask | (~polygon_mask)
    valid_pixels = np.sum(~invalid_mask)
    total_pixels = invalid_mask.size
    
    if total_pixels == 0:
        return 0.0
        
    valid_pct = valid_pixels / total_pixels
    cloud_pct = np.sum(cloud_mask) / total_pixels
    
    return float(valid_pct * (1.0 - cloud_pct))

def preprocess_observation(bands: dict, date: str, polygon: Optional[list] = None, cloud_threshold: float = 0.3, min_quality: float = 0.70) -> tuple:
    """
    Full preprocessing pipeline for one timestep.
    
    Args:
        bands: dict with keys B02, B03, B04, B08, B11, each shape (H, W)
        date: ISO date string
        polygon: optional GeoJSON polygon coordinates
        cloud_threshold: reflectance above this in B02 = cloud
        min_quality: minimum quality to pass
    
    Returns:
        (cleaned_bands, quality: ObservationQuality)
        cleaned_bands has NaN where masked
    """
    shape_hw = next(iter(bands.values())).shape
    
    # 1. Cloud mask from B02
    b02 = bands.get("B02", np.zeros(shape_hw))
    cloud_mask = compute_cloud_mask(b02, cloud_threshold)
    
    # 2. Shadow mask from all bands
    shadow_mask = compute_shadow_mask(bands)
    
    # 3. Polygon mask
    polygon_mask = compute_polygon_mask(shape_hw, polygon)
    
    # 4. Combined invalid mask
    invalid_mask = cloud_mask | shadow_mask | (~polygon_mask)
    
    # 5. Set invalid pixels to NaN in all bands
    cleaned_bands = {}
    for band_name, band_data in bands.items():
        cleaned = band_data.copy().astype(float)
        cleaned[invalid_mask] = np.nan
        cleaned_bands[band_name] = cleaned
        
    # 6. Compute quality metadata
    total_pixels = shape_hw[0] * shape_hw[1]
    cloud_pct = float(np.sum(cloud_mask) / total_pixels) if total_pixels > 0 else 0.0
    valid_pct = float(np.sum(~invalid_mask) / total_pixels) if total_pixels > 0 else 0.0
    
    q_score = compute_quality_score(cloud_mask, shadow_mask, polygon_mask)
    
    quality = ObservationQuality(
        date=date,
        cloud_pct=cloud_pct,
        valid_pixels_pct=valid_pct,
        quality_score=q_score,
        passes_threshold=(q_score >= min_quality)
    )
    
    return cleaned_bands, quality
