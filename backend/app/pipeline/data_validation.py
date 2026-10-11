"""
pipeline/data_validation.py
----------------------------
Schema and range validation for incoming data.

Validates:
- Required fields exist and are non-empty
- Data types are correct
- Values are within acceptable ranges

Returns validated records and a list of validation errors.
"""

from typing import List, Dict, Any, Tuple


# Acceptable ranges for climate data
YEAR_MIN = 1900
YEAR_MAX = 2100
TEMP_MIN = -50.0   # °C — extreme cold
TEMP_MAX = 65.0    # °C — extreme heat
HUMIDITY_MIN = 0.0
HUMIDITY_MAX = 100.0


def validate_climate_record(record: Dict[str, Any], row_index: int) -> List[str]:
    """
    Validate a single climate record.

    Args:
        record: Dictionary with keys: governorate, year, temperature_mean, humidity_pct.
        row_index: Row number in the source data (for error reporting).

    Returns:
        List of error messages. Empty list means the record is valid.
    """
    errors = []

    # --- governorate ---
    gov = record.get("governorate")
    if not gov or not isinstance(gov, str) or not gov.strip():
        errors.append(f"Row {row_index}: governorate is missing or empty.")

    # --- year ---
    year = record.get("year")
    if year is None:
        errors.append(f"Row {row_index}: year is missing.")
    elif not isinstance(year, int):
        errors.append(f"Row {row_index}: year must be an integer, got {type(year).__name__}.")
    elif year < YEAR_MIN or year > YEAR_MAX:
        errors.append(f"Row {row_index}: year {year} is out of range [{YEAR_MIN}, {YEAR_MAX}].")

    # --- temperature_mean ---
    temp = record.get("temperature_mean")
    if temp is None:
        errors.append(f"Row {row_index}: temperature_mean is missing.")
    elif not isinstance(temp, (int, float)):
        errors.append(f"Row {row_index}: temperature_mean must be numeric, got {type(temp).__name__}.")
    elif temp < TEMP_MIN or temp > TEMP_MAX:
        errors.append(f"Row {row_index}: temperature_mean {temp} is out of range [{TEMP_MIN}, {TEMP_MAX}].")

    # --- humidity_pct ---
    hum = record.get("humidity_pct")
    if hum is None:
        errors.append(f"Row {row_index}: humidity_pct is missing.")
    elif not isinstance(hum, (int, float)):
        errors.append(f"Row {row_index}: humidity_pct must be numeric, got {type(hum).__name__}.")
    elif hum < HUMIDITY_MIN or hum > HUMIDITY_MAX:
        errors.append(f"Row {row_index}: humidity_pct {hum} is out of range [{HUMIDITY_MIN}, {HUMIDITY_MAX}].")

    return errors


def validate_climate_batch(records: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Validate a batch of climate records.

    Args:
        records: List of parsed climate dictionaries.

    Returns:
        Tuple of (valid_records, invalid_records).
        Each invalid_record is: {"record": original_dict, "errors": [error_messages]}
    """
    valid = []
    invalid = []

    for i, record in enumerate(records, start=1):
        errors = validate_climate_record(record, i)
        if errors:
            invalid.append({"record": record, "errors": errors})
        else:
            valid.append(record)

    return valid, invalid


# Acceptable ranges for water data
WATER_MIN = 0.0
WATER_MAX = 50000.0  # m³ per feddan
VALID_IRRIGATION_TYPES = {"flood", "drip", "sprinkler", "furrow"}


def validate_water_record(record: Dict[str, Any], row_index: int) -> List[str]:
    """
    Validate a single water record.

    Args:
        record: Dictionary with keys: governorate, crop, year, water_consumption_m3, irrigation_type.
        row_index: Row number in the source data (for error reporting).

    Returns:
        List of error messages. Empty list means the record is valid.
    """
    errors = []

    # --- governorate ---
    gov = record.get("governorate")
    if not gov or not isinstance(gov, str) or not gov.strip():
        errors.append(f"Row {row_index}: governorate is missing or empty.")

    # --- crop ---
    crop = record.get("crop")
    if not crop or not isinstance(crop, str) or not crop.strip():
        errors.append(f"Row {row_index}: crop is missing or empty.")

    # --- year ---
    year = record.get("year")
    if year is None:
        errors.append(f"Row {row_index}: year is missing.")
    elif not isinstance(year, int):
        errors.append(f"Row {row_index}: year must be an integer, got {type(year).__name__}.")
    elif year < YEAR_MIN or year > YEAR_MAX:
        errors.append(f"Row {row_index}: year {year} is out of range [{YEAR_MIN}, {YEAR_MAX}].")

    # --- water_consumption_m3 ---
    water = record.get("water_consumption_m3")
    if water is None:
        errors.append(f"Row {row_index}: water_consumption_m3 is missing.")
    elif not isinstance(water, (int, float)):
        errors.append(f"Row {row_index}: water_consumption_m3 must be numeric, got {type(water).__name__}.")
    elif water < WATER_MIN or water > WATER_MAX:
        errors.append(f"Row {row_index}: water_consumption_m3 {water} is out of range [{WATER_MIN}, {WATER_MAX}].")

    # --- irrigation_type ---
    irr = record.get("irrigation_type")
    if irr and irr not in VALID_IRRIGATION_TYPES:
        errors.append(f"Row {row_index}: irrigation_type '{irr}' is not recognised.")

    return errors


def validate_water_batch(records: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Validate a batch of water records.

    Args:
        records: List of parsed water dictionaries.

    Returns:
        Tuple of (valid_records, invalid_records).
        Each invalid_record is: {"record": original_dict, "errors": [error_messages]}
    """
    valid = []
    invalid = []

    for i, record in enumerate(records, start=1):
        errors = validate_water_record(record, i)
        if errors:
            invalid.append({"record": record, "errors": errors})
        else:
            valid.append(record)

    return valid, invalid
