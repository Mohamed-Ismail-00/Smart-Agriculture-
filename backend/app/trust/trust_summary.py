"""Build per-land trust summary across all sections."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.crops import user_crops as user_crop_service
from app.lands import repository
from app.trust.schemas import LandTrustSummaryResponse, TrustMetricSummary
from app.trust.tier_resolver import TrustTierResolver
from app.trust.types import DetectionMethod, TrustTier


def build_land_trust_summary(db: Session, land_id: int) -> LandTrustSummaryResponse | None:
    land = repository.get_land(db, land_id)
    if land is None:
        return None

    resolver = TrustTierResolver()
    sections: list[TrustMetricSummary] = []

    crop_rows = repository.list_land_crop_rows(db, land_id, limit=1)
    has_ndvi = len(repository.list_land_crop_rows(db, land_id)) > 0
    synthetic = False
    if has_ndvi:
        latest = repository.get_latest_crop_record(db, land_id)
        if latest and latest.source_id:
            from app.models.data_source import DataSource
            src = db.get(DataSource, latest.source_id)
            if src and "synthetic" in (src.name or "").lower():
                synthetic = True

    ndvi_tier = resolver.for_ndvi(is_synthetic=synthetic, has_value=has_ndvi)
    sections.append(
        TrustMetricSummary(
            metric="ndvi",
            trust_tier=ndvi_tier.value,
            label=resolver.user_facing_label(ndvi_tier),
            source_name="Sentinel-2 L2A (Planetary Computer)" if not synthetic else "Synthetic NDVI (fallback)",
            method="satellite_reflectance" if not synthetic else "synthetic_fallback",
            notes="Polygon bbox sampling" if not synthetic else "Re-analyze when satellite data is available",
        )
    )

    climate_sampling = (land.metadata_ or {}).get("climate_sampling") if land.metadata_ else None
    climate_rows = repository.list_land_climate_rows(db, land_id)
    temp_spread = climate_sampling.get("temp_spread_c") if climate_sampling else None
    clim_tier = resolver.for_climate_aggregate(
        has_rows=bool(climate_rows),
        temp_spread_c=temp_spread,
    )
    spatial_scope = climate_sampling.get("spatial_scope") if climate_sampling else "centroid"
    sample_count = climate_sampling.get("sample_count", 1) if climate_sampling else 1
    climate_notes = (
        f"Polygon mean ({sample_count} points)"
        if spatial_scope == "polygon_mean"
        else "Land centroid"
    )
    if temp_spread is not None and temp_spread > 3.0:
        climate_notes += f" · corner spread {temp_spread}°C"
    sections.append(
        TrustMetricSummary(
            metric="climate",
            trust_tier=clim_tier.value,
            label=resolver.user_facing_label(clim_tier),
            source_name="Open-Meteo",
            method="reanalysis_archive",
            notes=climate_notes,
            metadata={"spatial_scope": spatial_scope, "temp_spread_c": temp_spread},
        )
    )

    soil_rows = repository.list_land_soil_rows(db, land_id)
    soil_tier = resolver.for_soil_moisture(has_rows=bool(soil_rows))
    soil_notes = (
        f"Polygon mean ({sample_count} points)"
        if spatial_scope == "polygon_mean"
        else "Volumetric % at 0–7 cm, centroid"
    )
    sections.append(
        TrustMetricSummary(
            metric="soil_moisture",
            trust_tier=soil_tier.value,
            label=resolver.user_facing_label(soil_tier),
            source_name="Open-Meteo",
            method="soil_moisture_0_7cm",
            notes=soil_notes,
        )
    )

    from app.models.land_soil_profile import LandSoilProfile
    profile = db.query(LandSoilProfile).filter(LandSoilProfile.land_id == land_id).first()
    fetch_status = getattr(profile, "fetch_status", None) if profile else None
    has_profile = profile is not None and profile.ph_h2o is not None
    profile_tier = resolver.for_soil_profile(fetch_status=fetch_status, has_data=has_profile)
    profile_notes = "ISRIC SoilGrids v2"
    if fetch_status == "timeout":
        profile_notes = "SoilGrids fetch timed out — retry available"
    elif not profile:
        profile_notes = "Not yet fetched"
    sections.append(
        TrustMetricSummary(
            metric="soil_profile",
            trust_tier=profile_tier.value,
            label=resolver.user_facing_label(profile_tier),
            source_name="ISRIC SoilGrids",
            method="static_profile",
            notes=profile_notes,
            metadata={"fetch_status": fetch_status} if fetch_status else {},
        )
    )

    declared = user_crop_service.get_primary_declaration(db, land_id)
    zones = repository.list_crop_zones(db, land_id)
    primary_zone = zones[0] if zones else None
    crop_tier = resolver.for_crop_label(
        user_confirmed=declared is not None,
        detection_method=declared and DetectionMethod.USER_CONFIRMED.value or (
            getattr(primary_zone, "detection_method", None) if primary_zone else None
        ),
        has_label=bool(declared or primary_zone),
    )
    crop_method = (
        DetectionMethod.USER_CONFIRMED.value
        if declared
        else (getattr(primary_zone, "detection_method", None) or DetectionMethod.NDVI_PROFILE_MATCH.value)
    )
    crop_conf = (
        1.0
        if declared
        else float(primary_zone.avg_confidence)
        if primary_zone and primary_zone.avg_confidence is not None
        else None
    )
    crop_notes = None
    if declared and primary_zone and primary_zone.crop_type.lower() != declared.crop_type.lower():
        crop_notes = (
            f"User confirmed '{declared.crop_type}'; "
            f"spectral estimate '{primary_zone.crop_type}'"
        )
    elif primary_zone and getattr(primary_zone, "ambiguous", False):
        crop_notes = "Ambiguous spectral mix — please confirm crop"

    sections.append(
        TrustMetricSummary(
            metric="crop_type",
            trust_tier=crop_tier.value,
            label=resolver.user_facing_label(crop_tier),
            confidence=crop_conf if crop_conf else None,
            source_name="User declaration" if declared else "NDVI profile match",
            method=crop_method,
            notes=crop_notes,
            metadata={
                "declared_crop": declared.crop_type if declared else None,
                "estimated_crop": primary_zone.crop_type if primary_zone else None,
            },
        )
    )

    return LandTrustSummaryResponse(land_id=land_id, sections=sections)