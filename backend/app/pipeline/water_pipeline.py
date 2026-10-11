"""
pipeline/water_pipeline.py
-----------------------------
Central orchestration pipeline for water data ingestion.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from sqlalchemy.orm import Session

from app.search.water_loader import load_water_csv, load_water_records
from app.ingestion.loaders import parse_water_csv
from app.pipeline.data_cleaning import clean_water_batch
from app.pipeline.data_validation import validate_water_batch
from app.ingestion.repository import (
    create_batch,
    mark_batch_completed,
    log_error,
    get_or_create_location,
    insert_water_record,
)

logger = logging.getLogger(__name__)


def run_water_ingestion(
    db: Session,
    filename: str = "egypt_crop_water_use.csv",
    source_system: str = "CSV_File_Pipeline",
) -> Dict[str, Any]:
    """
    Execute the full water data ingestion pipeline.
    """
    logger.info(f"[Water Pipeline] Starting ingestion from '{filename}'")

    batch = create_batch(db, source_system=source_system)
    batch_id = batch.batch_id
    logger.info(f"[Water Pipeline] Created batch #{batch_id}")

    try:
        raw_content = load_water_csv(filename)
        logger.info(f"[Water Pipeline] Loaded raw CSV ({len(raw_content)} bytes)")

        parsed_records = load_water_records(filename)
        logger.info(f"[Water Pipeline] Parsed {len(parsed_records)} records")

        cleaned_records = clean_water_batch(parsed_records)
        logger.info(f"[Water Pipeline] Cleaned {len(cleaned_records)} records")

        valid_records, invalid_records = validate_water_batch(cleaned_records)
        logger.info(
            f"[Water Pipeline] Validation: "
            f"{len(valid_records)} valid, {len(invalid_records)} invalid"
        )

        error_count = 0
        for inv in invalid_records:
            for err_msg in inv["errors"]:
                log_error(db, batch_id, "VALIDATION", err_msg, str(inv["record"]))
                error_count += 1

        inserted_count = 0
        skipped_duplicates = 0

        for record in valid_records:
            location = get_or_create_location(db, record["governorate"])
            try:
                insert_water_record(db, record, batch_id, location.location_id)
                inserted_count += 1
            except Exception as e:
                err_str = str(e)
                if "UNIQUE" in err_str.upper() or "duplicate" in err_str.lower() or "IntegrityError" in err_str:
                    skipped_duplicates += 1
                    logger.debug(
                        f"[Water Pipeline] Skipped duplicate: "
                        f"{record['governorate']} / {record['crop']} / {record['year']}"
                    )
                else:
                    error_count += 1
                    logger.warning(
                        f"[Water Pipeline] Insert error: {err_str}"
                    )

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

        logger.info(f"[Water Pipeline] Finished: {result}")
        return result

    except FileNotFoundError as e:
        log_error(db, batch_id, "SOURCE_LOAD", str(e))
        mark_batch_completed(db, batch_id, "FAILED")
        logger.error(f"[Water Pipeline] File not found: {e}")
        raise

    except ValueError as e:
        log_error(db, batch_id, "CSV_VALIDATION", str(e))
        mark_batch_completed(db, batch_id, "FAILED")
        logger.error(f"[Water Pipeline] Validation error: {e}")
        raise

    except Exception as e:
        log_error(db, batch_id, "UNKNOWN_ERROR", str(e))
        mark_batch_completed(db, batch_id, "FAILED")
        logger.error(f"[Water Pipeline] Unexpected error: {e}")
        raise


def run_water_ingestion_from_content(
    db: Session,
    csv_content: str,
    source_system: str = "CSV_Content_Pipeline",
) -> Dict[str, Any]:
    """
    Execute the water pipeline from raw CSV string content.
    """
    logger.info(f"[Water Pipeline] Starting ingestion from raw content ({len(csv_content)} bytes)")

    batch = create_batch(db, source_system=source_system)
    batch_id = batch.batch_id

    try:
        valid_parsed, invalid_parsed = parse_water_csv(csv_content)

        cleaned_records = clean_water_batch(valid_parsed)

        valid_records, invalid_records = validate_water_batch(cleaned_records)

        error_count = 0
        for inv in invalid_parsed:
            log_error(db, batch_id, "CSV_PARSE", inv["error"], inv["record"])
            error_count += 1

        for inv in invalid_records:
            for err_msg in inv["errors"]:
                log_error(db, batch_id, "VALIDATION", err_msg, str(inv["record"]))
                error_count += 1

        inserted_count = 0
        skipped_duplicates = 0

        for record in valid_records:
            location = get_or_create_location(db, record["governorate"])
            try:
                insert_water_record(db, record, batch_id, location.location_id)
                inserted_count += 1
            except Exception as e:
                err_str = str(e)
                if "UNIQUE" in err_str.upper() or "duplicate" in err_str.lower() or "IntegrityError" in err_str:
                    skipped_duplicates += 1
                else:
                    error_count += 1

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
