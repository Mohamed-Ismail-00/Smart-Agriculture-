"""
climate/repository.py
---------------------
Database operations for the Climate domain.
"""

from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.climate_record import ClimateRecord
from app.models.location import Location

def get_climate_records(
    db: Session, 
    year: Optional[int] = None, 
    governorate: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Retrieve climate records from the database, grouped/filtered.
    """
    query = select(
        ClimateRecord.year,
        ClimateRecord.temperature_mean,
        ClimateRecord.humidity_pct,
        Location.governorate
    ).join(Location, ClimateRecord.location_id == Location.location_id)

    if year is not None:
        query = query.where(ClimateRecord.year == year)
    if governorate:
        query = query.where(Location.governorate == governorate)

    result = db.execute(query).fetchall()
    
    return [
        {
            "year": row.year,
            "temperature_mean": float(row.temperature_mean) if row.temperature_mean is not None else None,
            "humidity_pct": float(row.humidity_pct) if row.humidity_pct is not None else None,
            "governorate": row.governorate
        }
        for row in result
    ]
