"""
models/climate_record.py
------------------------
SQLAlchemy ORM definition for the `climate_records` table.
"""

from datetime import datetime, timezone

from sqlalchemy import Column, Integer, DECIMAL, String, DateTime, ForeignKey, UniqueConstraint
from app.models.user import Base

def _utcnow() -> datetime:
    return datetime.now(timezone.utc)

class ClimateRecord(Base):
    __tablename__ = "climate_records"

    climate_record_id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    location_id = Column(Integer, ForeignKey("locations.location_id"), nullable=False)
    year = Column(Integer, nullable=False)
    temperature_mean = Column(DECIMAL(10, 4), nullable=True)
    humidity_pct = Column(DECIMAL(10, 4), nullable=True)
    batch_id = Column(Integer, ForeignKey("ingestion_batches.batch_id"), nullable=False)
    source_system = Column(String(100), nullable=False)
    ingestion_timestamp = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=_utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint('location_id', 'year', 'batch_id', name='uq_climate_location_year_batch'),
    )
