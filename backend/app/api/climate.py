"""
api/climate.py
--------------
HTTP endpoints for the Climate domain.
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.climate import service
from app.climate.schemas import ClimateDataResponse

router = APIRouter(tags=["climate"])

@router.get("/climate/records", response_model=ClimateDataResponse)
def get_climate_records(
    year: Optional[int] = Query(None, description="Year to filter (e.g. 2023)"),
    governorate: Optional[str] = Query(None, description="Governorate to filter (e.g. Cairo)"),
    db: Session = Depends(get_db)
):
    """
    Retrieve climate records based on filters.
    """
    # Validation against user sending invalid year explicitly
    if year is not None and (year < 1900 or year > 2100):
        # We raise a 422 standard unprocessable entity for validation failure
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid year. Must be between 1900 and 2100."
        )

    records = service.get_climate_records(db, year=year, governorate=governorate)
    
    return ClimateDataResponse(
        status="success",
        data=records,
        meta={"count": len(records)}
    )
