"""
Step 2 - fetch Sentinel-2 values for the sampled pixels.

Sentinel-2 files are tiled internally in 512x512 blocks, and a block has to be downloaded
whole even if one pixel is wanted. The work is therefore organised in "units": one unit is
a 10.24 km square of one scene, i.e. one internal block of the 20 m bands and up to four of
the 10 m bands.

  phase A  the Scene Classification layer (tiny) for every scene, whole region.
           It says where the clouds are before anything large is downloaded.
  phase B  the ten spectral bands, unit by unit, skipping squares that are cloudy.
           Squares are finished one at a time (all dates), so stopping early still leaves
           complete time series for part of each region.

Everything is resumable: finished pieces are never downloaded twice.

    python research/step2_download.py --plan          # sizes and time, downloads only phase A
    python research/step2_download.py                 # run / resume
    python research/step2_download.py --max-gb 2      # stop after about 2 GB
"""

import argparse
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd
import rasterio

import grid as G
import s2
from config import BANDS, BANDS_10M, LABELS_DIR, ORBIT, RAW_DIR, REGIONS, SCL_INVALID, SEED

BLOCK = 512                 # internal block size of the files, in their own pixels
MIN_CLEAR = 0.10            # a 5 km quadrant is fetched only if >= 10% of its sampled pixels are clear
# Quadrants on the ragged edge of a region hold a handful of sampled pixels but cost as much
# to download as a full one. Below this count they are left out (about 6% of Zankalon's
# pixels and under 1% of Sidi Ghazi's, spread evenly over the crop classes).
MIN_QUADRANT_PIXELS = 5_000
SCL_HALO = 32               # 20 m pixels read around the region so cloud distances are right at its edge
EST_MB = {10: 0.39, 20: 0.43}   # measured mean size of one compressed block, per band
UNITS_IN_FLIGHT = 3         # units downloaded at once, so one unit's waiting overlaps another's transfer


# ---------------------------------------------------------------------------
# Inventory and geometry
# ---------------------------------------------------------------------------

def load_scenes(region: str, grid: dict) -> list[dict]:
    """Scene list for a region, cached so that a resumed run plans exactly the same work."""
    path = RAW_DIR / region / "scenes.json"
    if path.exists():
        return json.loads(path.read_text())
    scenes = s2.search_scenes(G.region_bounds_lonlat(grid), *REGIONS[region]["imagery"])
    scenes = [s for s in scenes if s["orbit"] == ORBIT]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(scenes))
    return scenes


