"""Persistence helpers for `lands` and related geospatial tables."""

from datetime import datetime
from decimal import Decimal
from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.data_source import DataSource
from app.models.land import Land
from app.models.land_alert import LandAlert
from app.models.land_climate import LandClimate
from app.models.land_crop import LandCrop
from app.models.land_image import LandImage
from app.models.land_soil import LandSoil
from app.models.land_water import LandWater


# ---------------------------------------------------------------------------
# Land CRUD
# ---------------------------------------------------------------------------

def create_land(
    db: Session,
    *,
    name: str,
    latitude: Decimal,
    longitude: Decimal,
    description: Optional[str],
    user_id: Optional[int],
    boundary_polygon: Optional[dict] = None,
    area_hectares: Optional[float] = None,
    metadata_: Optional[dict] = None,
) -> Land:
    row = Land(
        name=name,
        latitude=latitude,
        longitude=longitude,
        description=description,
        user_id=user_id,
        boundary_polygon=boundary_polygon,
        area_hectares=Decimal(str(area_hectares)) if area_hectares is not None else None,
        status="processing",
        metadata_=metadata_ or {},
    )
    db.add(row)
    db.flush()
    return row


def get_land(db: Session, land_id: int) -> Optional[Land]:
    return db.get(Land, land_id)

def get_land_by_public_id(db: Session, public_id: str) -> Optional[Land]:
    """Safe lookup using public UUID instead of internal ID."""
    from uuid import UUID
    try:
        uuid_val = UUID(public_id)
    except ValueError:
        return None
    return db.query(Land).filter(Land.public_id == uuid_val, Land.is_deleted == False).first()  # noqa: E712


def update_land_climate_sampling_metadata(
    db: Session,
    land_id: int,
    climate_sampling: dict,
) -> None:
    """Persist polygon weather sampling metadata on land.metadata_."""
    land = get_land(db, land_id)
    if land is None:
        return
    meta = dict(land.metadata_ or {})
    meta["climate_sampling"] = climate_sampling
    land.metadata_ = meta
    db.flush()


def list_all_lands(
    db: Session,
    *,
    user_id: Optional[int] = None,
) -> Sequence[Land]:
    """Return all non-deleted lands, optionally filtered by owner."""
    stmt = select(Land).where(Land.is_deleted == False).order_by(Land.created_at.desc())  # noqa: E712
    if user_id is not None:
        stmt = stmt.where(Land.user_id == user_id)
    return db.execute(stmt).scalars().all()


def update_land_status(db: Session, land_id: int, status: str) -> None:
    land = db.get(Land, land_id)
    if land is None:
        return
    land.status = status


def list_land_ids_for_monitoring(db: Session) -> Sequence[int]:
    """Lands that should receive periodic monitoring snapshots."""
    stmt = select(Land.land_id).where(Land.status.in_(("active", "processing")))
    return [row[0] for row in db.execute(stmt)]


def get_latest_climate_timestamp(db: Session, land_id: int) -> Optional[datetime]:
    """Most recent climate snapshot for a land (used by monitoring due checks)."""
    stmt = (
        select(LandClimate.timestamp)
        .where(LandClimate.land_id == land_id)
        .order_by(LandClimate.timestamp.desc())
        .limit(1)
    )
    return db.execute(stmt).scalar_one_or_none()


# ---------------------------------------------------------------------------
# Data Sources
# ---------------------------------------------------------------------------

def get_or_create_data_source(db: Session, name: str) -> DataSource:
    stmt = select(DataSource).where(DataSource.name == name)
    existing = db.execute(stmt).scalar_one_or_none()
    if existing is not None:
        return existing
    row = DataSource(name=name)
    db.add(row)
    db.flush()
    return row


# ---------------------------------------------------------------------------
# Climate
# ---------------------------------------------------------------------------

