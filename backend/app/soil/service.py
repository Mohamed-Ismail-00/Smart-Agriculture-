"""soil/service.py — Soil intelligence business logic (3 endpoints)."""

from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from app.lands import repository as land_repo
from app.soil import intelligence as soil_intel
from app.soil import repository as soil_repo
from app.soil.schemas import (
    CropSuitabilityEntry,
    DepthLayerValue,
    SoilProfileResponse,
    SoilProperty,
    SoilStatusResponse,
    SoilSuitabilityResponse,
)

# Human-readable units for each SoilGrids property
_PROPERTY_UNITS = {
    "phh2o":    ("pH",          "pH units"),
    "soc":      ("SOC",         "g/kg"),
    "clay":     ("Clay",        "%"),
    "sand":     ("Sand",        "%"),
    "silt":     ("Silt",        "%"),
    "bdod":     ("Bulk Density","kg/dm³"),
    "nitrogen": ("Nitrogen",    "g/kg"),
    "cec":      ("CEC",         "cmol(c)/kg"),
}

_DEPTH_ORDER = ["0-5cm", "5-15cm", "15-30cm"]


# ---------------------------------------------------------------------------
# 1. Soil Profile
# ---------------------------------------------------------------------------

def get_soil_profile(db: Session, land_id: int) -> Optional[SoilProfileResponse]:
    if land_repo.get_land(db, land_id) is None:
        return None

    profile = soil_repo.get_soil_profile(db, land_id)
    if profile is None or profile.depth_profile is None:
        fetch_status = getattr(profile, "fetch_status", None) if profile else None
        retry_available = fetch_status in ("timeout", "error", "empty") or profile is None
        source = "ISRIC-SoilGrids-v2 (not yet fetched)"
        if fetch_status == "timeout":
            source = "ISRIC-SoilGrids-v2 (fetch timed out)"
        elif fetch_status == "error":
            source = "ISRIC-SoilGrids-v2 (fetch failed)"
        return SoilProfileResponse(
            land_id=land_id,
            profile_available=False,
            fetched_at=profile.fetched_at.isoformat() if profile and profile.fetched_at else None,
            texture_class=None,
            properties=[],
            source=source,
            fetch_status=fetch_status,
            fetch_attempts=getattr(profile, "fetch_attempts", None) if profile else None,
            last_fetch_error=getattr(profile, "last_fetch_error", None) if profile else None,
            trust_tier=getattr(profile, "trust_tier", None) if profile else "unavailable",
            retry_available=retry_available,
        )

    props: list[SoilProperty] = []
    depth_data = profile.depth_profile

    for prop_key, (label, unit) in _PROPERTY_UNITS.items():
        prop_depths = depth_data.get(prop_key, {})
        topsoil = prop_depths.get("0-5cm")

        # Classification label
        classification: Optional[str] = None
        if prop_key == "phh2o" and topsoil is not None:
            classification = soil_intel.classify_ph(topsoil)
        elif prop_key == "soc" and topsoil is not None:
            classification = soil_intel.classify_soc(topsoil)

        depth_layers = [
            DepthLayerValue(depth=d, value=prop_depths.get(d))
            for d in _DEPTH_ORDER
        ]
        props.append(SoilProperty(
            name=label,
            unit=unit,
            topsoil_value=topsoil,
            depths=depth_layers,
            classification=classification,
        ))

    return SoilProfileResponse(
        land_id=land_id,
        profile_available=True,
        fetched_at=profile.fetched_at.isoformat() if profile.fetched_at else None,
        texture_class=profile.texture_class,
        properties=props,
        source="ISRIC-SoilGrids-v2",
        fetch_status=getattr(profile, "fetch_status", None) or "success",
        fetch_attempts=getattr(profile, "fetch_attempts", None),
        last_fetch_error=getattr(profile, "last_fetch_error", None),
        trust_tier=getattr(profile, "trust_tier", None) or "observed",
        retry_available=False,
    )


# ---------------------------------------------------------------------------
# 2. Soil Suitability
# ---------------------------------------------------------------------------

