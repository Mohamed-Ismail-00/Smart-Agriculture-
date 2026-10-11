"""
models/ai_chat.py
-----------------
Stores per-land AI chat sessions and individual messages.
Each land can have one active chat session per user.
"""

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text

from app.models.user import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AiChatSession(Base):
    __tablename__ = "ai_chat_sessions"

    session_id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    land_id = Column(Integer, ForeignKey("lands.land_id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=True, index=True)
    title = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=_utcnow, nullable=False)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow, nullable=False)


class AiChatMessage(Base):
    __tablename__ = "ai_chat_messages"

    message_id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    session_id = Column(Integer, ForeignKey("ai_chat_sessions.session_id"), nullable=False, index=True)
    # 'user' | 'assistant'
    role = Column(String(32), nullable=False)
    content = Column(Text, nullable=False)
    # How many input/output tokens were used (for monitoring)
    tokens_used = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=_utcnow, nullable=False)
