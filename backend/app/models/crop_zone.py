"""ORM for `crop_zones` — sub-areas within a land with distinct crop types."""

from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB

from app.models.user import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class CropZone(Base):
    __tablename__ = "crop_zones"

    zone_id = Column(Integer, primary_key=True, autoincrement=True)
    land_id = Column(Integer, ForeignKey("lands.land_id"), nullable=False, index=True)
    crop_type = Column(String(100), nullable=False)
    area_hectares = Column(Numeric(12, 4), nullable=True)
    area_pct = Column(Numeric(5, 2), nullable=True)           # % of total land
    boundary_polygon = Column(JSONB, nullable=True)
    status = Column(String(32), nullable=False, default="active")
    avg_confidence = Column(Numeric(5, 4), nullable=True)     # avg detection confidence
    latest_ndvi = Column(Numeric(6, 4), nullable=True)
    latest_growth_stage = Column(String(50), nullable=True)
    estimated_yield_tons = Column(Numeric(14, 4), nullable=True)
    detection_method = Column(String(64), nullable=True)
    trust_tier = Column(String(16), nullable=True)
    separation_score = Column(Numeric(6, 4), nullable=True)
    ambiguous = Column(Boolean, nullable=True, default=False)
    suppressed = Column(Boolean, nullable=True, default=False)
    zone_metadata = Column(JSONB, nullable=True)
    first_detected = Column(DateTime, default=_utcnow, nullable=False)
    last_updated = Column(DateTime, default=_utcnow, onupdate=_utcnow, nullable=False)
