"""
core/activity.py
----------------
Lightweight activity logging for user actions.
Only admins can view these logs via the dedicated API.
"""

from typing import Optional

from sqlalchemy.orm import Session

from app.models.activity_log import UserActivityLog


def log_activity(
    db: Session,
    user_id: int,
    action: str,
    target_type: Optional[str] = None,
    target_id: Optional[int] = None,
    details: Optional[dict] = None,
    ip_address: Optional[str] = None,
) -> None:
    """
    Record a user activity. This is fire-and-forget style.
    Call this from services or API routes for important actions.
    """
    try:
        entry = UserActivityLog(
            user_id=user_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            details=details or {},
            ip_address=ip_address,
        )
        db.add(entry)
        db.commit()
    except Exception:
        # Never let logging break the main flow
        db.rollback()
