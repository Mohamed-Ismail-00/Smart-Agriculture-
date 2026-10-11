"""
climate/schemas.py
------------------
Pydantic schemas for the Climate domain.
"""

from typing import Optional, List
from pydantic import BaseModel, ConfigDict

class ClimateRecordBase(BaseModel):
    year: int
    temperature_mean: Optional[float] = None
    humidity_pct: Optional[float] = None

class ClimateRecordResponse(ClimateRecordBase):
    governorate: str
    
    model_config = ConfigDict(from_attributes=True)

class ClimateDataResponse(BaseModel):
    status: str
    data: List[ClimateRecordResponse]
    message: Optional[str] = None
    meta: dict = {}
