"""
tests/pipeline/test_climate_pipeline.py
----------------------------------------
Integration tests for the Climate Data Pipeline.

Tests the full pipeline flow:
    Source CSV → Parse → Clean → Validate → Store → Track

Uses the same SQLite test database as the rest of the test suite.
"""

import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.pipeline.climate_pipeline import (
    run_climate_ingestion,
    run_climate_ingestion_from_content,
)
from app.pipeline.data_cleaning import (
    clean_climate_record,
    clean_climate_batch,
    normalise_governorate,
)
from app.pipeline.data_validation import (
    validate_climate_record,
    validate_climate_batch,
)
from app.search.climate_loader import load_climate_records
from app.models.climate_record import ClimateRecord
from app.models.location import Location
from app.models.ingestion_batch import IngestionBatch
from app.models.etl_error import EtlError


# ============================================================================
# Unit Tests — Data Cleaning
# ============================================================================

class TestDataCleaning:
    """Tests for pipeline/data_cleaning.py"""

    def test_normalise_governorate_exact_match(self):
        assert normalise_governorate("Cairo") == "Cairo"

    def test_normalise_governorate_alias(self):
        assert normalise_governorate("el cairo") == "Cairo"
        assert normalise_governorate("al qahira") == "Cairo"
        assert normalise_governorate("alex") == "Alexandria"

    def test_normalise_governorate_whitespace(self):
        assert normalise_governorate("  Cairo  ") == "Cairo"
        assert normalise_governorate("  giza  ") == "Giza"

    def test_normalise_governorate_unknown_titlecased(self):
        assert normalise_governorate("some new place") == "Some New Place"

    def test_clean_climate_record_basic(self):
        raw = {
            "governorate": "  cairo  ",
            "year": "2023",
            "temperature_mean": "26.5",
            "humidity_pct": "55.0",
        }
        cleaned = clean_climate_record(raw)
        assert cleaned["governorate"] == "Cairo"
        assert cleaned["year"] == 2023
        assert cleaned["temperature_mean"] == 26.5
        assert cleaned["humidity_pct"] == 55.0

    def test_clean_climate_batch(self):
        records = [
            {"governorate": "el cairo", "year": 2023, "temperature_mean": 26.5, "humidity_pct": 55.0},
            {"governorate": "alex", "year": 2022, "temperature_mean": 20.5, "humidity_pct": 65.4},
        ]
        cleaned = clean_climate_batch(records)
        assert len(cleaned) == 2
        assert cleaned[0]["governorate"] == "Cairo"
        assert cleaned[1]["governorate"] == "Alexandria"


# ============================================================================
# Unit Tests — Data Validation
# ============================================================================

class TestDataValidation:
    """Tests for pipeline/data_validation.py"""

    def test_valid_record_passes(self):
        record = {
            "governorate": "Cairo",
            "year": 2023,
            "temperature_mean": 26.5,
            "humidity_pct": 55.0,
        }
        errors = validate_climate_record(record, 1)
        assert errors == []

    def test_missing_governorate_fails(self):
        record = {"governorate": "", "year": 2023, "temperature_mean": 26.5, "humidity_pct": 55.0}
        errors = validate_climate_record(record, 1)
        assert len(errors) == 1
        assert "governorate" in errors[0].lower()

    def test_year_out_of_range_fails(self):
        record = {"governorate": "Cairo", "year": 3000, "temperature_mean": 26.5, "humidity_pct": 55.0}
        errors = validate_climate_record(record, 1)
        assert len(errors) == 1
        assert "year" in errors[0].lower()

    def test_negative_humidity_fails(self):
        record = {"governorate": "Cairo", "year": 2023, "temperature_mean": 26.5, "humidity_pct": -5.0}
        errors = validate_climate_record(record, 1)
        assert len(errors) == 1
        assert "humidity" in errors[0].lower()

    def test_extreme_temperature_fails(self):
        record = {"governorate": "Cairo", "year": 2023, "temperature_mean": 70.0, "humidity_pct": 55.0}
        errors = validate_climate_record(record, 1)
        assert len(errors) == 1
        assert "temperature" in errors[0].lower()

    def test_missing_fields_multiple_errors(self):
        record = {"governorate": "", "year": None, "temperature_mean": None, "humidity_pct": None}
        errors = validate_climate_record(record, 1)
        assert len(errors) == 4

    def test_batch_validation_separates(self):
        records = [
            {"governorate": "Cairo", "year": 2023, "temperature_mean": 26.5, "humidity_pct": 55.0},
            {"governorate": "", "year": 3000, "temperature_mean": 70.0, "humidity_pct": -5.0},
        ]
        valid, invalid = validate_climate_batch(records)
        assert len(valid) == 1
        assert len(invalid) == 1
        assert valid[0]["governorate"] == "Cairo"