def load_pixels(region: str, grid: dict, scenes: list[dict]) -> pd.DataFrame:
    """
    Distinct sampled pixels of a region with their position inside a Sentinel-2 tile.

    Columns: pixel_id, row, col (region grid), tile, R, C (tile grid, 10 m), unit, quad.
    A pixel covered by two overlapping tiles is read from the tile holding most pixels.
    """
    samples = pd.read_parquet(LABELS_DIR / "samples.parquet", columns=["region", "pixel_id", "row", "col"])
    px = samples[samples["region"] == region].drop_duplicates("pixel_id").sort_values("pixel_id")
    px = px.drop(columns="region").reset_index(drop=True)

    geometry = {}
    for s in scenes:
        t = s["transform_10m"]
        geometry[s["tile"]] = (round((t[5] - grid["y1"]) / 10), round((grid["x0"] - t[2]) / 10), s["shape_10m"])

    def inside(tile):
        row_off, col_off, (height, width) = geometry[tile]
        r, c = px["row"] + row_off, px["col"] + col_off
        return ((r >= 0) & (r < height) & (c >= 0) & (c < width)).to_numpy()

    px["tile"] = ""
    for tile in sorted(geometry, key=lambda t: -inside(t).sum()):
        take = inside(tile) & (px["tile"] == "").to_numpy()
        px.loc[take, "tile"] = tile
        px.loc[take, "R"] = px.loc[take, "row"] + geometry[tile][0]
        px.loc[take, "C"] = px.loc[take, "col"] + geometry[tile][1]
    if (px["tile"] == "").any():
        raise RuntimeError(f"{region}: {(px['tile'] == '').sum()} sampled pixels are outside every tile")
    px[["R", "C"]] = px[["R", "C"]].astype(np.int32)
    sbr, sbc = px["R"] // (2 * BLOCK), px["C"] // (2 * BLOCK)
    px["unit"] = px["tile"] + "_" + sbr.astype(str).str.zfill(2) + "_" + sbc.astype(str).str.zfill(2)
    px["quad"] = ((px["R"] // BLOCK) % 2 * 2 + (px["C"] // BLOCK) % 2).astype(np.int8)
    in_quadrant = px.groupby(["unit", "quad"])["pixel_id"].transform("size")
    return px[in_quadrant >= MIN_QUADRANT_PIXELS].reset_index(drop=True)


# ---------------------------------------------------------------------------
# Phase A: scene classification
# ---------------------------------------------------------------------------

def scl_window(px_tile: pd.DataFrame, shape_10m) -> tuple:
    """(row, col, height, width) in 20 m pixels covering the tile's sampled pixels plus a halo."""
    height20, width20 = shape_10m[0] // 2, shape_10m[1] // 2
    r0 = max(0, int(px_tile["R"].min()) // 2 - SCL_HALO)
    c0 = max(0, int(px_tile["C"].min()) // 2 - SCL_HALO)
    r1 = min(height20, int(px_tile["R"].max()) // 2 + SCL_HALO + 1)
    c1 = min(width20, int(px_tile["C"].max()) // 2 + SCL_HALO + 1)
    return r0, c0, r1 - r0, c1 - c0


def scl_path(region: str, scene: dict):
    return RAW_DIR / region / "scl" / f"{scene['date']}_{scene['tile']}.npz"


def fetch_scl(region: str, scene: dict, window: tuple):
    path = scl_path(region, scene)
    if path.exists():
        return
    with rasterio.Env(**s2.GDAL_ENV), s2.open_asset(scene["hrefs"]["SCL"]) as src:
        scl = s2.read_window(src, *window)
    save_npz(path, scl=scl, r0=window[0], c0=window[1])


def pixel_scl(region: str, scene: dict, px_tile: pd.DataFrame) -> np.ndarray:
    with np.load(scl_path(region, scene)) as f:
        return f["scl"][px_tile["R"].to_numpy() // 2 - int(f["r0"]), px_tile["C"].to_numpy() // 2 - int(f["c0"])]


# ---------------------------------------------------------------------------
# Phase B: spectral bands
# ---------------------------------------------------------------------------

def read_band(href: str, is_10m: bool, sbr: int, sbc: int, R, C, quad, quads) -> tuple:
    """Values of one band for a unit's pixels (0 where the quadrant was not fetched), and bytes read."""
    out = np.zeros(len(R), dtype=np.uint16)
    nbytes = 0
    with rasterio.Env(**s2.GDAL_ENV), s2.open_asset(href) as src:
        if is_10m:
            for q in quads:
                br, bc = sbr * 2 + q // 2, sbc * 2 + q % 2
                r0, c0 = br * BLOCK, bc * BLOCK
                block = s2.read_window(src, r0, c0, min(BLOCK, src.height - r0), min(BLOCK, src.width - c0))
                sel = quad == q
                out[sel] = block[R[sel] - r0, C[sel] - c0]
                nbytes += int(src.get_tag_item(f"BLOCK_SIZE_{bc}_{br}", "TIFF", bidx=1) or 0)
        else:
            # A 10 m pixel (R, C) lies inside the 20 m pixel (R // 2, C // 2): no resampling.
            r0, c0 = sbr * BLOCK, sbc * BLOCK
            block = s2.read_window(src, r0, c0, min(BLOCK, src.height - r0), min(BLOCK, src.width - c0))
            sel = np.isin(quad, quads)
            out[sel] = block[R[sel] // 2 - r0, C[sel] // 2 - c0]
            nbytes += int(src.get_tag_item(f"BLOCK_SIZE_{sbc}_{sbr}", "TIFF", bidx=1) or 0)
    return out, nbytes


def retrying(fn, *args, attempts: int = 4):
    for attempt in range(attempts):
        try:
            return fn(*args)
        except Exception:
            if attempt == attempts - 1:
                raise
            time.sleep(4 * (attempt + 1))


def unit_path(region: str, unit: str, date: str):
    return RAW_DIR / region / "bands" / unit / f"{date}.npz"


# (region, unit) -> (R, C, quad) arrays of the unit's pixels, in pixel_id order.
UNIT_PIXELS: dict = {}


def fetch_unit(task: dict, pool: ThreadPoolExecutor) -> int:
    """Download one unit (one 10 km square of one scene). Returns compressed bytes read."""
    sbr, sbc = (int(v) for v in task["unit"].split("_")[1:])
    R, C, quad = UNIT_PIXELS[(task["region"], task["unit"])]
    futures = [
        pool.submit(retrying, read_band, task["scene"]["hrefs"][band], band in BANDS_10M, sbr, sbc, R, C, quad, task["quads"])
        for band in BANDS
    ]
    results = [f.result() for f in futures]
    values = np.stack([r[0] for r in results], axis=1)
    save_npz(unit_path(task["region"], task["unit"], task["scene"]["date"]),
             values=values, quads=np.array(task["quads"], dtype=np.uint8))
    return sum(r[1] for r in results)


def save_npz(path, **arrays):
    """Write atomically, so an interrupted run never leaves a half-written file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.stem + ".part.npz")
    np.savez_compressed(tmp, **arrays)
    os.replace(tmp, path)


# ---------------------------------------------------------------------------
# Planning
# ---------------------------------------------------------------------------

def prepare_region(region: str) -> list[dict]:
    """Run phase A for a region and return its phase B tasks (finished or not)."""
    grid = G.region_grid(region)
    scenes = load_scenes(region, grid)
    px = load_pixels(region, grid, scenes)
    region_dir = RAW_DIR / region
    pixels_path = region_dir / "pixels.parquet"
    if pixels_path.exists() and any((region_dir / "bands").glob("*/*.npz")):
        # Downloaded files hold values in the order of this pixel list; it must not change under them.
        if not pd.read_parquet(pixels_path, columns=["pixel_id"])["pixel_id"].equals(px["pixel_id"]):
            raise RuntimeError(
                f"{region}: the sampled pixels changed after the download started. "
                f"Delete {region_dir / 'bands'} to start this region again."
            )
    px.to_parquet(pixels_path, index=False)

    used_tiles = sorted(px["tile"].unique())
    scenes = [s for s in scenes if s["tile"] in used_tiles]
    by_tile = {tile: px[px["tile"] == tile] for tile in used_tiles}
    windows = {tile: scl_window(by_tile[tile], next(s for s in scenes if s["tile"] == tile)["shape_10m"])
               for tile in used_tiles}

    missing = [s for s in scenes if not scl_path(region, s).exists()]
    if missing:
        print(f"{region}: phase A - scene classification for {len(missing)} scenes ...", flush=True)
        with ThreadPoolExecutor(8) as pool:
            list(pool.map(lambda s: retrying(fetch_scl, region, s, windows[s["tile"]]), missing))

    for unit, group in px.groupby("unit", sort=True):
        UNIT_PIXELS[(region, unit)] = (group["R"].to_numpy(), group["C"].to_numpy(), group["quad"].to_numpy())

    # Clear share of every (unit, quadrant) per scene, counted with integer codes.
    codes = {}
    for tile, px_tile in by_tile.items():
        names, unit_idx = np.unique(px_tile["unit"].to_numpy(), return_inverse=True)
        code = unit_idx * 4 + px_tile["quad"].to_numpy()
        codes[tile] = (names, code, np.bincount(code, minlength=len(names) * 4))

    tasks, clear_shares, nodata_shares = [], [], []
    for scene in scenes:
        names, code, n_pixels = codes[scene["tile"]]
        scl = pixel_scl(region, scene, by_tile[scene["tile"]])
        clear = ~np.isin(scl, SCL_INVALID)
        clear_shares.append(clear.mean())
        nodata_shares.append((scl == 0).mean())
        n_clear = np.bincount(code, weights=clear, minlength=len(n_pixels))
        wanted = (n_pixels > 0) & (n_clear >= MIN_CLEAR * n_pixels)
        for i, unit in enumerate(names):
            quads = np.nonzero(wanted[i * 4:i * 4 + 4])[0].tolist()
            if quads:
                tasks.append({"region": region, "unit": unit, "scene": scene, "quads": quads})
    dates = sorted({s["date"] for s in scenes})
    print(f"{region}: {len(px):,} pixels, tiles {used_tiles}, {px['unit'].nunique()} squares, "
          f"{len(dates)} dates {dates[0]}..{dates[-1]}", flush=True)
    print(f"   sampled pixels clear per scene: mean {np.mean(clear_shares):.0%}; "
          f"outside the swath: mean {np.mean(nodata_shares):.1%}, worst scene {np.max(nodata_shares):.1%}", flush=True)
    return tasks


def estimate_mb(task: dict) -> float:
    return len(task["quads"]) * 4 * EST_MB[10] + 6 * EST_MB[20]


def ordered(tasks: list[dict]) -> list[dict]:
    """Square by square (all dates of a square together), squares shuffled, regions interleaved."""
    rng = np.random.default_rng(SEED)
    per_region = {}
    for region in sorted({t["region"] for t in tasks}):
        units = sorted({t["unit"] for t in tasks if t["region"] == region})
        per_region[region] = [units[i] for i in rng.permutation(len(units))]
    rank = {}
    for region, units in per_region.items():
        for i, unit in enumerate(units):
            rank[(region, unit)] = (i / len(units), region)
    return sorted(tasks, key=lambda t: (rank[(t["region"], t["unit"])], t["scene"]["date"]))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--regions", nargs="+", default=list(REGIONS))
    parser.add_argument("--plan", action="store_true", help="phase A and the size estimate only")
    parser.add_argument("--max-gb", type=float, default=None, help="stop after about this much in this run")
    args = parser.parse_args()

    tasks = ordered([t for region in args.regions for t in prepare_region(region)])
    todo = [t for t in tasks if not unit_path(t["region"], t["unit"], t["scene"]["date"]).exists()]
    total_mb, todo_mb = sum(map(estimate_mb, tasks)), sum(map(estimate_mb, todo))
    print(f"\nphase B: {len(tasks):,} units in total (~{total_mb / 1024:.1f} GB); "
          f"{len(tasks) - len(todo):,} done; {len(todo):,} to fetch (~{todo_mb / 1024:.1f} GB)", flush=True)
    for region in args.regions:
        r_all = [t for t in tasks if t["region"] == region]
        r_todo = [t for t in todo if t["region"] == region]
        print(f"   {region}: {len(r_all):,} units ~{sum(map(estimate_mb, r_all)) / 1024:.1f} GB, "
              f"{len(r_todo):,} left ~{sum(map(estimate_mb, r_todo)) / 1024:.1f} GB", flush=True)
    if args.plan or not todo:
        return

    if os.name == "nt":
        # Keep Windows from sleeping while the download runs (released when the script exits).
        import ctypes
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000001)

    started, got_bytes = time.time(), 0
    progress_path = RAW_DIR / "progress.json"

    def attempt(task, band_pool):
        try:
            return retrying(fetch_unit, task, band_pool, attempts=3), None
        except Exception as exc:  # reported below; the unit is retried in the next pass
            return 0, exc

    # A unit that fails (connection drop) is tried again in a later pass.
    for n_pass in range(1, 4):
        todo = [t for t in tasks if not unit_path(t["region"], t["unit"], t["scene"]["date"]).exists()]
        if not todo:
            break
        if n_pass > 1:
            print(f"pass {n_pass}: retrying {len(todo)} units", flush=True)
        stop = False
        units_pool = ThreadPoolExecutor(UNITS_IN_FLIGHT)
        with ThreadPoolExecutor(UNITS_IN_FLIGHT * len(BANDS)) as band_pool:
            results = units_pool.map(lambda t: attempt(t, band_pool), todo)
            for i, (task, (nbytes, error)) in enumerate(zip(todo, results), 1):
                got_bytes += nbytes
                if error is not None:
                    print(f"   failed {task['region']} {task['unit']} {task['scene']['date']}: {error}", flush=True)
                if i % 20 == 0 or i == len(todo):
                    elapsed = time.time() - started
                    left_mb = sum(map(estimate_mb, todo[i:]))
                    speed = got_bytes / 1e6 / elapsed
                    eta_min = left_mb / max(speed, 1e-6) / 60
                    print(f"   {i:,}/{len(todo):,} units  {got_bytes / 1e9:.2f} GB  {speed:.2f} MB/s  "
                          f"elapsed {elapsed / 60:.0f} min  left ~{left_mb / 1024:.1f} GB ~{eta_min:.0f} min", flush=True)
                    progress_path.write_text(json.dumps({
                        "updated": time.strftime("%Y-%m-%d %H:%M:%S"), "units_total": len(tasks),
                        "units_done": len(tasks) - len(todo) + i, "gb_this_run": round(got_bytes / 1e9, 2),
                        "mb_per_s": round(speed, 2), "minutes_left": round(eta_min),
                    }))
                if args.max_gb is not None and got_bytes / 1e9 >= args.max_gb:
                    print(f"stopping: reached --max-gb {args.max_gb}", flush=True)
                    stop = True
                    break
            units_pool.shutdown(wait=True, cancel_futures=True)
        if stop:
            break

    left = sum(not unit_path(t["region"], t["unit"], t["scene"]["date"]).exists() for t in tasks)
    print(f"finished this run: {got_bytes / 1e9:.2f} GB read in {(time.time() - started) / 60:.0f} min; "
          f"{len(tasks) - left:,} of {len(tasks):,} units on disk" + (f"; {left} missing - run again" if left else ""),
          flush=True)


if __name__ == "__main__":
    main()
