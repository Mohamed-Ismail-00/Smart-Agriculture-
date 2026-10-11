"""
api/ingestion.py
----------------
HTTP endpoints for CSV and external API Ingestion.
"""

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.ingestion import service
from app.ingestion.schemas import IngestionResponse

router = APIRouter(tags=["ingestion"])

@router.post("/ingestion/climate/upload", response_model=IngestionResponse, status_code=status.HTTP_201_CREATED)
def upload_climate_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Ingest climate data via CSV upload.
    CSV must contain: governorate, year, temperature_mean, humidity_pct.
    """
    if not file.filename.endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="File must be a CSV."
        )
    
    try:
        result = service.process_climate_upload(db, file)
        
        return IngestionResponse(
            status="success" if result["status"] != "FAILED" else "error",
            message="Upload processed.",
            data=result
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during ingestion."
        )
