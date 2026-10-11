"""ORM for `land_climate` time-series."""

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, Numeric

from app.models.user import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class LandClimate(Base):
    __tablename__ = "land_climate"

    id = Column(Integer, primary_key=True, autoincrement=True)
    land_id = Column(Integer, ForeignKey("lands.land_id"), nullable=False, index=True)
    timestamp = Column(DateTime, default=_utcnow, nullable=False)
    temperature_celsius = Column(Numeric(10, 4), nullable=True)  # daily max (°C)
    temperature_min_c = Column(Numeric(10, 4), nullable=True)
    temperature_mean_c = Column(Numeric(10, 4), nullable=True)
    humidity_pct = Column(Numeric(10, 4), nullable=True)
    rainfall_mm = Column(Numeric(10, 4), nullable=True)
    source_id = Column(Integer, ForeignKey("data_sources.source_id"), nullable=True)
