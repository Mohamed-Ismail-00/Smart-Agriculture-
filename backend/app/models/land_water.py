"""ORM for `land_water` time-series."""

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, Numeric, String

from app.models.user import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class LandWater(Base):
    __tablename__ = "land_water"

    id = Column(Integer, primary_key=True, autoincrement=True)
    land_id = Column(Integer, ForeignKey("lands.land_id"), nullable=False, index=True)
    timestamp = Column(DateTime, default=_utcnow, nullable=False)
    estimated_water_usage_liters = Column(Numeric(14, 4), nullable=True)
    irrigation_status = Column(String(100), nullable=True)
    crop_water_requirement_mm = Column(Numeric(10, 4), nullable=True)   # FAO ET₀ based daily requirement
    water_efficiency_ratio = Column(Numeric(10, 4), nullable=True)      # yield_tons / water_liters
    source_id = Column(Integer, ForeignKey("data_sources.source_id"), nullable=True)
