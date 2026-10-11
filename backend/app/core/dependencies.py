"""
core/dependencies.py
--------------------
Reusable FastAPI dependency functions (Depends).

Used by protected API endpoints to:
- Provide a DB session per request (get_db)
- Extract and validate the current user from JWT (get_current_user)
- Enforce admin-level access (require_admin)

Pattern:
    @router.get("/protected")
    def endpoint(user = Depends(get_current_user)):
        ...
"""

from typing import Generator, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.orm import Session

from app.core import security
from app.db.session import SessionLocal
from app.models.user import User
from app.users import repository

# OAuth2 scheme — reads the Bearer token from the Authorization header.
# tokenUrl is the login endpoint (used by Swagger UI's "Authorize" button).
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")
oauth2_scheme_optional = OAuth2PasswordBearer(
    tokenUrl="/api/v1/auth/login",
    auto_error=False,
)


# ---------------------------------------------------------------------------
# Database session
# ---------------------------------------------------------------------------

def get_db() -> Generator[Session, None, None]:
    """
    Yield a SQLAlchemy session and guarantee it is closed after the request,
    even if an exception occurs.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Auth guards
# ---------------------------------------------------------------------------

def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    Decode the JWT token and return the matching User.

    Raises:
        401 Unauthorized — invalid token, expired token, or user not found.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = security.decode_access_token(token)
        user_id: str = payload.get("sub")  # type: ignore[assignment]
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = repository.get_user_by_id(db, int(user_id))
    if user is None:
        raise credentials_exception
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated.",
        )
    return user


def get_current_user_optional(
    token: Optional[str] = Depends(oauth2_scheme_optional),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """Return the authenticated user, or None if no Bearer token was provided."""
    if not token:
        return None
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = security.decode_access_token(token)
        user_id: str = payload.get("sub")  # type: ignore[assignment]
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = repository.get_user_by_id(db, int(user_id))
    if user is None:
        raise credentials_exception
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated.",
        )
    return user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """
    Extension of get_current_user that additionally requires admin role.

    Raises:
        403 Forbidden — if the authenticated user is not an admin.
    """
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required.",
        )
    return current_user
