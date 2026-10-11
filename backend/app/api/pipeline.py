"""
api/pipeline.py
---------------
HTTP endpoints for triggering data pipelines.

Routes (all prefixed /api/v1 from main.py):
    POST /pipeline/climate/run         → run the climate ingestion pipeline from file
    GET  /pipeline/climate/files       → list available CSV files
    GET  /pipeline/climate/status/{id} → get batch status by ID
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.pipeline.climate_pipeline import run_climate_ingestion
from app.pipeline.water_pipeline import run_water_ingestion
from app.search.climate_loader import list_available_files as list_climate_files_loader
from app.search.water_loader import list_available_files as list_water_files_loader
from app.models.ingestion_batch import IngestionBatch

router = APIRouter(prefix="/pipeline", tags=["Data Pipeline"])


@router.post(
    "/climate/run",
    status_code=status.HTTP_201_CREATED,
    summary="Run the climate data ingestion pipeline",
)
def trigger_climate_pipeline(
    filename: str = Query(
        "egypt_governorate_climate_5yr.csv",
        description="CSV filename inside data/csv/ to ingest",
    ),
    db: Session = Depends(get_db),
):
    """
    Execute the full climate data pipeline:
    1. Read CSV from data/csv/
    2. Parse → Clean → Validate
    3. Store valid records into the database
    4. Log errors and track batch status

    Returns pipeline execution results.
    """
    try:
        result = run_climate_ingestion(db, filename=filename)
        return {
            "status": "success",
            "message": f"Pipeline completed with status: {result['status']}",
            "data": result,
        }
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Pipeline failed: {str(e)}",
        )


@router.get(
    "/climate/files",
    summary="List available climate CSV files",
)
def list_climate_files():
    """
    List all CSV files available in data/csv/ that can be used
    as input for the climate pipeline.
    """
    files = list_climate_files_loader()
    return {
        "status": "success",
        "data": files,
        "meta": {"count": len(files)},
    }


@router.post(
    "/water/run",
    status_code=status.HTTP_201_CREATED,
    summary="Run the water data ingestion pipeline",
)
def trigger_water_pipeline(
    filename: str = Query(
        "egypt_crop_water_use.csv",
        description="CSV filename inside data/csv/ to ingest",
    ),
    db: Session = Depends(get_db),
):
    try:
        result = run_water_ingestion(db, filename=filename)
        return {
            "status": "success",
            "message": f"Pipeline completed with status: {result['status']}",
            "data": result,
        }
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Pipeline failed: {str(e)}",
        )


@router.get(
    "/water/files",
    summary="List available water CSV files",
)
def list_water_files():
    files = list_water_files_loader()
    return {
        "status": "success",
        "data": files,
        "meta": {"count": len(files)},
    }


@router.get(
    "/climate/status/{batch_id}",
    summary="Get pipeline batch status",
)
def get_batch_status(
    batch_id: int,
    db: Session = Depends(get_db),
):
    """
    Check the status of a pipeline execution batch by its ID.
    """
    batch = db.query(IngestionBatch).filter(
        IngestionBatch.batch_id == batch_id
    ).first()

    if not batch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Batch #{batch_id} not found.",
        )

    return {
        "status": "success",
        "data": {
            "batch_id": batch.batch_id,
            "source_system": batch.source_system,
            "status": batch.status,
            "started_at": str(batch.started_at) if batch.started_at else None,
            "completed_at": str(batch.completed_at) if batch.completed_at else None,
        },
    }
