"""
api/lands.py
------------
Land registration (GeoJSON polygon), time-series reads, and image gallery.
"""

from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.dependencies import get_current_user_optional, get_db
from app.models.user import User
from app.lands.schemas import (
    CropZoneListResponse,
    LandDetailResponse,
    LandDiscoverAccepted,
    LandDiscoverRequest,
    LandImageListResponse,
    LandListResponse,
    LandTimeSeriesResponse,
)
from app.lands import service
from app.pipeline.land_discovery_pipeline import run_in_session

# New centralized security layer
from app.security import require_land_access

router = APIRouter(tags=["lands"])


@router.get(
    "/lands",
    response_model=LandListResponse,
    summary="List all registered lands",
)
def list_lands(db: Session = Depends(get_db), current_user: Optional[User] = Depends(get_current_user_optional)):
    """Return all lands as a lightweight list."""
    if current_user and current_user.role == "admin":
        return service.list_all_lands(db)
    if current_user:
        return service.list_all_lands(db, user_id=current_user.user_id)
    if settings.APP_ENV == "development":
        return service.list_all_lands(db)
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

@router.post(
    "/lands/discover",
    response_model=LandDiscoverAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Register a new land from a GeoJSON polygon",
)
def discover_land(
    body: LandDiscoverRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """
    Accepts a GeoJSON Polygon (drawn manually OR generated from a circle).

    Server-side:
    - Validates and closes the polygon ring
    - Computes centroid (lat/lon)
    - Computes area in hectares
    - Stores boundary_polygon
    - Enqueues discovery pipeline (climate + soil + ET₀ fetch)
    """
    user_id = int(current_user.user_id) if current_user else None
    land_id = service.register_land_for_discovery(
        db,
        name=body.name,
        geometry=body.geometry,
        description=body.description,
        user_id=user_id,
        metadata_=body.metadata_,
    )

    # Real activity log (only admins can see)
    if user_id:
        from app.users import service as user_service
        user_service.record_activity(
            db,
            user_id,
            "create_land",
            target_type="land",
            target_id=land_id,
            details={"name": body.name},
        )

    background_tasks.add_task(run_in_session, land_id)
    land = db.query(service.repository.Land).filter(service.repository.Land.land_id == land_id).first()
    public_id = str(land.public_id) if land and land.public_id else None
    return LandDiscoverAccepted(status="processing", land_id=land_id, public_id=public_id)


@router.get(
    "/lands/{public_id}",
    response_model=LandDetailResponse,
    summary="Get land detail including geometry and area",
)
def get_land_detail(
    public_id: str,
    land = Depends(require_land_access),
    db: Session = Depends(get_db),
):
    """Return full land detail using public UUID (protected by ownership check)."""
    result = service.get_land_by_public_id(db, public_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Land not found")
    return result


@router.get(
    "/lands/{public_id}/timeseries",
    response_model=LandTimeSeriesResponse,
    summary="Time-series data for a land metric",
)
def get_land_timeseries(
    public_id: str,
    metric: str = Query("climate", pattern="^(climate|water|crops|soil)$"),
    zone_id: Optional[int] = Query(None, description="Crop zone filter (crops metric only)"),
    land = Depends(require_land_access),
    db: Session = Depends(get_db),
):
    result = service.land_timeseries(db, land.land_id, metric, zone_id=zone_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Land not found")
    return result


@router.get(
    "/lands/{public_id}/images",
    response_model=LandImageListResponse,
    summary="Satellite and uploaded image gallery for a land",
)
def list_land_images(
    public_id: str,
    image_type: Optional[str] = Query(None, description="Filter: true_color, ndvi, user_upload"),
    land = Depends(require_land_access),
    db: Session = Depends(get_db),
):
    result = service.list_images(db, land.land_id, public_id=public_id, image_type=image_type)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Land not found")
    return result


from fastapi import Response
from app.lands import repository

@router.get(
    "/lands/{public_id}/images/{image_id}/content",
    summary="Get raw image content (PNG)",
)
def get_land_image_content(
    public_id: str,
    image_id: int,
    land=Depends(require_land_access),
    db: Session = Depends(get_db),
):
    image = db.query(service.repository.LandImage).filter_by(id=image_id, land_id=land.land_id).first()
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")
    
    return Response(content=image.image_data, media_type="image/png")


@router.get(
    "/lands/{public_id}/crop-zones",
    response_model=CropZoneListResponse,
    summary="Crop zones within a land — multi-crop composition",
)
def list_crop_zones(
    public_id: str,
    land = Depends(require_land_access),
    db: Session = Depends(get_db),
):
    """Return all detected crop zones with area %, NDVI, growth stage, and yield stats."""
    result = service.list_crop_zones(db, land.land_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Land not found")
    return result


# ---------------------------------------------------------------------------
# Re-Analysis, Settings, NDVI Comparison
# ---------------------------------------------------------------------------

@router.post(
    "/lands/{public_id}/analyze",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger re-analysis — fetch new satellite images and update intelligence",
)
def reanalyze_land(
    public_id: str,
    background_tasks: BackgroundTasks,
    refresh: str = Query(
        "environment,satellite,crops",
        description="Comma-separated sections to refresh: environment, satellite, crops",
    ),
    land = Depends(require_land_access),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """
    Queue a background task to refresh selected data sections.

    - **environment** — re-fetch Open-Meteo climate, soil moisture, and water (last 30 days)
    - **satellite** — fetch new Sentinel-2 thumbnails (true color + NDVI)
    - **crops** — recompute NDVI time-series and crop zones

    Old data outside the environment refresh window is preserved.
    """
    land_id = land.land_id
    from app.pipeline.land_discovery_pipeline import parse_refresh_sections

    sections = parse_refresh_sections(refresh)

    from app.tasks.sentinel_task import run_sentinel_visual_fetch
    from app.tasks.crop_task import run_crop_detection_task
    from app.ai.land_analyst import run_ai_land_analysis
    from app.pipeline.land_discovery_pipeline import refresh_environment_data
    
    uid = current_user.user_id if current_user else None

    def _run_fetch():
        from app.db.session import SessionLocal
        local_db = SessionLocal()
        try:
            def update_progress(msg: str):
                from app.models.land import Land
                l = local_db.get(Land, land_id)
                if l:
                    l.status = msg
                    local_db.commit()

            if "environment" in sections:
                refresh_environment_data(
                    land_id,
                    local_db,
                    days=30,
                    update_progress=update_progress,
                )

            if "satellite" in sections:
                update_progress("Downloading visual Sentinel-2 thumbnails...")
                run_sentinel_visual_fetch(land_id, local_db, update_progress=update_progress)

            if "crops" in sections:
                from sqlalchemy import text
                local_db.execute(text("DELETE FROM land_crops WHERE land_id=:lid"), {"lid": land_id})
                local_db.commit()
                update_progress("Fetching real STAC arrays and running ML multi-crop detection...")
                run_crop_detection_task(land_id, local_db, days=365)

            if sections:
                update_progress("Generating AI insights via Groq Vision...")
                run_ai_land_analysis(land_id, local_db, user_id=uid)

            update_progress("active")
        except Exception as e:
            import logging
            logging.getLogger(__name__).exception("Background analysis failed: %s", e)
            update_progress("failed")
        finally:
            local_db.close()

    background_tasks.add_task(_run_fetch)

    # Log reanalyze action
    if current_user:
        from app.users import service as user_service
        user_service.record_activity(
            db,
            current_user.user_id,
            "reanalyze_land",
            target_type="land",
            target_id=land_id,
            details={"refresh": sorted(sections)},
        )

    return {
        "status": "processing",
        "message": "Re-analysis queued.",
        "refresh": sorted(sections),
    }


from pydantic import BaseModel as _PydanticBase

class _LandSettingsUpdate(_PydanticBase):
    monitoring_interval_days: Optional[int] = None


@router.patch(
    "/lands/{public_id}/settings",
    summary="Update per-land settings (update period, etc.)",
)
def update_land_settings(
    public_id: str,
    body: _LandSettingsUpdate,
    land = Depends(require_land_access),
    db: Session = Depends(get_db),
):
    l = db.query(service.repository.Land).filter(service.repository.Land.land_id == land.land_id).first()
    if not l:
        raise HTTPException(status_code=404, detail="Land not found")

    if body.monitoring_interval_days is not None:
        l.monitoring_interval_days = body.monitoring_interval_days

    db.commit()
    return {
        "status": "success",
        "monitoring_interval_days": int(l.monitoring_interval_days),
    }


@router.get(
    "/lands/{public_id}/ndvi-comparison",
    summary="Weekly NDVI progress comparison over time",
)
def get_ndvi_comparison(
    public_id: str,
    weeks: int = Query(8, ge=2, le=52),
    land = Depends(require_land_access),
    db: Session = Depends(get_db),
):
    from app.crops.service import get_ndvi_comparison as _get_ndvi_comparison
    result = _get_ndvi_comparison(db, land.land_id, weeks)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Land not found")
    return result

@router.delete(
    "/lands/{public_id}",
    summary="Delete a land and all associated data",
    status_code=status.HTTP_204_NO_CONTENT
)
def delete_land(
    public_id: str,
    land = Depends(require_land_access),
    db: Session = Depends(get_db),
):
    from app.lands.repository import delete_land_cascading
    if not delete_land_cascading(db, land.land_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Land not found")
    db.commit()
    return Response(status_code=204)

@router.get(
    "/lands/{public_id}/export",
    summary="Export land data as CSV",
)
def export_land(
    public_id: str,
    land = Depends(require_land_access),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """Export land data including analysis and charts into an Excel sheet."""
    excel_stream = service.export_land_to_excel(db, land.land_id)
    if not excel_stream:
        raise HTTPException(status_code=404, detail="Land not found or no data available")

    # Log export for admins
    if current_user:
        from app.users import service as user_service
        user_service.record_activity(
            db,
            current_user.user_id,
            "export_land",
            target_type="land",
            target_id=land.land_id,
            details={"format": "xlsx"},
        )
        
    headers = {
        'Content-Disposition': f'attachment; filename="land_{land.land_id}_export.xlsx"'
    }
    return StreamingResponse(
        iter([excel_stream.getvalue()]), 
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers
    )



