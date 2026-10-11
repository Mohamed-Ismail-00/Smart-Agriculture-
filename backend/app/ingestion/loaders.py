"""
ingestion/loaders.py
--------------------
Parsers and loaders for ingestion files.
"""

import csv
from io import StringIO
from typing import List, Dict, Any, Tuple

def parse_climate_csv(content: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Parses climate CSV content.
    Returns: (valid_records, invalid_records)
    where invalid_records contains {"record": row, "error": msg}
    """
    reader = csv.DictReader(StringIO(content))
    valid_records = []
    invalid_records = []
    
    required_cols = {"governorate", "year", "temperature_mean", "humidity_pct"}
    
    if not reader.fieldnames or not required_cols.issubset(set(reader.fieldnames)):
        raise ValueError(f"Missing required columns. Expected: {required_cols}")

    for i, row in enumerate(reader):
        try:
            year = int(row["year"])
            temp = float(row["temperature_mean"])
            humidity = float(row["humidity_pct"])
            gov = row["governorate"].strip()
            
            if not gov:
                raise ValueError("Governorate is empty")
                
            valid_records.append({
                "governorate": gov,
                "year": year,
                "temperature_mean": temp,
                "humidity_pct": humidity
            })
        except Exception as e:
            invalid_records.append({
                "record": str(row),
                "error": str(e)
            })
            
    return valid_records, invalid_records


def parse_water_csv(content: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Parses water CSV content.
    Returns: (valid_records, invalid_records)
    where invalid_records contains {"record": row, "error": msg}
    """
    reader = csv.DictReader(StringIO(content))
    valid_records = []
    invalid_records = []
    
    required_cols = {"governorate", "crop", "year", "water_consumption_m3", "irrigation_type"}
    
    if not reader.fieldnames or not required_cols.issubset(set(reader.fieldnames)):
        raise ValueError(f"Missing required columns. Expected: {required_cols}")

    for i, row in enumerate(reader):
        try:
            gov = row["governorate"].strip()
            crop = row["crop"].strip()
            year = int(row["year"])
            water = float(row["water_consumption_m3"])
            irrigation = row["irrigation_type"].strip()
            
            if not gov:
                raise ValueError("Governorate is empty")
            if not crop:
                raise ValueError("Crop is empty")
                
            valid_records.append({
                "governorate": gov,
                "crop": crop,
                "year": year,
                "water_consumption_m3": water,
                "irrigation_type": irrigation
            })
        except Exception as e:
            invalid_records.append({
                "record": str(row),
                "error": str(e)
            })
            
    return valid_records, invalid_records
