"""
lands/service.py
----------------
Business logic for land registration, time-series reads, and image listing.

Land registration flow:
  1. Validate + close polygon ring
  2. Compute centroid (lat, lon) from polygon
  3. Compute area in hectares
  4. Persist land with geometry
  5. Return land_id for pipeline to process
"""

import io
import pandas as pd
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from app.lands import repository
from app.lands.geometry import (
    close_ring,
    compute_area_hectares,
    compute_centroid,
    validate_polygon,
)
from app.lands.schemas import (
    GeoJSONPolygon,
    LandDetailResponse,
    LandImageItem,
    LandImageListResponse,
    LandListItem,
    LandListResponse,
    LandTimeSeriesResponse,
    TimeSeriesPoint,
)


def list_all_lands(db: Session, user_id: Optional[int] = None) -> LandListResponse:
    """Return all lands as lightweight list items."""
    from app.models.land_image import LandImage
    from sqlalchemy import select, desc

    rows = repository.list_all_lands(db, user_id=user_id)
    
    # Fetch latest true_color images for these lands
    land_ids = [r.land_id for r in rows]
    latest_images = {}
    if land_ids:
        stmt = select(LandImage).where(
            LandImage.land_id.in_(land_ids),
            LandImage.image_type == "true_color"
        ).order_by(desc(LandImage.timestamp))
        for img in db.execute(stmt).scalars().all():
            if img.land_id not in latest_images:
                latest_images[img.land_id] = img

    items = []
    for r in rows:
        latest_img = latest_images.get(r.land_id)
        latest_image_url = f"/api/v1/lands/{r.public_id}/images/{latest_img.id}/content" if latest_img else None
        
        items.append(
            LandListItem(
                land_id=int(r.land_id),
                public_id=str(r.public_id),
                name=r.name,
                description=r.description,
                latitude=float(r.latitude),
                longitude=float(r.longitude),
                area_hectares=float(r.area_hectares) if r.area_hectares is not None else None,
                status=r.status,
                created_at=r.created_at.isoformat(),
                latest_image_url=latest_image_url,
            )
        )
    return LandListResponse(lands=items, total=len(items))


def register_land_for_discovery(
    db: Session,
    *,
    name: str,
    geometry: GeoJSONPolygon,
    description: Optional[str],
    user_id: Optional[int],
    metadata_: Optional[dict] = None,
) -> int:
    """
    Validate the GeoJSON polygon, compute centroid + area, persist, and return land_id.
    """
    outer_ring = geometry.coordinates[0]

    # Validate and close the ring
    validate_polygon(outer_ring)
    closed_ring = close_ring(outer_ring)

    # Compute centroid (lat, lon) and area
    centroid_lat, centroid_lng = compute_centroid(closed_ring)
    area_ha = compute_area_hectares(closed_ring)

    # Validate that this is actually agricultural land
    from app.lands.validator import validate_agricultural_land
    validate_agricultural_land(centroid_lat, centroid_lng)

    # Build closed GeoJSON geometry for storage
    closed_geojson = {
        "type": "Polygon",
        "coordinates": [closed_ring],
    }

    land = repository.create_land(
        db,
        name=name,
        latitude=Decimal(str(centroid_lat)),
        longitude=Decimal(str(centroid_lng)),
        description=description,
        user_id=user_id,
        boundary_polygon=closed_geojson,
        area_hectares=area_ha,
        metadata_=metadata_,
    )
    db.commit()
    db.refresh(land)
    return int(land.land_id)


def get_land_detail(db: Session, land_id: int) -> Optional[LandDetailResponse]:
    """Return full land detail including geometry and computed area."""
    land = repository.get_land(db, land_id)
    if land is None:
        return None
    return LandDetailResponse(
        land_id=int(land.land_id),
        public_id=str(land.public_id) if land.public_id else None,
        name=land.name,
        description=land.description,
        latitude=float(land.latitude),
        longitude=float(land.longitude),
        area_hectares=float(land.area_hectares) if land.area_hectares is not None else None,
        status=land.status,
        boundary_polygon=land.boundary_polygon,
        metadata_=land.metadata_,
        created_at=land.created_at.isoformat(),
    )

