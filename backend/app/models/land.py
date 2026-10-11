"""
models/land.py
--------------
ORM for `lands` (geospatial root entity).
"""

from datetime import datetime, timezone
import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import validates
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.models.user import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Land(Base):
    __tablename__ = "lands"

    land_id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    public_id = Column(UUID(as_uuid=True), unique=True, index=True, default=uuid.uuid4)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=True, index=True)
    name = Column(String(255), nullable=False)
    latitude = Column(Numeric(10, 8), nullable=False)
    longitude = Column(Numeric(11, 8), nullable=False)
    boundary_polygon = Column(JSONB, nullable=True)
    area_hectares = Column(Numeric(12, 4), nullable=True)
    description = Column(Text, nullable=True)
    status = Column(String(128), nullable=False, default="processing")
    monitoring_interval_days = Column(Integer, nullable=False, default=16)
    
    # Audit & Security Fields
    is_deleted = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, default=_utcnow, nullable=False)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow, nullable=False)
    
    # Flexible JSON metadata for business logic
    metadata_ = Column(JSONB, nullable=True, default=dict)

    # Business Logic Validations
    @validates("latitude")
    def validate_latitude(self, key, value):
        if value is not None:
            v = float(value)
            if not (-90 <= v <= 90):
                raise ValueError("Latitude must be between -90 and 90 degrees.")
        return value

    @validates("longitude")
    def validate_longitude(self, key, value):
        if value is not None:
            v = float(value)
            if not (-180 <= v <= 180):
                raise ValueError("Longitude must be between -180 and 180 degrees.")
        return value

    @validates("area_hectares")
    def validate_area(self, key, value):
        if value is not None:
            v = float(value)
            if v < 0:
                raise ValueError("Area cannot be negative.")
        return value
