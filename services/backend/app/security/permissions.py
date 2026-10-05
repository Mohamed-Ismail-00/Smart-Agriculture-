"""
permissions.py
--------------
Strong authorization layer to prevent Broken Access Control and IDOR.

Core principle:
- Never trust client-supplied IDs.
- Always verify ownership using public_id + current user.
- Return generic "not found" errors to avoid enumeration.
"""

from typing import Optional

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.lands.repository import get_land_by_public_id
from app.models.land import Land
from app.models.user import User
from app.security.audit import log_security_event
from app.security.auth import get_current_active_user
from app.security.exceptions import ResourceNotFoundOrForbidden

def require_land_access(
    public_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Land:
    """
    Strong ownership check using public UUID.

    Protects against:
    - Insecure Direct Object References (IDOR)
    - ID enumeration attacks
    - Unauthorized access to other users' data

    Always returns 404 on failure (never 403) to avoid leaking existence.
    """
    land = get_land_by_public_id(db, public_id)

    if not land:
        raise ResourceNotFoundOrForbidden()

    if land.user_id != current_user.user_id and current_user.role != "admin":
        log_security_event(
            db=db,
            user_id=current_user.user_id,
            action="unauthorized_land_access_attempt",
            target_type="land",
            target_id=land.land_id,
            details={"public_id": public_id, "user_id": current_user.user_id},
        )
        raise ResourceNotFoundOrForbidden()

    return land

def require_role(required_role: str):
    """Decorator factory for role-based access."""
    def decorator(current_user: User = Depends(get_current_active_user)):
        if current_user.role != required_role and current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This operation requires the '{required_role}' role."
            )
        return current_user
    return decorator

require_admin = require_role("admin")
