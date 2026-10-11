"""
Tests for soil/intelligence.py — pure math, no DB, no HTTP.
"""

import pytest
from app.soil.intelligence import (
    best_crops,
    classify_ph,
    classify_soc,
    classify_texture,
    generate_soil_advice,
    score_all_crops,
    score_crop_suitability,
)


class TestClassifyPH:
    @pytest.mark.parametrize("ph,expected", [
        (4.0, "extremely_acidic"),
        (5.2, "strongly_acidic"),
        (6.2, "slightly_acidic"),
        (7.0, "neutral"),
        (7.4, "slightly_alkaline"),
        (8.2, "strongly_alkaline"),
    ])
    def test_ph_classification(self, ph, expected):
        assert classify_ph(ph) == expected


class TestClassifySOC:
    @pytest.mark.parametrize("soc,expected", [
        (1.0,  "very_low"),
        (5.0,  "low"),
        (15.0, "medium"),
        (30.0, "high"),
        (50.0, "very_high"),
    ])
    def test_soc_classification(self, soc, expected):
        assert classify_soc(soc) == expected


class TestClassifyTexture:
    @pytest.mark.parametrize("clay,sand,expected", [
        (50,  20,  "clay"),
        (30,  30,  "clay_loam"),
        (25,  20,  "silty_clay_loam"),
        (10,  75,  "sandy_loam"),
        (15,  30,  "silt_loam"),
        (20,  45,  "loam"),
        (None, None, "unknown"),
    ])
    def test_texture_class(self, clay, sand, expected):
        assert classify_texture(clay, sand) == expected


class TestScoreCropSuitability:
    def test_optimal_wheat_gets_high_score(self):
        """pH=6.5, clay=25%, SOC=20, N=2.0 → all in ideal range for wheat"""
        score = score_crop_suitability("wheat", ph=6.5, clay_pct=25, soc=20, nitrogen=2.0)
        assert score > 80

    def test_unsuitable_acidic_soil_for_wheat(self):
        """pH=4.5 → far outside wheat range, should get low score"""
        score = score_crop_suitability("wheat", ph=4.5, clay_pct=25, soc=15, nitrogen=2.0)
        assert score < 30

    def test_rice_tolerates_higher_clay(self):
        """Rice is tolerant of high clay — should score well at 40% clay"""
        score_rice = score_crop_suitability("rice", ph=6.5, clay_pct=40, soc=15, nitrogen=1.5)
        score_wheat = score_crop_suitability("wheat", ph=6.5, clay_pct=40, soc=15, nitrogen=1.5)
        assert score_rice >= score_wheat

    def test_unknown_crop_returns_neutral(self):
        score = score_crop_suitability("banana", ph=7.0, clay_pct=25, soc=15, nitrogen=2.0)
        assert score == 50.0

    def test_none_values_dont_crash(self):
        score = score_crop_suitability("wheat", ph=None, clay_pct=None, soc=None, nitrogen=None)
        assert score == 50.0   # no valid properties → neutral


class TestScoreAllCrops:
    def test_returns_all_crops(self):
        scores = score_all_crops(ph=7.0, clay_pct=25, soc=15, nitrogen=2.0)
        assert len(scores) == 6
        assert "wheat" in scores
        assert "rice" in scores
        assert "cotton" in scores

    def test_all_scores_in_range(self):
        scores = score_all_crops(ph=7.0, clay_pct=25, soc=15, nitrogen=2.0)
        for crop, score in scores.items():
            assert 0 <= score <= 100, f"{crop} score {score} out of range"


class TestBestCrops:
    def test_returns_top_n(self):
        scores = {"wheat": 85, "rice": 60, "corn": 70, "cotton": 40, "tomato": 55, "sugarcane": 75}
        top3 = best_crops(scores, top_n=3)
        assert len(top3) == 3
        # Should be wheat, sugarcane, corn in that order
        assert top3[0]["crop"] == "wheat"
        assert top3[0]["score"] == 85

    def test_suitability_label_present(self):
        scores = {"wheat": 85, "rice": 30, "corn": 50}
        result = best_crops(scores, top_n=3)
        labels = {r["crop"]: r["suitability"] for r in result}
        assert labels["wheat"] == "highly_suitable"
        assert labels["rice"] == "marginally_unsuitable"


class TestGenerateSoilAdvice:
    def test_advice_for_acidic_soil(self):
        advice = generate_soil_advice(ph=4.8, soc=15, clay_pct=25, nitrogen=2.0, texture="loam")
        assert any("acidic" in a.lower() or "lime" in a.lower() for a in advice)

    def test_advice_for_alkaline_soil(self):
        advice = generate_soil_advice(ph=8.5, soc=15, clay_pct=25, nitrogen=2.0, texture="loam")
        assert any("alkaline" in a.lower() or "gypsum" in a.lower() for a in advice)

    def test_advice_for_low_soc(self):
        advice = generate_soil_advice(ph=7.0, soc=2.0, clay_pct=25, nitrogen=2.0, texture="loam")
        assert any("organic" in a.lower() or "compost" in a.lower() for a in advice)

    def test_advice_for_low_nitrogen(self):
        advice = generate_soil_advice(ph=7.0, soc=15, clay_pct=25, nitrogen=0.5, texture="loam")
        assert any("nitrogen" in a.lower() for a in advice)

    def test_good_soil_gets_positive_advice(self):
        advice = generate_soil_advice(ph=6.8, soc=20, clay_pct=25, nitrogen=2.5, texture="loam")
        assert any("acceptable" in a.lower() or "maintain" in a.lower() for a in advice)

    def test_none_values_dont_crash(self):
        advice = generate_soil_advice(None, None, None, None, None)
        assert isinstance(advice, list)
        assert len(advice) >= 1
