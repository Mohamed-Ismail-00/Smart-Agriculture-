"""
app/ai/land_analyst.py
-----------------------
Builds rich agricultural context from the database and sends it to Groq
for expert analysis. Results are stored as LandAiInsight rows.

Called from:
  - land_discovery_pipeline (Step 7, after crop detection)
  - The /ai/lands/{land_id}/analyze endpoint (on demand)
"""

from __future__ import annotations

import json
import logging
import base64
from typing import Optional

from sqlalchemy.orm import Session

from app.ai.groq_client import GroqClient
from app.models.land import Land
from app.models.land_ai_insight import LandAiInsight

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# System prompt — the agronomist persona for Groq
# ---------------------------------------------------------------------------

SYSTEM_PROMPT_PERSONA = """You are AgriMind, an expert AI agricultural analyst specializing in multimodal remote sensing, 
precision farming, and crop health assessment. You have deep expertise in:
- Visual interpretation of True Color and NDVI satellite imagery
- Multi-spectral indices: NDVI (health), EVI (biomass), NDWI (water stress), SAVI (soil adjustment), GNDVI (chlorophyll)
- Soil health assessment and irrigation scheduling
- Crop disease and stress detection
- Egyptian and North African agricultural conditions

When analyzing farm data, provide:
1. Clear, actionable insights a farmer can act on TODAY
2. Specific numbers and thresholds, not vague statements
3. Cross-reference visual anomalies in satellite imagery with numerical spectral data
4. Risk flags if anything looks anomalous
5. Your confidence level in the assessment
"""

SYSTEM_PROMPT_JSON = """
Always respond in structured JSON format as specified by the user prompt.
"""


# ---------------------------------------------------------------------------
# Context builder
# ---------------------------------------------------------------------------

def _build_land_context(land_id: int, db: Session) -> dict:
    """Fetch all relevant data for a land and return as a structured dict."""
    from app.lands import repository as land_repo

    land = db.query(Land).filter(Land.land_id == land_id).first()
    if not land:
        return {}

    context = {
        "land": {
            "name": land.name,
            "latitude": float(land.latitude),
            "longitude": float(land.longitude),
            "area_hectares": float(land.area_hectares) if land.area_hectares else None,
            "status": land.status,
        },
        "spectral_history": [],
        "recent_climate": [],
        "recent_soil": [],
        "crop_zones": [],
    }

    # Spectral history (dynamically downsampled to max 60 points)
    try:
        crops = land_repo.list_land_crop_rows(db, land_id)
        if len(crops) > 60:
            step = len(crops) // 60
            crops = crops[::step]
        for c in crops:
            context["spectral_history"].append({
                "date": c.timestamp.strftime("%Y-%m-%d"),
                "ndvi": round(float(c.ndvi_value), 4) if c.ndvi_value else None,
                "dvi": round(float(c.dvi_value), 4) if getattr(c, "dvi_value", None) else None,
                "evi": round(float(c.evi_value), 4) if getattr(c, "evi_value", None) else None,
                "ndwi": round(float(c.ndwi_value), 4) if getattr(c, "ndwi_value", None) else None,
                "savi": round(float(c.savi_value), 4) if getattr(c, "savi_value", None) else None,
                "gndvi": round(float(c.gndvi_value), 4) if getattr(c, "gndvi_value", None) else None,
                "stage": c.growth_stage,
                "trend": c.ndvi_trend,
            })
    except Exception as exc:
        logger.warning("Could not fetch spectral history for AI context: %s", exc)

    # Recent climate (dynamically downsampled to max 30 points)
    try:
        climate = land_repo.list_land_climate_rows(db, land_id)
        if len(climate) > 30:
            step = len(climate) // 30
            climate = climate[::step]
        for c in climate:
            context["recent_climate"].append({
                "date": c.timestamp.strftime("%Y-%m-%d"),
                "temp_c": float(c.temperature_celsius) if c.temperature_celsius else None,
                "humidity_pct": float(c.humidity_pct) if c.humidity_pct else None,
                "rainfall_mm": float(c.rainfall_mm) if c.rainfall_mm else None,
            })
    except Exception as exc:
        logger.warning("Could not fetch climate for AI context: %s", exc)

    # Recent soil (dynamically downsampled to max 15 points)
    try:
        soil = land_repo.list_land_soil_rows(db, land_id)
        if len(soil) > 15:
            step = len(soil) // 15
            soil = soil[::step]
        for s in soil:
            context["recent_soil"].append({
                "date": s.timestamp.strftime("%Y-%m-%d"),
                "moisture_pct": float(s.moisture_pct) if s.moisture_pct else None,
                "ph": float(s.ph_level) if s.ph_level else None,
                "organic_matter_pct": float(s.organic_matter_pct) if s.organic_matter_pct else None,
            })
    except Exception as exc:
        logger.warning("Could not fetch soil for AI context: %s", exc)

    # Crop zones
    try:
        from app.models.crop_zone import CropZone
        zones = db.query(CropZone).filter(CropZone.land_id == land_id).all()
        for z in zones:
            context["crop_zones"].append({
                "crop_type": z.crop_type,
                "area_pct": float(z.area_pct) if z.area_pct else None,
                "avg_ndvi": float(z.latest_ndvi) if z.latest_ndvi else None,
                "growth_stage": z.latest_growth_stage,
                "confidence": float(z.avg_confidence) if z.avg_confidence else None,
            })
    except Exception as exc:
        logger.warning("Could not fetch crop zones for AI context: %s", exc)

    return context


