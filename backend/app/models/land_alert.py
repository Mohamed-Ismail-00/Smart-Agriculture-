"""ORM for `land_alerts` (anomalies & risk alerts).

Extended with:
- user_id: for per-user cross-land notification queries
- is_read: to track which alerts have been acknowledged
"""

from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB

from app.models.user import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class LandAlert(Base):
    __tablename__ = "land_alerts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    land_id = Column(Integer, ForeignKey("lands.land_id"), nullable=False, index=True)
    # Owner user — allows filtering all alerts for a single user across all their lands
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=True, index=True)
    timestamp = Column(DateTime, default=_utcnow, nullable=False)
    alert_type = Column(String(100), nullable=False)   # ndvi_drop, heat_stress, drought, ai_analysis_complete
    severity = Column(String(20), nullable=False)      # low, medium, high, critical
    message = Column(Text, nullable=False)
    payload = Column(JSONB, nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    source_id = Column(Integer, ForeignKey("data_sources.source_id"), nullable=True)
    # Read tracking — allows unread badge on frontend bell
    is_read = Column(Boolean, nullable=False, default=False, index=True)
