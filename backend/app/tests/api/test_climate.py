"""
tests/api/test_climate.py
-------------------------
Integration tests for the Climate Pipeline vertical slice.
Includes testing the /api/v1/ingestion/climate/upload and /api/v1/climate/records endpoints.
"""

from fastapi.testclient import TestClient

def test_ingestion_valid_csv(client: TestClient):
    csv_content = "governorate,year,temperature_mean,humidity_pct\nCairo,2023,26.5,55\nGiza,2023,25.8,52"
    files = {"file": ("climate.csv", csv_content, "text/csv")}
    response = client.post("/api/v1/ingestion/climate/upload", files=files)
    
    assert response.status_code == 201
    assert response.json()["status"] == "success"
    assert response.json()["data"]["inserted_count"] == 2
    assert response.json()["data"]["error_count"] == 0

def test_ingestion_invalid_csv(client: TestClient):
    # Missing governorate column entirely
    csv_content = "year,temperature_mean,humidity_pct\n2023,26.5,55"
    files = {"file": ("climate.csv", csv_content, "text/csv")}
    response = client.post("/api/v1/ingestion/climate/upload", files=files)
    
    assert response.status_code == 422
    assert "Missing required columns" in response.json()["detail"]

def test_ingestion_partial_failures(client: TestClient):
    # One valid, one invalid (empty governorate)
    csv_content = "governorate,year,temperature_mean,humidity_pct\nCairo,2023,26.5,55\n,2024,25.8,52"
    files = {"file": ("climate.csv", csv_content, "text/csv")}
    response = client.post("/api/v1/ingestion/climate/upload", files=files)
    
    assert response.status_code == 201
    assert response.json()["status"] == "success"
    data = response.json()["data"]
    assert data["status"] == "PARTIAL_SUCCESS"
    assert data["inserted_count"] == 1
    assert data["error_count"] == 1

def test_get_climate_records_success(client: TestClient):
    # First ingest some data
    csv_content = "governorate,year,temperature_mean,humidity_pct\nCairo,2023,26.5,55"
    files = {"file": ("climate.csv", csv_content, "text/csv")}
    client.post("/api/v1/ingestion/climate/upload", files=files)
    
    # Then retrieve
    response = client.get("/api/v1/climate/records?year=2023")
    assert response.status_code == 200
    
    data = response.json()
    assert data["status"] == "success"
    assert len(data["data"]) == 1
    assert data["data"][0]["governorate"] == "Cairo"
    assert data["data"][0]["year"] == 2023
    assert data["data"][0]["temperature_mean"] == 26.5

def test_get_climate_records_invalid_year(client: TestClient):
    response = client.get("/api/v1/climate/records?year=3000")
    # Our API enforces 1900-2100 logic explicitly and raises 422
    assert response.status_code == 422
    
def test_get_climate_records_empty_list(client: TestClient):
    response = client.get("/api/v1/climate/records?year=2010")
    assert response.status_code == 200
    assert response.json()["data"] == []
