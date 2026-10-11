import numpy as np
import logging
from typing import Optional

logger = logging.getLogger(__name__)

try:
    from scipy.signal import savgol_filter
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False
    logger.warning("scipy not available, smoothing will fall back to moving average.")

def interpolate_gaps(values: np.ndarray) -> np.ndarray:
    """Linear interpolation of NaN gaps in 1D array."""
    out = values.copy()
    nans = np.isnan(out)
    
    if not np.any(nans):
        return out
        
    x = lambda z: z.nonzero()[0]
    if np.sum(~nans) < 2:
        # Cannot interpolate with less than 2 valid points
        out[nans] = 0.0
        return out
        
    out[nans] = np.interp(x(nans), x(~nans), out[~nans])
    return out

def moving_average_1d(values: np.ndarray, window: int = 3) -> np.ndarray:
    """Simple moving average with edge handling."""
    if len(values) < window:
        return values.copy()
    
    # Pad edges to keep same shape
    pad_width = window // 2
    padded = np.pad(values, pad_width, mode='edge')
    weights = np.ones(window) / window
    
    return np.convolve(padded, weights, mode='valid')

def savitzky_golay_1d(values: np.ndarray, window: int = 5, polyorder: int = 2) -> np.ndarray:
    """
    Apply Savitzky-Golay filter to a 1D array.
    Handles NaN by interpolating first, smoothing, then restoring NaN positions.
    Falls back to moving average if scipy not available or array too short.
    """
    if len(values) < window:
        # Array too short for this window size
        return values.copy()
        
    if not HAS_SCIPY:
        return moving_average_1d(values, window)
        
    # Interpolate NaNs before smoothing
    nans = np.isnan(values)
    clean_vals = interpolate_gaps(values)
    
    try:
        smoothed = savgol_filter(clean_vals, window_length=window, polyorder=polyorder)
    except ValueError as e:
        logger.warning(f"Savitzky-Golay failed: {e}. Falling back to moving average.")
        smoothed = moving_average_1d(clean_vals, window)
        
    return smoothed

def smooth_timeseries(values: np.ndarray, method: str = "savgol", window: int = 5, polyorder: int = 2) -> np.ndarray:
    """
    Apply smoothing to a 1D time-series.
    Methods: 'savgol' (Savitzky-Golay), 'moving_avg', 'none'
    """
    if method == "none":
        return values.copy()
    elif method == "savgol":
        # window must be odd
        w = window if window % 2 != 0 else window + 1
        return savitzky_golay_1d(values, w, polyorder)
    elif method == "moving_avg":
        return moving_average_1d(values, window)
    else:
        logger.warning(f"Unknown smoothing method '{method}'. Using 'none'.")
        return values.copy()

def build_clean_timeseries(values: list, dates: list, quality_scores: list, min_quality: float = 0.70) -> tuple:
    """
    1. Filter out observations below quality threshold
    2. Interpolate gaps (linear)
    3. Apply Savitzky-Golay smoothing
    4. Return (clean_values, clean_dates)
    """
    if not values:
        return [], []
        
    arr = np.array(values, dtype=float)
    clean_arr = arr.copy()
    
    # 1. Filter out poor quality
    for i, q in enumerate(quality_scores):
        if q < min_quality:
            clean_arr[i] = np.nan
            
    # 2. Interpolate
    clean_arr = interpolate_gaps(clean_arr)
    
    # 3. Smooth
    smoothed = smooth_timeseries(clean_arr, method="savgol", window=5, polyorder=2)
    
    return smoothed.tolist(), dates

def smooth_spatial_timeseries(array_3d: np.ndarray, method: str = "savgol", window: int = 5, polyorder: int = 2) -> np.ndarray:
    """
    Apply smoothing along the temporal axis (axis=0) of a (T, H, W) array.
    Smooths each pixel's time-series independently.
    """
    T, H, W = array_3d.shape
    out = np.zeros_like(array_3d)
    
    # window must be odd and <= T
    w = min(window if window % 2 != 0 else window + 1, T if T % 2 != 0 else T - 1)
    
    if w < 3:
        # Not enough temporal points to smooth
        return array_3d.copy()
        
    for h in range(H):
        for w_idx in range(W):
            pixel_ts = array_3d[:, h, w_idx]
            out[:, h, w_idx] = smooth_timeseries(pixel_ts, method=method, window=w, polyorder=polyorder)
            
    return out
