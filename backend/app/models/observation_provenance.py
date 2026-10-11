"""ORM for observation-level provenance and trust metadata."""

from datetime import datetime, timezone
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.models.user import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ObservationProvenance(Base):
    __tablename__ = "observation_provenance"

    id = Column(Integer, primary_key=True, autoincrement=True)
    public_id = Column(UUID(as_uuid=True), unique=True, index=True, default=uuid.uuid4)
    land_id = Column(Integer, ForeignKey("lands.land_id"), nullable=False, index=True)
    metric = Column(String(64), nullable=False)
    observation_ref = Column(String(128), nullable=True)
    trust_tier = Column(String(16), nullable=False)
    confidence = Column(Numeric(6, 4), nullable=True)
    source_id = Column(Integer, ForeignKey("data_sources.source_id"), nullable=True)
    source_name = Column(String(255), nullable=True)
    spatial_scope = Column(String(32), nullable=True)
    temporal_scope = Column(String(32), nullable=True)
    derivation = Column(JSONB, nullable=True)
    qa_flags = Column(JSONB, nullable=True)
    fetch_timestamp = Column(DateTime, default=_utcnow, nullable=False)
    created_at = Column(DateTime, default=_utcnow, nullable=False)