def get_land_by_public_id(db: Session, public_id: str) -> Optional[LandDetailResponse]:
    """Safe public lookup (used by security layer)."""
    land = repository.get_land_by_public_id(db, public_id)
    if land is None:
        return None
    return LandDetailResponse(
        land_id=int(land.land_id),
        public_id=str(land.public_id) if land.public_id else None,
        name=land.name,
        description=land.description,
        latitude=float(land.latitude),
        longitude=float(land.longitude),
        area_hectares=float(land.area_hectares) if land.area_hectares is not None else None,
        status=land.status,
        boundary_polygon=land.boundary_polygon,
        metadata_=land.metadata_,
        created_at=land.created_at.isoformat(),
    )


def _lookup_data_source_name(db: Session, source_id: Optional[int], cache: dict) -> Optional[str]:
    if source_id is None:
        return None
    if source_id not in cache:
        from app.models.data_source import DataSource
        row = db.get(DataSource, source_id)
        cache[source_id] = row.name if row else None
    return cache.get(source_id)


def _crop_observation_source(db: Session, source_id: Optional[int], cache: dict) -> Optional[str]:
    name = _lookup_data_source_name(db, source_id, cache) or ""
    if "synthetic" in name.lower():
        return "synthetic"
    if "sentinel" in name.lower():
        return "sentinel"
    return "observed"


def land_timeseries(
    db: Session,
    land_id: int,
    metric: str,
    *,
    zone_id: Optional[int] = None,
) -> Optional[LandTimeSeriesResponse]:
    if repository.get_land(db, land_id) is None:
        return None

    if metric == "climate":
        land = repository.get_land(db, land_id)
        climate_sampling = None
        if land and land.metadata_:
            climate_sampling = land.metadata_.get("climate_sampling")

        rows = repository.list_land_climate_rows(db, land_id)
        points: list[TimeSeriesPoint] = []
        for r in rows:
            payload = {}
            if r.temperature_min_c is not None:
                payload["temperature_min_c"] = float(r.temperature_min_c)
            if r.temperature_mean_c is not None:
                payload["temperature_mean_c"] = float(r.temperature_mean_c)
            if r.humidity_pct is not None:
                payload["humidity_pct"] = float(r.humidity_pct)
            if r.rainfall_mm is not None:
                payload["rainfall_mm"] = float(r.rainfall_mm)
            if climate_sampling:
                payload["spatial_sample"] = climate_sampling
            points.append(
                TimeSeriesPoint(
                    timestamp=r.timestamp.isoformat(),
                    value=float(r.temperature_celsius) if r.temperature_celsius is not None else None,
                    payload=payload or None,
                )
            )
        return LandTimeSeriesResponse(land_id=land_id, metric=metric, points=points)

    elif metric == "water":
        rows = repository.list_land_water_rows(db, land_id)
        points = []
        for r in rows:
            payload = {}
            if r.irrigation_status is not None:
                payload["irrigation_status"] = r.irrigation_status
            if r.crop_water_requirement_mm is not None:
                payload["crop_water_requirement_mm"] = float(r.crop_water_requirement_mm)
            if r.water_efficiency_ratio is not None:
                payload["water_efficiency_ratio"] = float(r.water_efficiency_ratio)
            points.append(
                TimeSeriesPoint(
                    timestamp=r.timestamp.isoformat(),
                    value=float(r.estimated_water_usage_liters) if r.estimated_water_usage_liters is not None else None,
                    payload=payload or None,
                )
            )
        return LandTimeSeriesResponse(land_id=land_id, metric=metric, points=points)

    elif metric == "crops":
        effective_zone_id = zone_id
        if effective_zone_id is None:
            primary = repository.get_primary_crop_zone(db, land_id)
            if primary is not None:
                effective_zone_id = int(primary.zone_id)
        rows = repository.list_land_crop_rows(db, land_id, zone_id=effective_zone_id)
        if zone_id is None and effective_zone_id is not None:
            # Monitoring stores new observations for the whole field (no zone). Without them the
            # default series would stop at the date the zones were computed.
            seen_days = {r.timestamp.date() for r in rows}
            field_rows = [
                r for r in repository.list_land_crop_rows(db, land_id)
                if r.zone_id is None and r.timestamp.date() not in seen_days
            ]
            rows = sorted([*rows, *field_rows], key=lambda r: r.timestamp)
        source_cache: dict = {}
        points = []
        for r in rows:
            payload = {}
            if r.zone_id is not None:
                payload["zone_id"] = int(r.zone_id)
            obs_source = _crop_observation_source(db, r.source_id, source_cache)
            if obs_source:
                payload["data_source"] = obs_source
            if r.trust_tier:
                payload["trust_tier"] = r.trust_tier
            elif obs_source == "synthetic":
                payload["trust_tier"] = "estimated"
            elif obs_source == "sentinel":
                payload["trust_tier"] = "observed"
            if r.is_synthetic:
                payload["is_synthetic"] = True
            if r.crop_type is not None:
                payload["crop_type"] = r.crop_type
            if r.estimated_yield_tons is not None:
                payload["estimated_yield_tons"] = float(r.estimated_yield_tons)
            if r.growth_stage is not None:
                payload["growth_stage"] = r.growth_stage
            if r.ndvi_trend is not None:
                payload["ndvi_trend"] = r.ndvi_trend
            if r.confidence is not None:
                payload["confidence"] = float(r.confidence)
            if r.dvi_value is not None:
                payload["dvi_value"] = float(r.dvi_value)
            if r.evi_value is not None:
                payload["evi_value"] = float(r.evi_value)
            if r.ndwi_value is not None:
                payload["ndwi_value"] = float(r.ndwi_value)
            if r.savi_value is not None:
                payload["savi_value"] = float(r.savi_value)
            if r.gndvi_value is not None:
                payload["gndvi_value"] = float(r.gndvi_value)
            points.append(
                TimeSeriesPoint(
                    timestamp=r.timestamp.isoformat(),
                    value=float(r.ndvi_value) if r.ndvi_value is not None else None,
                    payload=payload or None,
                )
            )
        return LandTimeSeriesResponse(land_id=land_id, metric=metric, points=points)

    elif metric == "soil":
        rows = repository.list_land_soil_rows(db, land_id)
        points = []
        for r in rows:
            payload = {}
            if r.soil_type is not None:
                payload["soil_type"] = r.soil_type
            if r.ph_level is not None:
                payload["ph_level"] = float(r.ph_level)
            if r.organic_matter_pct is not None:
                payload["organic_matter_pct"] = float(r.organic_matter_pct)
            if r.suitability_score is not None:
                payload["suitability_score"] = float(r.suitability_score)
            points.append(
                TimeSeriesPoint(
                    timestamp=r.timestamp.isoformat(),
                    value=float(r.moisture_pct) if r.moisture_pct is not None else None,
                    payload=payload or None,
                )
            )
        return LandTimeSeriesResponse(land_id=land_id, metric=metric, points=points)

    return LandTimeSeriesResponse(land_id=land_id, metric=metric, points=[])


