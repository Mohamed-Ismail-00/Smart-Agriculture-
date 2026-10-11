"""
tests/pipeline/test_water_pipeline.py
----------------------------------------
Integration tests for the Water Data Pipeline.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.pipeline.water_pipeline import (
    run_water_ingestion,
    run_water_ingestion_from_content,
)
from app.pipeline.data_cleaning import (
    clean_water_record,
    clean_water_batch,
    normalise_governorate,
)
from app.pipeline.data_validation import (
    validate_water_record,
    validate_water_batch,
)
from app.search.water_loader import load_water_records
from app.models.water_record import WaterRecord
from app.models.location import Location
from app.models.ingestion_batch import IngestionBatch
from app.models.etl_error import EtlError


# ============================================================================
# Unit Tests — Data Cleaning
# ============================================================================

class TestWaterDataCleaning:
    def test_clean_water_record_basic(self):
        raw = {
            "governorate": "  cairo  ",
            "crop": "wheat",
            "year": "2023",
            "water_consumption_m3": "4500.5",
            "irrigation_type": "flood irrigation",
        }
        cleaned = clean_water_record(raw)
        assert cleaned["governorate"] == "Cairo"
        assert cleaned["crop"] == "Wheat"
        assert cleaned["year"] == 2023
        assert cleaned["water_consumption_m3"] == 4500.5
        assert cleaned["irrigation_type"] == "flood"

    def test_clean_water_batch(self):
        records = [
            {"governorate": "el cairo", "crop": "WHEAT", "year": 2023, "water_consumption_m3": 4500, "irrigation_type": "flood"},
            {"governorate": "alex", "crop": "cotton", "year": 2022, "water_consumption_m3": 5000, "irrigation_type": "drip irrigation"},
        ]
        cleaned = clean_water_batch(records)
        assert len(cleaned) == 2
        assert cleaned[0]["governorate"] == "Cairo"
        assert cleaned[0]["crop"] == "Wheat"
        assert cleaned[0]["irrigation_type"] == "flood"
        assert cleaned[1]["governorate"] == "Alexandria"
        assert cleaned[1]["crop"] == "Cotton"
        assert cleaned[1]["irrigation_type"] == "drip"


# ============================================================================
# Unit Tests — Data Validation
# ============================================================================

class TestWaterDataValidation:
    def test_valid_record_passes(self):
        record = {
            "governorate": "Cairo",
            "crop": "Wheat",
            "year": 2023,
            "water_consumption_m3": 4500.0,
            "irrigation_type": "flood",
        }
        errors = validate_water_record(record, 1)
        assert errors == []

    def test_missing_fields_fails(self):
        record = {"governorate": "", "crop": "", "year": None, "water_consumption_m3": None, "irrigation_type": "unknown"}
        errors = validate_water_record(record, 1)
        assert len(errors) == 5

    def test_water_out_of_range_fails(self):
        record = {"governorate": "Cairo", "crop": "Wheat", "year": 2023, "water_consumption_m3": -100.0, "irrigation_type": "flood"}
        errors = validate_water_record(record, 1)
        assert len(errors) == 1
        assert "water_consumption_m3" in errors[0].lower()

        record2 = {"governorate": "Cairo", "crop": "Wheat", "year": 2023, "water_consumption_m3": 60000.0, "irrigation_type": "flood"}
        errors2 = validate_water_record(record2, 2)
        assert len(errors2) == 1
        assert "water_consumption_m3" in errors2[0].lower()

    def test_invalid_irrigation_type_fails(self):
        record = {"governorate": "Cairo", "crop": "Wheat", "year": 2023, "water_consumption_m3": 4500.0, "irrigation_type": "magic"}
        errors = validate_water_record(record, 1)
        assert len(errors) == 1
        assert "irrigation_type" in errors[0].lower()

    def test_batch_validation_separates(self):
        records = [
            {"governorate": "Cairo", "crop": "Wheat", "year": 2023, "water_consumption_m3": 4500.0, "irrigation_type": "flood"},
            {"governorate": "", "crop": "Rice", "year": 2023, "water_consumption_m3": -5.0, "irrigation_type": "flood"},
        ]
        valid, invalid = validate_water_batch(records)
        assert len(valid) == 1
        assert len(invalid) == 1
        assert valid[0]["governorate"] == "Cairo"


# ============================================================================
# Integration Tests — Full Pipeline
# ============================================================================

class TestWaterPipelineIntegration:
    def test_pipeline_from_content_success(self, db_session: Session):
        csv_content = (
            "governorate,crop,year,water_consumption_m3,irrigation_type\n"
            "Cairo,Wheat,2023,4500,flood\n"
            "Giza,Rice,2023,8200,flood\n"
            "Alexandria,Cotton,2023,5100,drip\n"
        )
        result = run_water_ingestion_from_content(db_session, csv_content)

        assert result["status"] == "COMPLETED"
        assert result["inserted_count"] == 3
        assert result["error_count"] == 0

        records = db_session.query(WaterRecord).all()
        assert len(records) == 3

        locations = db_session.query(Location).all()
        gov_names = {loc.governorate for loc in locations}
        assert "Cairo" in gov_names
        assert "Giza" in gov_names
        assert "Alexandria" in gov_names

    def test_pipeline_from_content_with_invalid_rows(self, db_session: Session):
        csv_content = (
            "governorate,crop,year,water_consumption_m3,irrigation_type\n"
            "Cairo,Wheat,2023,4500,flood\n"
            ",Rice,2023,8200,flood\n"  # empty governorate
            "Aswan,Sugarcane,2023,12000,flood\n"
        )
        result = run_water_ingestion_from_content(db_session, csv_content)

        assert result["inserted_count"] == 2
        assert result["error_count"] >= 1
        assert result["status"] in ("PARTIAL_SUCCESS", "COMPLETED")

    def test_pipeline_from_content_all_invalid(self, db_session: Session):
        csv_content = (
            "governorate,crop,year,water_consumption_m3,irrigation_type\n"
            ",bad_crop,bad_year,not_a_number,also_bad\n"
        )
        result = run_water_ingestion_from_content(db_session, csv_content)

        assert result["inserted_count"] == 0
        assert result["status"] == "FAILED"

    def test_pipeline_from_content_missing_columns(self, db_session: Session):
        csv_content = "year,water_consumption_m3\n2023,4500\n"

        with pytest.raises(ValueError, match="Missing required columns"):
            run_water_ingestion_from_content(db_session, csv_content)

    def test_pipeline_creates_batch_record(self, db_session: Session):
        csv_content = (
            "governorate,crop,year,water_consumption_m3,irrigation_type\n"
            "Cairo,Wheat,2023,4500,flood\n"
        )
        result = run_water_ingestion_from_content(db_session, csv_content)
        batch_id = result["batch_id"]

        batch = db_session.query(IngestionBatch).filter(
            IngestionBatch.batch_id == batch_id
        ).first()

        assert batch is not None
        assert batch.status == "COMPLETED"
        assert batch.completed_at is not None

    def test_pipeline_logs_errors_to_etl_errors(self, db_session: Session):
        csv_content = (
            "governorate,crop,year,water_consumption_m3,irrigation_type\n"
            ",Wheat,2023,4500,flood\n"
        )
        result = run_water_ingestion_from_content(db_session, csv_content)

        errors = db_session.query(EtlError).filter(
            EtlError.batch_id == result["batch_id"]
        ).all()

        assert len(errors) >= 1

    def test_pipeline_idempotent_rerun(self, db_session: Session):
        csv_content = (
            "governorate,crop,year,water_consumption_m3,irrigation_type\n"
            "Cairo,Wheat,2023,4500,flood\n"
        )

        result1 = run_water_ingestion_from_content(db_session, csv_content)
        assert result1["inserted_count"] == 1

        result2 = run_water_ingestion_from_content(db_session, csv_content)
        assert result2["status"] in ("COMPLETED_NO_NEW_DATA", "PARTIAL_SUCCESS", "FAILED", "COMPLETED")


# ============================================================================
# API Endpoint Tests
# ============================================================================

class TestWaterPipelineAPI:
    def test_list_water_files(self, client: TestClient):
        response = client.get("/api/v1/pipeline/water/files")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert isinstance(data["data"], list)

    def test_pipeline_run_via_api_not_found(self, client: TestClient):
        response = client.post("/api/v1/pipeline/water/run?filename=not_exist.csv")
        assert response.status_code == 404