def insert_land_climate_snapshot(
    db: Session,
    land_id: int,
    *,
    temperature_celsius: Optional[float] = None,
    temperature_min_c: Optional[float] = None,
    temperature_mean_c: Optional[float] = None,
    humidity_pct: Optional[float] = None,
    rainfall_mm: Optional[float] = None,
    source_id: Optional[int] = None,
) -> LandClimate:
    row = LandClimate(
        land_id=land_id,
        temperature_celsius=Decimal(str(temperature_celsius)) if temperature_celsius is not None else None,
        temperature_min_c=Decimal(str(temperature_min_c)) if temperature_min_c is not None else None,
        temperature_mean_c=Decimal(str(temperature_mean_c)) if temperature_mean_c is not None else None,
        humidity_pct=Decimal(str(humidity_pct)) if humidity_pct is not None else None,
        rainfall_mm=Decimal(str(rainfall_mm)) if rainfall_mm is not None else None,
        source_id=source_id,
    )
    db.add(row)
    db.flush()
    return row


def delete_environment_rows_since(db: Session, land_id: int, since) -> None:
    """Remove climate/soil/water rows on or after `since` (for environment refresh)."""
    from sqlalchemy import text

    params = {"lid": land_id, "since": since}
    db.execute(
        text("DELETE FROM land_climate WHERE land_id=:lid AND timestamp >= :since"),
        params,
    )
    db.execute(
        text("DELETE FROM land_soil WHERE land_id=:lid AND timestamp >= :since"),
        params,
    )
    db.execute(
        text("DELETE FROM land_water WHERE land_id=:lid AND timestamp >= :since"),
        params,
    )


def list_land_climate_rows(db: Session, land_id: int) -> Sequence[LandClimate]:
    stmt = select(LandClimate).where(LandClimate.land_id == land_id).order_by(LandClimate.timestamp.asc())
    return db.execute(stmt).scalars().all()


# ---------------------------------------------------------------------------
# Crops
# ---------------------------------------------------------------------------

def insert_land_crop_snapshot(
    db: Session,
    land_id: int,
    *,
    timestamp: Optional[datetime] = None,
    crop_type: Optional[str] = None,
    ndvi_value: Optional[float] = None,
    dvi_value: Optional[float] = None,
    evi_value: Optional[float] = None,
    ndwi_value: Optional[float] = None,
    savi_value: Optional[float] = None,
    gndvi_value: Optional[float] = None,
    estimated_yield_tons: Optional[float] = None,
    growth_stage: Optional[str] = None,
    ndvi_trend: Optional[str] = None,
    confidence: Optional[float] = None,
    zone_id: Optional[int] = None,
    source_id: Optional[int] = None,
) -> LandCrop:
    row = LandCrop(
        land_id=land_id,
        crop_type=crop_type,
        ndvi_value=Decimal(str(ndvi_value)) if ndvi_value is not None else None,
        dvi_value=Decimal(str(dvi_value)) if dvi_value is not None else None,
        evi_value=Decimal(str(evi_value)) if evi_value is not None else None,
        ndwi_value=Decimal(str(ndwi_value)) if ndwi_value is not None else None,
        savi_value=Decimal(str(savi_value)) if savi_value is not None else None,
        gndvi_value=Decimal(str(gndvi_value)) if gndvi_value is not None else None,
        estimated_yield_tons=Decimal(str(estimated_yield_tons)) if estimated_yield_tons is not None else None,
        growth_stage=growth_stage,
        ndvi_trend=ndvi_trend,
        confidence=Decimal(str(confidence)) if confidence is not None else None,
        zone_id=zone_id,
        source_id=source_id,
    )
    if timestamp is not None:
        row.timestamp = timestamp
    db.add(row)
    db.flush()
    return row


def list_land_crop_rows(
    db: Session,
    land_id: int,
    *,
    zone_id: Optional[int] = None,
    limit: Optional[int] = None,
) -> Sequence[LandCrop]:
    stmt = select(LandCrop).where(LandCrop.land_id == land_id)
    if zone_id is not None:
        stmt = stmt.where(LandCrop.zone_id == zone_id)
    stmt = stmt.order_by(LandCrop.timestamp.asc())
    if limit is not None:
        stmt = stmt.limit(limit)
    return db.execute(stmt).scalars().all()


def get_primary_crop_zone(db: Session, land_id: int):
    zones = list_crop_zones(db, land_id)
    return zones[0] if zones else None


