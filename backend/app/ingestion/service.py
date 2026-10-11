"""
ingestion/service.py
--------------------
Orchestration logic for handling ingestion files and databases.
"""

from sqlalchemy.orm import Session
from fastapi import UploadFile

from app.ingestion import loaders
from app.ingestion import repository

def process_climate_upload(db: Session, file: UploadFile) -> dict:
    content = file.file.read().decode("utf-8")
    
    batch = repository.create_batch(db, source_system="CSV_Upload")
    
    try:
        valid_records, invalid_records = loaders.parse_climate_csv(content)
        
        inserted_count = 0
        error_count = 0
        
        # log invalid rows immediately
        for invalid in invalid_records:
            repository.log_error(db, batch.batch_id, "CSV_PARSE", invalid["error"], invalid["record"])
            error_count += 1
            
        # process valid rows
        for record in valid_records:
            loc = repository.get_or_create_location(db, record["governorate"])
            try:
                repository.insert_climate_record(db, record, batch.batch_id, loc.location_id)
                inserted_count += 1
            except Exception as e:
                error_count += 1
                
        status = "COMPLETED" if error_count == 0 else "PARTIAL_SUCCESS"
        if inserted_count == 0 and error_count > 0:
            status = "FAILED"
            
        repository.mark_batch_completed(db, batch.batch_id, status)
        
        return {
            "batch_id": batch.batch_id,
            "inserted_count": inserted_count,
            "error_count": error_count,
            "status": status
        }
            
    except ValueError as e:
        # E.g. Missing required columns
        repository.log_error(db, batch.batch_id, "CSV_VALIDATION", str(e))
        repository.mark_batch_completed(db, batch.batch_id, "FAILED")
        raise e
    except Exception as e:
        repository.log_error(db, batch.batch_id, "UNKNOWN_ERROR", str(e))
        repository.mark_batch_completed(db, batch.batch_id, "FAILED")
        raise e
