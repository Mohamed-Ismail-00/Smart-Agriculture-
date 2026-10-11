"""
soil/repository.py
------------------
Persistence helpers for LandSoilProfile (static SoilGrids data).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.land_soil_profile import LandSoilProfile


def get_soil_profile(db: Session, land_id: int) -> Optional[LandSoilProfile]:
    """Fetch the stored profile for a land, or None if not yet populated."""
    return db.execute(
        select(LandSoilProfile).where(LandSoilProfile.land_id == land_id)
    ).scalar_one_or_none()


def upsert_soil_profile(
    db: Session,
    land_id: int,
    *,
    ph_h2o: Optional[float] = None,
    soc_g_per_kg: Optional[float] = None,
    clay_pct: Optional[float] = None,
    sand_pct: Optional[float] = None,
    silt_pct: Optional[float] = None,
    bulk_density: Optional[float] = None,
    nitrogen_g_per_kg: Optional[float] = None,
    cec_cmol: Optional[float] = None,
    texture_class: Optional[str] = None,
    depth_profile: Optional[dict[str, Any]] = None,
    suitability_score: Optional[float] = None,
    source_id: Optional[int] = None,
    fetch_status: Optional[str] = None,
    fetch_attempts: Optional[int] = None,
    last_fetch_error: Optional[str] = None,
    trust_tier: Optional[str] = None,
) -> LandSoilProfile:
    """
    Insert or update the soil profile for a land.
    One row per land enforced by the unique index on land_id.
    """
    def _dec(v: Optional[float]) -> Optional[Decimal]:
        return Decimal(str(v)) if v is not None else None

    existing = get_soil_profile(db, land_id)
    if existing is not None:
        existing.ph_h2o            = _dec(ph_h2o)
        existing.soc_g_per_kg      = _dec(soc_g_per_kg)
        existing.clay_pct          = _dec(clay_pct)
        existing.sand_pct          = _dec(sand_pct)
        existing.silt_pct          = _dec(silt_pct)
        existing.bulk_density      = _dec(bulk_density)
        existing.nitrogen_g_per_kg = _dec(nitrogen_g_per_kg)
        existing.cec_cmol          = _dec(cec_cmol)
        existing.texture_class     = texture_class
        existing.depth_profile     = depth_profile
        existing.suitability_score = _dec(suitability_score)
        existing.source_id         = source_id
        if fetch_status is not None:
            existing.fetch_status = fetch_status
        if fetch_attempts is not None:
            existing.fetch_attempts = fetch_attempts
        if last_fetch_error is not None:
            existing.last_fetch_error = last_fetch_error
        elif fetch_status == "success":
            existing.last_fetch_error = None
        if trust_tier is not None:
            existing.trust_tier = trust_tier
        from datetime import datetime, timezone
        existing.fetched_at = datetime.now(timezone.utc)
        db.flush()
        return existing

    row = LandSoilProfile(
        land_id=land_id,
        ph_h2o=_dec(ph_h2o),
        soc_g_per_kg=_dec(soc_g_per_kg),
        clay_pct=_dec(clay_pct),
        sand_pct=_dec(sand_pct),
        silt_pct=_dec(silt_pct),
        bulk_density=_dec(bulk_density),
        nitrogen_g_per_kg=_dec(nitrogen_g_per_kg),
        cec_cmol=_dec(cec_cmol),
        texture_class=texture_class,
        depth_profile=depth_profile,
        suitability_score=_dec(suitability_score),
        source_id=source_id,
        fetch_status=fetch_status,
        fetch_attempts=fetch_attempts or 0,
        last_fetch_error=last_fetch_error,
        trust_tier=trust_tier,
    )
    db.add(row)
    db.flush()
    return row


def upsert_soil_fetch_status(
    db: Session,
    land_id: int,
    *,
    fetch_status: str,
    fetch_attempts: int,
    last_fetch_error: Optional[str] = None,
    trust_tier: Optional[str] = None,
) -> LandSoilProfile:
    """Record a failed SoilGrids fetch without overwriting prior successful data."""
    existing = get_soil_profile(db, land_id)
    if existing is not None and existing.depth_profile is not None:
        existing.fetch_status = fetch_status
        existing.fetch_attempts = fetch_attempts
        existing.last_fetch_error = last_fetch_error
        if trust_tier is not None:
            existing.trust_tier = trust_tier
        db.flush()
        return existing

    return upsert_soil_profile(
        db,
        land_id,
        fetch_status=fetch_status,
        fetch_attempts=fetch_attempts,
        last_fetch_error=last_fetch_error,
        trust_tier=trust_tier,
    )