def get_latest_crop_record(
    db: Session,
    land_id: int,
    *,
    zone_id: Optional[int] = None,
) -> Optional[LandCrop]:
    stmt = select(LandCrop).where(LandCrop.land_id == land_id)
    if zone_id is not None:
        stmt = stmt.where(LandCrop.zone_id == zone_id)
    stmt = stmt.order_by(LandCrop.timestamp.desc()).limit(1)
    return db.execute(stmt).scalar_one_or_none()


def backfill_image_ndvi_means(db: Session, land_id: int) -> int:
    """Join NDVI image rows to nearest land_crops NDVI (primary zone). Returns update count."""
    primary = get_primary_crop_zone(db, land_id)
    zone_id = int(primary.zone_id) if primary else None
    imgs = list_land_images(db, land_id, image_type="ndvi")
    updated = 0
    for img in imgs:
        if img.ndvi_mean is not None:
            continue
        val = find_crop_ndvi_near_date(db, land_id, img.timestamp, zone_id=zone_id)
        if val is not None:
            img.ndvi_mean = Decimal(str(round(val, 4)))
            updated += 1
    if updated:
        db.flush()
    return updated


def find_crop_ndvi_near_date(
    db: Session,
    land_id: int,
    target_ts,
    *,
    zone_id: Optional[int] = None,
    day_tolerance: int = 1,
) -> Optional[float]:
    """Nearest land_crops NDVI for an image timestamp (±day_tolerance days)."""
    from datetime import timedelta

    start = target_ts - timedelta(days=day_tolerance)
    end = target_ts + timedelta(days=day_tolerance)
    stmt = (
        select(LandCrop)
        .where(LandCrop.land_id == land_id)
        .where(LandCrop.timestamp >= start)
        .where(LandCrop.timestamp <= end)
        .where(LandCrop.ndvi_value.isnot(None))
    )
    if zone_id is not None:
        stmt = stmt.where(LandCrop.zone_id == zone_id)
    rows = db.execute(stmt.order_by(LandCrop.timestamp.asc())).scalars().all()
    if not rows:
        return None
    best = min(rows, key=lambda r: abs((r.timestamp - target_ts).total_seconds()))
    return float(best.ndvi_value) if best.ndvi_value is not None else None


# ---------------------------------------------------------------------------
# Water
# ---------------------------------------------------------------------------

def insert_land_water_snapshot(
    db: Session,
    land_id: int,
    *,
    estimated_water_usage_liters: Optional[float] = None,
    irrigation_status: Optional[str] = None,
    crop_water_requirement_mm: Optional[float] = None,
    water_efficiency_ratio: Optional[float] = None,
    source_id: Optional[int] = None,
) -> LandWater:
    row = LandWater(
        land_id=land_id,
        estimated_water_usage_liters=Decimal(str(estimated_water_usage_liters)) if estimated_water_usage_liters is not None else None,
        irrigation_status=irrigation_status,
        crop_water_requirement_mm=Decimal(str(crop_water_requirement_mm)) if crop_water_requirement_mm is not None else None,
        water_efficiency_ratio=Decimal(str(water_efficiency_ratio)) if water_efficiency_ratio is not None else None,
        source_id=source_id,
    )
    db.add(row)
    db.flush()
    return row


def list_land_water_rows(db: Session, land_id: int) -> Sequence[LandWater]:
    stmt = select(LandWater).where(LandWater.land_id == land_id).order_by(LandWater.timestamp.asc())
    return db.execute(stmt).scalars().all()


def get_latest_water_record(db: Session, land_id: int) -> Optional[LandWater]:
    stmt = (
        select(LandWater)
        .where(LandWater.land_id == land_id)
        .order_by(LandWater.timestamp.desc())
        .limit(1)
    )
    return db.execute(stmt).scalar_one_or_none()


# ---------------------------------------------------------------------------
# Soil
# ---------------------------------------------------------------------------

