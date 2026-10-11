"""
models/activity_log.py
----------------------
SQLAlchemy ORM for user activity logs (visible only to admins).
"""

from datetime import datetime, timezone

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import declarative_base, relationship

from app.models.user import Base  # reuse the same Base

class UserActivityLog(Base):
    __tablename__ = "user_activity_logs"

    log_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True)
    action = Column(String(100), nullable=False, index=True)       # login, create_land, export_land, etc.
    target_type = Column(String(50))                               # land, user, etc.
    target_id = Column(Integer)
    details = Column(JSON)                                         # extra context
    ip_address = Column(String(45))
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Optional relationship (lazy)
    # user = relationship("User", backref="activity_logs")

    def __repr__(self):
        return f"<UserActivityLog id={self.log_id} user={self.user_id} action={self.action}>"