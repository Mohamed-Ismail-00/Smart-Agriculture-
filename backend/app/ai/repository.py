"""
app/ai/repository.py
---------------------
Database CRUD operations for AI tables.
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from app.models.ai_settings import AiApiKey
from app.models.ai_chat import AiChatSession, AiChatMessage
from app.models.land_ai_insight import LandAiInsight


from app.security.encryption import encrypt_string, decrypt_string

# ---------------------------------------------------------------------------
# API Key CRUD
# ---------------------------------------------------------------------------

def get_keys_for_user(db: Session, user_id: int) -> list[AiApiKey]:
    keys = (
        db.query(AiApiKey)
        .filter(AiApiKey.user_id == user_id)
        .order_by(AiApiKey.sort_order.asc(), AiApiKey.key_id.asc())
        .all()
    )
    # Decrypt in memory (do not commit!)
    for k in keys:
        if k.api_key:
            k.api_key = decrypt_string(k.api_key)
    return keys


def create_key(db: Session, user_id: int, api_key: str, label: Optional[str] = None, provider: str = "groq") -> AiApiKey:
    # Set sort_order to max + 1
    max_order = db.query(AiApiKey).filter(AiApiKey.user_id == user_id).count()
    
    # Encrypt the key at rest
    encrypted_key = encrypt_string(api_key)
    
    row = AiApiKey(
        user_id=user_id,
        api_key=encrypted_key,
        label=label,
        provider=provider,
        sort_order=max_order,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    
    # Decrypt for the returned object
    row.api_key = decrypt_string(row.api_key)
    return row


def delete_key(db: Session, key_id: int, user_id: int) -> bool:
    row = db.query(AiApiKey).filter(AiApiKey.key_id == key_id, AiApiKey.user_id == user_id).first()
    if not row:
        return False
    db.delete(row)
    db.commit()
    return True


def toggle_key(db: Session, key_id: int, user_id: int, is_active: bool) -> Optional[AiApiKey]:
    row = db.query(AiApiKey).filter(AiApiKey.key_id == key_id, AiApiKey.user_id == user_id).first()
    if not row:
        return None
    row.is_active = is_active
    row.quota_exceeded = False  # reset on toggle
    db.commit()
    db.refresh(row)
    return row


# ---------------------------------------------------------------------------
# Chat CRUD
# ---------------------------------------------------------------------------

def get_or_create_session(db: Session, land_id: int, user_id: Optional[int]) -> AiChatSession:
    """Get the most recent session for this land/user pair, or create one."""
    session = (
        db.query(AiChatSession)
        .filter(AiChatSession.land_id == land_id, AiChatSession.user_id == user_id)
        .order_by(AiChatSession.created_at.desc())
        .first()
    )
    if not session:
        session = AiChatSession(land_id=land_id, user_id=user_id)
        db.add(session)
        db.commit()
        db.refresh(session)
    return session


def list_messages(db: Session, session_id: int) -> list[AiChatMessage]:
    return (
        db.query(AiChatMessage)
        .filter(AiChatMessage.session_id == session_id)
        .order_by(AiChatMessage.created_at.asc())
        .all()
    )


def add_message(db: Session, session_id: int, role: str, content: str, tokens_used: Optional[int] = None) -> AiChatMessage:
    msg = AiChatMessage(session_id=session_id, role=role, content=content, tokens_used=tokens_used)
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return msg


def clear_session(db: Session, session_id: int, user_id: Optional[int]) -> bool:
    """Delete all messages in a session (keeps the session itself)."""
    session = db.query(AiChatSession).filter(AiChatSession.session_id == session_id, AiChatSession.user_id == user_id).first()
    if not session:
        return False
    db.query(AiChatMessage).filter(AiChatMessage.session_id == session_id).delete()
    db.commit()
    return True


# ---------------------------------------------------------------------------
# AI Insights CRUD
# ---------------------------------------------------------------------------

def get_insights_for_land(db: Session, land_id: int) -> list[LandAiInsight]:
    return (
        db.query(LandAiInsight)
        .filter(LandAiInsight.land_id == land_id)
        .order_by(LandAiInsight.created_at.desc())
        .all()
    )