def insert_land_soil_snapshot(
    db: Session,
    land_id: int,
    *,
    moisture_pct: Optional[float] = None,
    soil_type: Optional[str] = None,
    ph_level: Optional[float] = None,
    organic_matter_pct: Optional[float] = None,
    suitability_score: Optional[float] = None,
    source_id: Optional[int] = None,
) -> LandSoil:
    row = LandSoil(
        land_id=land_id,
        moisture_pct=Decimal(str(moisture_pct)) if moisture_pct is not None else None,
        soil_type=soil_type,
        ph_level=Decimal(str(ph_level)) if ph_level is not None else None,
        organic_matter_pct=Decimal(str(organic_matter_pct)) if organic_matter_pct is not None else None,
        suitability_score=Decimal(str(suitability_score)) if suitability_score is not None else None,
        source_id=source_id,
    )
    db.add(row)
    db.flush()
    return row


def list_land_soil_rows(db: Session, land_id: int) -> Sequence[LandSoil]:
    stmt = select(LandSoil).where(LandSoil.land_id == land_id).order_by(LandSoil.timestamp.asc())
    return db.execute(stmt).scalars().all()


def get_latest_soil_record(db: Session, land_id: int) -> Optional[LandSoil]:
    stmt = (
        select(LandSoil)
        .where(LandSoil.land_id == land_id)
        .order_by(LandSoil.timestamp.desc())
        .limit(1)
    )
    return db.execute(stmt).scalar_one_or_none()


# ---------------------------------------------------------------------------
# Images
# ---------------------------------------------------------------------------

def insert_land_image(
    db: Session,
    land_id: int,
    *,
    image_data: bytes,
    image_type: str,
    cv_analysis_summary: Optional[dict] = None,
    ndvi_mean: Optional[float] = None,
    cloud_cover_pct: Optional[float] = None,
    source_id: Optional[int] = None,
    timestamp=None,
) -> LandImage:
    row = LandImage(
        land_id=land_id,
        image_data=image_data,
        image_type=image_type,
        cv_analysis_summary=cv_analysis_summary,
        ndvi_mean=Decimal(str(ndvi_mean)) if ndvi_mean is not None else None,
        cloud_cover_pct=Decimal(str(cloud_cover_pct)) if cloud_cover_pct is not None else None,
        source_id=source_id,
    )
    if timestamp is not None:
        row.timestamp = timestamp
    db.add(row)
    db.flush()
    return row


from sqlalchemy.orm import defer

def list_land_images(
    db: Session,
    land_id: int,
    image_type: Optional[str] = None,
) -> Sequence[LandImage]:
    stmt = select(LandImage).options(defer(LandImage.image_data)).where(LandImage.land_id == land_id)
    if image_type:
        stmt = stmt.where(LandImage.image_type == image_type)
    stmt = stmt.order_by(LandImage.timestamp.asc())
    return db.execute(stmt).scalars().all()


def get_land_image(db: Session, image_id: int) -> Optional[LandImage]:
    return db.get(LandImage, image_id)


# ---------------------------------------------------------------------------
# Alerts
# ---------------------------------------------------------------------------

def insert_land_alert(
    db: Session,
    land_id: int,
    *,
    alert_type: str,
    severity: str,
    message: str,
    payload: Optional[dict] = None,
    source_id: Optional[int] = None,
) -> LandAlert:
    row = LandAlert(
        land_id=land_id,
        alert_type=alert_type,
        severity=severity,
        message=message,
        payload=payload,
        source_id=source_id,
    )
    db.add(row)
    db.flush()
    return row


def list_land_alerts(
    db: Session,
    land_id: int,
    *,
    unresolved_only: bool = False,
) -> Sequence[LandAlert]:
    stmt = select(LandAlert).where(LandAlert.land_id == land_id)
    if unresolved_only:
        stmt = stmt.where(LandAlert.resolved_at.is_(None))
    stmt = stmt.order_by(LandAlert.timestamp.desc())
    return db.execute(stmt).scalars().all()


