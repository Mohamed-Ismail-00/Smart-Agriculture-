"""
pipeline/data_cleaning.py
--------------------------
Minimal data standardisation at the ingestion stage.

What IS allowed here (per architecture docs):
- Rename/normalise column values
- Strip whitespace
- Basic type coercion
- Standardise governorate names

What is NOT allowed here:
- Heavy statistical cleaning
- Aggregation
- Analytics / feature engineering
"""

from typing import List, Dict, Any

# Known canonical governorate names → normalise common variations
_GOVERNORATE_ALIASES: Dict[str, str] = {
    "el cairo": "Cairo",
    "al qahira": "Cairo",
    "al qahirah": "Cairo",
    "el giza": "Giza",
    "al jizah": "Giza",
    "el iskandereya": "Alexandria",
    "al iskandariyah": "Alexandria",
    "alex": "Alexandria",
    "el minya": "Minya",
    "al minya": "Minya",
    "el faiyum": "Fayoum",
    "el fayoum": "Fayoum",
    "al fayyum": "Fayoum",
    "el beheira": "Beheira",
    "al buhayrah": "Beheira",
    "el daqahliyya": "Dakahlia",
    "al daqahliyah": "Dakahlia",
    "el sharqia": "Sharqia",
    "al sharqiyah": "Sharqia",
    "el gharbiyya": "Gharbia",
    "al gharbiyah": "Gharbia",
    "el qalyubiyya": "Qalyubia",
    "al qalyubiyah": "Qalyubia",
    "el ismailia": "Ismailia",
    "al ismailiyah": "Ismailia",
    "bur said": "Port Said",
    "port-said": "Port Said",
    "portsaid": "Port Said",
    "dumyat": "Damietta",
    "el monufia": "Monufia",
    "al minufiyah": "Monufia",
    "bani suwayf": "Beni Suef",
    "beni-suef": "Beni Suef",
    "asyut": "Asyut",
    "assiut": "Asyut",
    "suhaj": "Sohag",
    "qina": "Qena",
    "el wadi el gedid": "New Valley",
    "new-valley": "New Valley",
    "matruh": "Matrouh",
    "marsa matruh": "Matrouh",
    "shamāl sīnāʼ": "North Sinai",
    "janub sina": "South Sinai",
    "el bahr el ahmar": "Red Sea",
    "kafr el-sheikh": "Kafr El Sheikh",
    "kafr el shaykh": "Kafr El Sheikh",
}


def normalise_governorate(name: str) -> str:
    """
    Normalise a governorate name to its canonical form.

    Args:
        name: Raw governorate name from source data.

    Returns:
        Canonical governorate name (title-cased or mapped).
    """
    stripped = name.strip()
    lookup = stripped.lower()

    if lookup in _GOVERNORATE_ALIASES:
        return _GOVERNORATE_ALIASES[lookup]

    # Default: title-case the stripped name
    return stripped.title()


def clean_climate_record(record: Dict[str, Any]) -> Dict[str, Any]:
    """
    Apply minimal standardisation to a single climate record.

    Operations:
    - Strip whitespace from governorate
    - Normalise governorate name
    - Ensure numeric types for temperature and humidity

    Args:
        record: Raw parsed record dict.

    Returns:
        Cleaned record dict (new copy).
    """
    cleaned = {}

    # Governorate normalisation
    raw_gov = record.get("governorate", "")
    cleaned["governorate"] = normalise_governorate(str(raw_gov))

    # Year — ensure int
    cleaned["year"] = int(record["year"])

    # Temperature — ensure float
    cleaned["temperature_mean"] = float(record["temperature_mean"])

    # Humidity — ensure float
    cleaned["humidity_pct"] = float(record["humidity_pct"])

    return cleaned


def clean_climate_batch(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Clean an entire batch of climate records.

    Args:
        records: List of raw parsed records.

    Returns:
        List of cleaned records.
    """
    return [clean_climate_record(r) for r in records]


# Known irrigation type aliases
_IRRIGATION_ALIASES: Dict[str, str] = {
    "drip irrigation": "drip",
    "flood irrigation": "flood",
    "sprinkler irrigation": "sprinkler",
    "pivot": "sprinkler",
}


def clean_water_record(record: Dict[str, Any]) -> Dict[str, Any]:
    """
    Apply minimal standardisation to a single water record.

    Operations:
    - Normalise governorate name
    - Title-case crop name
    - Ensure numeric types for year and water_consumption_m3
    - Normalise irrigation type

    Args:
        record: Raw parsed record dict.

    Returns:
        Cleaned record dict (new copy).
    """
    cleaned = {}

    raw_gov = record.get("governorate", "")
    cleaned["governorate"] = normalise_governorate(str(raw_gov))

    cleaned["crop"] = str(record.get("crop", "")).strip().title()

    cleaned["year"] = int(record["year"])
    cleaned["water_consumption_m3"] = float(record["water_consumption_m3"])

    raw_irr = str(record.get("irrigation_type", "")).strip().lower()
    cleaned["irrigation_type"] = _IRRIGATION_ALIASES.get(raw_irr, raw_irr)

    return cleaned


def clean_water_batch(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Clean an entire batch of water records.

    Args:
        records: List of raw parsed records.

    Returns:
        List of cleaned records.
    """
    return [clean_water_record(r) for r in records]
