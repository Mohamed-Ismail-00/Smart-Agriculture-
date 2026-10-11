"""
tests/api/test_users.py
-----------------------
Full coverage unit tests for the user management endpoints.

Endpoints covered:
  GET    /api/v1/users      — list all users (admin only)
  GET    /api/v1/users/{id} — get user by ID (admin only)
  PUT    /api/v1/users/{id} — update a user (admin only)
  DELETE /api/v1/users/{id} — delete a user (admin only)

All tests use in-memory SQLite (no Docker required).
Auth guards are tested for both admin and non-admin users.
"""

import pytest

REGISTER_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"
USERS_URL = "/api/v1/users"

ADMIN_USER = {
    "email": "admin@agri.com",
    "password": "adminpassword",
    "role": "admin",
}

VIEWER_USER = {
    "email": "viewer@agri.com",
    "password": "viewerpassword",
    "role": "viewer",
}

ANALYST_USER = {
    "email": "analyst@agri.com",
    "password": "analystpassword",
    "role": "analyst",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def register(client, user: dict) -> dict:
    """Register a user and return the response data dict."""
    resp = client.post(REGISTER_URL, json=user)
    assert resp.status_code == 201, f"Register failed: {resp.json()}"
    return resp.json()["data"]


def login(client, user: dict) -> str:
    """Login and return the JWT token string."""
    resp = client.post(LOGIN_URL, json={
        "email": user["email"],
        "password": user["password"],
    })
    assert resp.status_code == 200, f"Login failed: {resp.json()}"
    return resp.json()["data"]["access_token"]


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# GET /users — list all users
# ---------------------------------------------------------------------------

class TestListUsers:
    def test_admin_can_list_users(self, client):
        """Admin must receive HTTP 200 and a list of users."""
        register(client, ADMIN_USER)
        token = login(client, ADMIN_USER)
        response = client.get(USERS_URL + "/", headers=auth_headers(token))
        assert response.status_code == 200

    def test_list_response_shape(self, client):
        """Response must contain status, data (list), meta with total."""
        register(client, ADMIN_USER)
        token = login(client, ADMIN_USER)
        response = client.get(USERS_URL + "/", headers=auth_headers(token))
        body = response.json()
        assert body["status"] == "success"
        assert isinstance(body["data"], list)
        assert "total" in body["meta"]

    def test_total_matches_registered_users(self, client):
        """Meta.total must reflect the number of registered users."""
        register(client, ADMIN_USER)
        register(client, VIEWER_USER)
        token = login(client, ADMIN_USER)
        response = client.get(USERS_URL + "/", headers=auth_headers(token))
        body = response.json()
        assert body["meta"]["total"] == 2

    def test_viewer_cannot_list_users(self, client):
        """Non-admin role must receive 403 Forbidden."""
        register(client, VIEWER_USER)
        token = login(client, VIEWER_USER)
        response = client.get(USERS_URL + "/", headers=auth_headers(token))
        assert response.status_code == 403

    def test_analyst_cannot_list_users(self, client):
        """Analyst role must also be rejected from admin-only routes."""
        register(client, ANALYST_USER)
        token = login(client, ANALYST_USER)
        response = client.get(USERS_URL + "/", headers=auth_headers(token))
        assert response.status_code == 403

    def test_unauthenticated_cannot_list_users(self, client):
        """Requests without a token must return 401."""
        response = client.get(USERS_URL + "/")
        assert response.status_code == 401

    def test_password_not_in_list_response(self, client):
        """Password hash must never leak through the list endpoint."""
        register(client, ADMIN_USER)
        token = login(client, ADMIN_USER)
        response = client.get(USERS_URL + "/", headers=auth_headers(token))
        assert "password" not in response.text
        assert "hash" not in response.text


# ---------------------------------------------------------------------------
# GET /users/{id}
# ---------------------------------------------------------------------------

class TestGetUser:
    def test_admin_can_get_user_by_id(self, client):
        """Admin must retrieve a user by ID with HTTP 200."""
        user_data = register(client, ADMIN_USER)
        user_id = user_data["user_id"]
        token = login(client, ADMIN_USER)
        response = client.get(f"{USERS_URL}/{user_id}", headers=auth_headers(token))
        assert response.status_code == 200

    def test_get_user_response_shape(self, client):
        """Response must match the UserResponse schema shape."""
        user_data = register(client, ADMIN_USER)
        user_id = user_data["user_id"]
        token = login(client, ADMIN_USER)
        response = client.get(f"{USERS_URL}/{user_id}", headers=auth_headers(token))
        data = response.json()["data"]
        assert data["email"] == ADMIN_USER["email"]
        assert data["user_id"] == user_id
        assert "role" in data
        assert "is_active" in data

    def test_nonexistent_user_returns_404(self, client):
        """Fetching a user ID that doesn't exist must return 404."""
        register(client, ADMIN_USER)
        token = login(client, ADMIN_USER)
        response = client.get(f"{USERS_URL}/99999", headers=auth_headers(token))
        assert response.status_code == 404

    def test_viewer_cannot_get_user_by_id(self, client):
        """Viewer role must receive 403."""
        register(client, VIEWER_USER)
        token = login(client, VIEWER_USER)
        response = client.get(f"{USERS_URL}/1", headers=auth_headers(token))
        assert response.status_code == 403

    def test_unauthenticated_returns_401(self, client):
        """No token → 401."""
        response = client.get(f"{USERS_URL}/1")
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# PUT /users/{id}
# ---------------------------------------------------------------------------

class TestUpdateUser:
    def test_admin_can_update_role(self, client):
        """Admin must be able to change a user's role."""
        viewer_data = register(client, VIEWER_USER)
        viewer_id = viewer_data["user_id"]
        register(client, ADMIN_USER)
        token = login(client, ADMIN_USER)
        response = client.put(
            f"{USERS_URL}/{viewer_id}",
            json={"role": "analyst"},
            headers=auth_headers(token),
        )
        assert response.status_code == 200
        assert response.json()["data"]["role"] == "analyst"

    def test_admin_can_deactivate_user(self, client):
        """Admin must be able to set is_active=False."""
        viewer_data = register(client, VIEWER_USER)
        viewer_id = viewer_data["user_id"]
        register(client, ADMIN_USER)
        token = login(client, ADMIN_USER)
        response = client.put(
            f"{USERS_URL}/{viewer_id}",
            json={"is_active": False},
            headers=auth_headers(token),
        )
        assert response.status_code == 200
        assert response.json()["data"]["is_active"] is False

    def test_admin_can_update_email(self, client):
        """Admin must be able to change a user's email."""
        viewer_data = register(client, VIEWER_USER)
        viewer_id = viewer_data["user_id"]
        register(client, ADMIN_USER)
        token = login(client, ADMIN_USER)
        new_email = "newemail@agri.com"
        response = client.put(
            f"{USERS_URL}/{viewer_id}",
            json={"email": new_email},
            headers=auth_headers(token),
        )
        assert response.status_code == 200
        assert response.json()["data"]["email"] == new_email

    def test_update_nonexistent_user_returns_404(self, client):
        """Updating a missing user must return 404."""
        register(client, ADMIN_USER)
        token = login(client, ADMIN_USER)
        response = client.put(
            f"{USERS_URL}/99999",
            json={"role": "analyst"},
            headers=auth_headers(token),
        )
        assert response.status_code == 404

    def test_update_to_duplicate_email_returns_400(self, client):
        """Changing email to an already-taken address must return 400."""
        register(client, ADMIN_USER)
        viewer_data = register(client, VIEWER_USER)
        viewer_id = viewer_data["user_id"]
        token = login(client, ADMIN_USER)
        response = client.put(
            f"{USERS_URL}/{viewer_id}",
            json={"email": ADMIN_USER["email"]},  # admin's email
            headers=auth_headers(token),
        )
        assert response.status_code == 400

    def test_viewer_cannot_update_users(self, client):
        """Non-admin cannot update any user."""
        register(client, VIEWER_USER)
        token = login(client, VIEWER_USER)
        response = client.put(
            f"{USERS_URL}/1",
            json={"role": "admin"},
            headers=auth_headers(token),
        )
        assert response.status_code == 403

    def test_invalid_role_on_update_returns_422(self, client):
        """Pydantic validation: invalid role value must be rejected."""
        viewer_data = register(client, VIEWER_USER)
        viewer_id = viewer_data["user_id"]
        register(client, ADMIN_USER)
        token = login(client, ADMIN_USER)
        response = client.put(
            f"{USERS_URL}/{viewer_id}",
            json={"role": "root"},
            headers=auth_headers(token),
        )
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# DELETE /users/{id}
# ---------------------------------------------------------------------------

class TestDeleteUser:
    def test_admin_can_delete_user(self, client):
        """Admin must be able to delete a user — returns 200."""
        viewer_data = register(client, VIEWER_USER)
        viewer_id = viewer_data["user_id"]
        register(client, ADMIN_USER)
        token = login(client, ADMIN_USER)
        response = client.delete(
            f"{USERS_URL}/{viewer_id}",
            headers=auth_headers(token),
        )
        assert response.status_code == 200

    def test_delete_response_shape(self, client):
        """Delete response must confirm success."""
        viewer_data = register(client, VIEWER_USER)
        viewer_id = viewer_data["user_id"]
        register(client, ADMIN_USER)
        token = login(client, ADMIN_USER)
        response = client.delete(
            f"{USERS_URL}/{viewer_id}",
            headers=auth_headers(token),
        )
        body = response.json()
        assert body["status"] == "success"
        assert "deleted" in body["message"].lower() or str(viewer_id) in body["message"]

    def test_deleted_user_no_longer_accessible(self, client):
        """After deletion, GET /users/{id} must return 404."""
        viewer_data = register(client, VIEWER_USER)
        viewer_id = viewer_data["user_id"]
        register(client, ADMIN_USER)
        token = login(client, ADMIN_USER)
        client.delete(f"{USERS_URL}/{viewer_id}", headers=auth_headers(token))
        response = client.get(f"{USERS_URL}/{viewer_id}", headers=auth_headers(token))
        assert response.status_code == 404

    def test_delete_nonexistent_user_returns_404(self, client):
        """Deleting a missing user must return 404."""
        register(client, ADMIN_USER)
        token = login(client, ADMIN_USER)
        response = client.delete(
            f"{USERS_URL}/99999",
            headers=auth_headers(token),
        )
        assert response.status_code == 404

    def test_viewer_cannot_delete_users(self, client):
        """Non-admin cannot delete any user."""
        register(client, VIEWER_USER)
        token = login(client, VIEWER_USER)
        response = client.delete(
            f"{USERS_URL}/1",
            headers=auth_headers(token),
        )
        assert response.status_code == 403

    def test_unauthenticated_cannot_delete(self, client):
        """No token → 401."""
        response = client.delete(f"{USERS_URL}/1")
        assert response.status_code == 401
