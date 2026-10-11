"""
connectors/sentinel.py
----------------------
Connector to Microsoft Planetary Computer STAC API.
Fetches real Sentinel-2 L2A imagery:
  - True Color (RGB) rendered PNGs
  - NDVI false-color rendered PNGs

Images are downloaded to /data/images/ and served via static files.
"""

import logging
import os
from pathlib import Path
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

STAC_API_URL = "https://planetarycomputer.microsoft.com/api/stac/v1/search"
DATA_API_URL = "https://planetarycomputer.microsoft.com/api/data/v1/item/preview.png"

TIMEOUT = 45.0
IMAGES_DIR = Path(os.environ.get("IMAGES_DIR", "/data/images"))


DATA_API_CROP_URL = "https://planetarycomputer.microsoft.com/api/data/v1/item/bbox/{bbox}.png"

import math
from datetime import datetime, timezone

# Sentinel-2 L2A scenes from processing baseline 04.00 on (every acquisition since
# 2022-01-25, plus older scenes ESA has reprocessed) store DN = reflectance * 10000 + 1000.
# Planetary Computer serves the raw DNs, so the offset has to be removed here; skipping it
# pulls NDVI down by roughly 0.25 over healthy crops.
BOA_ADD_OFFSET_DN = 1000
_BOA_OFFSET_FROM_BASELINE = 4.0
_BOA_OFFSET_FROM_DATE = datetime(2022, 1, 25, tzinfo=timezone.utc)


def boa_offset_dn(processing_baseline, acquired: Optional[datetime] = None) -> int:
    """DN offset to subtract for a scene, from its `s2:processing_baseline` (date as fallback)."""
    try:
        return BOA_ADD_OFFSET_DN if float(processing_baseline) >= _BOA_OFFSET_FROM_BASELINE else 0
    except (TypeError, ValueError):
        pass
    if acquired is None:
        return BOA_ADD_OFFSET_DN
    if acquired.tzinfo is None:
        acquired = acquired.replace(tzinfo=timezone.utc)
    return BOA_ADD_OFFSET_DN if acquired >= _BOA_OFFSET_FROM_DATE else 0

def compute_bbox_from_area(lat: float, lon: float, area_ha: float) -> list[float]:
    """
    Compute a bounding box centered at (lat, lon) that covers a given area in hectares.
    Adds a small buffer to ensure the full field is captured.
    """
    # 1 hectare = 10,000 square meters
    area_sq_m = area_ha * 10000.0
    # Approximate field as a circle, compute radius
    radius_m = math.sqrt(area_sq_m / math.pi)
    # Add 15% buffer
    radius_m *= 1.15
    # Convert meters to degrees (1 degree ~ 111320 meters at equator)
    # Adjust longitude scaling by latitude
    lat_rad = math.radians(lat)
    radius_deg_lat = radius_m / 111320.0
    radius_deg_lon = radius_m / (111320.0 * math.cos(lat_rad))
    
    return [
        lon - radius_deg_lon,
        lat - radius_deg_lat,
        lon + radius_deg_lon,
        lat + radius_deg_lat,
    ]


def _pad_bbox(bbox: list[float], pad: float = 0.002) -> list[float]:
    """Pad the bounding box to give surrounding context and increase image resolution."""
    return [
        bbox[0] - pad,
        bbox[1] - pad,
        bbox[2] + pad,
        bbox[3] + pad,
    ]

def _build_preview_url(
    collection: str,
    item_id: str,
    bbox: list[float],
    mode: str = "true_color",
    boa_offset: int = 0,
) -> str:
    """Build a Planetary Computer preview URL for an item, cropped to the padded bounding box."""
    padded_bbox = _pad_bbox(bbox)
    bbox_str = f"{padded_bbox[0]},{padded_bbox[1]},{padded_bbox[2]},{padded_bbox[3]}"
    base_url = DATA_API_CROP_URL.format(bbox=bbox_str)

    if mode == "ndvi":
        # The offset cancels in the numerator and appears twice in the denominator.
        denominator = f"(B08+B04-{2 * boa_offset})" if boa_offset else "(B08+B04)"
        params = {
            "collection": collection,
            "item": item_id,
            "expression": f"(B08-B04)/{denominator}",
            "asset_as_band": "true",
            "colormap_name": "rdylgn",
            "rescale": "-0.2,0.8",
        }
    else:
        params = {
            "collection": collection,
            "item": item_id,
            "assets": "visual",
            "asset_bidx": "visual|1,2,3",
        }
    # Use httpx to build properly URL-encoded query string
    req = httpx.Request("GET", base_url, params=params)
    return str(req.url)


