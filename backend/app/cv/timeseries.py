import numpy as np
from app.cv.smoothing import smooth_spatial_timeseries

def extract_timeseries_features(ts_array: np.ndarray, dates: list) -> dict:
    """
    Extracts 12 statistical features from a time-series array of shape (T, H, W).
    Returns a dictionary of feature arrays each of shape (H, W).
    """
    T, H, W = ts_array.shape
    if T < 3:
        raise ValueError("Need at least 3 time steps to extract meaningful features")

    # Apply spatial-temporal smoothing before feature extraction
    clean_ts = smooth_spatial_timeseries(ts_array, method="savgol", window=5)
    
    # Safely handle completely cloudy pixels (all-NaNs) by filling with 0.0
    clean_ts = np.nan_to_num(clean_ts, nan=0.0)

    # Basic stats
    v_max = np.max(clean_ts, axis=0)
    v_min = np.min(clean_ts, axis=0)
    v_mean = np.mean(clean_ts, axis=0)
    v_median = np.median(clean_ts, axis=0)
    v_std = np.std(clean_ts, axis=0)
    v_var = np.var(clean_ts, axis=0)

    # Peak index and month
    peak_idx = np.argmax(clean_ts, axis=0)
    months = np.array([d.month for d in dates])
    peak_month = months[peak_idx]

    # Growth Rate and Decline Rate
    start_vals = clean_ts[0]
    end_vals = clean_ts[-1]
    
    i_idx, j_idx = np.indices((H, W))
    peak_vals = clean_ts[peak_idx, i_idx, j_idx]
    
    dt_growth = np.where(peak_idx > 0, peak_idx, 1)
    growth_rate = np.where(peak_idx > 0, (peak_vals - start_vals) / dt_growth, 0.0)
    
    dt_decline = np.where(T - 1 - peak_idx > 0, T - 1 - peak_idx, 1)
    decline_rate = np.where(T - 1 - peak_idx > 0, (end_vals - peak_vals) / dt_decline, 0.0)

    # Area Under Curve (AUC)
    if hasattr(np, 'trapezoid'):
        auc = np.trapezoid(clean_ts, axis=0)
    else:
        auc = np.trapz(clean_ts, axis=0)

    # New Feature: season_length (days above 50% of max)
    # Assumes ~8 days per time step, consistent with fetch_sentinel_timeseries
    threshold_50 = v_max * 0.5
    above_threshold_mask = clean_ts > threshold_50[np.newaxis, :, :]
    season_length = np.sum(above_threshold_mask, axis=0) * 8

    # New Feature: number_of_peaks (local maxima)
    # Simple calculation: a point is a peak if it's greater than both its neighbors
    diff_forward = np.diff(clean_ts, axis=0)
    diff_backward = -diff_forward
    # To compare point i with i-1, diff_backward[i-1] should be > 0 (meaning i > i-1)
    # To compare point i with i+1, diff_forward[i] should be < 0 (meaning i > i+1)
    peaks = np.zeros_like(clean_ts, dtype=bool)
    if T >= 3:
        # peaks[1:-1] = (clean_ts[1:-1] > clean_ts[:-2]) & (clean_ts[1:-1] > clean_ts[2:])
        peaks[1:-1] = (diff_backward[:-1] < 0) & (diff_forward[1:] < 0)
    number_of_peaks = np.sum(peaks, axis=0)

    return {
        "max": v_max,
        "min": v_min,
        "mean": v_mean,
        "median": v_median,
        "std": v_std,
        "var": v_var,
        "peak_month": peak_month.astype(np.float64),
        "growth_rate": growth_rate,
        "decline_rate": decline_rate,
        "auc": auc,
        "season_length": season_length.astype(np.float64),
        "number_of_peaks": number_of_peaks.astype(np.float64)
    }
