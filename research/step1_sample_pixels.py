"""
Step 1 - choose which pixels go into the dataset.

For every region and labelled season:
  1. warp the FAO crop map onto the Sentinel-2 grid;
  2. keep only "interior" pixels (3x3 neighbourhood is a single class), away from the
     edges of the 2 km blocks used for train / validation / test;
  3. draw a spatially spread sample per class (capped, so rare crops are not swamped);
  4. assign each 2 km block to one of five folds, balanced by class.

Outputs (research/data/labels/):
  samples.parquet            one row per sampled pixel and season
  {REGION}_{SEASON}.tif      the warped label map, for reference and later mapping
  grids.json                 region grid definitions

    python research/step1_sample_pixels.py
"""

import json

import numpy as np
import pandas as pd
import rasterio
from scipy import ndimage

import grid as G
from config import (
    BLOCK_PX, CAP_CROP, CAP_NON_CROP, CELL_PX, CRS_UTM, FAO_NODATA, GUARD_PX, LABELS_DIR, LEGEND,
    MIN_CLASS_FOR_FOLDS, N_FOLDS, NON_CROP, PURITY_WINDOW, REGIONS, SEASONS, SEED,
)


def interior_mask(labels: np.ndarray) -> np.ndarray:
    """True where the whole PURITY_WINDOW neighbourhood carries the pixel's own class."""
    lo = ndimage.minimum_filter(labels, size=PURITY_WINDOW, mode="constant", cval=FAO_NODATA)
    hi = ndimage.maximum_filter(labels, size=PURITY_WINDOW, mode="constant", cval=FAO_NODATA)
    return (lo == hi) & (labels != FAO_NODATA)


def purity_5x5(labels: np.ndarray) -> np.ndarray:
    """Share of the 5x5 neighbourhood that has the pixel's own class (1.0 = fully homogeneous)."""
    purity = np.zeros(labels.shape, dtype=np.float32)
    for code in np.unique(labels[labels != FAO_NODATA]):
        same = labels == code
        share = ndimage.uniform_filter(same.astype(np.float32), size=5, mode="constant")
        purity[same] = share[same]
    return purity


def guard_mask(shape: tuple) -> np.ndarray:
    """False within GUARD_PX of a block edge, so pixels in different blocks are >= 100 m apart."""
    def inside(n):
        pos = np.arange(n) % BLOCK_PX
        return (pos >= GUARD_PX) & (pos < BLOCK_PX - GUARD_PX)
    return inside(shape[0])[:, None] & inside(shape[1])[None, :]