def list_images(
    db: Session,
    land_id: int,
    public_id: Optional[str] = None,
    image_type: Optional[str] = None,
) -> Optional[LandImageListResponse]:
    if repository.get_land(db, land_id) is None:
        return None
    rows = repository.list_land_images(db, land_id, image_type=image_type)
    items = []
    
    # Fallback to land_id if public_id is not provided (though it should be)
    pid = public_id if public_id else land_id
    
    for r in rows:
        image_url = f"/api/v1/lands/{pid}/images/{r.id}/content"

        items.append(
            LandImageItem(
                id=int(r.id),
                date=r.timestamp.strftime("%Y-%m-%d"),
                image_type=r.image_type,
                image_url=image_url,
                ndvi_mean=float(r.ndvi_mean) if r.ndvi_mean is not None else None,
                cloud_cover_pct=float(r.cloud_cover_pct) if r.cloud_cover_pct is not None else None,
            )
        )
    return LandImageListResponse(land_id=land_id, images=items)


# ---------------------------------------------------------------------------
# Crop Zones
# ---------------------------------------------------------------------------

from app.lands.schemas import CropZoneItem, CropZoneListResponse


def list_crop_zones(db: Session, land_id: int) -> Optional[CropZoneListResponse]:
    """Return all crop zones for a land with their latest stats."""
    land = repository.get_land(db, land_id)
    if land is None:
        return None

    from app.trust.confidence_scorer import ConfidenceScorer

    zones = [z for z in repository.list_crop_zones(db, land_id) if not z.suppressed]
    items = []
    for z in zones:
        conf = float(z.avg_confidence) if z.avg_confidence else None
        sep = float(z.separation_score) if z.separation_score else None
        items.append(
            CropZoneItem(
                zone_id=int(z.zone_id),
                crop_type=z.crop_type,
                area_hectares=float(z.area_hectares) if z.area_hectares else None,
                area_pct=float(z.area_pct) if z.area_pct else None,
                status=z.status,
                avg_confidence=conf,
                latest_ndvi=float(z.latest_ndvi) if z.latest_ndvi else None,
                latest_growth_stage=z.latest_growth_stage,
                estimated_yield_tons=float(z.estimated_yield_tons) if z.estimated_yield_tons else None,
                first_detected=z.first_detected.isoformat() if z.first_detected else None,
                last_updated=z.last_updated.isoformat() if z.last_updated else None,
                detection_method=z.detection_method,
                trust_tier=z.trust_tier,
                separation_score=sep,
                ambiguous=bool(z.ambiguous),
                show_confidence_bar=ConfidenceScorer.should_show_confidence_bar(
                    conf or 0.0, sep
                ),
            )
        )
    return CropZoneListResponse(
        land_id=land_id,
        total_zones=len(items),
        zones=items,
    )


