"""
Step 3 - turn the downloaded values into the dataset.

For every region and labelled season:
  1. digital numbers -> surface reflectance (per-scene offset rule taken from the platform);
  2. an observation is kept only if it is clear: Scene Classification, a 100 m buffer around
     clouds and shadows, and a test for leftover haze or shadow (a pass that departs from
     both of its neighbours in time, see cloud_like_outliers);
  3. the series of satellite passes (one every 5 days) is stored as is;
  4. it is also composited into dekads (the 10-day calendar FAO WaPOR uses) by median.

Nothing is gap-filled here: a missing value stays missing, so that later steps decide how
to fill it (early-classification experiments must not borrow from future dates).

Outputs (research/data/dataset/):
  samples.parquet            one row per sample (pixel x season): label, split, quality
  {REGION}_{SEASON}.npz      passes, dekads, dekad_n, their dates, sample_id (same order)
  build_report.json          counts of what was kept and why

    python research/step3_build_dataset.py
"""

import json
import sys
import warnings
from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd
from scipy import ndimage

from config import (
    BANDS, DATASET_DIR, DOUBTFUL_LABELS, LABELS_DIR, RAW_DIR, REGIONS, REPO, SCL_CLOUD, SCL_INVALID, SEASONS,
)

sys.path.insert(0, str(REPO / "backend"))
from app.connectors.sentinel import boa_offset_dn  # noqa: E402  (the platform's own rule)

CLOUD_BUFFER_M = 100      # observations closer than this to a cloud or cloud shadow are dropped
BLUE_SPIKE = 0.03         # blue reflectance this far above both neighbouring passes = haze / thin cloud
DARK_SPIKE = 0.7          # NIR and SWIR both under 70% of both neighbouring passes = cloud shadow
MISSING = -1              # stored reflectance is int16 = reflectance x 10000, MISSING where unusable


def dekad_bounds(start: str, end: str) -> list[tuple[date, date]]:
    """(first day, last day) of every dekad from start to end: days 1-10, 11-20, 21-month end."""
    first, last = date.fromisoformat(start), date.fromisoformat(end)
    out, month = [], date(first.year, first.month, 1)
    while month <= last:
        next_month = date(month.year + month.month // 12, month.month % 12 + 1, 1)
        out += [(month, month.replace(day=10)), (month.replace(day=11), month.replace(day=20)),
                (month.replace(day=21), next_month - timedelta(days=1))]
        month = next_month
    return out


def classification_per_pixel(region: str, px: pd.DataFrame, scenes: list[dict], date_idx: dict):
    """Scene Classification value and distance to the nearest cloud (in 20 m pixels), per date and pixel."""
    scl = np.zeros((len(date_idx), len(px)), dtype=np.uint8)
    cloud_dist = np.zeros((len(date_idx), len(px)), dtype=np.uint8)
    tile_of = px["tile"].to_numpy()
    R, C = px["R"].to_numpy(), px["C"].to_numpy()
    for scene in scenes:
        sel = np.nonzero(tile_of == scene["tile"])[0]
        with np.load(RAW_DIR / region / "scl" / f"{scene['date']}_{scene['tile']}.npz") as f:
            window, r0, c0 = f["scl"], int(f["r0"]), int(f["c0"])
        cloud = np.isin(window, SCL_CLOUD)
        dist = ndimage.distance_transform_edt(~cloud) if cloud.any() else np.full(window.shape, 255.0)
        rows, cols = R[sel] // 2 - r0, C[sel] // 2 - c0
        scl[date_idx[scene["date"]], sel] = window[rows, cols]
        cloud_dist[date_idx[scene["date"]], sel] = np.minimum(dist[rows, cols], 255)
    return scl, cloud_dist


def neighbours(x: np.ndarray, clear: np.ndarray) -> tuple:
    """Value at the previous and at the next clear pass of each pixel (NaN where there is none)."""
    before, after = np.empty_like(x), np.empty_like(x)
    last = np.full(x.shape[1], np.nan, dtype=x.dtype)
    for d in range(len(x)):
        before[d] = last
        last = np.where(clear[d], x[d], last)
    last = np.full(x.shape[1], np.nan, dtype=x.dtype)
    for d in range(len(x) - 1, -1, -1):
        after[d] = last
        last = np.where(clear[d], x[d], last)
    return before, after


def cloud_like_outliers(refl: np.ndarray, clear: np.ndarray) -> np.ndarray:
    """
    Passes that Scene Classification called clear but that look like leftover cloud or shadow.

    A pass is flagged when it departs from BOTH the previous and the next clear pass of the
    same pixel in the direction contamination pushes it:
      - haze / thin cloud: blue reflectance higher than both by more than BLUE_SPIKE;
      - cloud shadow:      NIR and SWIR both below DARK_SPIKE x the darker neighbour.
    A real change (harvest, flooding a rice field) persists into the next pass, so it is
    not flagged. Measured on Sidi Ghazi: flagged passes are 6x more common in the 100 m
    around clouds, and their NDVI sits 0.10 below their neighbours (0.005 for unflagged).
    refl: [dates, pixels, bands] reflectance x 10000; clear: [dates, pixels].
    """
    def band(name):
        return refl[:, :, BANDS.index(name)].astype(np.float32) / 1e4

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=RuntimeWarning)
        blue = band("B02")
        before, after = neighbours(blue, clear)
        outlier = blue - np.maximum(before, after) > BLUE_SPIKE      # NaN (no neighbour) compares False
        del blue
        dark = np.ones(clear.shape, dtype=bool)
        for name in ("B08", "B11"):
            x = band(name)
            before, after = neighbours(x, clear)
            dark &= x < DARK_SPIKE * np.minimum(before, after)
        return clear & (outlier | dark)


