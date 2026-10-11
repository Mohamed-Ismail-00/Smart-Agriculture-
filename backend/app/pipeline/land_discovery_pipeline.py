"""
land_discovery_pipeline.py
--------------------------
Full discovery fan-out: connectors, NDVI backfill, Soil profile, ETL, modular inserts.

Runs outside the HTTP request (BackgroundTasks or worker). Uses its own DB session.

Real data fetched at discovery:
  Step 1. Climate snapshot         → land_climate   (Open-Meteo current)
  Step 2. Soil moisture + ET₀      → land_water, land_soil  (Open-Meteo archive)
  Step 3. NDVI history backfill    → land_crops  (Sentinel-2 L2A, per-zone ML detection)
  Step 4. Static soil profile      → land_soil_profiles  (ISRIC SoilGrids v2)
  Step 5. High-Res Satellite       → land_images  (Sentinel-2 via Planetary Computer)
  Step 6. Mark land active
"""

import logging

from sqlalchemy.orm import Session

from app.connectors import open_meteo_polygon
from app.lands import repository
from app.lands.water_metrics import derive_irrigation_status, estimate_daily_water_liters

logger = logging.getLogger(__name__)

VALID_REFRESH_SECTIONS = frozenset({"environment", "satellite", "crops"})


def _tracked_vars_for_land(land) -> list[str] | None:
    tracked_vars = land.metadata_.get("trackingVariables") if land.metadata_ else None
    if isinstance(tracked_vars, list) and "ndvi" not in tracked_vars:
        tracked_vars.append("ndvi")
    return tracked_vars


def _climate_mean_temp(temp_max, temp_min) -> float | None:
    if temp_max is None or temp_min is None:
        return None
    return round((float(temp_max) + float(temp_min)) / 2.0, 2)


def insert_historical_environment_records(
    db: Session,
    land,
    records: list[dict],
    tracked_vars: list[str] | None,
    *,
    source_id: int,
) -> tuple[int, int, int]:
    """Persist Open-Meteo daily rows into climate, soil, and water tables."""
    from datetime import datetime

    land_id = int(land.land_id)
    area_ha = float(land.area_hectares) if land.area_hectares else None
    count_clim, count_soil, count_water = 0, 0, 0

    for rec in records:
        date_str = rec.get("date")
        if not date_str:
            continue
        try:
            ts = datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            continue

        temp_max = rec.get("temperature_max_c")
        temp_min = rec.get("temperature_min_c")
        temp_mean = _climate_mean_temp(temp_max, temp_min)

        if (tracked_vars is None or "climate" in tracked_vars) and (
            temp_max is not None or rec.get("rainfall_mm") is not None
        ):
            row_clim = repository.insert_land_climate_snapshot(
                db,
                land_id,
                temperature_celsius=temp_max,
                temperature_min_c=temp_min,
                temperature_mean_c=temp_mean,
                humidity_pct=rec.get("humidity_pct"),
                rainfall_mm=rec.get("rainfall_mm"),
                source_id=source_id,
            )
            row_clim.timestamp = ts
            count_clim += 1

        if (tracked_vars is None or "soil" in tracked_vars) and "soil_moisture_pct" in rec:
            row_soil = repository.insert_land_soil_snapshot(
                db,
                land_id,
                moisture_pct=rec["soil_moisture_pct"],
                source_id=source_id,
            )
            row_soil.timestamp = ts
            count_soil += 1

        if (tracked_vars is None or "water" in tracked_vars) and "et0_mm" in rec:
            et0_mm = float(rec["et0_mm"])
            soil_moisture = rec.get("soil_moisture_pct")
            estimated_liters = (
                estimate_daily_water_liters(et0_mm, area_ha) if area_ha else None
            )
            row_water = repository.insert_land_water_snapshot(
                db,
                land_id,
                estimated_water_usage_liters=estimated_liters,
                crop_water_requirement_mm=et0_mm,
                irrigation_status=derive_irrigation_status(soil_moisture, et0_mm),
                source_id=source_id,
            )
            row_water.timestamp = ts
            count_water += 1

    return count_clim, count_soil, count_water


