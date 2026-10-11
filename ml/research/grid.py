"""Region grids on the Sentinel-2 pixel lattice, and FAO label maps warped onto them."""

import math

import numpy as np
import rasterio
from rasterio.transform import from_origin
from rasterio.warp import Resampling, reproject, transform, transform_bounds

from config import CRS_UTM, FAO_DIR, FAO_NODATA, PIXEL_M, REGIONS


def fao_path(map_code: str):
    return FAO_DIR / f"WAPOR-3.L3-CROP-TYPE.{map_code}.tif"


def region_grid(region: str) -> dict:
    """
    Top-left corner and size of a region's grid.

    Edges are snapped to multiples of 20 m: Sentinel-2 tiles start on that lattice, so every
    grid pixel coincides with one native 10 m pixel and sits inside one native 20 m pixel.
    """
    xs, ys = [], []
    for map_code in REGIONS[region]["maps"].values():
        with rasterio.open(fao_path(map_code)) as src:
            if src.crs.to_epsg() != 4326:
                raise ValueError(f"{map_code}: expected EPSG:4326, got {src.crs}")
            left, bottom, right, top = transform_bounds(src.crs, CRS_UTM, *src.bounds, densify_pts=41)
        xs += [left, right]
        ys += [bottom, top]
    x0 = math.floor(min(xs) / 20) * 20
    y1 = math.ceil(max(ys) / 20) * 20
    width = math.ceil((max(xs) - x0) / 20) * 2
    height = math.ceil((y1 - min(ys)) / 20) * 2
    return {"x0": x0, "y1": y1, "width": width, "height": height}


def grid_transform(grid: dict):
    return from_origin(grid["x0"], grid["y1"], PIXEL_M, PIXEL_M)


def warp_labels(map_code: str, grid: dict) -> np.ndarray:
    """FAO class codes on the region grid (nearest neighbour: class codes must not be blended)."""
    labels = np.full((grid["height"], grid["width"]), FAO_NODATA, dtype=np.uint8)
    with rasterio.open(fao_path(map_code)) as src:
        reproject(
            source=rasterio.band(src, 1),
            destination=labels,
            dst_transform=grid_transform(grid),
            dst_crs=CRS_UTM,
            src_nodata=FAO_NODATA,
            dst_nodata=FAO_NODATA,
            resampling=Resampling.nearest,
        )
    return labels


def pixel_centres(grid: dict, rows: np.ndarray, cols: np.ndarray):
    """UTM and geographic coordinates of pixel centres."""
    x = grid["x0"] + (cols + 0.5) * PIXEL_M
    y = grid["y1"] - (rows + 0.5) * PIXEL_M
    lon, lat = transform(CRS_UTM, "EPSG:4326", x.tolist(), y.tolist())
    return x, y, np.asarray(lon), np.asarray(lat)


def region_bounds_lonlat(grid: dict) -> tuple:
    left, top = grid["x0"], grid["y1"]
    right, bottom = left + grid["width"] * PIXEL_M, top - grid["height"] * PIXEL_M
    return transform_bounds(CRS_UTM, "EPSG:4326", left, bottom, right, top, densify_pts=41)