def composite_dekads(passes: np.ndarray, pass_dates: list[date], bounds: list) -> tuple:
    """Median of the clear passes in each dekad. Returns (values int16 [N, T, bands], n_clear uint8 [N, T])."""
    n = len(passes)
    values = np.full((n, len(bounds), passes.shape[2]), MISSING, dtype=np.int16)
    n_clear = np.zeros((n, len(bounds)), dtype=np.uint8)
    for t, (first, last) in enumerate(bounds):
        idx = [i for i, d in enumerate(pass_dates) if first <= d <= last]
        if not idx:
            continue
        chunk = passes[:, idx, :].astype(np.float32)
        chunk[chunk == MISSING] = np.nan
        count = np.isfinite(chunk[:, :, 0]).sum(axis=1)
        n_clear[:, t] = count
        # Median over the few passes of a dekad: sort (NaN last) and average the two middle values.
        chunk.sort(axis=1)
        every = np.arange(n)
        last = len(idx) - 1
        lower = chunk[every, np.clip((count - 1) // 2, 0, last)]
        upper = chunk[every, np.clip(count // 2, 0, last)]
        seen = count > 0
        values[seen, t, :] = np.rint((lower[seen] + upper[seen]) / 2).astype(np.int16)
    return values, n_clear


def longest_gap(n_clear: np.ndarray) -> np.ndarray:
    """Longest run of dekads without any clear pass, per sample."""
    run = np.zeros(len(n_clear), dtype=np.int16)
    longest = np.zeros(len(n_clear), dtype=np.int16)
    for t in range(n_clear.shape[1]):
        run = np.where(n_clear[:, t] == 0, run + 1, 0)
        longest = np.maximum(longest, run)
    return longest


def build_region(region: str, all_samples: pd.DataFrame, report: dict) -> list[pd.DataFrame]:
    px = pd.read_parquet(RAW_DIR / region / "pixels.parquet")
    scenes = [s for s in json.loads((RAW_DIR / region / "scenes.json").read_text()) if s["tile"] in set(px["tile"])]
    dates = sorted({s["date"] for s in scenes})
    date_idx = {d: i for i, d in enumerate(dates)}
    scene_at = {(s["date"], s["tile"]): s for s in scenes}
    scl, cloud_dist = classification_per_pixel(region, px, scenes, date_idx)
    buffer_px = CLOUD_BUFFER_M / 20

    samples = all_samples[(all_samples["region"] == region) & all_samples["pixel_id"].isin(px["pixel_id"])].copy()
    samples["pos"] = pd.Series(np.arange(len(px)), index=px["pixel_id"]).reindex(samples["pixel_id"]).to_numpy()
    samples["unit"] = px["unit"].to_numpy()[samples["pos"].to_numpy()]

    seasons = {}
    for season_key in REGIONS[region]["maps"]:
        cfg = SEASONS[season_key]
        rows = samples[samples["season_key"] == season_key].sort_values("sample_id")
        d_idx = [i for i, d in enumerate(dates) if cfg["start"] <= d <= cfg["end"]]
        seasons[season_key] = {
            "d_idx": d_idx, "sample_id": rows["sample_id"].to_numpy(), "by_unit": dict(tuple(rows.groupby("unit"))),
            "passes": np.full((len(rows), len(d_idx), len(BANDS)), MISSING, dtype=np.int16),
        }

    counts = {"fetched": 0, "clear_scl": 0, "after_buffer": 0, "after_outlier_test": 0, "squares_without_data": 0}
    units = list(px.groupby("unit", sort=True))
    for n_unit, (unit, group) in enumerate(units, 1):
        pos, tile = group.index.to_numpy(), group["tile"].iloc[0]
        refl = np.zeros((len(dates), len(pos), len(BANDS)), dtype=np.int16)
        has_data = np.zeros((len(dates), len(pos)), dtype=bool)
        found = 0
        for di, d in enumerate(dates):
            path = RAW_DIR / region / "bands" / unit / f"{d}.npz"
            if not path.exists():
                continue
            scene = scene_at[(d, tile)]
            offset = boa_offset_dn(scene["baseline"], datetime.fromisoformat(scene["datetime"]))
            with np.load(path) as f:
                dn = f["values"]
            has_data[di] = (dn > 0).all(axis=1)      # 0 = no data, or a quadrant that was not fetched
            refl[di] = np.clip(dn.astype(np.int32) - offset, 0, 32767)
            found += 1
        counts["squares_without_data"] += found == 0

        clear_scl = has_data & ~np.isin(scl[:, pos], SCL_INVALID)
        clear = clear_scl & (cloud_dist[:, pos] >= buffer_px)
        valid = clear & ~cloud_like_outliers(refl, clear)
        refl[~valid] = MISSING
        for key, mask in (("fetched", has_data), ("clear_scl", clear_scl), ("after_buffer", clear), ("after_outlier_test", valid)):
            counts[key] += int(mask.sum())

        for season in seasons.values():
            rows = season["by_unit"].get(unit)
            if rows is None:
                continue
            local = np.searchsorted(pos, rows["pos"].to_numpy())
            target = np.searchsorted(season["sample_id"], rows["sample_id"].to_numpy())
            season["passes"][target] = refl[season["d_idx"]][:, local, :].transpose(1, 0, 2)
        print(f"   {region} {n_unit}/{len(units)} {unit}: {len(pos):,} pixels, {found} dates", flush=True)
    report[region] = {"pixels": len(px), "dates": len(dates), **counts}

    frames = []
    for season_key, season in seasons.items():
        sample_id, passes = season["sample_id"], season["passes"]
        pass_dates = [date.fromisoformat(dates[i]) for i in season["d_idx"]]
        bounds = dekad_bounds(SEASONS[season_key]["start"], SEASONS[season_key]["end"])
        dekads, dekad_n = composite_dekads(passes, pass_dates, bounds)

        DATASET_DIR.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(
            DATASET_DIR / f"{region}_{season_key}.npz",
            sample_id=sample_id, bands=np.array(BANDS),
            passes=passes, pass_dates=np.array([d.isoformat() for d in pass_dates]),
            dekads=dekads, dekad_n=dekad_n, dekad_start=np.array([b[0].isoformat() for b in bounds]),
        )
        quality = pd.DataFrame({
            "sample_id": sample_id,
            "n_passes_clear": (passes[:, :, 0] != MISSING).sum(axis=1).astype(np.int16),
            "n_dekads_clear": (dekad_n > 0).sum(axis=1).astype(np.int16),
            "longest_gap_dekads": longest_gap(dekad_n),
        })
        frames.append(samples[samples["season_key"] == season_key].drop(columns=["pos", "unit"]).merge(quality, on="sample_id"))
        report[f"{region}_{season_key}"] = {
            "samples": len(sample_id), "passes": len(pass_dates), "dekads": len(bounds),
            "clear_passes_per_sample_mean": round(float(quality["n_passes_clear"].mean()), 1),
            "dekads_without_clear_pass_pct": round(float((dekad_n == 0).mean() * 100), 1),
            "samples_with_gap_over_3_dekads_pct": round(float((quality["longest_gap_dekads"] > 3).mean() * 100), 2),
        }
        print(f"{region} {season_key}: {report[f'{region}_{season_key}']}", flush=True)
    return frames


def main():
    all_samples = pd.read_parquet(LABELS_DIR / "samples.parquet")
    report, frames = {}, []
    for region in REGIONS:
        frames += build_region(region, all_samples, report)
    samples = pd.concat(frames, ignore_index=True).sort_values("sample_id").reset_index(drop=True)
    samples["label_doubt"] = [key in DOUBTFUL_LABELS for key in zip(samples["region"], samples["season_key"], samples["crop"])]
    samples.to_parquet(DATASET_DIR / "samples.parquet", index=False)
    report["samples_total"] = len(samples)
    report["samples_without_imagery"] = len(all_samples) - len(samples)
    report["settings"] = {"cloud_buffer_m": CLOUD_BUFFER_M, "blue_spike": BLUE_SPIKE, "dark_spike": DARK_SPIKE}
    (DATASET_DIR / "build_report.json").write_text(json.dumps(report, indent=2))
    print(json.dumps({k: v for k, v in report.items() if k in REGIONS or k.startswith("samples")}, indent=2))


if __name__ == "__main__":
    main()