def refresh_environment_data(
    land_id: int,
    db: Session,
    *,
    days: int = 30,
    update_progress=None,
) -> bool:
    """
    Re-fetch recent Open-Meteo climate/soil/water for a land and replace rows
    in the requested window (default last 30 days).
    """
    land = repository.get_land(db, land_id)
    if land is None:
        return False

    if update_progress:
        update_progress("Refreshing climate, soil moisture & water data...")

    lat = float(land.latitude)
    lon = float(land.longitude)
    tracked_vars = _tracked_vars_for_land(land)
    area_ha = float(land.area_hectares) if land.area_hectares else None

    records, spatial_meta = open_meteo_polygon.fetch_polygon_historical_climate(
        boundary_polygon=land.boundary_polygon,
        latitude=lat,
        longitude=lon,
        days=days,
        area_hectares=area_ha,
    )
    if not records:
        logger.warning("environment refresh returned no records land_id=%s", land_id)
        return False

    from datetime import datetime

    first_date = records[0].get("date")
    if not first_date:
        return False
    since = datetime.strptime(first_date, "%Y-%m-%d")

    ds = repository.get_or_create_data_source(db, "Open-Meteo")
    repository.delete_environment_rows_since(db, land_id, since)
    count_clim, count_soil, count_water = insert_historical_environment_records(
        db,
        land,
        records,
        tracked_vars,
        source_id=int(ds.source_id),
    )
    if spatial_meta:
        repository.update_land_climate_sampling_metadata(db, land_id, spatial_meta)
    db.commit()
    logger.info(
        "environment refresh land_id=%s climate=%d soil=%d water=%d scope=%s",
        land_id,
        count_clim,
        count_soil,
        count_water,
        spatial_meta.get("spatial_scope") if spatial_meta else "unknown",
    )
    return True


def parse_refresh_sections(refresh: str | None) -> set[str]:
    if not refresh:
        return set(VALID_REFRESH_SECTIONS)
    sections = {s.strip().lower() for s in refresh.split(",") if s.strip()}
    return sections & VALID_REFRESH_SECTIONS or set(VALID_REFRESH_SECTIONS)


