"""
models/data_source.py
---------------------
ORM for `data_sources` (connector / dataset provenance).
"""

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, Numeric, String

from app.models.user import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class DataSource(Base):
    __tablename__ = "data_sources"

    source_id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    name = Column(String(255), unique=True, nullable=False)
    confidence_score = Column(Numeric(5, 2), nullable=True)
    created_at = Column(DateTime, default=_utcnow, nullable=False)
