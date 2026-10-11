"""
models/location.py
------------------
SQLAlchemy ORM definition for the `locations` table.
"""

from datetime import datetime, timezone

from sqlalchemy import Column, Integer, String, DateTime
from app.models.user import Base

def _utcnow() -> datetime:
    return datetime.now(timezone.utc)

class Location(Base):
    __tablename__ = "locations"

    location_id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    governorate = Column(String(100), unique=True, nullable=False, index=True)
    region = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=_utcnow, nullable=False)
