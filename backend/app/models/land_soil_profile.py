"""
models/land_soil_profile.py
----------------------------
Static SoilGrids property profile for a land parcel.

Unlike `land_soil` (time-series moisture snapshots), this table stores
the structural soil properties from ISRIC SoilGrids — fetched once at
land registration and refreshed only when explicitly requested.

One row per land (upsert on refresh).  All measurements are topsoil (0-5cm)
plus optional subsurface (5-15cm, 15-30cm) stored as JSONB.
"""

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB

from app.models.user import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class LandSoilProfile(Base):
    """
    Static ISRIC SoilGrids profile — one authoritative row per land.

    Topsoil (0-5 cm) scalar columns are indexed for fast queries.
    Full depth profiles stored as JSONB for completeness.
    """
    __tablename__ = "land_soil_profiles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    land_id = Column(Integer, ForeignKey("lands.land_id"), nullable=False,
                     unique=True, index=True)   # one profile per land

    # Topsoil scalars (0-5cm) — most used for suitability scoring
    ph_h2o            = Column(Numeric(5, 2), nullable=True)   # pH units
    soc_g_per_kg      = Column(Numeric(8, 3), nullable=True)   # Soil Organic Carbon g/kg
    clay_pct          = Column(Numeric(6, 2), nullable=True)   # Clay %
    sand_pct          = Column(Numeric(6, 2), nullable=True)   # Sand %
    silt_pct          = Column(Numeric(6, 2), nullable=True)   # Silt %
    bulk_density      = Column(Numeric(6, 3), nullable=True)   # kg/dm³
    nitrogen_g_per_kg = Column(Numeric(7, 3), nullable=True)   # Total N g/kg
    cec_cmol          = Column(Numeric(8, 3), nullable=True)   # CEC cmol(c)/kg

    # Texture class derived from sand + clay
    texture_class = Column(String(32), nullable=True)          # loam | clay_loam | ...

    # Full depth profiles (raw JSONB from SoilGrids for all depths)
    depth_profile = Column(JSONB, nullable=True)

    # Computed suitability score (0–100) for the land's primary crop
    suitability_score = Column(Numeric(5, 2), nullable=True)

    fetched_at = Column(DateTime, default=_utcnow, nullable=False)
    source_id  = Column(Integer, ForeignKey("data_sources.source_id"), nullable=True)
    fetch_status = Column(String(16), nullable=True)
    fetch_attempts = Column(Integer, nullable=True, default=0)
    last_fetch_error = Column(String(512), nullable=True)
    trust_tier = Column(String(16), nullable=True)
