"""
ingestion/schemas.py
--------------------
Pydantic schemas for the Ingestion domain.
"""

from pydantic import BaseModel
from typing import Optional

class IngestionResponse(BaseModel):
    status: str
    message: str
    data: Optional[dict] = None
    meta: Optional[dict] = None