def spread_sample(rows: np.ndarray, cols: np.ndarray, n: int, rng) -> np.ndarray:
    """
    Indices of n candidates spread evenly in space.

    Candidates are grouped into 100 m cells. One pixel is taken from every cell before a
    second is taken from any, and so on: a large field cannot dominate the sample.
    """
    if len(rows) <= n:
        return np.arange(len(rows))
    cell = (rows // CELL_PX).astype(np.int64) * 100_000 + cols // CELL_PX
    order = rng.permutation(len(rows))
    by_cell = np.argsort(cell[order], kind="stable")
    cells_sorted = cell[order][by_cell]
    is_first = np.r_[True, cells_sorted[1:] != cells_sorted[:-1]]
    first_pos = np.maximum.accumulate(np.where(is_first, np.arange(len(cells_sorted)), 0))
    rank = np.empty(len(rows), dtype=np.int64)
    rank[by_cell] = np.arange(len(cells_sorted)) - first_pos      # 0 = first pick of its cell
    return order[np.argsort(rank, kind="stable")[:n]]


def assign_folds(counts: pd.DataFrame, rng, tries: int = 20000) -> pd.Series:
    """
    Give every block a fold so that each class is split as evenly as possible.

    counts: blocks x classes table of sample counts. Random equal-sized partitions are
    tried and the one with the smallest deviation from 1/N_FOLDS per class is kept.
    """
    blocks = counts.index.to_numpy()
    totals = counts.to_numpy(dtype=np.float64)
    class_totals = totals.sum(axis=0)
    base = np.arange(len(blocks)) % N_FOLDS
    best, best_score = None, np.inf
    for _ in range(tries):
        folds = rng.permutation(base)
        shares = np.stack([totals[folds == f].sum(axis=0) for f in range(N_FOLDS)]) / class_totals
        score = ((shares - 1 / N_FOLDS) ** 2).sum() + 10 * (shares == 0).sum()
        if score < best_score:
            best, best_score = folds, score
    return pd.Series(best, index=blocks, name="fold")


def main():
    LABELS_DIR.mkdir(parents=True, exist_ok=True)
    grids, frames = {}, []

    for region_idx, (region, cfg) in enumerate(REGIONS.items()):
        g = G.region_grid(region)
        grids[region] = g
        guard = guard_mask((g["height"], g["width"]))
        n_block_cols = -(-g["width"] // BLOCK_PX)

        for season_idx, (season_key, map_code) in enumerate(cfg["maps"].items()):
            season = SEASONS[season_key]["season"]
            legend = LEGEND[season]
            labels = G.warp_labels(map_code, g)

            unknown = set(np.unique(labels).tolist()) - set(legend) - {FAO_NODATA}
            if unknown:
                raise ValueError(f"{map_code}: class codes {sorted(unknown)} are not in the {season} legend")

            with rasterio.open(
                LABELS_DIR / f"{region}_{season_key}.tif", "w", driver="GTiff", height=g["height"],
                width=g["width"], count=1, dtype="uint8", crs=CRS_UTM, transform=G.grid_transform(g),
                nodata=FAO_NODATA, compress="deflate",
            ) as dst:
                dst.write(labels, 1)

            candidates = interior_mask(labels) & guard
            purity = purity_5x5(labels)

            for code, crop in legend.items():
                n_map = int((labels == code).sum())
                if n_map == 0:
                    continue
                rows, cols = np.nonzero(candidates & (labels == code))
                cap = CAP_NON_CROP if crop in NON_CROP else CAP_CROP
                rng = np.random.default_rng([SEED, region_idx, season_idx, code])
                pick = spread_sample(rows, cols, cap, rng)
                rows, cols = rows[pick], cols[pick]
                x, y, lon, lat = G.pixel_centres(g, rows, cols)
                frames.append(pd.DataFrame({
                    "region": region,
                    "season_key": season_key,
                    "season": season,
                    "crop": crop,
                    "fao_code": np.uint8(code),
                    "is_crop": crop not in NON_CROP,
                    "row": rows.astype(np.int32),
                    "col": cols.astype(np.int32),
                    "x": x, "y": y, "lon": lon, "lat": lat,
                    "purity5": purity[rows, cols],
                    "block": (rows // BLOCK_PX) * n_block_cols + cols // BLOCK_PX,
                    # each sampled pixel stands for this many interior pixels of its class
                    "weight": np.float32(len(pick) and (candidates & (labels == code)).sum() / len(pick)),
                    "class_px_in_map": n_map,
                }))

    samples = pd.concat(frames, ignore_index=True)
    region_no = samples["region"].map({r: i + 1 for i, r in enumerate(REGIONS)}).astype(np.int64)
    samples.insert(0, "pixel_id", region_no * 100_000_000 + samples["row"].astype(np.int64) * 10_000 + samples["col"])
    samples.insert(0, "sample_id", np.arange(len(samples), dtype=np.int64))
    samples["block_id"] = samples["region"] + "_" + samples["block"].astype(str).str.zfill(3)

    # Folds are assigned per region and shared by all seasons, so a location never changes side.
    samples["fold"] = -1
    for region_idx, region in enumerate(REGIONS):
        sel = samples["region"] == region
        key = samples.loc[sel, "season_key"] + ":" + samples.loc[sel, "crop"]
        counts = pd.crosstab(samples.loc[sel, "block_id"], key)
        crop_keys = set(key[samples.loc[sel, "is_crop"]])
        balanced = [k for k in counts.columns if k in crop_keys and counts[k].sum() >= MIN_CLASS_FOR_FOLDS]
        folds = assign_folds(counts[balanced], np.random.default_rng([SEED, region_idx, 99]))
        samples.loc[sel, "fold"] = samples.loc[sel, "block_id"].map(folds).astype(int)
    samples["split"] = samples["fold"].map({0: "test", 1: "val"}).fillna("train")
    samples = samples.drop(columns="block")

    samples.to_parquet(LABELS_DIR / "samples.parquet", index=False)
    (LABELS_DIR / "grids.json").write_text(json.dumps(grids, indent=2))
    report(samples)


def report(samples: pd.DataFrame):
    pd.set_option("display.width", 200)
    print(f"\nsamples: {len(samples):,} (pixel x season)   distinct pixels: {samples['pixel_id'].nunique():,}")
    summary = samples.groupby(["region", "season_key", "crop"]).agg(
        sampled=("sample_id", "size"), map_px=("class_px_in_map", "first"), weight=("weight", "first"),
        blocks=("block_id", "nunique"), purity5=("purity5", "mean"),
    )
    summary["interior_px"] = (summary["sampled"] * summary["weight"]).round().astype(int)
    print(summary[["map_px", "interior_px", "sampled", "blocks", "purity5"]].round(3).to_string())
    print("\nper region:")
    print(samples.groupby("region").agg(samples=("sample_id", "size"), pixels=("pixel_id", "nunique"),
                                        blocks=("block_id", "nunique")).to_string())
    crops = samples[samples["is_crop"]]
    share = pd.crosstab([crops["region"], crops["season_key"], crops["crop"]], crops["split"], normalize="index")
    print("\nsplit shares per crop class (target: train 0.60, val 0.20, test 0.20):")
    print(share.round(2).to_string())


if __name__ == "__main__":
    main()
