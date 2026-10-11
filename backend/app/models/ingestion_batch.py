"""
models/ingestion_batch.py
-------------------------
SQLAlchemy ORM definition for the `ingestion_batches` table.
"""

from datetime import datetime, timezone

from sqlalchemy import Column, Integer, String, DateTime
from app.models.user import Base

def _utcnow() -> datetime:
    return datetime.now(timezone.utc)

class IngestionBatch(Base):
    __tablename__ = "ingestion_batches"

    batch_id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    source_system = Column(String(100), nullable=False)
    source_version = Column(String(100), nullable=True)
    started_at = Column(DateTime, default=_utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    status = Column(String(50), nullable=False)
