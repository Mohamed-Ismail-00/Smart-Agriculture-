"""
Features for the crop models. Every model notebook uses this file, and the platform will use
it to serve the model, so a field is described the same way in training and in use.

    import features
    X, meta = features.load("winter")          # bands [samples, dekads, 10], NaN = no clear view
    C = features.channels(X)                    # [samples, dekads, 14]: 10 bands + 4 indices
    C = features.truncate(C, k)                 # early classification: only the first k dekads seen
    table = features.flatten(C)                 # LightGBM (NaN allowed)
    table = features.flatten(features.fill(C))  # Random Forest (no NaN); cut first, then fill
    P = features.phenology(C)                   # season summary of NDVI and NDWI
"""

import json
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / "research"))
import dataset  # noqa: E402  (loads the arrays, same index formulas as the platform)
from config import BANDS  # noqa: E402

DATA = ROOT / "data"                                   # git-ignored outputs of 01_prepare_data
CLEAN_IDS = ROOT.parent / "eda" / "clean_samples.csv"  # samples kept by the EDA cleaning

# One model per season. Each season stacks the districts and years that share its calendar.
SEASONS = {
    "winter": [("ZAN", "W2324"), ("SGZ", "W2324")],
    "summer": [("ZAN", "S2024"), ("SGZ", "S2023"), ("SGZ", "S2024")],
}
META_COLUMNS = ["sample_id", "pixel_id", "region", "season", "season_key", "crop", "split", "fold", "block_id"]

INDICES = ["ndvi", "ndwi", "gndvi", "evi"]   # SAVI left out: almost identical to EVI (EDA)
CHANNELS = BANDS + INDICES

PHENOLOGY_CHANNELS = ["ndvi", "ndwi"]
PHENOLOGY_STATS = ["max", "peak_dekad", "min", "mean", "std", "max_rise"]
PHENOLOGY_NAMES = [f"{c}_{s}" for c in PHENOLOGY_CHANNELS for s in PHENOLOGY_STATS]


def load(season: str) -> tuple[np.ndarray, pd.DataFrame]:
    """Clean samples of one season: bands float32 [samples, dekads, 10] (NaN = missing) and their rows."""
    clean = pd.read_csv(CLEAN_IDS)["sample_id"].to_numpy()
    parts, meta = [], []
    for region, season_key in SEASONS[season]:
        d = dataset.load(region, season_key)
        keep = np.isin(d["samples"]["sample_id"].to_numpy(), clean)
        parts.append(d["X"][keep])
        meta.append(d["samples"].loc[keep, META_COLUMNS])
        del d
    return np.concatenate(parts), pd.concat(meta, ignore_index=True)


def channels(X: np.ndarray, chunk: int = 50_000) -> np.ndarray:
    """[..., 10 bands] -> [..., 14]: the bands, then NDVI, NDWI, GNDVI, EVI (NaN where the bands are NaN)."""
    out = np.empty(X.shape[:-1] + (len(CHANNELS),), dtype=np.float32)
    out[..., :len(BANDS)] = X
    formulas = dataset.platform_indices
    for start in range(0, len(X), chunk):
        b = {name: X[start:start + chunk, ..., i] for i, name in enumerate(BANDS)}
        out[start:start + chunk, ..., len(BANDS):] = np.stack([
            formulas.compute_ndvi(b["B08"], b["B04"]),
            formulas.compute_ndwi(b["B08"], b["B11"]),
            formulas.compute_gndvi(b["B08"], b["B03"]),
            formulas.compute_evi(b["B08"], b["B04"], b["B02"]),
        ], axis=-1)
    return out


def truncate(C: np.ndarray, k: int) -> np.ndarray:
    """Copy in which only the first k dekads are seen; later dekads become NaN (same shape)."""
    out = C.copy()
    out[:, k:] = np.nan
    return out


def fill(C: np.ndarray) -> np.ndarray:
    """
    Linear gap filling in time; before the first and after the last clear dekad the nearest
    clear value is used. Applied to a truncated series it only uses the dekads seen so far,
    so the rule is: truncate first, then fill.
    """
    return dataset.fill_gaps(C)


def feature_names(n_dekads: int) -> list[str]:
    """Column names of flatten(): channel_dDD, dekad by dekad."""
    return [f"{c}_d{t:02d}" for t in range(1, n_dekads + 1) for c in CHANNELS]


def flatten(C: np.ndarray) -> np.ndarray:
    """[samples, dekads, channels] -> [samples, dekads x channels], in the order of feature_names()."""
    return C.reshape(len(C), -1)


def phenology(C: np.ndarray) -> np.ndarray:
    """
    Season summary of NDVI and NDWI from the dekads seen (NaN ignored, nothing filled),
    float32 [samples, 12] in the order of PHENOLOGY_NAMES:
      max, peak_dekad (1-based dekad of the max), min, mean, std,
      max_rise = largest increase from one clear dekad to the next one.
    """
    out = []
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=RuntimeWarning)    # a sample with no clear dekad
        for name in PHENOLOGY_CHANNELS:
            x = C[:, :, CHANNELS.index(name)]
            seen = np.isfinite(x).any(axis=1)
            peak = np.argmax(np.where(np.isfinite(x), x, -np.inf), axis=1).astype(np.float32) + 1
            peak[~seen] = np.nan
            previous = dataset.fill_gaps(x[:, :, None], causal=True)[:, :-1, 0]
            out += [np.nanmax(x, axis=1), peak, np.nanmin(x, axis=1), np.nanmean(x, axis=1),
                    np.nanstd(x, axis=1), np.nanmax(x[:, 1:] - previous, axis=1)]
    return np.stack(out, axis=1).astype(np.float32)


def load_prep() -> dict:
    """Decisions saved by 01_prepare_data: classes, feature names, class weights, scaling."""
    return json.loads((DATA / "prep.json").read_text())


def encode(crop: pd.Series, season: str, prep: dict) -> np.ndarray:
    """Crop names -> class numbers of the season (fixed order saved in prep.json)."""
    return crop.map({c: i for i, c in enumerate(prep[season]["classes"])}).to_numpy()


def standardize(C: np.ndarray, season: str, prep: dict) -> np.ndarray:
    """Per-channel (x - mean) / std with the train statistics. For LSTM and MiniRocket only."""
    mean = np.array(prep[season]["mean"], dtype=np.float32)
    std = np.array(prep[season]["std"], dtype=np.float32)
    return (C - mean) / std
