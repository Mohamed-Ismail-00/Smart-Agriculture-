"""ORM for `land_images` (uploads + CV outputs)."""

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, LargeBinary, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB

from app.models.user import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class LandImage(Base):
    __tablename__ = "land_images"

    id = Column(Integer, primary_key=True, autoincrement=True)
    land_id = Column(Integer, ForeignKey("lands.land_id"), nullable=False, index=True)
    timestamp = Column(DateTime, default=_utcnow, nullable=False)
    # BYTEA in PostgreSQL — stores raw binary image data
    image_data = Column(LargeBinary, nullable=False)
    image_type = Column(String(100), nullable=False)
    cv_analysis_summary = Column(JSONB, nullable=True)
    ndvi_mean = Column(Numeric(6, 4), nullable=True)
    cloud_cover_pct = Column(Numeric(5, 2), nullable=True)
    source_id = Column(Integer, ForeignKey("data_sources.source_id"), nullable=True)
