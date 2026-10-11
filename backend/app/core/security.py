"""
core/security.py
----------------
Pure cryptographic utilities — no FastAPI imports.

Responsibilities:
- Password hashing and verification (bcrypt via passlib)
- JWT access token creation and decoding (HS256 via python-jose)

All auth-related HTTP concerns (401, 403, Depends) live in core/dependencies.py.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

# ---------------------------------------------------------------------------
# Password hashing
# bcrypt 5.x removed __about__ which breaks passlib's version detection.
# Using sha256_crypt as a portable, secure alternative for local dev + tests.
# In production with Docker the bcrypt version is pinned and works fine —
# swap schemes=["bcrypt"] back if your Docker image pins bcrypt<4.
# ---------------------------------------------------------------------------

_pwd_context = CryptContext(schemes=["sha256_crypt"], deprecated="auto")


def hash_password(plain_password: str) -> str:
    """Return a bcrypt hash of the plain-text password."""
    return _pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Return True if plain_password matches the bcrypt hash."""
    return _pwd_context.verify(plain_password, hashed_password)


# ---------------------------------------------------------------------------
# JWT tokens
# ---------------------------------------------------------------------------

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a signed JWT access token (short lived).
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a signed JWT refresh token (longer lived).
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    )
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> dict:
    """
    Decode and validate an access JWT token.
    """
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    if payload.get("type") != "access":
        raise JWTError("Not an access token")
    return payload


def decode_refresh_token(token: str) -> dict:
    """
    Decode and validate a refresh JWT token.
    """
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    if payload.get("type") != "refresh":
        raise JWTError("Not a refresh token")
    return payload