def _download_image(url: str, timeout: float = TIMEOUT) -> Optional[bytes]:
    """Download an image from a URL and return raw bytes."""
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            resp = client.get(url)
            resp.raise_for_status()
            content_type = resp.headers.get("content-type", "")
            if "image" not in content_type and len(resp.content) < 1000:
                logger.warning("Response doesn't look like an image: %s bytes, type=%s",
                               len(resp.content), content_type)
                return None
            logger.info("Downloaded %d bytes from %s", len(resp.content), url)
            return resp.content
    except Exception as e:
        logger.error("Failed to download %s: %s", url, e)
        return None


def fetch_sentinel_visual_urls(
    bbox: list[float],
    max_cloud_cover: int = 15,
    limit: int = 60,
    days: int = 90,
) -> list[dict]:
    """
    Query STAC API for the most recent clear Sentinel-2 images within a bbox.

    Returns a list of dicts, each with:
        source, date, cloud_cover_pct, item_id, collection,
        true_color_url, ndvi_url
    """
    from datetime import datetime, timedelta, timezone
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=days)
    datetime_str = f"{start_date.strftime('%Y-%m-%dT%H:%M:%SZ')}/{end_date.strftime('%Y-%m-%dT%H:%M:%SZ')}"

    payload = {
        "collections": ["sentinel-2-l2a"],
        "bbox": bbox,
        "datetime": datetime_str,
        "query": {
            "eo:cloud_cover": {"lt": max_cloud_cover}
        },
        "limit": limit,
        "sortby": [{"field": "properties.datetime", "direction": "desc"}]
    }

    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            stac_resp = client.post(STAC_API_URL, json=payload)
            stac_resp.raise_for_status()
            data = stac_resp.json()

            features = data.get("features", [])
            if not features:
                logger.warning("No Sentinel-2 imagery found for bbox %s", bbox)
                return []

            results = []
            for item in features:
                item_id = item["id"]
                collection = item["collection"]
                properties = item.get("properties", {})
                date_str = properties.get("datetime", "")
                cloud_cover = properties.get("eo:cloud_cover", 0)

                acquired = None
                if date_str:
                    try:
                        acquired = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                    except ValueError:
                        pass
                offset = boa_offset_dn(properties.get("s2:processing_baseline"), acquired)

                tc_url = _build_preview_url(collection, item_id, bbox, "true_color")
                ndvi_url = _build_preview_url(collection, item_id, bbox, "ndvi", boa_offset=offset)

                results.append({
                    "source": "ESA Sentinel-2 via Planetary Computer",
                    "date": date_str,
                    "cloud_cover_pct": cloud_cover,
                    "item_id": item_id,
                    "collection": collection,
                    "true_color_url": tc_url,
                    "ndvi_url": ndvi_url,
                })

            return results

    except httpx.RequestError as e:
        logger.error("Network error communicating with STAC API: %s", e)
        return []
    except Exception as e:
        logger.error("Failed to fetch Sentinel URLs: %s", e)
        return []

def _empty_timeseries():
    import numpy as np
    return {
        "dates": [],
        "quality_scores": [],
        "B02": np.array([]),
        "B03": np.array([]),
        "B04": np.array([]),
        "B08": np.array([]),
        "B11": np.array([]),
    }


