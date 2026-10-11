"""
QA: are the FAO label maps registered to the Sentinel-2 pixels?

For each label map, one clear mid-season scene is read over a 10 km window. The labels are
then slid by a few pixels in every direction, and for each offset we measure how much of the
image's variance the classes explain (eta squared). If the maps are correctly registered,
the best offset is (0, 0).

    python research/check_alignment.py
"""

import json

import numpy as np
import rasterio

import grid as G
import s2
from config import FAO_NODATA, LABELS_DIR, REGIONS, SEASONS

WINDOW = 1024      # pixels (10.24 km)
MAX_SHIFT = 4      # pixels tested in each direction
MID_SEASON = {"winter": ("02-10", "03-15"), "summer": ("08-01", "08-31")}


def eta_squared(values: np.ndarray, labels: np.ndarray) -> float:
    """Share of the variance of `values` explained by the class labels."""
    ok = (labels != FAO_NODATA) & np.isfinite(values)
    v, lab = values[ok], labels[ok]
    total = ((v - v.mean()) ** 2).sum()
    between = sum((lab == c).sum() * (v[lab == c].mean() - v.mean()) ** 2 for c in np.unique(lab))
    return float(between / total)


def best_window(labels: np.ndarray, row_lo: int, row_hi: int) -> tuple[int, int]:
    """Top-left corner of the window with the most labelled pixels, inside the given rows."""
    best, corner = -1, (row_lo, 0)
    for r in range(row_lo, row_hi - WINDOW + 1, 256):
        for c in range(0, labels.shape[1] - WINDOW + 1, 256):
            n = int((labels[r:r + WINDOW, c:c + WINDOW] != FAO_NODATA).sum())
            if n > best:
                best, corner = n, (r, c)
    return corner


def main():
    results = {}
    with rasterio.Env(**s2.GDAL_ENV):
        for region, cfg in REGIONS.items():
            g = G.region_grid(region)
            bounds = G.region_bounds_lonlat(g)
            for season_key, map_code in cfg["maps"].items():
                season = SEASONS[season_key]["season"]
                year = SEASONS[season_key]["end"][:4]
                lo, hi = MID_SEASON[season]
                scenes = [s for s in s2.search_scenes(bounds, f"{year}-{lo}", f"{year}-{hi}") if s["orbit"] == 21]
                labels = G.warp_labels(map_code, g)

                # Use the tile that covers the most labelled rows, and its clearest scene.
                tile = max({s["tile"] for s in scenes}, key=lambda t: _rows_in_tile(g, scenes, t, labels))
                scene = min((s for s in scenes if s["tile"] == tile), key=lambda s: s["cloud_pct"])
                tile_x, tile_y = scene["transform_10m"][2], scene["transform_10m"][5]
                row_off = int((tile_y - g["y1"]) / 10)      # tile row of region row 0
                col_off = int((g["x0"] - tile_x) / 10)
                row_lo = max(0, -row_off) + MAX_SHIFT
                row_hi = min(g["height"], scene["shape_10m"][0] - row_off) - MAX_SHIFT
                r0, c0 = best_window(labels, row_lo, row_hi)

                with s2.open_asset(scene["hrefs"]["B04"]) as src:
                    red = s2.read_window(src, r0 + row_off, c0 + col_off, WINDOW, WINDOW).astype(np.float32)
                with s2.open_asset(scene["hrefs"]["B08"]) as src:
                    nir = s2.read_window(src, r0 + row_off, c0 + col_off, WINDOW, WINDOW).astype(np.float32)
                red[red == 0] = np.nan
                nir[nir == 0] = np.nan
                ndvi = (nir - red) / (nir + red - 2000)   # baseline 05.x: DN carries a +1000 offset

                scores = np.zeros((2 * MAX_SHIFT + 1, 2 * MAX_SHIFT + 1))
                for dy in range(-MAX_SHIFT, MAX_SHIFT + 1):
                    for dx in range(-MAX_SHIFT, MAX_SHIFT + 1):
                        shifted = labels[r0 + dy:r0 + dy + WINDOW, c0 + dx:c0 + dx + WINDOW]
                        scores[dy + MAX_SHIFT, dx + MAX_SHIFT] = np.mean(
                            [eta_squared(band, shifted) for band in (red, nir, ndvi)]
                        )
                iy, ix = np.unravel_index(scores.argmax(), scores.shape)
                best = (int(iy - MAX_SHIFT), int(ix - MAX_SHIFT))
                at_zero = scores[MAX_SHIFT, MAX_SHIFT]
                print(f"\n{region} {season_key} ({map_code}) scene {scene['date']} {tile} cloud {scene['cloud_pct']:.1f}%")
                print(f"  eta2 at (0,0) = {at_zero:.4f}; best = {scores.max():.4f} at (dy,dx) = {best}")
                print("  eta2 by offset (rows dy=-2..2, cols dx=-2..2):")
                for dy in range(-2, 3):
                    print("   ", " ".join(f"{scores[dy + MAX_SHIFT, dx + MAX_SHIFT]:.4f}" for dx in range(-2, 3)))
                results[f"{region}_{season_key}"] = {
                    "scene": scene["id"], "best_offset_dy_dx": best,
                    "eta2_at_zero": round(float(at_zero), 4), "eta2_best": round(float(scores.max()), 4),
                }
    LABELS_DIR.mkdir(parents=True, exist_ok=True)
    (LABELS_DIR / "alignment_check.json").write_text(json.dumps(results, indent=2))


def _rows_in_tile(g, scenes, tile, labels) -> int:
    scene = next(s for s in scenes if s["tile"] == tile)
    row_off = int((scene["transform_10m"][5] - g["y1"]) / 10)
    lo, hi = max(0, -row_off), min(g["height"], scene["shape_10m"][0] - row_off)
    return int((labels[lo:hi] != FAO_NODATA).sum()) if hi > lo else 0


if __name__ == "__main__":
    main()
