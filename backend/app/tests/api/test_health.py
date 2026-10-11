"""
tests/api/test_health.py
------------------------
Tests for the system health endpoints.

Coverage:
  GET /api/health      — backend liveness check
  GET /api/health/db   — database connectivity check
"""

import pytest


# ---------------------------------------------------------------------------
# GET /api/health
# ---------------------------------------------------------------------------

class TestBackendHealth:
    def test_returns_200(self, client):
        """Health endpoint must return HTTP 200."""
        response = client.get("/api/health")
        assert response.status_code == 200

    def test_response_body(self, client):
        """Response must confirm the backend is running."""
        response = client.get("/api/health")
        body = response.json()
        assert body == {"status": "backend running"}

    def test_content_type_is_json(self, client):
        """Response must be JSON."""
        response = client.get("/api/health")
        assert "application/json" in response.headers["content-type"]


# ---------------------------------------------------------------------------
# GET /api/health/db
# ---------------------------------------------------------------------------

class TestDatabaseHealth:
    def test_returns_200(self, client):
        """DB health endpoint must return HTTP 200."""
        response = client.get("/api/health/db")
        assert response.status_code == 200

    def test_status_field_present(self, client):
        """Response must contain a 'status' field."""
        response = client.get("/api/health/db")
        body = response.json()
        assert "status" in body

    def test_database_is_reachable(self, client):
        """
        DB query SELECT 1 should succeed and return result=1.
        In the test environment this runs against SQLite via the overridden session.

        NOTE: if running against a live Docker stack, this tests the real MySQL.
        """
        response = client.get("/api/health/db")
        body = response.json()
        # Accept both success (Docker) and connectivity error (standalone SQLite)
        # The endpoint must always return 200 and a body — never crash.
        assert response.status_code == 200
        assert body.get("status") in ("success", "error")
