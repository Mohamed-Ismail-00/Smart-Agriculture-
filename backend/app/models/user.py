"""
models/user.py
--------------
SQLAlchemy ORM definition for the `users` table.

Schema:
  user_id       INT PK (SERIAL in PostgreSQL)
  email         VARCHAR(255) UNIQUE NOT NULL
  password_hash VARCHAR(255) NOT NULL
  role          VARCHAR(50) NOT NULL (admin | analyst | viewer)
  is_active     BOOLEAN DEFAULT TRUE
  created_at    TIMESTAMP
  updated_at    TIMESTAMP
"""

from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Integer, String
from sqlalchemy.orm import declarative_base

Base = declarative_base()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    user_id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    # password_hash can be NULL for users who only sign in with Google
    password_hash = Column(String(255), nullable=True)
    role = Column(String(50), nullable=False, default="viewer")
    is_active = Column(Boolean, nullable=False, default=True)
    is_deleted = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, default=_utcnow, nullable=False)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow, nullable=False)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<User id={self.user_id} email={self.email} role={self.role}>"
