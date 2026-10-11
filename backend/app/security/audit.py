"""
audit.py
--------
Security event logging.

Usage:
    from app.security import log_security_event

    log_security_event(
        db,
        user_id=current_user.user_id,
        action="land_access_denied",
        details={"public_id": public_id}
    )
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.models.activity_log import UserActivityLog  # reuse existing activity log table

def log_security_event(
    db: Session,
    user_id: Optional[int],
    action: str,
    target_type: str = "security",
    target_id: Optional[int] = None,
    details: Optional[dict] = None,
    ip_address: Optional[str] = None,
):
    """Log security-relevant events for audit purposes."""
    log = UserActivityLog(
        user_id=user_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        details=details or {},
        ip_address=ip_address,
        created_at=datetime.now(timezone.utc),
    )
    db.add(log)
    db.commit()
    # In production: also send to external SIEM / logging service