def get_soil_suitability(
    db: Session,
    land_id: int,
    crop: Optional[str] = None,
) -> Optional[SoilSuitabilityResponse]:
    if land_repo.get_land(db, land_id) is None:
        return None

    profile = soil_repo.get_soil_profile(db, land_id)
    if profile is None:
        return SoilSuitabilityResponse(
            land_id=land_id,
            profile_available=False,
            overall_best_score=None,
            top_crops=[],
            all_crops=[],
            advice=["Soil profile not yet fetched. Register land to trigger automatic soil profiling."],
            texture_class=None,
        )

    ph       = float(profile.ph_h2o) if profile.ph_h2o is not None else None
    clay     = float(profile.clay_pct) if profile.clay_pct is not None else None
    soc      = float(profile.soc_g_per_kg) if profile.soc_g_per_kg is not None else None
    nitrogen = float(profile.nitrogen_g_per_kg) if profile.nitrogen_g_per_kg is not None else None

    all_scores = soil_intel.score_all_crops(ph, clay, soc, nitrogen)
    top3 = soil_intel.best_crops(all_scores, top_n=3)
    all_ranked = soil_intel.best_crops(all_scores, top_n=len(all_scores))
    advice = soil_intel.generate_soil_advice(ph, soc, clay, nitrogen, profile.texture_class)
    best_score = max(all_scores.values()) if all_scores else None

    return SoilSuitabilityResponse(
        land_id=land_id,
        profile_available=True,
        overall_best_score=round(best_score, 2) if best_score is not None else None,
        top_crops=[CropSuitabilityEntry(**c) for c in top3],
        all_crops=[CropSuitabilityEntry(**c) for c in all_ranked],
        advice=advice,
        texture_class=profile.texture_class,
    )


# ---------------------------------------------------------------------------
# 3. Soil Status (live moisture + static profile summary)
# ---------------------------------------------------------------------------

def get_soil_status(db: Session, land_id: int) -> Optional[SoilStatusResponse]:
    if land_repo.get_land(db, land_id) is None:
        return None

    # Live moisture from time-series land_soil table
    latest_moisture_row = land_repo.get_latest_soil_record(db, land_id)
    moisture_val = None
    moisture_ts = None
    if latest_moisture_row:
        moisture_val = float(latest_moisture_row.moisture_pct) \
            if latest_moisture_row.moisture_pct is not None else None
        moisture_ts = latest_moisture_row.timestamp.isoformat()

    # Static SoilGrids profile summary
    profile = soil_repo.get_soil_profile(db, land_id)
    ph = soc = clay = sand = nitrogen = texture = suitability = None
    ph_class = soc_class = None
    profile_source = "ISRIC-SoilGrids-v2 (not yet fetched)"

    if profile is not None:
        ph = float(profile.ph_h2o) if profile.ph_h2o is not None else None
        soc = float(profile.soc_g_per_kg) if profile.soc_g_per_kg is not None else None
        clay = float(profile.clay_pct) if profile.clay_pct is not None else None
        sand = float(profile.sand_pct) if profile.sand_pct is not None else None
        nitrogen = float(profile.nitrogen_g_per_kg) if profile.nitrogen_g_per_kg is not None else None
        texture = profile.texture_class
        suitability = float(profile.suitability_score) if profile.suitability_score is not None else None
        ph_class = soil_intel.classify_ph(ph) if ph is not None else None
        soc_class = soil_intel.classify_soc(soc) if soc is not None else None
        profile_source = "ISRIC-SoilGrids-v2"

    advice = soil_intel.generate_soil_advice(ph, soc, clay, nitrogen, texture)

    return SoilStatusResponse(
        land_id=land_id,
        latest_moisture_pct=moisture_val,
        moisture_timestamp=moisture_ts,
        ph_h2o=ph,
        ph_class=ph_class,
        soc_g_per_kg=soc,
        soc_class=soc_class,
        clay_pct=clay,
        sand_pct=sand,
        nitrogen_g_per_kg=nitrogen,
        texture_class=texture,
        suitability_score=suitability,
        profile_source=profile_source,
        advice=advice,
    )
