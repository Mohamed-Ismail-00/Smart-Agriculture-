"""api/crops.py — Crop intelligence endpoints under /lands/{id}/..."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, get_db
from app.crops import service as crop_service
from app.crops import user_crops as user_crop_service
from app.crops.schemas import (
    CropDetectionResponse,
    CropHealthResponse,
    CropStatusResponse,
    CropTrendResponse,
    DeclaredCropRequest,
    HarvestPredictionResponse,
)
from app.models.user import User
from app.security import require_land_access

router = APIRouter(tags=["crops"])


@router.get(
    "/lands/{public_id}/crop-detection",
    response_model=CropDetectionResponse,
    summary="Suggested crop type from NDVI profile match (or user-confirmed)",
)
def crop_detection(public_id: str, land=Depends(require_land_access), db: Session = Depends(get_db)):
    """
    Returns user-confirmed crop (verified) or spectral suggestion (estimated).
    Method: ndvi_profile_match — not ML classification.
    """
    result = crop_service.get_crop_detection(db, land.land_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Land not found")
    return result


@router.post(
    "/lands/{public_id}/declared-crops",
    summary="Confirm or correct the primary crop for this land",
)
def declare_primary_crop(
    public_id: str,
    body: DeclaredCropRequest,
    land=Depends(require_land_access),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    row = user_crop_service.upsert_primary_declaration(
        db,
        land.land_id,
        body.crop_type,
        user_id=current_user.user_id,
        notes=body.notes,
    )
    db.commit()
    return {
        "land_id": land.land_id,
        "crop_type": row.crop_type,
        "trust_tier": "verified",
        "detection_method": "user_confirmed",
        "notes": row.notes,
    }


@router.delete(
    "/lands/{public_id}/declared-crops",
    summary="Remove user-confirmed crop declaration",
)
def delete_declared_crop(
    public_id: str,
    land=Depends(require_land_access),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not user_crop_service.delete_primary_declaration(db, land.land_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No declaration found")
    db.commit()
    return {"land_id": land.land_id, "deleted": True}


@router.get(
    "/lands/{public_id}/crop-health",
    response_model=CropHealthResponse,
    summary="Current crop health based on NDVI vs expected range",
)
def crop_health(public_id: str, land=Depends(require_land_access), db: Session = Depends(get_db)):
    result = crop_service.get_crop_health(db, land.land_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Land not found")
    return result


@router.post(
    "/lands/{public_id}/crop-health/refresh",
    response_model=CropHealthResponse,
    summary="Recompute and persist crop health from latest intelligence",
)
def crop_health_refresh(
    public_id: str,
    land=Depends(require_land_access),
    db: Session = Depends(get_db),
):
    result = crop_service.refresh_crop_health(db, land.land_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Land not found")
    return result


@router.get(
    "/lands/{public_id}/crop-status",
    response_model=CropStatusResponse,
    summary="Current growth stage and NDVI trend",
)
def crop_status(
    public_id: str,
    land=Depends(require_land_access),
    zone_id: Optional[int] = Query(None, description="Crop zone filter; defaults to primary zone"),
    db: Session = Depends(get_db),
):
    result = crop_service.get_crop_status(db, land.land_id, zone_id=zone_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Land not found")
    return result


@router.get(
    "/lands/{public_id}/crop-trend",
    response_model=CropTrendResponse,
    summary="NDVI time-series with trend analysis",
)
def crop_trend(
    public_id: str,
    land=Depends(require_land_access),
    days: int = Query(90, ge=16, le=365, description="Analysis window in days"),
    zone_id: Optional[int] = Query(None, description="Crop zone filter; defaults to primary zone"),
    db: Session = Depends(get_db),
):
    result = crop_service.get_crop_trend(db, land.land_id, days=days, zone_id=zone_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Land not found")
    return result


@router.get(
    "/lands/{public_id}/harvest-prediction",
    response_model=HarvestPredictionResponse,
    summary="Estimated harvest window based on NDVI peak analysis",
)
def harvest_prediction(public_id: str, land=Depends(require_land_access), db: Session = Depends(get_db)):
    result = crop_service.get_harvest_prediction(db, land.land_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Land not found")
    return result