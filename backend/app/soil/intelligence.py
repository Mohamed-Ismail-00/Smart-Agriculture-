"""
soil/intelligence.py
--------------------
Pure Python soil intelligence engine.

No external dependencies. Uses FAO/USDA-based thresholds to:
  - Classify soil health from individual properties
  - Score suitability (0-100) for specific crops
  - Generate actionable advice per property

All thresholds are sourced from:
  - FAO Soil Quality Indicators (2022)
  - USDA Natural Resources Conservation Service
  - Egyptian Ministry of Agriculture crop guides
"""

from __future__ import annotations

from typing import Any, Optional


# ---------------------------------------------------------------------------
# FAO-based thresholds for top-soil properties
# ---------------------------------------------------------------------------

# pH optimal ranges per agricultural context
_PH_CLASSES = [
    (4.5, "extremely_acidic"),
    (5.0, "very_strongly_acidic"),
    (5.5, "strongly_acidic"),
    (6.0, "moderately_acidic"),
    (6.5, "slightly_acidic"),
    (7.0, "neutral"),
    (7.5, "slightly_alkaline"),
    (8.0, "moderately_alkaline"),
    (8.5, "strongly_alkaline"),
    (9.0, "very_strongly_alkaline"),
    (float("inf"), "extremely_alkaline"),
]

# Soil Organic Carbon (g/kg) quality thresholds
_SOC_CLASSES = [
    (3.0,  "very_low"),
    (10.0, "low"),
    (20.0, "medium"),
    (35.0, "high"),
    (float("inf"), "very_high"),
]

# Per-crop soil suitability thresholds
# Each entry: (crop_name, {property: (min_ok, max_ok, min_ideal, max_ideal)})
_CROP_THRESHOLDS: dict[str, dict[str, tuple]] = {
    "wheat": {
        "ph_h2o":   (5.5, 8.5, 6.0, 7.5),
        "clay_pct": (10,  50,  20,  35),
        "soc_g_per_kg": (5, 100, 12, 40),
        "nitrogen_g_per_kg": (0.5, 10, 1.5, 5.0),
    },
    "corn": {
        "ph_h2o":   (5.5, 7.5, 6.0, 7.0),
        "clay_pct": (10,  45,  15,  30),
        "soc_g_per_kg": (8, 100, 15, 45),
        "nitrogen_g_per_kg": (1.0, 10, 2.0, 6.0),
    },
    "rice": {
        "ph_h2o":   (5.0, 8.0, 5.5, 7.0),
        "clay_pct": (20,  80,  30,  60),
        "soc_g_per_kg": (5, 100, 12, 35),
        "nitrogen_g_per_kg": (0.8, 10, 1.5, 4.0),
    },
    "cotton": {
        "ph_h2o":   (5.8, 8.0, 6.5, 7.5),
        "clay_pct": (15,  55,  20,  40),
        "soc_g_per_kg": (5, 100, 10, 30),
        "nitrogen_g_per_kg": (0.5, 8, 1.0, 4.0),
    },
    "tomato": {
        "ph_h2o":   (5.5, 7.5, 6.0, 7.0),
        "clay_pct": (10,  40,  15,  30),
        "soc_g_per_kg": (8, 100, 15, 40),
        "nitrogen_g_per_kg": (1.0, 10, 2.0, 5.0),
    },
    "sugarcane": {
        "ph_h2o":   (5.0, 8.5, 6.0, 7.5),
        "clay_pct": (15,  60,  25,  45),
        "soc_g_per_kg": (6, 100, 12, 35),
        "nitrogen_g_per_kg": (0.8, 10, 1.5, 4.5),
    },
}

_ALL_CROPS = list(_CROP_THRESHOLDS.keys())


# ---------------------------------------------------------------------------
# Property classification
# ---------------------------------------------------------------------------

def classify_ph(ph: float) -> str:
    """Return FAO pH class label."""
    for threshold, label in _PH_CLASSES:
        if ph <= threshold:
            return label
    return "extremely_alkaline"


def classify_soc(soc: float) -> str:
    """Return SOC quality class."""
    for threshold, label in _SOC_CLASSES:
        if soc < threshold:
            return label
    return "very_high"


def classify_texture(clay_pct: Optional[float], sand_pct: Optional[float]) -> str:
    """Return USDA texture class name."""
    if clay_pct is None or sand_pct is None:
        return "unknown"
    silt = max(0.0, 100.0 - clay_pct - sand_pct)
    if clay_pct >= 40:
        return "clay"
    elif clay_pct >= 27 and sand_pct < 45:
        return "clay_loam"
    elif clay_pct >= 20 and silt >= 50:
        return "silty_clay_loam"
    elif sand_pct >= 70 and clay_pct < 15:
        return "sandy_loam"
    elif silt >= 50:
        return "silt_loam"
    else:
        return "loam"


# ---------------------------------------------------------------------------
# Per-property scoring (0-100)
# ---------------------------------------------------------------------------