def fetch_sentinel_timeseries(bbox: list[float], days: int = 90, update_progress=None) -> dict:
    """
    Fetches a real time-series of Sentinel-2 L2A tiles over `days` using STAC.
    
    Returns a dict with numpy arrays of shape (T, H, W):
      'dates': list of datetime objects (length T)
      'B02': Blue reflectance
      'B03': Green reflectance
      'B04': Red reflectance
      'B08': NIR reflectance
      'B11': SWIR reflectance
    """
    import numpy as np
    from datetime import datetime, timedelta, timezone
    from pystac_client import Client
    import planetary_computer
    import odc.stac
    import pandas as pd

    try:
        return _fetch_sentinel_timeseries_impl(
            bbox=bbox,
            days=days,
            update_progress=update_progress,
            np=np,
            datetime=datetime,
            timedelta=timedelta,
            timezone=timezone,
            Client=Client,
            planetary_computer=planetary_computer,
            odc_stac=odc.stac,
            pd=pd,
        )
    except Exception as exc:
        logger.exception("Sentinel timeseries fetch failed for bbox=%s: %s", bbox, exc)
        return _empty_timeseries()


def _fetch_sentinel_timeseries_impl(
    *,
    bbox,
    days,
    update_progress,
    np,
    datetime,
    timedelta,
    timezone,
    Client,
    planetary_computer,
    odc_stac,
    pd,
) -> dict:
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=days)
    datetime_str = f"{start_date.strftime('%Y-%m-%dT%H:%M:%SZ')}/{end_date.strftime('%Y-%m-%dT%H:%M:%SZ')}"
    
    if update_progress:
        update_progress(f"Connecting to Planetary Computer STAC (searching past {days} days)...")
        
    client = Client.open(
        "https://planetarycomputer.microsoft.com/api/stac/v1",
        modifier=planetary_computer.sign_inplace,
    )

    search = client.search(
        collections=["sentinel-2-l2a"],
        bbox=bbox,
        datetime=datetime_str,
        query={"eo:cloud_cover": {"lt": 20}}
    )
    
    items = list(search.items())
    if not items:
        if update_progress:
            update_progress("No clear Sentinel-2 imagery found. Falling back to empty arrays.")
        return _empty_timeseries()
        
    if update_progress:
        update_progress(f"Found {len(items)} matching satellite scenes. Downloading multi-spectral bands (B02, B03, B04, B08, B11)...")
        
    # Load data using odc.stac (10m resolution approx = 0.0001 deg)
    ds = odc_stac.load(
        items,
        bbox=bbox,
        bands=["B02", "B03", "B04", "B08", "B11", "SCL"], # SCL is scene classification layer for cloud masking
        crs="EPSG:4326",
        resolution=0.0001,
        chunks={"time": 1, "latitude": 1024, "longitude": 1024}
    )
    
    if update_progress:
        update_progress("Computing multi-spectral arrays in memory using Dask...")
        
    # Compute the dataset (download happens here)
    ds = ds.compute()
    
    # Save the raw multi-spectral data to disk for Data Scientists before extracting NumPy arrays.
    import os
    save_dir = os.path.join(os.path.dirname(__file__), "..", "..", "data", "raw", "sentinel2")
    os.makedirs(save_dir, exist_ok=True)
    try:
        # Create a unique filename based on the bbox and current date
        filename = f"stac_{abs(int(bbox[0]*100))}_{abs(int(bbox[1]*100))}_{end_date.strftime('%Y%m%d')}.nc"
        filepath = os.path.join(save_dir, filename)
        if update_progress:
            update_progress(f"Saving raw GeoTIFF/NetCDF data to {filepath} for ML Training...")
        ds.to_netcdf(filepath)
    except Exception as e:
        logger.error("Failed to save raw Sentinel-2 NetCDF: %s", e)
    # ------------------------------------
    
    dates = pd.to_datetime(ds.time.values).to_pydatetime().tolist()

    # Reflectance = (DN - offset) / 10000, with the offset decided per scene (see boa_offset_dn).
    offset_by_time = {
        pd.Timestamp(item.datetime).tz_convert(None): boa_offset_dn(
            item.properties.get("s2:processing_baseline"), item.datetime
        )
        for item in items
    }
    offsets = np.array(
        [offset_by_time.get(pd.Timestamp(d), boa_offset_dn(None, d)) for d in dates],
        dtype=np.float32,
    )[:, None, None]

    def to_reflectance(dn):
        return (np.clip(dn.astype(np.float32) - offsets, 0.0, None) / 10000.0).astype(np.float32)

    # Create numpy arrays (T, H, W)
    b02 = to_reflectance(ds.B02.values)
    b03 = to_reflectance(ds.B03.values)
    b04 = to_reflectance(ds.B04.values)
    b08 = to_reflectance(ds.B08.values)
    b11 = to_reflectance(ds.B11.values)
    scl = ds.SCL.values
    
    if update_progress:
        update_progress("Applying cloud masking and quality scoring...")
        
    # Apply cloud masking (SCL values: 4=Vegetation, 5=Bare Soils, 6=Water, 3=Cloud shadows, 8,9,10=Clouds)
    # We will mask out 3, 8, 9, 10
    invalid_mask = np.isin(scl, [3, 8, 9, 10, 0, 1])
    
    clean_b02, clean_b03, clean_b04, clean_b08, clean_b11 = [], [], [], [], []
    quality_scores = []
    clean_dates = []
    
    for t in range(len(dates)):
        # Calculate quality (percentage of valid pixels)
        valid_pct = 1.0 - np.mean(invalid_mask[t])
        
        # If image is mostly clouds, skip it entirely
        if valid_pct < 0.2:
            continue
            
        # Apply mask (set invalid to NaN)
        m = invalid_mask[t]
        
        b02_t = np.where(m, np.nan, b02[t])
        b03_t = np.where(m, np.nan, b03[t])
        b04_t = np.where(m, np.nan, b04[t])
        b08_t = np.where(m, np.nan, b08[t])
        b11_t = np.where(m, np.nan, b11[t])
        
        clean_b02.append(b02_t)
        clean_b03.append(b03_t)
        clean_b04.append(b04_t)
        clean_b08.append(b08_t)
        clean_b11.append(b11_t)
        quality_scores.append(valid_pct)
        clean_dates.append(dates[t])
        
    return {
        "dates": clean_dates,
        "quality_scores": quality_scores,
        "B02": np.stack(clean_b02) if clean_b02 else np.array([]),
        "B03": np.stack(clean_b03) if clean_b03 else np.array([]),
        "B04": np.stack(clean_b04) if clean_b04 else np.array([]),
        "B08": np.stack(clean_b08) if clean_b08 else np.array([]),
        "B11": np.stack(clean_b11) if clean_b11 else np.array([]),
    }


