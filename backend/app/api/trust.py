"""Trust summary API."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.security import require_land_access
from app.trust.schemas import LandTrustSummaryResponse
from app.trust.trust_summary import build_land_trust_summary

router = APIRouter(tags=["trust"])


@router.get(
    "/lands/{public_id}/trust-summary",
    response_model=LandTrustSummaryResponse,
    summary="Trust tiers and provenance summary for a land",
)
def land_trust_summary(
    public_id: str,
    land=Depends(require_land_access),
    db: Session = Depends(get_db),
):
    result = build_land_trust_summary(db, land.land_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Land not found")
    return result