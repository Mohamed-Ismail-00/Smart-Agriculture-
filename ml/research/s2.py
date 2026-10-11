"""Sentinel-2 L2A on Planetary Computer: scene inventory and windowed reads."""

import planetary_computer
import pystac_client
import rasterio
from rasterio.windows import Window

from config import BANDS

STAC_URL = "https://planetarycomputer.microsoft.com/api/stac/v1"
COLLECTION = "sentinel-2-l2a"
ASSETS = BANDS + ["SCL"]

# GDAL settings for reading Cloud-Optimized GeoTIFFs over HTTP.
GDAL_ENV = {
    "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
    "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".tif",
    "GDAL_HTTP_MAX_RETRY": "5",
    "GDAL_HTTP_RETRY_DELAY": "2",
    "GDAL_HTTP_TIMEOUT": "120",
    "GDAL_HTTP_CONNECTTIMEOUT": "30",
    # give up on a stalled transfer (under 1 KB/s for 30 s) instead of waiting out the timeout
    "GDAL_HTTP_LOW_SPEED_LIMIT": "1000",
    "GDAL_HTTP_LOW_SPEED_TIME": "30",
    "GDAL_HTTP_MERGE_CONSECUTIVE_RANGES": "YES",
    "GDAL_HTTP_MULTIRANGE": "YES",
}


def search_scenes(bounds_lonlat, start: str, end: str) -> list[dict]:
    """Every Sentinel-2 L2A scene touching the bounds in [start, end], one per tile and day."""
    client = pystac_client.Client.open(STAC_URL)
    search = client.search(collections=[COLLECTION], bbox=list(bounds_lonlat), datetime=f"{start}/{end}")
    scenes = {}
    for item in search.items():
        p = item.properties
        b04 = item.assets["B04"].extra_fields
        scene = {
            "id": item.id,
            "date": item.datetime.strftime("%Y-%m-%d"),
            "datetime": item.datetime.isoformat(),
            "tile": p.get("s2:mgrs_tile"),
            "orbit": p.get("sat:relative_orbit"),
            "baseline": p.get("s2:processing_baseline"),
            "generated": p.get("s2:generation_time") or "",
            "cloud_pct": p.get("eo:cloud_cover"),
            "nodata_pct": p.get("s2:nodata_pixel_percentage"),
            "epsg": p.get("proj:epsg") or int(str(p.get("proj:code", "EPSG:0")).split(":")[-1]),
            "transform_10m": b04.get("proj:transform"),
            "shape_10m": b04.get("proj:shape"),
            "hrefs": {a: item.assets[a].href for a in ASSETS},
        }
        # A scene can be published twice after reprocessing; keep the newest processing.
        key = (scene["date"], scene["tile"])
        rank = (str(scene["baseline"]), scene["generated"])
        if key not in scenes or rank > scenes[key][0]:
            scenes[key] = (rank, scene)
    return sorted((s for _, s in scenes.values()), key=lambda s: (s["date"], s["tile"]))


def open_asset(href: str):
    """Open a scene asset; the access token is refreshed by the SDK when it nears expiry."""
    return rasterio.open(planetary_computer.sign(href))


def read_window(src, row_off: int, col_off: int, height: int, width: int):
    return src.read(1, window=Window(col_off, row_off, width, height))