def list_recent_alerts(db: Session, limit: int = 10, unresolved_only: bool = True) -> list[LandAlert]:
    """List recent alerts across all lands (for notifications)."""
    stmt = select(LandAlert)
    if unresolved_only:
        stmt = stmt.where(LandAlert.resolved_at.is_(None))
    stmt = stmt.order_by(LandAlert.timestamp.desc()).limit(limit)
    return db.execute(stmt).scalars().all()


# ---------------------------------------------------------------------------
# Crop Zones
# ---------------------------------------------------------------------------

from app.models.crop_zone import CropZone


def list_crop_zones(db: Session, land_id: int) -> Sequence[CropZone]:
    stmt = (
        select(CropZone)
        .where(CropZone.land_id == land_id)
        .order_by(CropZone.area_pct.desc())
    )
    return db.execute(stmt).scalars().all()


def get_or_create_crop_zone(
    db: Session,
    land_id: int,
    crop_type: str,
    area_hectares: Optional[float] = None,
    area_pct: Optional[float] = None,
) -> CropZone:
    """Find existing zone by land+crop_type, or create a new one."""
    stmt = (
        select(CropZone)
        .where(CropZone.land_id == land_id)
        .where(CropZone.crop_type == crop_type)
    )
    zone = db.execute(stmt).scalars().first()
    if zone:
        if area_hectares is not None:
            zone.area_hectares = Decimal(str(area_hectares))
        if area_pct is not None:
            zone.area_pct = Decimal(str(area_pct))
        return zone

    zone = CropZone(
        land_id=land_id,
        crop_type=crop_type,
        area_hectares=Decimal(str(area_hectares)) if area_hectares is not None else None,
        area_pct=Decimal(str(area_pct)) if area_pct is not None else None,
    )
    db.add(zone)
    db.flush()
    return zone


def update_crop_zone_stats(
    db: Session,
    zone_id: int,
    *,
    latest_ndvi: Optional[float] = None,
    latest_growth_stage: Optional[str] = None,
    avg_confidence: Optional[float] = None,
    estimated_yield_tons: Optional[float] = None,
) -> None:
    zone = db.get(CropZone, zone_id)
    if zone is None:
        return
    if latest_ndvi is not None:
        zone.latest_ndvi = Decimal(str(latest_ndvi))
    if latest_growth_stage is not None:
        zone.latest_growth_stage = latest_growth_stage
    if avg_confidence is not None:
        zone.avg_confidence = Decimal(str(avg_confidence))
    if estimated_yield_tons is not None:
        zone.estimated_yield_tons = Decimal(str(estimated_yield_tons))
    db.flush()
from sqlalchemy import text
def delete_land_cascading(db: Session, land_id: int) -> bool:
    land = db.get(Land, land_id)
    if not land:
        return False
    lid = land_id
    db.execute(text('DELETE FROM ai_chat_messages WHERE session_id IN (SELECT session_id FROM ai_chat_sessions WHERE land_id=:lid)'), {'lid': lid})
    db.execute(text('DELETE FROM ai_chat_sessions WHERE land_id=:lid'), {'lid': lid})
    db.execute(text('DELETE FROM land_ai_insights WHERE land_id=:lid'), {'lid': lid})
    db.execute(text('DELETE FROM land_climate WHERE land_id=:lid'), {'lid': lid})
    db.execute(text('DELETE FROM land_soil WHERE land_id=:lid'), {'lid': lid})
    db.execute(text('DELETE FROM land_water WHERE land_id=:lid'), {'lid': lid})
    db.execute(text('DELETE FROM land_images WHERE land_id=:lid'), {'lid': lid})
    db.execute(text('DELETE FROM land_crops WHERE land_id=:lid'), {'lid': lid})
    db.execute(text('DELETE FROM land_alerts WHERE land_id=:lid'), {'lid': lid})
    db.execute(text('DELETE FROM land_soil_profiles WHERE land_id=:lid'), {'lid': lid})
    db.execute(text('DELETE FROM observation_provenance WHERE land_id=:lid'), {'lid': lid})
    db.execute(text('DELETE FROM user_declared_crops WHERE land_id=:lid'), {'lid': lid})
    db.execute(text('DELETE FROM crop_zones WHERE land_id=:lid'), {'lid': lid})
    db.delete(land)
    return True
