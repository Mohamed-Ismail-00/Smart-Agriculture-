"""Persist and query observation provenance records."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models.observation_provenance import ObservationProvenance
from app.trust.types import TrustTier


def _trust_tier_value(tier: TrustTier | str) -> str:
    if isinstance(tier, TrustTier):
        return tier.value
    return str(tier)


class ProvenanceService:
    @staticmethod
    def record(
        db: Session,
        *,
        land_id: int,
        metric: str,
        trust_tier: TrustTier | str,
        observation_ref: Optional[str] = None,
        confidence: Optional[float] = None,
        source_id: Optional[int] = None,
        source_name: Optional[str] = None,
        spatial_scope: Optional[str] = None,
        temporal_scope: Optional[str] = None,
        derivation: Optional[dict[str, Any]] = None,
        qa_flags: Optional[list[str]] = None,
        fetch_timestamp: Optional[datetime] = None,
    ) -> ObservationProvenance:
        row = ObservationProvenance(
            land_id=land_id,
            metric=metric,
            observation_ref=observation_ref,
            trust_tier=_trust_tier_value(trust_tier),
            confidence=confidence,
            source_id=source_id,
            source_name=source_name,
            spatial_scope=spatial_scope,
            temporal_scope=temporal_scope,
            derivation=derivation,
            qa_flags=qa_flags,
            fetch_timestamp=fetch_timestamp or datetime.now(timezone.utc),
        )
        db.add(row)
        db.flush()
        return row

    @staticmethod
    def latest_for_metric(
        db: Session,
        land_id: int,
        metric: str,
    ) -> Optional[ObservationProvenance]:
        return (
            db.query(ObservationProvenance)
            .filter(
                ObservationProvenance.land_id == land_id,
                ObservationProvenance.metric == metric,
            )
            .order_by(ObservationProvenance.created_at.desc())
            .first()
        )