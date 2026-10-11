"""ORM for `analytics_summaries` (AI / roll-up insights)."""

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB

from app.models.user import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AnalyticsSummary(Base):
    __tablename__ = "analytics_summaries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    land_id = Column(Integer, ForeignKey("lands.land_id"), nullable=False, index=True)
    timestamp = Column(DateTime, default=_utcnow, nullable=False)
    summary_text = Column(Text, nullable=False)
    summary_payload = Column(JSONB, nullable=True)
    source_id = Column(Integer, ForeignKey("data_sources.source_id"), nullable=True)
