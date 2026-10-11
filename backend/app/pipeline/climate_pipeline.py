"""
pipeline/climate_pipeline.py
-----------------------------
Central orchestration pipeline for climate data ingestion.

End-to-end flow (from architecture docs):
    1. Source Connector (search/climate_loader) → fetches raw CSV data
    2. Parse                → convert CSV text to structured dicts
    3. Clean                → normalise governorate names, types
    4. Validate             → range checks, schema validation
    5. Store                → insert into DB (locations + climate_records)
    6. Track                → batch status, error logging

This module is the single entry-point for running the climate pipeline.
It can be called from:
    - An API endpoint (POST /api/v1/pipeline/climate/run)
    - A background task / scheduler
    - A CLI script
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from sqlalchemy.orm import Session

from app.search.climate_loader import load_climate_csv, load_climate_records
from app.ingestion.loaders import parse_climate_csv
from app.pipeline.data_cleaning import clean_climate_batch
from app.pipeline.data_validation import validate_climate_batch
from app.ingestion.repository import (
    create_batch,
    mark_batch_completed,
    log_error,
    get_or_create_location,
    insert_climate_record,
)

logger = logging.getLogger(__name__)


def run_climate_ingestion(
    db: Session,
    filename: str = "egypt_governorate_climate_5yr.csv",
    source_system: str = "CSV_File_Pipeline",
) -> Dict[str, Any]:
    """
    Execute the full climate data ingestion pipeline.

    Steps:
        1. Read CSV from data/csv/ via the climate_loader connector
        2. Parse into structured records
        3. Clean (normalise governorate names, types)
        4. Validate (range checks, schema)
        5. Store valid records into DB
        6. Log errors for invalid records
        7. Track batch status

    Args:
        db: SQLAlchemy database session.
        filename: CSV filename inside data/csv/.
        source_system: Label for the source (stored in batch metadata).

    Returns:
        Dict with pipeline execution results:
            batch_id, inserted_count, error_count, skipped_duplicates, status
    """
    logger.info(f"[Climate Pipeline] Starting ingestion from '{filename}'")

    # --- Step 1: Create batch record ---
    batch = create_batch(db, source_system=source_system)
    batch_id = batch.batch_id
    logger.info(f"[Climate Pipeline] Created batch #{batch_id}")

    try:
        # --- Step 2: Load raw CSV from source connector ---
        raw_content = load_climate_csv(filename)
        logger.info(f"[Climate Pipeline] Loaded raw CSV ({len(raw_content)} bytes)")

        # --- Step 3: Parse CSV into records ---
        parsed_records = load_climate_records(filename)
        logger.info(f"[Climate Pipeline] Parsed {len(parsed_records)} records")

        # --- Step 4: Clean records ---
        cleaned_records = clean_climate_batch(parsed_records)
        logger.info(f"[Climate Pipeline] Cleaned {len(cleaned_records)} records")

        # --- Step 5: Validate records ---
        valid_records, invalid_records = validate_climate_batch(cleaned_records)
        logger.info(
            f"[Climate Pipeline] Validation: "
            f"{len(valid_records)} valid, {len(invalid_records)} invalid"
        )

        # --- Step 6: Log validation errors ---
        error_count = 0
        for inv in invalid_records:
            for err_msg in inv["errors"]:
                log_error(db, batch_id, "VALIDATION", err_msg, str(inv["record"]))
                error_count += 1

        # --- Step 7: Store valid records ---
        inserted_count = 0
        skipped_duplicates = 0

        for record in valid_records:
            location = get_or_create_location(db, record["governorate"])
            try:
                insert_climate_record(db, record, batch_id, location.location_id)
                inserted_count += 1
            except Exception as e:
                err_str = str(e)
                if "UNIQUE" in err_str.upper() or "duplicate" in err_str.lower():
                    skipped_duplicates += 1
                    logger.debug(
                        f"[Climate Pipeline] Skipped duplicate: "
                        f"{record['governorate']} / {record['year']}"
                    )
                else:
                    error_count += 1
                    logger.warning(
                        f"[Climate Pipeline] Insert error: {err_str}"
                    )

        # --- Step 8: Determine final status ---
        if error_count == 0 and inserted_count > 0:
            status = "COMPLETED"
        elif inserted_count > 0 and error_count > 0:
            status = "PARTIAL_SUCCESS"
        elif inserted_count == 0 and skipped_duplicates > 0 and error_count == 0:
            status = "COMPLETED_NO_NEW_DATA"
        else:
            status = "FAILED"

        mark_batch_completed(db, batch_id, status)

        result = {
            "batch_id": batch_id,
            "source_file": filename,
            "total_parsed": len(parsed_records),
            "total_cleaned": len(cleaned_records),
            "total_valid": len(valid_records),
            "total_invalid": len(invalid_records),
            "inserted_count": inserted_count,
            "skipped_duplicates": skipped_duplicates,
            "error_count": error_count,
            "status": status,
        }

        logger.info(f"[Climate Pipeline] Finished: {result}")
        return result

    except FileNotFoundError as e:
        log_error(db, batch_id, "SOURCE_LOAD", str(e))
        mark_batch_completed(db, batch_id, "FAILED")
        logger.error(f"[Climate Pipeline] File not found: {e}")
        raise

    except ValueError as e:
        log_error(db, batch_id, "CSV_VALIDATION", str(e))
        mark_batch_completed(db, batch_id, "FAILED")
        logger.error(f"[Climate Pipeline] Validation error: {e}")
        raise

    except Exception as e:
        log_error(db, batch_id, "UNKNOWN_ERROR", str(e))
        mark_batch_completed(db, batch_id, "FAILED")
        logger.error(f"[Climate Pipeline] Unexpected error: {e}")
        raise


def run_climate_ingestion_from_content(
    db: Session,
    csv_content: str,
    source_system: str = "CSV_Content_Pipeline",
) -> Dict[str, Any]:
    """
    Execute the climate pipeline from raw CSV string content
    (e.g., from an API upload or external API response).

    This bypasses the file-based loader and feeds content directly.

    Args:
        db: SQLAlchemy database session.
        csv_content: Raw CSV string.
        source_system: Label for the source.

    Returns:
        Pipeline execution results dict.
    """
    logger.info(f"[Climate Pipeline] Starting ingestion from raw content ({len(csv_content)} bytes)")

    batch = create_batch(db, source_system=source_system)
    batch_id = batch.batch_id

    try:
        # Parse using the existing ingestion loader
        valid_parsed, invalid_parsed = parse_climate_csv(csv_content)

        # Clean valid records
        cleaned_records = clean_climate_batch(valid_parsed)

        # Validate cleaned records
        valid_records, invalid_records = validate_climate_batch(cleaned_records)

        # Log parse errors
        error_count = 0
        for inv in invalid_parsed:
            log_error(db, batch_id, "CSV_PARSE", inv["error"], inv["record"])
            error_count += 1

        # Log validation errors
        for inv in invalid_records:
            for err_msg in inv["errors"]:
                log_error(db, batch_id, "VALIDATION", err_msg, str(inv["record"]))
                error_count += 1

        # Store valid records
        inserted_count = 0
        skipped_duplicates = 0

        for record in valid_records:
            location = get_or_create_location(db, record["governorate"])
            try:
                insert_climate_record(db, record, batch_id, location.location_id)
                inserted_count += 1
            except Exception as e:
                err_str = str(e)
                if "UNIQUE" in err_str.upper() or "duplicate" in err_str.lower():
                    skipped_duplicates += 1
                else:
                    error_count += 1

        # Determine status
        if error_count == 0 and inserted_count > 0:
            status = "COMPLETED"
        elif inserted_count > 0 and error_count > 0:
            status = "PARTIAL_SUCCESS"
        elif inserted_count == 0 and skipped_duplicates > 0 and error_count == 0:
            status = "COMPLETED_NO_NEW_DATA"
        else:
            status = "FAILED"

        mark_batch_completed(db, batch_id, status)

        return {
            "batch_id": batch_id,
            "total_parsed": len(valid_parsed) + len(invalid_parsed),
            "inserted_count": inserted_count,
            "skipped_duplicates": skipped_duplicates,
            "error_count": error_count,
            "status": status,
        }

    except ValueError as e:
        log_error(db, batch_id, "CSV_VALIDATION", str(e))
        mark_batch_completed(db, batch_id, "FAILED")
        raise

    except Exception as e:
        log_error(db, batch_id, "UNKNOWN_ERROR", str(e))
        mark_batch_completed(db, batch_id, "FAILED")
        raise