# ---------------------------------------------------------------------------
# Analysis runner
# ---------------------------------------------------------------------------

def run_ai_land_analysis(land_id: int, db: Session, user_id: Optional[int] = None) -> list[LandAiInsight]:
    """
    Main entry point: fetch land context, send to Groq, store insights.
    Returns list of created LandAiInsight rows.

    If user_id is None, uses the land's owner user_id.
    """
    # Resolve user_id
    if user_id is None:
        land = db.query(Land).filter(Land.land_id == land_id).first()
        if land:
            user_id = land.user_id
    if not user_id:
        logger.warning("No user_id for AI analysis of land_id=%s — skipping", land_id)
        return []

    context = _build_land_context(land_id, db)
    if not context:
        logger.warning("Empty context for land_id=%s — skipping AI analysis", land_id)
        return []

    client = GroqClient(db, user_id)

    insights_created = []

    # ---- Single Combined Prompt to Save API Quota ----
    # Note: We intentionally do not attach raw base64 satellite images to Groq anymore,
    # as 2000x2000 STAC arrays consume massive amounts of tokens. The AI relies on the numerical metrics.
    images_payload = []
    
    combined_prompt = f"""You are analyzing a farm. Return ONLY valid JSON with 4 distinct insights.
    
Format:
{{
  "crop_analysis": {{
    "title": "short headline max 10 words",
    "summary": "2-3 sentence expert analysis of crop health",
    "ndvi_assessment": "excellent|good|fair|poor|critical",
    "key_observations": ["obs 1"],
    "recommended_action": "specific action",
    "risk_flags": ["risk 1"],
    "confidence": 0.0
  }},
  "irrigation_advice": {{
    "title": "short headline",
    "summary": "2-3 sentence irrigation assessment",
    "irrigation_status": "adequate|needed_soon|overdue|excessive",
    "recommended_water_mm": 0.0,
    "next_irrigation_days": 0,
    "key_observations": ["obs 1"],
    "confidence": 0.0
  }},
  "harvest_timing": {{
    "title": "short headline",
    "summary": "harvest timing analysis for all crops",
    "key_observations": ["obs 1"],
    "recommended_action": "e.g. Harvest Alfalfa now",
    "confidence": 0.0
  }},
  "vision_analysis": {{
    "title": "short headline",
    "summary": "multimodal analysis comparing spectral indices and images (if provided)",
    "spectral_assessment": "excellent|good|fair|poor|critical",
    "key_observations": ["obs 1"],
    "recommended_action": "action",
    "risk_flags": [],
    "confidence": 0.0
  }}
}}

Farm data context:
{json.dumps(context, indent=2)}"""

    combined_insight = _request_insight(
        client=client,
        land_id=land_id,
        db=db,
        insight_type="combined",
        title_fallback="AI Analysis",
        prompt=combined_prompt,
        images=images_payload if images_payload else None
    )

    if combined_insight and combined_insight.structured_data:
        # Delete previous auto-generated insights for this land to keep them fresh
        db.query(LandAiInsight).filter(LandAiInsight.land_id == land_id).delete()
        db.flush()
        
        # The _request_insight helper saved the combined insight into the DB. 
        # But we actually want to split it into 4 rows and delete the combined one.
        db.delete(combined_insight)
        db.flush()
        
        data = combined_insight.structured_data
        
        for key, insight_type in [
            ("crop_analysis", "crop_analysis"), 
            ("irrigation_advice", "irrigation_advice"), 
            ("harvest_timing", "harvest_timing"), 
            ("vision_analysis", "vision_analysis")
        ]:
            if key in data and data[key]:
                section = data[key]
                new_insight = LandAiInsight(
                    land_id=land_id,
                    insight_type=insight_type,
                    title=section.get("title", f"AI {insight_type.replace('_', ' ').title()}"),
                    body=section.get("summary", ""),
                    structured_data=section,
                    confidence=section.get("confidence"),
                    model_used=combined_insight.model_used,
                )
                db.add(new_insight)
                insights_created.append(new_insight)

    db.commit()
    logger.info("AI analysis complete for land_id=%s — %d insights created", land_id, len(insights_created))
    return insights_created