def export_land_to_excel(db: Session, land_id: int) -> Optional[io.BytesIO]:
    """Generates an Excel file containing summary, analysis, and timeseries data for the land."""
    land = repository.get_land(db, land_id)
    if not land:
        return None
        
    climate_rows = repository.list_land_climate_rows(db, land_id)
    soil_rows = repository.list_land_soil_rows(db, land_id)
    water_rows = repository.list_land_water_rows(db, land_id)
    crop_rows = repository.list_land_crop_rows(db, land_id)
    source_cache: dict = {}

    def _source_label(source_id: Optional[int]) -> str:
        return _lookup_data_source_name(db, source_id, source_cache) or "Unknown"

    # Create DataFrames
    df_climate = pd.DataFrame([{
        "Timestamp": r.timestamp.replace(tzinfo=None),
        "Max Temp (°C)": float(r.temperature_celsius) if r.temperature_celsius is not None else None,
        "Min Temp (°C)": float(r.temperature_min_c) if r.temperature_min_c is not None else None,
        "Mean Temp (°C)": float(r.temperature_mean_c) if r.temperature_mean_c is not None else None,
        "Humidity (%)": float(r.humidity_pct) if r.humidity_pct is not None else None,
        "Precipitation (mm)": float(r.rainfall_mm) if r.rainfall_mm is not None else None,
        "Source": _source_label(r.source_id),
    } for r in climate_rows]) if climate_rows else pd.DataFrame()

    df_soil = pd.DataFrame([{
        "Timestamp": r.timestamp.replace(tzinfo=None),
        "Moisture (%)": float(r.moisture_pct) if r.moisture_pct else None,
        "pH Level": float(r.ph_level) if r.ph_level else None,
        "Soil Type": r.soil_type,
        "Organic Matter (%)": float(r.organic_matter_pct) if r.organic_matter_pct else None,
        "Source": _source_label(r.source_id),
    } for r in soil_rows]) if soil_rows else pd.DataFrame()

    df_water = pd.DataFrame([{
        "Timestamp": r.timestamp.replace(tzinfo=None),
        "Estimated Usage (Liters)": float(r.estimated_water_usage_liters) if r.estimated_water_usage_liters else None,
        "Crop Water Req (mm)": float(r.crop_water_requirement_mm) if r.crop_water_requirement_mm else None,
        "Efficiency Ratio": float(r.water_efficiency_ratio) if r.water_efficiency_ratio else None,
        "Irrigation Status": r.irrigation_status,
        "Source": _source_label(r.source_id),
    } for r in water_rows]) if water_rows else pd.DataFrame()

    df_crop = pd.DataFrame([{
        "Timestamp": r.timestamp.replace(tzinfo=None),
        "Zone ID": int(r.zone_id) if r.zone_id is not None else None,
        "Crop Type": r.crop_type,
        "NDVI": float(r.ndvi_value) if r.ndvi_value else None,
        "EVI": float(r.evi_value) if r.evi_value else None,
        "Growth Stage": r.growth_stage,
        "Est. Yield (Tons)": float(r.estimated_yield_tons) if r.estimated_yield_tons else None,
        "Data Source": _crop_observation_source(db, r.source_id, source_cache) or "observed",
        "Source": _source_label(r.source_id),
    } for r in crop_rows]) if crop_rows else pd.DataFrame()

    # --- Analytics & Aggregations ---
    avg_temp = (
        df_climate["Mean Temp (°C)"].mean()
        if not df_climate.empty and "Mean Temp (°C)" in df_climate
        else None
    )
    max_temp = (
        df_climate["Max Temp (°C)"].max()
        if not df_climate.empty and "Max Temp (°C)" in df_climate
        else None
    )
    min_temp = (
        df_climate["Min Temp (°C)"].min()
        if not df_climate.empty and "Min Temp (°C)" in df_climate
        else None
    )

    avg_ndvi = df_crop["NDVI"].mean() if not df_crop.empty and "NDVI" in df_crop else None
    max_ndvi = df_crop["NDVI"].max() if not df_crop.empty and "NDVI" in df_crop else None
    
    avg_moisture = df_soil["Moisture (%)"].mean() if not df_soil.empty and "Moisture (%)" in df_soil else None
    min_moisture = df_soil["Moisture (%)"].min() if not df_soil.empty and "Moisture (%)" in df_soil else None
    max_moisture = df_soil["Moisture (%)"].max() if not df_soil.empty and "Moisture (%)" in df_soil else None

    # We will build the summary sheet manually instead of using a DataFrame to avoid overwriting issues.
    summary_sections = [
        ("General Information", [
            ("Land Name", land.name),
            ("Area (Hectares)", float(land.area_hectares) if land.area_hectares else "N/A"),
            ("Status", land.status.capitalize() if land.status else "N/A"),
            ("Description", land.description or "N/A"),
        ]),
        ("Exported Data Records", [
            ("Climate Records", len(df_climate)),
            ("Crop / NDVI Records", len(df_crop)),
            ("Soil Records", len(df_soil)),
            ("Water / Irrigation Records", len(df_water)),
        ]),
        ("Averages & Extremes", [
            ("Avg Mean Temperature (°C)", avg_temp),
            ("Peak Max Temperature (°C)", max_temp),
            ("Lowest Min Temperature (°C)", min_temp),
            ("Avg NDVI Index", avg_ndvi),
            ("Peak NDVI Index", max_ndvi),
            ("Avg Soil Moisture (%)", avg_moisture),
            ("Max Soil Moisture (%)", max_moisture),
            ("Min Soil Moisture (%)", min_moisture),
        ]),
        ("Data Provenance", [
            ("Climate / Soil Moisture / Water", "Open-Meteo (per-row Source column)"),
            ("Crop / NDVI", "Sentinel-2 L2A or synthetic fallback (Data Source column)"),
            ("Soil Chemistry (pH, type)", "ISRIC SoilGrids where available"),
        ]),
    ]
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        workbook = writer.book
        
        # Create Summary Sheet FIRST so it appears as the default first tab in Excel
        summary_sheet = workbook.add_worksheet('Summary')
        
        # Write data sheets next
        if not df_climate.empty:
            df_climate.to_excel(writer, sheet_name='Climate Data', index=False)
        if not df_crop.empty:
            df_crop.to_excel(writer, sheet_name='Crop Data', index=False)
        if not df_water.empty:
            df_water.to_excel(writer, sheet_name='Water Data', index=False)
        if not df_soil.empty:
            df_soil.to_excel(writer, sheet_name='Soil Data', index=False)
        
        # --- Rich Formatting Styles ---
        title_format = workbook.add_format({
            'bold': True, 'font_size': 18, 'font_color': 'white', 
            'bg_color': '#1E3A8A', 'align': 'center', 'valign': 'vcenter', 'border': 1
        })
        section_format = workbook.add_format({
            'bold': True, 'font_size': 12, 'font_color': '#1E3A8A', 
            'bg_color': '#DBEAFE', 'border': 1, 'valign': 'vcenter'
        })
        metric_format = workbook.add_format({
            'bold': True, 'bg_color': '#F3F4F6', 'border': 1, 'valign': 'vcenter'
        })
        value_text_format = workbook.add_format({
            'border': 1, 'valign': 'vcenter'
        })
        value_num_format = workbook.add_format({
            'border': 1, 'valign': 'vcenter', 'num_format': '#,##0.00'
        })
        value_int_format = workbook.add_format({
            'border': 1, 'valign': 'vcenter', 'num_format': '#,##0'
        })
        
        # Add Title
        summary_sheet.merge_range('A1:B2', f"Land Analytics Report: {land.name}", title_format)
        
        # Set column widths
        summary_sheet.set_column('A:A', 35)
        summary_sheet.set_column('B:B', 25)
        
        current_row = 3
        
        for section_title, items in summary_sections:
            summary_sheet.merge_range(current_row, 0, current_row, 1, section_title, section_format)
            current_row += 1
            for metric, value in items:
                summary_sheet.write_string(current_row, 0, metric, metric_format)
                
                if value is None or value == "N/A":
                    summary_sheet.write_string(current_row, 1, "N/A", value_text_format)
                elif isinstance(value, float):
                    summary_sheet.write_number(current_row, 1, value, value_num_format)
                elif isinstance(value, int):
                    summary_sheet.write_number(current_row, 1, value, value_int_format)
                else:
                    summary_sheet.write_string(current_row, 1, str(value), value_text_format)
                current_row += 1
            current_row += 1 # Empty row between sections
            
        summary_sheet.hide_gridlines(2)
        
        # Format other sheets as Excel Tables
        for sheet_name, df in [('Climate Data', df_climate), ('Crop Data', df_crop), ('Water Data', df_water), ('Soil Data', df_soil)]:
            if not df.empty:
                worksheet = writer.sheets[sheet_name]
                # Auto-fit columns safely
                for i, col in enumerate(df.columns):
                    column_len = max(df[col].astype(str).str.len().max(), len(col)) + 4
                    worksheet.set_column(i, i, float(column_len))
                
                max_row, max_col = df.shape
                worksheet.add_table(0, 0, max_row, max_col - 1, {
                    'columns': [{'header': c} for c in df.columns],
                    'style': 'Table Style Medium 2'
                })

        # --- Enhanced Charts ---
        if not df_crop.empty and 'NDVI' in df_crop and len(df_crop) > 0:
            ndvi_col = df_crop.columns.get_loc('NDVI')
            chart = workbook.add_chart({'type': 'area'}) # Changed to area chart for cooler look
            max_row = len(df_crop) + 1
            chart.add_series({
                'name':       ['Crop Data', 0, ndvi_col],
                'categories': ['Crop Data', 1, 0, max_row - 1, 0],
                'values':     ['Crop Data', 1, ndvi_col, max_row - 1, ndvi_col],
                'fill':       {'color': '#10B981', 'transparency': 40},
                'line':       {'color': '#059669', 'width': 2.5},
            })
            chart.set_title({'name': 'NDVI Vegetation Index', 'name_font': {'size': 14, 'color': '#1F2937'}})
            chart.set_x_axis({'name': 'Timeline', 'num_font': {'color': '#6B7280'}})
            chart.set_y_axis({'name': 'NDVI', 'major_gridlines': {'visible': True, 'line': {'color': '#E5E7EB'}}})
            chart.set_chartarea({'border': {'none': True}, 'fill': {'color': '#F9FAFB'}})
            chart.set_legend({'position': 'none'})
            chart.set_size({'width': 650, 'height': 300})
            summary_sheet.insert_chart('D2', chart)
            
        if not df_climate.empty and 'Max Temp (°C)' in df_climate and len(df_climate) > 0:
            max_temp_col = df_climate.columns.get_loc('Max Temp (°C)')
            min_temp_col = (
                df_climate.columns.get_loc('Min Temp (°C)')
                if 'Min Temp (°C)' in df_climate
                else None
            )
            chart_temp = workbook.add_chart({'type': 'line'})
            max_row_temp = len(df_climate) + 1
            chart_temp.add_series({
                'name':       ['Climate Data', 0, max_temp_col],
                'categories': ['Climate Data', 1, 0, max_row_temp - 1, 0],
                'values':     ['Climate Data', 1, max_temp_col, max_row_temp - 1, max_temp_col],
                'line':       {'color': '#F59E0B', 'width': 3},
                'smooth':     True
            })
            if min_temp_col is not None:
                chart_temp.add_series({
                    'name':       ['Climate Data', 0, min_temp_col],
                    'categories': ['Climate Data', 1, 0, max_row_temp - 1, 0],
                    'values':     ['Climate Data', 1, min_temp_col, max_row_temp - 1, min_temp_col],
                    'line':       {'color': '#3B82F6', 'width': 2},
                    'smooth':     True
                })
            chart_temp.set_title({'name': 'Daily Temperature Range (°C)', 'name_font': {'size': 14, 'color': '#1F2937'}})
            chart_temp.set_x_axis({'name': 'Timeline', 'num_font': {'color': '#6B7280'}})
            chart_temp.set_y_axis({'name': 'Temperature', 'major_gridlines': {'visible': True, 'line': {'color': '#E5E7EB'}}})
            chart_temp.set_chartarea({'border': {'none': True}, 'fill': {'color': '#F9FAFB'}})
            chart_temp.set_legend({'position': 'none'})
            chart_temp.set_size({'width': 650, 'height': 300})
            summary_sheet.insert_chart('D19', chart_temp)
            
    output.seek(0)
    return output
