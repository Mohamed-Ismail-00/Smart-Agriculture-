"""
models/water_record.py
------------------------
SQLAlchemy ORM definition for the `water_records` table.
"""

from datetime import datetime, timezone

from sqlalchemy import Column, Integer, DECIMAL, String, DateTime, ForeignKey, UniqueConstraint
from app.models.user import Base

def _utcnow() -> datetime:
    return datetime.now(timezone.utc)

class WaterRecord(Base):
    __tablename__ = "water_records"

    water_record_id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    location_id = Column(Integer, ForeignKey("locations.location_id"), nullable=False)
    crop = Column(String(100), nullable=False)
    year = Column(Integer, nullable=False)
    water_consumption_m3 = Column(DECIMAL(12, 2), nullable=True)
    irrigation_type = Column(String(50), nullable=True)
    batch_id = Column(Integer, ForeignKey("ingestion_batches.batch_id"), nullable=False)
    source_system = Column(String(100), nullable=False)
    ingestion_timestamp = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=_utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint('location_id', 'crop', 'year', 'batch_id',
                         name='uq_water_location_crop_year_batch'),
    )