def _request_insight(
    client: GroqClient,
    land_id: int,
    db: Session,
    insight_type: str,
    title_fallback: str,
    prompt: str,
    images: Optional[list[dict]] = None
) -> Optional[LandAiInsight]:
    """Send one insight prompt to Groq and store the result."""
    
    if images:
        content_array = [{"type": "text", "text": prompt}]
        for img in images:
            content_array.append(img)
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT_PERSONA + SYSTEM_PROMPT_JSON},
            {"role": "user", "content": content_array},
        ]
    else:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT_PERSONA + SYSTEM_PROMPT_JSON},
            {"role": "user", "content": prompt},
        ]
        
    response = client.chat(messages, max_tokens=2048, temperature=0.2)
    if not response:
        return None

    try:
        raw_content = response["choices"][0]["message"]["content"]
        model_used = response.get("model", "llama-3.3-70b-versatile")
        tokens = response.get("usage", {}).get("total_tokens")

        # Parse JSON from Groq's response (clean markdown if present)
        import re
        cleaned_content = re.sub(r"```(?:json)?|```", "", raw_content).strip()
        
        structured = None
        body = raw_content
        try:
            structured = json.loads(cleaned_content)
            title = structured.get("title", title_fallback)
            body = structured.get("summary", raw_content)
            confidence = structured.get("confidence")
        except json.JSONDecodeError:
            title = title_fallback
            confidence = None

        insight = LandAiInsight(
            land_id=land_id,
            insight_type=insight_type,
            title=title,
            body=body,
            structured_data=structured,
            confidence=confidence,
            model_used=model_used,
        )
        db.add(insight)
        db.flush()
        return insight

    except (KeyError, IndexError) as exc:
        logger.warning("Failed to parse Groq response for insight_type=%s: %s", insight_type, exc)
        return None


# ---------------------------------------------------------------------------
# Chat helper — builds context-aware chat messages
# ---------------------------------------------------------------------------

def build_chat_system_message(land_id: int, db: Session) -> str:
    """Build a system message with current farm context for the chat interface."""
    context = _build_land_context(land_id, db)
    context_json = json.dumps(context, indent=2)

    # Keep context under ~4000 chars to avoid huge token costs
    if len(context_json) > 4000:
        # Truncate older history, keep most recent
        if "spectral_history" in context:
            context["spectral_history"] = context["spectral_history"][-10:]
        if "recent_climate" in context:
            context["recent_climate"] = context["recent_climate"][-10:]
        if "recent_soil" in context:
            context["recent_soil"] = context["recent_soil"][-5:]
        context_json = json.dumps(context, indent=2)

    return f"""{SYSTEM_PROMPT_PERSONA}

You are in a live chat interface directly with the farmer. Respond naturally in conversational markdown (NOT JSON).
Location: {context.get('land', {}).get('latitude')}°N, {context.get('land', {}).get('longitude')}°E
Area: {context.get('land', {}).get('area_hectares')} hectares

Live Farm Data Context:
{context_json}

Answer the farmer's questions based on this specific farm data. Be concise, practical, and use the real numbers from the data.
If you notice something critical in the data, proactively flag it."""