# ============================================================================
# Integration Tests — Full Pipeline (using test DB)
# ============================================================================

class TestClimatePipelineIntegration:
    """Integration tests for the full pipeline flow using test SQLite DB."""

    # ---------- run_climate_ingestion_from_content ----------

    def test_pipeline_from_content_success(self, db_session: Session):
        """Full pipeline: parse → clean → validate → store from raw CSV content."""
        csv_content = (
            "governorate,year,temperature_mean,humidity_pct\n"
            "Cairo,2023,26.5,55.0\n"
            "Giza,2023,25.8,52.0\n"
            "Alexandria,2022,20.5,65.4\n"
        )
        result = run_climate_ingestion_from_content(db_session, csv_content)

        assert result["status"] == "COMPLETED"
        assert result["inserted_count"] == 3
        assert result["error_count"] == 0

        # Verify records are actually in the database
        records = db_session.query(ClimateRecord).all()
        assert len(records) == 3

        # Verify locations were created
        locations = db_session.query(Location).all()
        gov_names = {loc.governorate for loc in locations}
        assert "Cairo" in gov_names
        assert "Giza" in gov_names
        assert "Alexandria" in gov_names

    def test_pipeline_from_content_with_invalid_rows(self, db_session: Session):
        """Pipeline correctly handles mixed valid/invalid records."""
        csv_content = (
            "governorate,year,temperature_mean,humidity_pct\n"
            "Cairo,2023,26.5,55.0\n"
            ",2023,25.8,52.0\n"  # empty governorate — parse error
            "Aswan,2023,27.9,22.8\n"
        )
        result = run_climate_ingestion_from_content(db_session, csv_content)

        assert result["inserted_count"] == 2
        assert result["error_count"] >= 1
        assert result["status"] in ("PARTIAL_SUCCESS", "COMPLETED")

    def test_pipeline_from_content_all_invalid(self, db_session: Session):
        """Pipeline marks FAILED when no records can be inserted."""
        csv_content = (
            "governorate,year,temperature_mean,humidity_pct\n"
            ",bad_year,not_a_number,also_bad\n"
        )
        result = run_climate_ingestion_from_content(db_session, csv_content)

        assert result["inserted_count"] == 0
        assert result["status"] == "FAILED"

    def test_pipeline_from_content_missing_columns(self, db_session: Session):
        """Pipeline raises ValueError when CSV is missing required columns."""
        csv_content = "year,temperature_mean\n2023,26.5\n"

        with pytest.raises(ValueError, match="Missing required columns"):
            run_climate_ingestion_from_content(db_session, csv_content)

    def test_pipeline_creates_batch_record(self, db_session: Session):
        """Pipeline creates and updates an ingestion batch record."""
        csv_content = (
            "governorate,year,temperature_mean,humidity_pct\n"
            "Cairo,2023,26.5,55.0\n"
        )
        result = run_climate_ingestion_from_content(db_session, csv_content)
        batch_id = result["batch_id"]

        batch = db_session.query(IngestionBatch).filter(
            IngestionBatch.batch_id == batch_id
        ).first()

        assert batch is not None
        assert batch.status == "COMPLETED"
        assert batch.completed_at is not None

    def test_pipeline_logs_errors_to_etl_errors(self, db_session: Session):
        """Pipeline logs parse errors into the etl_errors table."""
        csv_content = (
            "governorate,year,temperature_mean,humidity_pct\n"
            ",2023,26.5,55.0\n"  # empty governorate
        )
        result = run_climate_ingestion_from_content(db_session, csv_content)

        errors = db_session.query(EtlError).filter(
            EtlError.batch_id == result["batch_id"]
        ).all()

        assert len(errors) >= 1

    def test_pipeline_idempotent_rerun(self, db_session: Session):
        """Running the pipeline twice with same data should handle duplicates."""
        csv_content = (
            "governorate,year,temperature_mean,humidity_pct\n"
            "Cairo,2023,26.5,55.0\n"
        )

        # First run
        result1 = run_climate_ingestion_from_content(db_session, csv_content)
        assert result1["inserted_count"] == 1

        # Second run — should handle the duplicate gracefully
        result2 = run_climate_ingestion_from_content(db_session, csv_content)
        # Either it skips or errors, but should not crash
        assert result2["status"] in ("COMPLETED_NO_NEW_DATA", "PARTIAL_SUCCESS", "FAILED", "COMPLETED")

    def test_pipeline_governorate_cleaning_applied(self, db_session: Session):
        """Pipeline applies governorate name normalisation before storage."""
        csv_content = (
            "governorate,year,temperature_mean,humidity_pct\n"
            "el cairo,2023,26.5,55.0\n"
            "alex,2022,20.5,65.4\n"
        )
        result = run_climate_ingestion_from_content(db_session, csv_content)
        assert result["inserted_count"] == 2

        locations = db_session.query(Location).all()
        gov_names = {loc.governorate for loc in locations}
        assert "Cairo" in gov_names
        assert "Alexandria" in gov_names
        # Originals should NOT be stored
        assert "el cairo" not in gov_names
        assert "alex" not in gov_names

    def test_pipeline_real_dataset_sample(self, db_session: Session):
        """Pipeline handles a realistic multi-governorate, multi-year dataset."""
        csv_content = (
            "governorate,year,temperature_mean,humidity_pct\n"
            "Cairo,2019,22.1,50.3\n"
            "Cairo,2020,22.4,49.8\n"
            "Cairo,2021,22.6,50.1\n"
            "Giza,2019,22.3,51.0\n"
            "Giza,2020,22.5,50.5\n"
            "Alexandria,2019,20.5,65.4\n"
            "Alexandria,2020,20.7,64.9\n"
            "Aswan,2019,26.8,24.6\n"
            "Aswan,2020,27.0,24.2\n"
            "Luxor,2019,25.9,28.4\n"
        )
        result = run_climate_ingestion_from_content(db_session, csv_content)

        assert result["status"] == "COMPLETED"
        assert result["inserted_count"] == 10
        assert result["error_count"] == 0

        # Verify 5 governorates created
        locations = db_session.query(Location).count()
        assert locations == 5

        # Verify records queryable
        cairo_records = db_session.query(ClimateRecord).join(
            Location, ClimateRecord.location_id == Location.location_id
        ).filter(Location.governorate == "Cairo").all()
        assert len(cairo_records) == 3


