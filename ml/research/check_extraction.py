"""
QA: are the stored pixel values the right pixels?

The downloader reads whole blocks and picks pixels out of them by row and column. Here a
few stored values are fetched again a different way: by asking GDAL for the value at each
pixel's map coordinate. Both routes must agree exactly, for 10 m and for 20 m bands.

    python research/check_extraction.py
"""

import json

import numpy as np
import pandas as pd
import rasterio

import grid as G
import s2
from config import BANDS, PIXEL_M, RAW_DIR, REGIONS, SEED

UNITS_PER_REGION = 3
PIXELS_PER_UNIT = 60
CHECK_BANDS = ["B04", "B8A", "B11"]     # one 10 m band, two 20 m bands


def main():
    rng = np.random.default_rng(SEED)
    total = mismatches = 0
    with rasterio.Env(**s2.GDAL_ENV):
        for region in REGIONS:
            files = sorted((RAW_DIR / region / "bands").glob("*/*.npz"))
            files = [f for f in files if not f.name.endswith(".part.npz")]
            if not files:
                print(f"{region}: nothing downloaded yet")
                continue
            g = G.region_grid(region)
            pixels = pd.read_parquet(RAW_DIR / region / "pixels.parquet")
            scenes = {(s["date"], s["tile"]): s for s in json.loads((RAW_DIR / region / "scenes.json").read_text())}
            for path in rng.choice(files, size=min(UNITS_PER_REGION, len(files)), replace=False):
                unit, date = path.parent.name, path.stem
                px = pixels[pixels["unit"] == unit].reset_index(drop=True)
                with np.load(path) as f:
                    values, quads = f["values"], f["quads"]
                assert len(values) == len(px), f"{path}: {len(values)} rows for {len(px)} pixels"
                fetched = np.nonzero(np.isin(px["quad"].to_numpy(), quads))[0]
                pick = rng.choice(fetched, size=min(PIXELS_PER_UNIT, len(fetched)), replace=False)
                x = g["x0"] + (px["col"].to_numpy()[pick] + 0.5) * PIXEL_M
                y = g["y1"] - (px["row"].to_numpy()[pick] + 0.5) * PIXEL_M
                scene = scenes[(date, unit.split("_")[0])]
                for band in CHECK_BANDS:
                    with s2.open_asset(scene["hrefs"][band]) as src:
                        independent = np.array([v[0] for v in src.sample(zip(x, y))])
                    stored = values[pick, BANDS.index(band)]
                    bad = int((independent != stored).sum())
                    total += len(pick)
                    mismatches += bad
                    print(f"{region} {unit} {date} {band}: {len(pick) - bad}/{len(pick)} identical "
                          f"(values {stored.min()}..{stored.max()})")
    print(f"\n{total - mismatches:,} of {total:,} values identical" + ("" if mismatches == 0 else "  <-- MISMATCH"))


if __name__ == "__main__":
    main()
