"""
models/land_ai_insight.py
--------------------------
Stores automated AI-generated analysis for a land, produced during the
discovery pipeline or re-analysis. These are shown on the UI with an AI badge.
"""

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB

from app.models.user import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class LandAiInsight(Base):
    __tablename__ = "land_ai_insights"

    insight_id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    land_id = Column(Integer, ForeignKey("lands.land_id"), nullable=False, index=True)
    # Category: 'crop_analysis' | 'ndvi_analysis' | 'irrigation_advice' | 'risk_alert'
    insight_type = Column(String(64), nullable=False)
    # Short headline shown on the card
    title = Column(String(255), nullable=False)
    # Detailed markdown body from Grok
    body = Column(Text, nullable=False)
    # Optional structured data (e.g. estimated yield, recommended action)
    structured_data = Column(JSONB, nullable=True)
    # Confidence 0-1 as rated by the model (or None)
    confidence = Column(Float, nullable=True)
    # Which Grok model produced this
    model_used = Column(String(128), nullable=True)
    created_at = Column(DateTime, default=_utcnow, nullable=False)
