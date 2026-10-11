"""
models/ai_settings.py
----------------------
Stores per-user Grok API key pool.
Each user can have multiple keys; the system rotates them on quota errors.
"""

from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text

from app.models.user import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AiApiKey(Base):
    __tablename__ = "ai_api_keys"

    key_id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False, index=True)
    # Store the key; in production consider encrypting at rest.
    api_key = Column(String(512), nullable=False)
    label = Column(String(128), nullable=True)          # e.g. "Primary", "Backup 1"
    provider = Column(String(64), nullable=False, default="grok")
    is_active = Column(Boolean, nullable=False, default=True)
    # Quota tracking
    quota_exceeded = Column(Boolean, nullable=False, default=False)
    quota_reset_at = Column(DateTime, nullable=True)    # when to retry the key
    sort_order = Column(Integer, nullable=False, default=0)  # lower = try first
    created_at = Column(DateTime, default=_utcnow, nullable=False)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow, nullable=False)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<AiApiKey id={self.key_id} label={self.label} provider={self.provider}>"