def _score_property(value: float, min_ok: float, max_ok: float,
                    min_ideal: float, max_ideal: float) -> float:
    """
    Score a soil property on a 0-100 scale using a trapezoidal function:
      - Outside [min_ok, max_ok]   → 0 (marginal/unsuitable)
      - Inside  [min_ideal, max_ideal] → 100 (optimal)
      - Transition zones           → linearly interpolated
    """
    if value < min_ok or value > max_ok:
        return 0.0     # unsuitable

    if min_ideal <= value <= max_ideal:
        return 100.0     # optimal

    # Rising edge: min_ok → min_ideal
    if value < min_ideal:
        t = (value - min_ok) / max(min_ideal - min_ok, 1e-9)
        return t * 100.0

    # Falling edge: max_ideal → max_ok
    t = (max_ok - value) / max(max_ok - max_ideal, 1e-9)
    return t * 100.0


# ---------------------------------------------------------------------------
# Crop suitability scoring
# ---------------------------------------------------------------------------

def score_crop_suitability(
    crop: str,
    ph: Optional[float],
    clay_pct: Optional[float],
    soc: Optional[float],
    nitrogen: Optional[float],
) -> float:
    """
    Score overall suitability for a specific crop (0-100).

    Uses geometric mean of per-property scores so a single
    critical deficiency limits the overall score (Liebig's law of minimum).
    """
    crop_key = crop.lower()
    thresholds = _CROP_THRESHOLDS.get(crop_key)
    if not thresholds:
        return 50.0     # unknown crop — neutral

    values = {
        "ph_h2o": ph,
        "clay_pct": clay_pct,
        "soc_g_per_kg": soc,
        "nitrogen_g_per_kg": nitrogen,
    }

    scores: list[float] = []
    for prop, bounds in thresholds.items():
        val = values.get(prop)
        if val is None:
            continue    # skip missing — don't penalize
        scores.append(_score_property(val, *bounds))

    if not scores:
        return 50.0

    # Geometric mean — penalises any single bad property strongly
    product = 1.0
    for s in scores:
        product *= s
    return round(product ** (1.0 / len(scores)), 2)


def score_all_crops(
    ph: Optional[float],
    clay_pct: Optional[float],
    soc: Optional[float],
    nitrogen: Optional[float],
) -> dict[str, float]:
    """Score all known crops and return {crop_name: score} dict."""
    return {crop: score_crop_suitability(crop, ph, clay_pct, soc, nitrogen)
            for crop in _ALL_CROPS}


def best_crops(scores: dict[str, float], top_n: int = 3) -> list[dict]:
    """Return the top N crops sorted by suitability score."""
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_n]
    return [{"crop": c, "score": s, "suitability": _score_label(s)} for c, s in ranked]


def _score_label(score: float) -> str:
    if score >= 80:
        return "highly_suitable"
    elif score >= 60:
        return "suitable"
    elif score >= 40:
        return "marginally_suitable"
    elif score >= 20:
        return "marginally_unsuitable"
    else:
        return "unsuitable"


# ---------------------------------------------------------------------------
# Advice generation
# ---------------------------------------------------------------------------

def generate_soil_advice(
    ph: Optional[float],
    soc: Optional[float],
    clay_pct: Optional[float],
    nitrogen: Optional[float],
    texture: Optional[str],
) -> list[str]:
    """
    Generate a list of actionable farming recommendations based on
    soil property values.
    """
    advice: list[str] = []
    has_deficiency = False

    if ph is not None:
        if ph < 5.5:
            advice.append("pH is too acidic. Apply agricultural lime (2-4 t/ha) to raise pH above 6.0.")
            has_deficiency = True
        elif ph > 8.0:
            advice.append("pH is alkaline. Consider gypsum or sulfur amendments to lower pH for sensitive crops.")
            has_deficiency = True

    if soc is not None:
        if soc < 5.0:
            advice.append("Organic carbon is very low. Add compost (10-15 t/ha/yr) or incorporate crop residues.")
            has_deficiency = True
        elif soc < 12.0:
            advice.append("Organic carbon is below optimal. Green manure or organic mulch will improve soil health.")
            has_deficiency = True

    if nitrogen is not None:
        if nitrogen < 1.0:
            advice.append("Nitrogen is very low. Apply basal nitrogen fertilizer and consider legume rotation.")
            has_deficiency = True
        elif nitrogen < 1.5:
            advice.append("Nitrogen is low. Supplement with urea or ammonium nitrate at crop establishment.")
            has_deficiency = True

    if clay_pct is not None:
        if clay_pct > 50:
            advice.append("High clay content may cause waterlogging. Ensure adequate drainage and consider raised beds.")
            has_deficiency = True
        elif clay_pct < 10:
            advice.append("Sandy soil has low water retention. Increase irrigation frequency and add organic matter.")
            has_deficiency = True

    if texture in ("clay", "sandy_loam"):
        if texture == "clay":
            advice.append("Heavy clay soil: use deep tillage and avoid working when wet to prevent compaction.")
            has_deficiency = True
        else:
            advice.append("Sandy loam soil drains well but needs more frequent irrigation and fertilization.")
            has_deficiency = True

    if not has_deficiency:
        advice.append("Soil properties are within acceptable ranges. Maintain current management practices.")

    return advice
