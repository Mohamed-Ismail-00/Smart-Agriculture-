"""
models/etl_error.py
-------------------
SQLAlchemy ORM definition for the `etl_errors` table.
"""

from datetime import datetime, timezone

from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey
from app.models.user import Base

def _utcnow() -> datetime:
    return datetime.now(timezone.utc)

class EtlError(Base):
    __tablename__ = "etl_errors"

    etl_error_id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    batch_id = Column(Integer, ForeignKey("ingestion_batches.batch_id"), nullable=True)
    stage_name = Column(String(100), nullable=False)
    record_key = Column(String(255), nullable=True)
    error_code = Column(String(100), nullable=False)
    error_message = Column(Text, nullable=False)
    is_retryable = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, default=_utcnow, nullable=False)
