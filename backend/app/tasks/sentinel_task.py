"""
tasks/sentinel_task.py
----------------------
Background task: fetch real Sentinel-2 imagery from Microsoft Planetary Computer,
download PNGs locally, and store records in land_images.

Called by the land discovery pipeline (Step 5).
"""

import logging
from datetime import datetime

from sqlalchemy.orm import Session

from app.connectors import sentinel
from app.lands import geometry, repository

logger = logging.getLogger(__name__)


def run_sentinel_visual_fetch(land_id: int, db: Session, days: int = 180, limit: int = 30, update_progress=None) -> int:
    """
    Computes land bounding box, fetches up to 30 recent Sentinel-2 image pairs
    (true_color + NDVI) for the past year, downloads them into memory, and stores DB records.

    Returns the number of images stored.
    """
    logger.info("Starting Sentinel-2 visual fetch for land_id=%s, days=%d", land_id, days)

    # 1. Get land geometry
    land = repository.get_land(db, land_id)
    if not land or not land.boundary_polygon:
        logger.error("Land %s has no boundary_polygon — skipping Sentinel", land_id)
        return 0

    ring = land.boundary_polygon.get("coordinates", [[]])[0]
    if not ring:
        logger.error("Land %s has empty coordinates ring", land_id)
        return 0

    try:
        bbox = geometry.compute_bounding_box(ring)
    except Exception as e:
        logger.error("Failed to compute bbox for land %s: %s", land_id, e)
        return 0

    # 2. Fetch & download real images into memory
    if update_progress:
        update_progress("Fetching STAC metadata for visual previews...")
        
    downloaded = sentinel.fetch_and_download_sentinel_images(
        bbox=bbox,
        max_cloud_cover=20,
        limit=limit,
        days=days,
        update_progress=update_progress,
    )

    if not downloaded:
        logger.warning("No Sentinel images downloaded for land %s", land_id)
        return 0

    # 3. Store each image in the database
    count = 0
    ds = repository.get_or_create_data_source(db, "Sentinel-2 (Planetary Computer)")
    src_id = int(ds.source_id)

    for img in downloaded:
        try:
            # Parse date from ISO string
            date_str = img["date"]
            if "T" in date_str:
                ts = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            else:
                ts = datetime.strptime(date_str, "%Y-%m-%d")

            # Check for duplicates: same land + same date + same type
            existing = _check_duplicate(
                db, land_id, ts, img["image_type"]
            )
            if existing:
                logger.debug("Skipping duplicate: land=%s date=%s type=%s",
                             land_id, date_str, img["image_type"])
                continue

            ndvi_mean = None
            if img["image_type"] == "ndvi":
                primary = repository.get_primary_crop_zone(db, land_id)
                zone_id = int(primary.zone_id) if primary else None
                ndvi_mean = repository.find_crop_ndvi_near_date(
                    db, land_id, ts, zone_id=zone_id
                )

            repository.insert_land_image(
                db=db,
                land_id=land_id,
                image_data=img["image_data"],
                image_type=img["image_type"],
                cloud_cover_pct=img["cloud_cover_pct"],
                ndvi_mean=ndvi_mean,
                source_id=src_id,
                timestamp=ts,
            )
            count += 1
        except Exception as e:
            logger.error("Failed to insert image record: %s", e)
            continue

    db.commit()
    logger.info("Stored %d Sentinel images for land %s", count, land_id)
    return count


def _check_duplicate(
    db: Session,
    land_id: int,
    timestamp: datetime,
    image_type: str,
) -> bool:
    """Check if an image with the same land/date/type already exists."""
    from app.models.land_image import LandImage
    from sqlalchemy import select

    date_only = timestamp.date()
    stmt = (
        select(LandImage.id)
        .where(LandImage.land_id == land_id)
        .where(LandImage.image_type == image_type)
        .limit(1)
    )
    # Simple check — we filter by date in Python since MySQL datetime comparison
    rows = db.execute(stmt).scalars().all()
    for _ in rows:
        # If any image of this type exists, check dates
        all_images = db.execute(
            select(LandImage)
            .where(LandImage.land_id == land_id)
            .where(LandImage.image_type == image_type)
        ).scalars().all()
        for img in all_images:
            if img.timestamp.date() == date_only:
                return True
    return False