def execute(land_id: int, db: Session) -> None:
    """
    Discovery pipeline:
      Step 1 — Climate snapshot (Open-Meteo current)
      Step 2 — Soil moisture + ET₀ (Open-Meteo archive)
      Step 3 — Mark land active
    """
    try:
        def update_progress(msg: str):
            from app.models.land import Land
            l = db.get(Land, land_id)
            if l:
                l.status = msg
                db.commit()
                
        land = repository.get_land(db, land_id)
        if land is None:
            logger.warning("discovery skipped: land_id=%s not found", land_id)
            return

        lat = float(land.latitude)
        lon = float(land.longitude)
        
        tracked_vars = _tracked_vars_for_land(land)
        
        pipeline_errors = []

        # ------------------------------------------------------------------
        # Step 1 & 2: Historical Climate, Soil Moisture, and ET0 Backfill (365 days)
        # ------------------------------------------------------------------
        try:
            update_progress("Step 1/6: Fetching historical climate & soil moisture...")
            area_ha = float(land.area_hectares) if land.area_hectares else None
            records, spatial_meta = open_meteo_polygon.fetch_polygon_historical_climate(
                boundary_polygon=land.boundary_polygon,
                latitude=lat,
                longitude=lon,
                days=365,
                area_hectares=area_ha,
            )
            if records:
                ds = repository.get_or_create_data_source(db, "Open-Meteo")
                count_clim, count_soil, count_water = insert_historical_environment_records(
                    db,
                    land,
                    records,
                    tracked_vars,
                    source_id=int(ds.source_id),
                )
                if spatial_meta:
                    repository.update_land_climate_sampling_metadata(db, land_id, spatial_meta)
                logger.info(
                    "historical backfill saved land_id=%s climate=%d soil=%d water=%d scope=%s",
                    land_id,
                    count_clim,
                    count_soil,
                    count_water,
                    spatial_meta.get("spatial_scope") if spatial_meta else "unknown",
                )
        except Exception as e:
            pipeline_errors.append("climate_data")
            logger.exception("historical climate connector failed land_id=%s (continuing)", land_id)

        # ------------------------------------------------------------------
        # Step 3: High-Res Satellite Visuals (Sentinel-2)
        # ------------------------------------------------------------------
        try:
            update_progress("Step 2/6: Downloading visual Sentinel-2 thumbnails...")
            from app.tasks.sentinel_task import run_sentinel_visual_fetch
            run_sentinel_visual_fetch(land_id, db, update_progress=update_progress)
        except Exception as e:
            pipeline_errors.append("satellite_imagery")
            logger.exception("Sentinel visual task failed land_id=%s (continuing)", land_id)

        # ------------------------------------------------------------------
        # Step 4: NDVI history backfill (last 90 days from Planetary Computer)
        # ------------------------------------------------------------------
        # (Removed because run_crop_detection_task now handles time-series backfill directly per zone)

        # ------------------------------------------------------------------
        # Step 5: Static soil profile (ISRIC SoilGrids v2)
        # ------------------------------------------------------------------
        try:
            if tracked_vars is None or "soil" in tracked_vars:
                update_progress("Step 4/6: Fetching soil profile from ISRIC SoilGrids...")
                from app.tasks.soil_task import run_soil_profile_task
                run_soil_profile_task(land_id, db)
            else:
                logger.info("Skipping soil profile task (tracking disabled)")
        except Exception as e:
            pipeline_errors.append("soil_profile")
            logger.exception("soil profile task failed land_id=%s (continuing)", land_id)

        # ------------------------------------------------------------------
        # Step 6: Crop Detection & Intelligence (AI-based)
        # ------------------------------------------------------------------
        try:
            if tracked_vars is None or "ndvi" in tracked_vars:
                update_progress("Step 5/6: Running ML multi-crop detection...")
                from app.tasks.crop_task import run_crop_detection_task
                run_crop_detection_task(land_id, db, days=365)
            else:
                logger.info("Skipping crop detection task (tracking disabled)")
        except Exception as e:
            pipeline_errors.append("crop_detection")
            logger.exception("Crop detection task failed land_id=%s (continuing)", land_id)

        # ------------------------------------------------------------------
        # Step 7: AI Land Analysis (Groq — runs if user has API keys)
        # ------------------------------------------------------------------
        try:
            update_progress("Step 6/6: Generating AI insights via Groq Vision...")
            from app.ai.land_analyst import run_ai_land_analysis
            run_ai_land_analysis(land_id, db, user_id=land.user_id)
        except Exception as e:
            # AI is optional — do NOT mark this as a pipeline warning/error.
            # The land should finish cleanly even without AI insights.
            logger.info(
                "AI analysis skipped for land_id=%s (non-fatal): %s", land_id, e
            )

        # ------------------------------------------------------------------
        # Step 8: Finalize Status — keep land even when optional steps fail
        # ------------------------------------------------------------------
        land = repository.get_land(db, land_id)
        if land is not None:
            from datetime import datetime, timezone
            meta = dict(land.metadata_ or {})
            meta["pipeline_completed_at"] = datetime.now(timezone.utc).isoformat()
            
            if pipeline_errors:
                meta["pipeline_warnings"] = pipeline_errors
                logger.warning(
                    "land discovery completed with warnings land_id=%s warnings=%s",
                    land_id,
                    pipeline_errors,
                )
            else:
                meta.pop("pipeline_warnings", None)
                logger.info("land discovery completed land_id=%s", land_id)
                
            land.metadata_ = meta
            update_progress("active")
            db.commit()

    except Exception as e:
        logger.exception("land discovery failed land_id=%s", land_id)
        db.rollback()
        try:
            land = repository.get_land(db, land_id)
            if land is not None:
                meta = dict(land.metadata_ or {})
                meta["pipeline_warnings"] = meta.get("pipeline_warnings", []) + ["fatal_error"]
                meta["pipeline_last_error"] = str(e)[:500]
                land.metadata_ = meta
                land.status = "error"
                db.commit()
                logger.warning(
                    "land_id=%s marked error after fatal pipeline exception (not deleted)",
                    land_id,
                )
        except Exception:
            db.rollback()
        raise


def run_in_session(land_id: int) -> None:
    """Entrypoint for FastAPI BackgroundTasks (opens and closes a session)."""
    from app.db.session import SessionLocal

    db: Session = SessionLocal()
    try:
        execute(land_id, db)
    finally:
        db.close()
