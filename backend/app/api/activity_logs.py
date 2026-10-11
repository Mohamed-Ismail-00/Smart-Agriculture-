"""
api/activity_logs.py
--------------------
Admin-only endpoints for viewing real user activity logs.
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.dependencies import get_db, require_admin
from app.models.user import User
from app.users import service as user_service  # for activity log queries we'll add

router = APIRouter(prefix="/activity-logs", tags=["Activity Logs (Admin)"])


@router.get(
    "",
    summary="List user activity logs (admin only)",
)
def list_activity_logs(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
    user_id: Optional[int] = Query(None, description="Filter by specific user"),
    action: Optional[str] = Query(None, description="Filter by action type"),
    limit: int = Query(100, le=500),
    offset: int = Query(0),
):
    """
    Returns recent user activities. Only admins can access this.
    """
    logs = user_service.get_activity_logs(
        db, user_id=user_id, action=action, limit=limit, offset=offset
    )
    total = user_service.count_activity_logs(db, user_id=user_id, action=action)

    return {
        "status": "success",
        "data": [
            {
                "log_id": log.log_id,
                "user_id": log.user_id,
                "action": log.action,
                "target_type": log.target_type,
                "target_id": log.target_id,
                "details": log.details,
                "ip_address": log.ip_address,
                "created_at": log.created_at.isoformat(),
            }
            for log in logs
        ],
        "meta": {
            "total": total,
            "limit": limit,
            "offset": offset,
        },
    }
