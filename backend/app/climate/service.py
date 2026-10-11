"""
climate/service.py
------------------
Business logic layer for the Climate domain.
"""

from typing import Optional, List
from sqlalchemy.orm import Session

from app.climate import repository
from app.climate.schemas import ClimateRecordResponse

def get_climate_records(
    db: Session, 
    year: Optional[int] = None, 
    governorate: Optional[str] = None
) -> List[ClimateRecordResponse]:
    """
    Process business rules and return climate records.
    """
    records = repository.get_climate_records(db, year=year, governorate=governorate)
    return [ClimateRecordResponse(**record) for record in records]
