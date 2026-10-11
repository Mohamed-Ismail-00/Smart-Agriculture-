"""
app/api/notifications.py
-------------------------
Cross-land notification endpoints for the authenticated user.

Endpoints:
  GET  /notifications          — list recent alerts across all the user's lands
  GET  /notifications/unread-count — returns just the unread badge count
  PATCH /notifications/{id}/read   — mark a single alert as read
  POST  /notifications/read-all    — mark all alerts as read for the current user
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, get_db
from app.models.user import User
from app.models.land_alert import LandAlert
from app.models.land import Land

logger = logging.getLogger(__name__)
router = APIRouter(tags=["notifications"])


# ---------------------------------------------------------------------------
# GET /notifications
# ---------------------------------------------------------------------------

@router.get("/notifications")
def list_notifications(
    limit: int = 20,
    unread_only: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Return recent alerts across ALL lands owned by the current user.
    Sorted newest first. Supports unread_only filter.
    """
    # Get all land_ids owned by this user
    user_land_ids = [
        r[0] for r in db.query(Land.land_id).filter(Land.user_id == current_user.user_id).all()
    ]
    if not user_land_ids:
        return {"data": [], "unread_count": 0}

    query = db.query(LandAlert).filter(LandAlert.land_id.in_(user_land_ids))

    if unread_only:
        query = query.filter(LandAlert.is_read == False)  # noqa: E712

    alerts = (
        query
        .order_by(LandAlert.timestamp.desc())
        .limit(max(1, min(limit, 50)))
        .all()
    )

    unread_count = (
        db.query(LandAlert)
        .filter(LandAlert.land_id.in_(user_land_ids), LandAlert.is_read == False)  # noqa: E712
        .count()
    )

    return {
        "data": [
            {
                "id": a.id,
                "land_id": a.land_id,
                "timestamp": a.timestamp.isoformat(),
                "alert_type": a.alert_type,
                "severity": a.severity,
                "message": a.message,
                "payload": a.payload,
                "is_read": a.is_read,
                "resolved_at": a.resolved_at.isoformat() if a.resolved_at else None,
            }
            for a in alerts
        ],
        "unread_count": unread_count,
    }


# ---------------------------------------------------------------------------
# GET /notifications/unread-count
# ---------------------------------------------------------------------------

@router.get("/notifications/unread-count")
def get_unread_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Fast endpoint for polling unread badge count only."""
    user_land_ids = [
        r[0] for r in db.query(Land.land_id).filter(Land.user_id == current_user.user_id).all()
    ]
    count = (
        db.query(LandAlert)
        .filter(LandAlert.land_id.in_(user_land_ids), LandAlert.is_read == False)  # noqa: E712
        .count()
        if user_land_ids else 0
    )
    return {"unread_count": count}


# ---------------------------------------------------------------------------
# PATCH /notifications/{id}/read
# ---------------------------------------------------------------------------

@router.patch("/notifications/{alert_id}/read")
def mark_notification_read(
    alert_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mark a single notification as read (ownership verified)."""
    user_land_ids = [
        r[0] for r in db.query(Land.land_id).filter(Land.user_id == current_user.user_id).all()
    ]
    alert = db.query(LandAlert).filter(
        LandAlert.id == alert_id,
        LandAlert.land_id.in_(user_land_ids),
    ).first()

    if not alert:
        raise HTTPException(status_code=404, detail="Notification not found.")

    alert.is_read = True
    db.commit()
    return {"id": alert_id, "is_read": True}


# ---------------------------------------------------------------------------
# POST /notifications/read-all
# ---------------------------------------------------------------------------

@router.post("/notifications/read-all")
def mark_all_read(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mark all unread notifications as read for the current user."""
    user_land_ids = [
        r[0] for r in db.query(Land.land_id).filter(Land.user_id == current_user.user_id).all()
    ]
    if not user_land_ids:
        return {"updated": 0}

    updated = (
        db.query(LandAlert)
        .filter(LandAlert.land_id.in_(user_land_ids), LandAlert.is_read == False)  # noqa: E712
        .update({"is_read": True}, synchronize_session=False)
    )
    db.commit()
    return {"updated": updated}
