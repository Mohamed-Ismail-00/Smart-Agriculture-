"""
app/api/ai.py
--------------
AI endpoints:
  POST   /ai/keys                      — add a Groq API key
  GET    /ai/keys                      — list user's keys (masked)
  DELETE /ai/keys/{key_id}             — remove a key
  PATCH  /ai/keys/{key_id}/toggle      — enable/disable a key
  
  GET    /ai/lands/{land_id}/chat      — get chat history for a land
  POST   /ai/lands/{land_id}/chat      — send a message to AI
  DELETE /ai/lands/{land_id}/chat      — clear chat history
  
  GET    /ai/lands/{land_id}/insights  — get stored AI insights
  POST   /ai/lands/{land_id}/analyze   — trigger a fresh AI analysis
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, get_db
from app.models.user import User
from app.security import require_land_access
from app.ai import repository as ai_repo
from app.ai.groq_client import GroqClient
from app.ai.land_analyst import build_chat_system_message, run_ai_land_analysis

logger = logging.getLogger(__name__)
router = APIRouter(tags=["ai"])


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class AddKeyRequest(BaseModel):
    api_key: str
    label: Optional[str] = None
    provider: str = "groq"


class ChatMessageRequest(BaseModel):
    message: str


class ToggleKeyRequest(BaseModel):
    is_active: bool


# ---------------------------------------------------------------------------
# API Key Management
# ---------------------------------------------------------------------------

@router.get("/ai/keys")
def list_api_keys(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return all API keys (masked) for the current user."""
    client = GroqClient(db, current_user.user_id)
    return {"keys": client.get_key_pool_status()}


