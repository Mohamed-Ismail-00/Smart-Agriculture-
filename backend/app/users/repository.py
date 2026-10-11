"""
users/repository.py
-------------------
Pure database queries for the users domain.

Rules (from architecture docs):
- NO business logic here — only SQLAlchemy queries.
- NO HTTP imports (no FastAPI, no status codes).
- Receives db session from caller (injected by dependencies.py).
"""

from typing import Optional

from sqlalchemy.orm import Session

from app.models.user import User


def get_user_by_email(db: Session, email: str) -> Optional[User]:
    """Return the User with the given email, or None if not found."""
    return db.query(User).filter(User.email == email).first()


def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
    """Return the User with the given ID, or None if not found."""
    return db.query(User).filter(User.user_id == user_id).first()


def get_all_users(db: Session) -> list[User]:
    """Return all users ordered by creation date (newest first)."""
    return db.query(User).order_by(User.created_at.desc()).all()


def create_user(db: Session, email: str, password_hash: str | None = None, role: str = "viewer") -> User:
    """
    Persist a new user record.

    Args:
        db: active database session.
        email: unique user email.
        password_hash: pre-hashed password, or None for Google-only users.
        role: one of admin | analyst | viewer.

    Returns:
        The newly created User ORM object (with user_id populated).
    """
    user = User(email=email, password_hash=password_hash, role=role)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def update_user(db: Session, user_id: int, data: dict) -> Optional[User]:
    """
    Update allowed fields on an existing user.

    Args:
        db: active database session.
        user_id: target user.
        data: dict of fields to update (keys must match User column names).

    Returns:
        Updated User object, or None if user_id not found.
    """
    user = get_user_by_id(db, user_id)
    if user is None:
        return None
    for field, value in data.items():
        if value is not None:
            setattr(user, field, value)
    db.commit()
    db.refresh(user)
    return user


def delete_user(db: Session, user_id: int) -> bool:
    """
    Delete a user record.

    Returns:
        True if deleted, False if user_id was not found.
    """
    user = get_user_by_id(db, user_id)
    if user is None:
        return False
    db.delete(user)
    db.commit()
    return True


# ---------------------------------------------------------------------------
# Activity Logs (admin only)
# ---------------------------------------------------------------------------

from app.models.activity_log import UserActivityLog


def get_activity_logs(
    db: Session,
    user_id: Optional[int] = None,
    action: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> list[UserActivityLog]:
    q = db.query(UserActivityLog)
    if user_id is not None:
        q = q.filter(UserActivityLog.user_id == user_id)
    if action:
        q = q.filter(UserActivityLog.action == action)
    return (
        q.order_by(UserActivityLog.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


def count_activity_logs(
    db: Session, user_id: Optional[int] = None, action: Optional[str] = None
) -> int:
    q = db.query(UserActivityLog)
    if user_id is not None:
        q = q.filter(UserActivityLog.user_id == user_id)
    if action:
        q = q.filter(UserActivityLog.action == action)
    return q.count()


def create_activity_log(
    db: Session,
    user_id: int,
    action: str,
    target_type: Optional[str] = None,
    target_id: Optional[int] = None,
    details: Optional[dict] = None,
    ip_address: Optional[str] = None,
) -> UserActivityLog:
    log = UserActivityLog(
        user_id=user_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        details=details or {},
        ip_address=ip_address,
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log
