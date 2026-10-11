"""
api/auth.py
-----------
Authentication endpoints.

Routes (all prefixed /api/v1 from main.py):
    POST  /auth/register  → create a new user account
    POST  /auth/login     → authenticate and receive a JWT token
    GET   /auth/me        → get the currently authenticated user (protected)
    POST  /auth/logout    → client-side logout notice (stateless JWT)

Design rule: this file stays thin — no business logic, no DB queries.
All logic lives in users/service.py.
"""

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core import security
from app.core.dependencies import get_current_user, get_current_user_optional, get_db
from app.models.user import User
from app.users import service as user_service
from app.users.schemas import (
    APIResponse,
    TokenResponse,
    UserCreate,
    UserLogin,
    UserResponse,
)

class RefreshRequest(BaseModel):
    refresh_token: str
    model_config = {"extra": "forbid"}


class GoogleAuthRequest(BaseModel):
    """Body for POST /auth/google — the ID token from Google Identity Services."""
    credential: str  # This is the ID token from Google
    model_config = {"extra": "forbid"}

router = APIRouter(prefix="/auth", tags=["Authentication"])


# ---------------------------------------------------------------------------
# POST /auth/register
# ---------------------------------------------------------------------------

@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    response_model=APIResponse,
    summary="Register a new user account",
)
def register(user_in: UserCreate, db: Session = Depends(get_db)):
    """
    Create a new user.

    - **email**: must be unique
    - **password**: minimum 8 characters
    - **role**: analyst | viewer only (admin role cannot be created via this endpoint)
    """
    user = user_service.register_user(db, user_in)
    return APIResponse(
        status="success",
        data=UserResponse.model_validate(user).model_dump(),
        message="User registered successfully.",
    )


# ---------------------------------------------------------------------------
# POST /auth/login
# ---------------------------------------------------------------------------

@router.post(
    "/login",
    response_model=APIResponse,
    summary="Login and receive a JWT access token",
)
def login(credentials: UserLogin, db: Session = Depends(get_db)):
    """
    Authenticate with email + password.

    Returns a **Bearer JWT token** to be sent in the `Authorization` header
    for all protected endpoints.
    """
    user = user_service.authenticate_user(db, credentials.email, credentials.password)
    access_token = security.create_access_token(data={"sub": str(user.user_id)})
    refresh_token = security.create_refresh_token(data={"sub": str(user.user_id)})

    # Log real activity (visible only to admins)
    user_service.record_activity(
        db,
        user.user_id,
        "login",
        target_type="user",
        target_id=user.user_id,
        details={"email": user.email},
    )

    return APIResponse(
        status="success",
        data=TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
        ).model_dump(),
        message="Login successful.",
    )


# ---------------------------------------------------------------------------
# GET /auth/me
# ---------------------------------------------------------------------------

@router.get(
    "/me",
    response_model=APIResponse,
    summary="Get the currently authenticated user",
)
def me(current_user: User = Depends(get_current_user)):
    """
    Returns the profile of the user identified by the JWT token in the
    `Authorization: Bearer <token>` header.
    """
    return APIResponse(
        status="success",
        data=UserResponse.model_validate(current_user).model_dump(),
    )


# ---------------------------------------------------------------------------
# POST /auth/logout
# ---------------------------------------------------------------------------

from typing import Optional

@router.post(
    "/logout",
    response_model=APIResponse,
    summary="Logout (client-side token invalidation)",
)
def logout(current_user: Optional[User] = Depends(get_current_user_optional)):
    """
    Stateless logout — the server acknowledges the request but does not
    maintain a token blacklist. The client is responsible for discarding the
    JWT token after this call.
    """
    email = current_user.email if current_user else "Unknown"
    return APIResponse(
        status="success",
        message=f"User {email} logged out. Discard your token.",
    )


# ---------------------------------------------------------------------------
# POST /auth/refresh   (Auth v2)
# ---------------------------------------------------------------------------

@router.post(
    "/refresh",
    response_model=APIResponse,
    summary="Refresh access token using a valid refresh token",
)
def refresh_token(body: RefreshRequest, db: Session = Depends(get_db)):
    """
    Takes a refresh_token and returns a new access_token (and new refresh_token).
    """
    try:
        payload = security.decode_refresh_token(body.refresh_token)
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid refresh token")

        user = user_service.get_user_by_id(db, int(user_id))
        if not user or not user.is_active:
            raise HTTPException(status_code=401, detail="User not active")

        new_access = security.create_access_token(data={"sub": str(user.user_id)})
        new_refresh = security.create_refresh_token(data={"sub": str(user.user_id)})

        return APIResponse(
            status="success",
            data=TokenResponse(access_token=new_access, refresh_token=new_refresh).model_dump(),
            message="Token refreshed",
        )
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")


# ---------------------------------------------------------------------------
# POST /auth/google   — Sign in / Sign up with Google (OAuth 2.0 ID token)
# ---------------------------------------------------------------------------

@router.post(
    "/google",
    response_model=APIResponse,
    summary="Sign in or sign up using Google ID token",
)
def google_auth(body: GoogleAuthRequest, db: Session = Depends(get_db)):
    """
    Accepts a Google ID token (from Google Identity Services on the frontend).

    - If the email exists → logs the user in.
    - If the email does not exist → creates a new user account (role=viewer).
    """
    user = user_service.authenticate_with_google(db, body.credential)

    access_token = security.create_access_token(data={"sub": str(user.user_id)})
    refresh_token = security.create_refresh_token(data={"sub": str(user.user_id)})

    # Log activity
    user_service.record_activity(
        db,
        user.user_id,
        "login",
        target_type="user",
        target_id=user.user_id,
        details={"email": user.email, "provider": "google"},
    )

    return APIResponse(
        status="success",
        data=TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
        ).model_dump(),
        message="Google authentication successful.",
    )
