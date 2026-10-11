"""ORM for `land_crops` time-series."""

from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, Numeric, String

from app.models.user import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class LandCrop(Base):
    __tablename__ = "land_crops"

    id = Column(Integer, primary_key=True, autoincrement=True)
    land_id = Column(Integer, ForeignKey("lands.land_id"), nullable=False, index=True)
    timestamp = Column(DateTime, default=_utcnow, nullable=False)
    crop_type = Column(String(100), nullable=True)
    ndvi_value = Column(Numeric(10, 4), nullable=True)
    dvi_value = Column(Numeric(10, 4), nullable=True)
    evi_value = Column(Numeric(10, 4), nullable=True)
    ndwi_value = Column(Numeric(10, 4), nullable=True)
    savi_value = Column(Numeric(10, 4), nullable=True)
    gndvi_value = Column(Numeric(10, 4), nullable=True)
    estimated_yield_tons = Column(Numeric(14, 4), nullable=True)
    growth_stage = Column(String(50), nullable=True)       # planting/vegetative/flowering/maturity/harvest
    ndvi_trend = Column(String(20), nullable=True)         # improving/stable/declining
    confidence = Column(Numeric(5, 4), nullable=True)      # ML confidence score 0-1
    zone_id = Column(Integer, ForeignKey("crop_zones.zone_id"), nullable=True, index=True)
    source_id = Column(Integer, ForeignKey("data_sources.source_id"), nullable=True)
    trust_tier = Column(String(16), nullable=True)
    is_synthetic = Column(Boolean, nullable=True, default=False)
