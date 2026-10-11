"""
Load the dataset built by step 3.

    import dataset
    d = dataset.load("ZAN", "W2324")            # dekads (10-day); series="passes" for 5-day
    X = dataset.fill_gaps(d["X"])               # [samples, time, 10 bands]
    V = dataset.vegetation_indices(X)           # [samples, time, 5 indices]
    y = d["samples"]["crop"]
"""

import sys

import numpy as np
import pandas as pd

from config import BANDS, DATASET_DIR, REPO

sys.path.insert(0, str(REPO / "backend"))
from app.cv import indices as platform_indices  # noqa: E402  (same formulas the platform serves)

MISSING = -1
INDICES = ["ndvi", "evi", "ndwi", "savi", "gndvi"]


def load(region: str, season_key: str, series: str = "dekads") -> dict:
    """
    X        float32 [samples, time, bands]: surface reflectance, NaN where there was no clear view
    n_clear  uint8 [samples, time]: clear passes behind each dekad (None for series="passes")
    dates    first day of each dekad, or the date of each pass
    samples  one row per row of X: label, split, coordinates, quality
    """
    with np.load(DATASET_DIR / f"{region}_{season_key}.npz") as f:
        raw, sample_id = f[series], f["sample_id"]
        dates = f["dekad_start" if series == "dekads" else "pass_dates"].tolist()
        n_clear = f["dekad_n"] if series == "dekads" else None
    X = raw.astype(np.float32) / 1e4
    X[raw == MISSING] = np.nan
    samples = pd.read_parquet(DATASET_DIR / "samples.parquet").set_index("sample_id").loc[sample_id].reset_index()
    return {"X": X, "n_clear": n_clear, "dates": dates, "samples": samples}


def vegetation_indices(X: np.ndarray) -> np.ndarray:
    """NDVI, EVI, NDWI, SAVI, GNDVI (in that order) from reflectance [..., bands]."""
    b = {name: X[..., i] for i, name in enumerate(BANDS)}
    return np.stack([
        platform_indices.compute_ndvi(b["B08"], b["B04"]),
        platform_indices.compute_evi(b["B08"], b["B04"], b["B02"]),
        platform_indices.compute_ndwi(b["B08"], b["B11"]),
        platform_indices.compute_savi(b["B08"], b["B04"]),
        platform_indices.compute_gndvi(b["B08"], b["B03"]),
    ], axis=-1).astype(np.float32)


def fill_gaps(X: np.ndarray, causal: bool = False, chunk: int = 50_000) -> np.ndarray:
    """
    Fill missing time steps of [samples, time, bands].

    causal=False  linear interpolation between the clear values on either side; before the
                  first or after the last clear value, the nearest one is used.
    causal=True   the last clear value is carried forward and nothing after a time step is
                  ever used. Use this for early classification, where a series cut at week k
                  must not contain information from later weeks.
    Samples with no clear value at all stay NaN.
    """
    out = np.empty_like(X)
    steps = X.shape[1]
    for start in range(0, len(X), chunk):
        x = X[start:start + chunk]
        seen = np.isfinite(x[:, :, 0])
        prev_val, prev_t = np.empty_like(x), np.empty(seen.shape, dtype=np.float32)
        value, when = np.full(x[:, 0].shape, np.nan, dtype=x.dtype), np.full(len(x), np.nan, dtype=np.float32)
        for t in range(steps):
            value = np.where(seen[:, t, None], x[:, t], value)
            when = np.where(seen[:, t], t, when)
            prev_val[:, t], prev_t[:, t] = value, when
        if causal:
            out[start:start + chunk] = prev_val
            continue
        next_val, next_t = np.empty_like(x), np.empty(seen.shape, dtype=np.float32)
        value, when = np.full(x[:, 0].shape, np.nan, dtype=x.dtype), np.full(len(x), np.nan, dtype=np.float32)
        for t in range(steps - 1, -1, -1):
            value = np.where(seen[:, t, None], x[:, t], value)
            when = np.where(seen[:, t], t, when)
            next_val[:, t], next_t[:, t] = value, when
        span = next_t - prev_t
        weight = np.where(span > 0, (np.arange(steps, dtype=np.float32) - prev_t) / np.where(span > 0, span, 1), 0.0)
        filled = prev_val + (next_val - prev_val) * weight[:, :, None]
        filled = np.where(np.isnan(prev_val), next_val, filled)       # before the first clear value
        filled = np.where(np.isnan(next_val), prev_val, filled)       # after the last clear value
        out[start:start + chunk] = filled
    return out
