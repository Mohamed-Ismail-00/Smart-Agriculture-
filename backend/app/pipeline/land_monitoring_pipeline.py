"""
land_monitoring_pipeline.py
---------------------------
Scheduled monitoring cycle: incremental environment refresh, recent Sentinel
imagery, and light NDVI backfill for lands due per monitoring_interval_days.

Invoked from `app.scheduler.jobs` (Docker service `agri_scheduler`).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Iterable, Optional

from sqlalchemy.orm import Session

from app.lands import repository

logger = logging.getLogger(__name__)

ENVIRONMENT_REFRESH_DAYS = 7
SATELLITE_LOOKBACK_DAYS = 180
NDVI_LOOKBACK_DAYS = 90


def _is_due_for_monitoring(db: Session, land_id: int, interval_days: int) -> bool:
    """True when no climate rows exist or the latest row is older than the interval."""
    latest = repository.get_latest_climate_timestamp(db, land_id)
    if latest is None:
        return True
    if latest.tzinfo is None:
        latest = latest.replace(tzinfo=timezone.utc)
    elapsed_days = (datetime.now(timezone.utc) - latest).days
    return elapsed_days >= max(1, int(interval_days))


def _refresh_single_land(db: Session, land_id: int) -> bool:
    """Run incremental refreshes for one land. Returns True if any step succeeded."""
    from app.pipeline.land_discovery_pipeline import refresh_environment_data
    from app.tasks.satellite_task import run_ndvi_history_backfill, run_sentinel_visual_fetch

    land = repository.get_land(db, land_id)
    if land is None:
        return False

    succeeded = False

    if refresh_environment_data(land_id, db, days=ENVIRONMENT_REFRESH_DAYS):
        succeeded = True

    try:
        if run_sentinel_visual_fetch(land_id, db, days=SATELLITE_LOOKBACK_DAYS) > 0:
            succeeded = True
    except Exception:
        logger.exception("monitoring: sentinel visual fetch failed land_id=%s", land_id)
        db.rollback()

    try:
        if run_ndvi_history_backfill(land_id, db, days=NDVI_LOOKBACK_DAYS) > 0:
            succeeded = True
    except Exception:
        logger.exception("monitoring: NDVI backfill failed land_id=%s", land_id)
        db.rollback()

    if succeeded:
        try:
            repository.backfill_image_ndvi_means(db, land_id)
            db.commit()
        except Exception:
            logger.exception("monitoring: image NDVI backfill failed land_id=%s", land_id)
            db.rollback()

    return succeeded


def run_monitoring_cycle(
    db: Session,
    land_ids: Optional[Iterable[int]] = None,
    *,
    force: bool = False,
) -> list[int]:
    """
    Refresh due active lands with aligned environment, satellite, and NDVI snapshots.

    When `land_ids` is omitted, only lands whose latest climate row is older than
    `monitoring_interval_days` are processed (unless `force=True`).

    Returns internal land_ids that completed at least one refresh step.
    """
    if land_ids is not None:
        candidates = list(land_ids)
    else:
        candidates = []
        for lid in repository.list_land_ids_for_monitoring(db):
            land = repository.get_land(db, lid)
            if land is None:
                continue
            interval = int(land.monitoring_interval_days or 16)
            if force or _is_due_for_monitoring(db, lid, interval):
                candidates.append(lid)

    if not candidates:
        logger.info("monitoring cycle: no lands due for refresh")
        return []

    logger.info("monitoring cycle: processing %d land(s)", len(candidates))
    completed: list[int] = []

    for land_id in candidates:
        try:
            if _refresh_single_land(db, land_id):
                completed.append(land_id)
                logger.info("monitoring cycle: refreshed land_id=%s", land_id)
            else:
                logger.warning("monitoring cycle: no data updated for land_id=%s", land_id)
        except Exception:
            logger.exception("monitoring cycle: failed land_id=%s — skipping", land_id)
            db.rollback()

    logger.info("monitoring cycle: completed %d/%d land(s)", len(completed), len(candidates))
    return completed