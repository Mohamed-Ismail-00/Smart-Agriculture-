"""
users/service.py
----------------
Business logic layer for the users domain.

Rules:
- Calls repository for all DB access.
- Calls core/security.py for crypto.
- Raises HTTPException with meaningful status codes.
- No SQLAlchemy queries directly — always goes through repository.
"""

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core import security
from app.core.activity import log_activity
from app.core.google_auth import verify_google_token
from app.models.user import User
from app.users import repository
from app.users.schemas import UserCreate, UserUpdate


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def register_user(db: Session, user_in: UserCreate) -> User:
    """
    Create a new user account.

    Raises:
        400 Bad Request — if email is already registered.
    """
    existing = repository.get_user_by_email(db, user_in.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email already exists.",
        )
    hashed = security.hash_password(user_in.password)
    # Security: never allow admin creation through registration.
    # Only the two seeded admin accounts (in init/seed.sql) may have role=admin.
    role = user_in.role if user_in.role in ("analyst", "viewer") else "viewer"
    return repository.create_user(db, user_in.email, hashed, role)


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

def authenticate_user(db: Session, email: str, password: str) -> User:
    """
    Verify credentials and return the user.

    Raises:
        401 Unauthorized — if email not found or password is wrong.
    """
    user = repository.get_user_by_email(db, email)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Google-only users have no password
    if user.password_hash is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="This account uses Google Sign-In. Please sign in with Google.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not security.verify_password(password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
            headers={"WWW-Authenticator": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated. Contact an administrator.",
        )
    return user


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------

def get_user_by_id(db: Session, user_id: int) -> User:
    """
    Fetch a single user by ID.

    Raises:
        404 Not Found — if no user matches user_id.
    """
    user = repository.get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with id={user_id} not found.",
        )
    return user


def get_all_users(db: Session) -> list[User]:
    """Return all users (admin-only access enforced by API layer)."""
    return repository.get_all_users(db)


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------

def update_user(db: Session, user_id: int, user_in: UserUpdate) -> User:
    """
    Update an existing user.

    Raises:
        404 Not Found — if no user matches user_id.
        400 Bad Request — if the new email is already taken by another user.
    """
    # Ensure user exists
    target = repository.get_user_by_id(db, user_id)
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with id={user_id} not found.",
        )

    # Guard email uniqueness
    if user_in.email and user_in.email != target.email:
        taken = repository.get_user_by_email(db, user_in.email)
        if taken:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email is already in use by another account.",
            )

    update_data = user_in.model_dump(exclude_unset=True)
    updated = repository.update_user(db, user_id, update_data)
    return updated  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------

def delete_user(db: Session, user_id: int) -> None:
    """
    Delete a user account.

    Raises:
        404 Not Found — if no user matches user_id.
    """
    deleted = repository.delete_user(db, user_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with id={user_id} not found.",
        )


# ---------------------------------------------------------------------------
# Activity Logs (admin view + internal logging helper)
# ---------------------------------------------------------------------------

def get_activity_logs(db, user_id=None, action=None, limit=100, offset=0):
    return repository.get_activity_logs(db, user_id, action, limit, offset)


def count_activity_logs(db, user_id=None, action=None):
    return repository.count_activity_logs(db, user_id, action)


def record_activity(
    db,
    user_id: int,
    action: str,
    target_type: str | None = None,
    target_id: int | None = None,
    details: dict | None = None,
    ip_address: str | None = None,
):
    """Internal helper used by other modules."""
    # Also write to the simple core logger (which does its own commit)
    log_activity(db, user_id, action, target_type, target_id, details, ip_address)
    # Fallback direct if needed
    try:
        repository.create_activity_log(
            db, user_id, action, target_type, target_id, details, ip_address
        )
    except Exception:
        pass  # already logged via core


# ---------------------------------------------------------------------------
# Google OAuth
# ---------------------------------------------------------------------------

def authenticate_with_google(db: Session, google_id_token: str) -> User:
    """
    Verify Google ID token, find or create user, and return the user.

    This implements "Sign in with Google" using OAuth2 ID tokens.
    """
    try:
        google_user = verify_google_token(google_id_token)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid Google token: {str(e)}",
        )

    email = google_user.get("email")
    google_id = google_user.get("sub")  # Google's unique user ID

    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google account has no email address.",
        )

    # Try to find existing user by email
    user = repository.get_user_by_email(db, email)

    if user:
        # User exists — allow login (even if they originally registered with password)
        # Optionally store google_id if not present (for future linking)
        # For now we just log them in.
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is deactivated.",
            )
        return user

    # New user — create account with Google
    # No password_hash for pure Google users
    user = repository.create_user(
        db,
        email=email,
        password_hash=None,
        role="viewer",  # default role for Google sign-ups
    )

    # You could store google_id on the user model if you extend it later.
    return user
