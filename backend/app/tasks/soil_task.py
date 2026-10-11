"""
tasks/soil_task.py
------------------
Per-land soil profile fetch and storage task.

Called once at land registration (discovery pipeline Step 4).
Can also be called manually to refresh profile data.
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.connectors import soilgrids
from app.lands import repository as land_repo
from app.soil import intelligence as soil_intel
from app.soil import repository as soil_repo
from app.trust.tier_resolver import TrustTierResolver

logger = logging.getLogger(__name__)


def run_soil_profile_task(land_id: int, db: Session) -> bool:
    """
    Fetch ISRIC SoilGrids profile for a land and persist it.

    Returns True if profile was successfully stored.
    """
    land = land_repo.get_land(db, land_id)
    if land is None:
        logger.warning("soil_task skipped: land_id=%s not found", land_id)
        return False

    lat = float(land.latitude)
    lon = float(land.longitude)

    result = soilgrids.fetch_soil_profile(lat, lon)
    if result.profile is None:
        logger.warning(
            "soil_task: SoilGrids fetch failed land_id=%s status=%s attempts=%s",
            land_id,
            result.status,
            result.attempts,
        )
        tier = TrustTierResolver.for_soil_profile(
            fetch_status=result.status,
            has_data=False,
        )
        soil_repo.upsert_soil_fetch_status(
            db,
            land_id,
            fetch_status=result.status,
            fetch_attempts=result.attempts,
            last_fetch_error=result.last_error,
            trust_tier=tier.value,
        )
        db.commit()
        return False

    profile = result.profile
    props = profile.get("properties", {})

    def _top(name: str):
        """Get 0-5cm value for a property."""
        return (props.get(name) or {}).get("0-5cm")

    ph       = _top("phh2o")
    soc      = _top("soc")
    clay     = _top("clay")
    sand     = _top("sand")
    silt     = _top("silt")
    bdod     = _top("bdod")
    nitrogen = _top("nitrogen")
    cec      = _top("cec")

    all_scores = soil_intel.score_all_crops(ph, clay, soc, nitrogen)
    best_score = max(all_scores.values()) if all_scores else None

    ds = land_repo.get_or_create_data_source(db, "ISRIC-SoilGrids-v2")
    tier = TrustTierResolver.for_soil_profile(fetch_status="success", has_data=True)

    soil_repo.upsert_soil_profile(
        db, land_id,
        ph_h2o=ph,
        soc_g_per_kg=soc,
        clay_pct=clay,
        sand_pct=sand,
        silt_pct=silt,
        bulk_density=bdod,
        nitrogen_g_per_kg=nitrogen,
        cec_cmol=cec,
        texture_class=profile.get("texture_class"),
        depth_profile=props,
        suitability_score=best_score,
        source_id=int(ds.source_id),
        fetch_status="success",
        fetch_attempts=result.attempts,
        last_fetch_error=None,
        trust_tier=tier.value,
    )

    db.commit()
    logger.info(
        "soil_task complete land_id=%s  ph=%.1f  clay=%.1f%%  soc=%.2f g/kg  best_score=%.1f",
        land_id,
        ph or 0, clay or 0, soc or 0, best_score or 0,
    )
    return True