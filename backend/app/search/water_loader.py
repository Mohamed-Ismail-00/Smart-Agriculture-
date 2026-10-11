"""
search/water_loader.py
------------------------
Data connector for water datasets.

Reads water CSV files from the local data/csv/ directory
and returns structured data ready for the ingestion pipeline.
"""

import os
import csv
from io import StringIO
from typing import List, Dict, Any


# Base path to the raw CSV data directory
_DATA_DIR = os.path.join(
    os.path.dirname(__file__),
    os.pardir, os.pardir, os.pardir,  # services/backend/app -> project root
    "data", "csv"
)
_DATA_DIR = os.path.normpath(_DATA_DIR)


def _resolve_data_dir() -> str:
    """
    Resolve the data/csv directory.
    Checks both relative path (from app) and absolute project root.
    """
    if os.path.isdir(_DATA_DIR):
        return _DATA_DIR

    # Fallback: try from project root via env var
    project_root = os.getenv("PROJECT_ROOT", "")
    if project_root:
        alt = os.path.join(project_root, "data", "csv")
        if os.path.isdir(alt):
            return alt

    raise FileNotFoundError(
        f"Data directory not found at {_DATA_DIR}. "
        "Set PROJECT_ROOT environment variable or ensure data/csv/ exists."
    )


def load_water_csv(filename: str = "egypt_crop_water_use.csv") -> str:
    """
    Load a water CSV file from the data directory and return its raw content.

    Args:
        filename: Name of the CSV file inside data/csv/.

    Returns:
        Raw CSV string content.

    Raises:
        FileNotFoundError: If the file does not exist.
    """
    data_dir = _resolve_data_dir()
    filepath = os.path.join(data_dir, filename)

    if not os.path.isfile(filepath):
        raise FileNotFoundError(f"Water data file not found: {filepath}")

    with open(filepath, "r", encoding="utf-8") as f:
        return f.read()


def load_water_records(filename: str = "egypt_crop_water_use.csv") -> List[Dict[str, Any]]:
    """
    Load and parse a water CSV file into a list of dictionaries.

    Each record contains:
        - governorate (str)
        - crop (str)
        - year (int)
        - water_consumption_m3 (float)
        - irrigation_type (str)

    Args:
        filename: Name of the CSV file inside data/csv/.

    Returns:
        List of parsed records.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If required columns are missing.
    """
    content = load_water_csv(filename)
    reader = csv.DictReader(StringIO(content))

    required_cols = {"governorate", "crop", "year", "water_consumption_m3", "irrigation_type"}
    if not reader.fieldnames or not required_cols.issubset(set(reader.fieldnames)):
        raise ValueError(
            f"CSV is missing required columns. "
            f"Expected: {required_cols}, Got: {reader.fieldnames}"
        )

    records = []
    for row in reader:
        records.append({
            "governorate": row["governorate"].strip(),
            "crop": row["crop"].strip(),
            "year": int(row["year"]),
            "water_consumption_m3": float(row["water_consumption_m3"]),
            "irrigation_type": row["irrigation_type"].strip(),
        })

    return records


def list_available_files() -> List[str]:
    """
    List all CSV files available in the data directory.

    Returns:
        List of filenames.
    """
    try:
        data_dir = _resolve_data_dir()
    except FileNotFoundError:
        return []

    return [f for f in os.listdir(data_dir) if f.endswith(".csv")]