def fetch_and_download_sentinel_images(
    bbox: list[float],
    max_cloud_cover: int = 15,
    limit: int = 30,
    days: int = 90,
    update_progress=None,
) -> list[dict]:
    """
    Fetch Sentinel-2 STAC metadata AND download actual PNG images into memory.

    Returns list of dicts with:
        date, cloud_cover_pct, image_type, image_data (bytes)
    """
    items = fetch_sentinel_visual_urls(bbox, max_cloud_cover, limit, days=days)
    if not items:
        return []

    downloaded = []
    total = len(items)
    for idx, item in enumerate(items, 1):
        if update_progress:
            update_progress(f"Downloading Sentinel-2 imagery {idx}/{total}...")
            
        cloud_pct = item["cloud_cover_pct"]

        # Download true color
        tc_bytes = _download_image(item["true_color_url"])
        if tc_bytes:
            downloaded.append({
                "date": item["date"],
                "cloud_cover_pct": cloud_pct,
                "image_type": "true_color",
                "image_data": tc_bytes,
            })

        # Download NDVI
        ndvi_bytes = _download_image(item["ndvi_url"])
        if ndvi_bytes:
            downloaded.append({
                "date": item["date"],
                "cloud_cover_pct": cloud_pct,
                "image_type": "ndvi",
                "image_data": ndvi_bytes,
            })

    logger.info("Downloaded %d Sentinel images", len(downloaded))
    return downloaded
