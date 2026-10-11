"""User-confirmed crop declarations (verified ground truth)."""

from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text

from app.models.user import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UserDeclaredCrop(Base):
    __tablename__ = "user_declared_crops"

    id = Column(Integer, primary_key=True, autoincrement=True)
    land_id = Column(Integer, ForeignKey("lands.land_id"), nullable=False, index=True)
    crop_type = Column(String(100), nullable=False)
    is_primary = Column(Boolean, nullable=False, default=True)
    notes = Column(Text, nullable=True)
    declared_by = Column(Integer, ForeignKey("users.user_id"), nullable=True)
    created_at = Column(DateTime, default=_utcnow, nullable=False)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow, nullable=False)