# ============================================================================
# API Endpoint Tests — Pipeline Trigger via HTTP
# ============================================================================

class TestPipelineAPI:
    """Tests for the pipeline HTTP API endpoints."""

    def test_list_climate_files(self, client: TestClient):
        """GET /pipeline/climate/files returns available CSV files."""
        response = client.get("/api/v1/pipeline/climate/files")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert isinstance(data["data"], list)

    def test_get_batch_status_not_found(self, client: TestClient):
        """GET /pipeline/climate/status/999 returns 404."""
        response = client.get("/api/v1/pipeline/climate/status/999")
        assert response.status_code == 404

    def test_pipeline_run_via_api_content_upload(self, client: TestClient):
        """
        End-to-end test: upload CSV via existing ingestion endpoint,
        then verify data is readable via climate endpoint.
        This validates the data flows through the full stack.
        """
        csv_content = (
            "governorate,year,temperature_mean,humidity_pct\n"
            "Cairo,2023,26.5,55.0\n"
            "Aswan,2023,27.9,22.8\n"
        )
        files = {"file": ("climate.csv", csv_content, "text/csv")}
        upload_response = client.post("/api/v1/ingestion/climate/upload", files=files)

        assert upload_response.status_code == 201
        assert upload_response.json()["data"]["inserted_count"] == 2

        # Now read the data back via the climate endpoint
        read_response = client.get("/api/v1/climate/records?year=2023")
        assert read_response.status_code == 200
        records = read_response.json()["data"]
        assert len(records) == 2

        govs = {r["governorate"] for r in records}
        assert "Cairo" in govs
        assert "Aswan" in govs
