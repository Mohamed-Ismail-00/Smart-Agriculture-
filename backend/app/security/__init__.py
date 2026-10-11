"""
Security package - centralized protection against common attacks.

Import everything you need from here:
    from app.security import (
        get_current_user,
        require_land_access,
        generate_public_id,
        SecurityHeadersMiddleware,
        log_security_event,
    )
"""

from .auth import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
    decode_refresh_token,
    get_current_active_user,
    get_current_user,
)
from .audit import log_security_event
from .exceptions import (
    ForbiddenException,
    ResourceNotFoundOrForbidden,
    SecurityException,
    UnauthorizedException,
)
from .middleware import RateLimitMiddleware, SecurityHeadersMiddleware
from .permissions import require_admin, require_land_access, require_role
from .public_ids import generate_public_id, get_by_public_id, get_land_by_public_id
from .validators import SecureString, sanitize_string

__all__ = [
    # Authentication
    "get_current_user",
    "get_current_active_user",
    "create_access_token",
    "create_refresh_token",
    "decode_access_token",
    "decode_refresh_token",
    # Authorization
    "require_land_access",
    "require_role",
    "require_admin",
    # ID Protection
    "generate_public_id",
    "get_by_public_id",
    "get_land_by_public_id",
    # Middleware
    "SecurityHeadersMiddleware",
    "RateLimitMiddleware",
    # Audit & Logging
    "log_security_event",
    # Input Validation
    "sanitize_string",
    "SecureString",
    # Exceptions (safe responses)
    "SecurityException",
    "UnauthorizedException",
    "ForbiddenException",
    "ResourceNotFoundOrForbidden",
]
