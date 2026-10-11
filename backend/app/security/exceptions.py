"""
exceptions.py
-------------
Security-aware exceptions that avoid leaking information.

Using `ResourceNotFoundOrForbidden` instead of separate 404/403 prevents
attackers from determining whether a resource exists.
"""

from fastapi import HTTPException, status

class SecurityException(HTTPException):
    """Base security exception."""
    pass

class UnauthorizedException(SecurityException):
    def __init__(self, detail: str = "Authentication required"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )

class ForbiddenException(SecurityException):
    def __init__(self, detail: str = "Insufficient permissions"):
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail=detail)

class ResourceNotFoundOrForbidden(SecurityException):
    """
    Use this for any case where the user might be trying to access
    a resource they don't own.

    Always returns 404 to avoid ID enumeration attacks.
    """
    def __init__(self, detail: str = "Resource not found"):
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=detail)
