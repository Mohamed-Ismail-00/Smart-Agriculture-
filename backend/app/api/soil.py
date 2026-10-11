"""api/soil.py — 3 soil intelligence endpoints."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.soil import service as soil_service
from app.soil.schemas import SoilProfileResponse, SoilStatusResponse, SoilSuitabilityResponse
from app.security import require_land_access
from app.tasks.soil_task import run_soil_profile_task

router = APIRouter(tags=["soil"])


@router.get(
    "/lands/{public_id}/soil-profile",
    response_model=SoilProfileResponse,
    summary="Full ISRIC SoilGrids property profile at 3 depths",
)
def soil_profile(public_id: str, land = Depends(require_land_access), db: Session = Depends(get_db)):
    """
    Returns pH, SOC, clay, sand, silt, bulk density, nitrogen, CEC
    at 0-5cm, 5-15cm and 15-30cm depths from ISRIC SoilGrids.

    Profile is fetched once at land registration and cached in the DB.
    """
    result = soil_service.get_soil_profile(db, land.land_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Land not found")
    return result


@router.post(
    "/lands/{public_id}/soil-profile/retry",
    response_model=SoilProfileResponse,
    summary="Retry ISRIC SoilGrids profile fetch",
)
def retry_soil_profile(public_id: str, land=Depends(require_land_access), db: Session = Depends(get_db)):
    """
    Manually retry SoilGrids fetch when the initial registration fetch failed
    (timeout, network error, or empty response).
    """
    run_soil_profile_task(land.land_id, db)
    result = soil_service.get_soil_profile(db, land.land_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Land not found")
    return result


@router.get(
    "/lands/{public_id}/soil-suitability",
    response_model=SoilSuitabilityResponse,
    summary="Crop suitability scores based on soil properties",
)
def soil_suitability(
    public_id: str,
    land = Depends(require_land_access),
    crop: Optional[str] = Query(None, description="Focus on specific crop (wheat, corn, rice, ...)"),
    db: Session = Depends(get_db),
):
    """
    Scores suitability for 6 crops using FAO/USDA soil thresholds.
    Returns ranked crop list + farming advice per soil deficiency.
    Uses geometric mean scoring — a single critical deficiency limits overall score.
    """
    result = soil_service.get_soil_suitability(db, land.land_id, crop=crop)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Land not found")
    return result


@router.get(
    "/lands/{public_id}/soil-status",
    response_model=SoilStatusResponse,
    summary="Combined live moisture + static soil profile summary",
)
def soil_status(public_id: str, land = Depends(require_land_access), db: Session = Depends(get_db)):
    """
    Combines:
    - Live soil moisture (from Open-Meteo time-series)
    - Static soil property summary (from ISRIC SoilGrids profile)
    - Farming advice tailored to detected deficiencies
    """
    result = soil_service.get_soil_status(db, land.land_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Land not found")
    return result
