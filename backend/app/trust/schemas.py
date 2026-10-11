"""Pydantic schemas for trust APIs."""

from typing import Any, Optional

from pydantic import BaseModel, Field


class TrustMetricSummary(BaseModel):
    metric: str
    trust_tier: str
    label: str
    confidence: Optional[float] = None
    source_name: Optional[str] = None
    method: Optional[str] = None
    notes: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class LandTrustSummaryResponse(BaseModel):
    land_id: int
    sections: list[TrustMetricSummary]