@router.post("/ai/keys", status_code=status.HTTP_201_CREATED)
def add_api_key(
    body: AddKeyRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Add a new Groq API key for the current user."""
    api_key = body.api_key.strip()
    
    # Validate key format — Groq keys start with 'gsk_' and are at least 40 chars
    if not api_key:
        raise HTTPException(status_code=400, detail="API key cannot be empty.")
    if len(api_key) < 20:
        raise HTTPException(status_code=400, detail="API key is too short to be valid.")
    if body.provider == "groq" and not api_key.startswith("gsk_"):
        raise HTTPException(
            status_code=400, 
            detail="Groq API keys must start with 'gsk_'. Please check your key and try again."
        )
    
    row = ai_repo.create_key(
        db,
        user_id=current_user.user_id,
        api_key=api_key,
        label=body.label,
        provider=body.provider,
    )
    return {"key_id": row.key_id, "label": row.label, "message": "API key added successfully."}


@router.delete("/ai/keys/{key_id}", status_code=status.HTTP_200_OK)
def delete_api_key(
    key_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a specific API key."""
    deleted = ai_repo.delete_key(db, key_id=key_id, user_id=current_user.user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="API key not found.")
    return {"message": "API key deleted."}


@router.patch("/ai/keys/{key_id}/toggle")
def toggle_api_key(
    key_id: int,
    body: ToggleKeyRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Enable or disable a specific API key."""
    row = ai_repo.toggle_key(db, key_id=key_id, user_id=current_user.user_id, is_active=body.is_active)
    if not row:
        raise HTTPException(status_code=404, detail="API key not found.")
    return {"key_id": row.key_id, "is_active": row.is_active}


# ---------------------------------------------------------------------------
# AI Chat Endpoints
# ---------------------------------------------------------------------------

@router.get("/ai/lands/{public_id}/chat")
def get_chat_history(
    public_id: str,
    land = Depends(require_land_access),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve the full chat history for a land."""
    session = ai_repo.get_or_create_session(db, land_id=land.land_id, user_id=current_user.user_id)
    messages = ai_repo.list_messages(db, session_id=session.session_id)
    return {
        "session_id": session.session_id,
        "land_id": land.land_id,
        "messages": [
            {
                "message_id": m.message_id,
                "role": m.role,
                "content": m.content,
                "created_at": m.created_at.isoformat(),
            }
            for m in messages
        ],
    }


@router.post("/ai/lands/{public_id}/chat")
def send_chat_message(
    public_id: str,
    body: ChatMessageRequest,
    land = Depends(require_land_access),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Send a message to the AI about a specific land.
    Stores both user message and AI reply in the database.
    """
    if not body.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    # Get or create session
    session = ai_repo.get_or_create_session(db, land_id=land.land_id, user_id=current_user.user_id)

    # Store user message
    ai_repo.add_message(db, session_id=session.session_id, role="user", content=body.message)

    # Build conversation history for Groq (last 20 messages for context)
    history = ai_repo.list_messages(db, session_id=session.session_id)
    conversation_messages = [
        {"role": "system", "content": build_chat_system_message(land.land_id, db)}
    ]
    for m in history[-20:]:
        conversation_messages.append({"role": m.role, "content": m.content})

    # Query Groq
    client = GroqClient(db, current_user.user_id)
    response = client.chat(conversation_messages, max_tokens=1024, temperature=0.4)

    if not response:
        # No keys available
        raise HTTPException(
            status_code=503,
            detail="AI service unavailable. Please add a valid Groq API key in your profile settings."
        )

    try:
        reply_content = response["choices"][0]["message"]["content"]
        tokens_used = response.get("usage", {}).get("total_tokens")
    except (KeyError, IndexError) as exc:
        logger.error("Unexpected Groq response format: %s", exc)
        raise HTTPException(status_code=502, detail="Unexpected response from AI service.")

    # Store AI reply
    reply_msg = ai_repo.add_message(
        db,
        session_id=session.session_id,
        role="assistant",
        content=reply_content,
        tokens_used=tokens_used,
    )

    return {
        "session_id": session.session_id,
        "message_id": reply_msg.message_id,
        "role": "assistant",
        "content": reply_content,
        "tokens_used": tokens_used,
    }


@router.delete("/ai/lands/{public_id}/chat")
def clear_chat_history(
    public_id: str,
    land = Depends(require_land_access),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Clear all messages in the chat session for this land."""
    session = ai_repo.get_or_create_session(db, land_id=land.land_id, user_id=current_user.user_id)
    ai_repo.clear_session(db, session_id=session.session_id, user_id=current_user.user_id)
    return {"message": "Chat history cleared."}


# ---------------------------------------------------------------------------
# AI Insights Endpoints
# ---------------------------------------------------------------------------

@router.get("/ai/lands/{public_id}/insights")
def get_ai_insights(
    public_id: str,
    land = Depends(require_land_access),
    db: Session = Depends(get_db),
):
    """Get all AI-generated insights for a land (no auth required to read)."""
    insights = ai_repo.get_insights_for_land(db, land_id=land.land_id)
    return {
        "land_id": land.land_id,
        "insights": [
            {
                "insight_id": ins.insight_id,
                "insight_type": ins.insight_type,
                "title": ins.title,
                "body": ins.body,
                "structured_data": ins.structured_data,
                "confidence": ins.confidence,
                "model_used": ins.model_used,
                "created_at": ins.created_at.isoformat(),
            }
            for ins in insights
        ],
    }


@router.post("/ai/lands/{public_id}/analyze")
def trigger_ai_analysis(
    public_id: str,
    land = Depends(require_land_access),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Trigger a fresh AI analysis for a land synchronously."""
    insights = run_ai_land_analysis(land_id=land.land_id, db=db, user_id=current_user.user_id)
    if not insights:
        # Check if they have active keys to give a better error message
        client = GroqClient(db, current_user.user_id)
        keys = client.get_key_pool_status()
        active_keys = [k for k in keys if k["is_active"] and not k["quota_exceeded"]]
        
        if not keys:
            detail = "No AI API keys configured. Please add one in Settings."
        elif not active_keys:
            detail = "All AI API keys are currently restricted, invalid, or have exceeded their quota. Please check your AI Settings."
        else:
            detail = "AI analysis failed or returned no insights. The data might be insufficient."
            
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=detail)
        
    return {"message": "AI analysis complete.", "insights": True}


# ---------------------------------------------------------------------------
# AI Status Endpoint
# ---------------------------------------------------------------------------

@router.get("/ai/status")
def get_ai_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Return AI system health status for the current user:
    - Key pool availability
    - Count of active/quota-exceeded keys  
    - Last AI analysis timestamp across all user's lands
    """
    client = GroqClient(db, current_user.user_id)
    keys = client.get_key_pool_status()
    
    active_keys = [k for k in keys if k["is_active"] and not k["quota_exceeded"]]
    quota_exceeded_keys = [k for k in keys if k["quota_exceeded"]]
    
    # Find most recent AI insight across all user's lands
    from app.models.land import Land
    from app.models.land_ai_insight import LandAiInsight
    
    user_land_ids = [
        r[0] for r in db.query(Land.land_id).filter(Land.user_id == current_user.user_id).all()
    ]
    
    last_insight = None
    if user_land_ids:
        last = (
            db.query(LandAiInsight)
            .filter(LandAiInsight.land_id.in_(user_land_ids))
            .order_by(LandAiInsight.created_at.desc())
            .first()
        )
        if last:
            last_insight = last.created_at.isoformat()
    
    ai_available = len(active_keys) > 0
    
    return {
        "ai_available": ai_available,
        "total_keys": len(keys),
        "active_keys": len(active_keys),
        "quota_exceeded_keys": len(quota_exceeded_keys),
        "last_analysis_at": last_insight,
        "status": "ready" if ai_available else ("quota_exceeded" if keys else "no_keys"),
    }


# ---------------------------------------------------------------------------
# Async AI Analysis (background task + notification)
# ---------------------------------------------------------------------------

def _run_analysis_background(
    land_id: int,
    user_id: int,
    land_public_id: str,
) -> None:
    """
    Background worker: runs AI analysis and creates a LandAlert notification
    when complete so the frontend bell rings.

    NOTE: Creates its own DB session because FastAPI closes the request session
    before background tasks run (DetachedInstanceError otherwise).
    """
    from app.db.session import SessionLocal
    db = SessionLocal()
    try:
        insights = run_ai_land_analysis(land_id=land_id, db=db, user_id=user_id)

        # Create completion notification
        from app.models.land_alert import LandAlert
        if insights:
            alert = LandAlert(
                land_id=land_id,
                user_id=user_id,
                alert_type="ai_analysis_complete",
                severity="low",
                message=f"AI analysis complete: {len(insights)} fresh insights generated.",
                payload={"insight_count": len(insights), "public_id": land_public_id},
                is_read=False,
            )
        else:
            alert = LandAlert(
                land_id=land_id,
                user_id=user_id,
                alert_type="ai_analysis_failed",
                severity="medium",
                message="AI analysis could not complete. Check your API key pool.",
                payload={"public_id": land_public_id},
                is_read=False,
            )
        db.add(alert)
        db.commit()
    except Exception as exc:
        logger.exception("Background AI analysis failed for land_id=%s: %s", land_id, exc)
    finally:
        db.close()


@router.post("/ai/lands/{public_id}/analyze-async", status_code=status.HTTP_202_ACCEPTED)
def trigger_ai_analysis_async(
    public_id: str,
    background_tasks: BackgroundTasks,
    land = Depends(require_land_access),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Trigger AI analysis in the background.
    Returns immediately with 202 Accepted.
    A LandAlert notification is created when complete (visible in bell).
    """
    background_tasks.add_task(
        _run_analysis_background,
        land_id=land.land_id,
        user_id=current_user.user_id,
        land_public_id=public_id,
    )
    return {"message": "AI analysis started in background. You will be notified when complete.", "status": "accepted"}
