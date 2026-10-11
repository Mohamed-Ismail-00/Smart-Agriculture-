"""
app/ai/groq_client.py
----------------------
Groq API client wrapper with automatic key fallback.

When a key hits quota (HTTP 429) or is invalid (HTTP 401), the manager marks
it as exceeded and tries the next key in the pool automatically.

Usage:
    from app.ai.groq_client import GroqClient
    client = GroqClient(db, user_id)
    response = client.chat([{"role": "user", "content": "Hello"}])
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import httpx
from sqlalchemy.orm import Session

from app.models.ai_settings import AiApiKey
from app.security.encryption import decrypt_string

logger = logging.getLogger(__name__)

GROQ_API_BASE = "https://api.groq.com/openai/v1"
GROQ_MODEL = "llama-3.3-70b-versatile"
QUOTA_RETRY_AFTER_HOURS = 1  # re-try quota-exceeded keys after 1 hour


class GroqClient:
    """
    Smart Groq client that rotates through the user's API key pool
    automatically when a key hits its rate limit.
    """

    def __init__(self, db: Session, user_id: int, timeout: float = 60.0) -> None:
        self.db = db
        self.user_id = user_id
        self.timeout = timeout

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def chat(
        self,
        messages: list[dict[str, Any]],
        model: str = GROQ_MODEL,
        max_tokens: int = 1024,
        temperature: float = 0.3,
    ) -> Optional[dict[str, Any]]:
        """
        Send a chat-completion request to Groq.

        Returns the parsed response dict on success, or None if all keys are exhausted.
        Automatically upgrades to `llama-3.2-90b-vision-preview` if multimodal image data is detected.
        """
        # Detect if this is a vision request
        has_vision = False
        for msg in messages:
            if isinstance(msg.get("content"), list):
                for item in msg["content"]:
                    if isinstance(item, dict) and item.get("type") == "image_url":
                        has_vision = True
                        break
        
        if has_vision and model == GROQ_MODEL:
            model = "llama-3.2-11b-vision-preview"

        keys = self._get_active_keys()
        if not keys:
            logger.warning("No active Groq API keys available for user_id=%s", self.user_id)
            return None

        for key_row in keys:
            result = self._try_key(key_row, messages, model, max_tokens, temperature)
            if result is not None:
                return result
            # Try next key

        logger.error("All Groq API keys exhausted for user_id=%s", self.user_id)
        return None

    def get_key_pool_status(self) -> list[dict]:
        """Return status of all keys for the settings UI."""
        keys = (
            self.db.query(AiApiKey)
            .filter(AiApiKey.user_id == self.user_id)
            .order_by(AiApiKey.sort_order.asc())
            .all()
        )
        result = []
        for k in keys:
            decrypted = decrypt_string(k.api_key) if k.api_key else ""
            result.append({
                "key_id": k.key_id,
                "label": k.label or f"Key #{k.key_id}",
                "provider": k.provider,
                "is_active": k.is_active,
                "quota_exceeded": k.quota_exceeded,
                "quota_reset_at": k.quota_reset_at.isoformat() if k.quota_reset_at else None,
                "sort_order": k.sort_order,
                "key_preview": f"...{decrypted[-6:]}" if len(decrypted) > 6 else "******",
            })
        return result

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _get_active_keys(self) -> list[AiApiKey]:
        """Return active, non-quota-exceeded keys; auto-reset keys whose cooldown has passed."""
        now = datetime.now(timezone.utc)
        keys = (
            self.db.query(AiApiKey)
            .filter(
                AiApiKey.user_id == self.user_id,
                AiApiKey.is_active == True,  # noqa: E712
            )
            .order_by(AiApiKey.sort_order.asc())
            .all()
        )

        available = []
        for k in keys:
            if k.quota_exceeded:
                # Auto-reset if cooldown has passed
                if k.quota_reset_at and k.quota_reset_at.replace(tzinfo=timezone.utc) <= now:
                    k.quota_exceeded = False
                    k.quota_reset_at = None
                    self.db.add(k)
                    self.db.flush()
                    
                    available.append(k)
            else:
                available.append(k)

        return available

    def _try_key(
        self,
        key_row: AiApiKey,
        messages: list[dict],
        model: str,
        max_tokens: int,
        temperature: float,
    ) -> Optional[dict[str, Any]]:
        """
        Attempt a request with a specific API key.
        Marks the key as quota-exceeded on 429/401 and returns None so the caller retries.
        """
        plain_key = decrypt_string(key_row.api_key) if key_row.api_key else ""
        headers = {
            "Authorization": f"Bearer {plain_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(f"{GROQ_API_BASE}/chat/completions", json=payload, headers=headers)

            if resp.status_code == 200:
                return resp.json()

            if resp.status_code in (429,):
                logger.warning(
                    "Groq key_id=%s returned %s (quota) — marking exceeded and trying next key.",
                    key_row.key_id, resp.status_code,
                )
                key_row.quota_exceeded = True
                key_row.quota_reset_at = datetime.now(timezone.utc) + timedelta(hours=QUOTA_RETRY_AFTER_HOURS)
                self.db.add(key_row)
                self.db.flush()
                return None

            if resp.status_code in (401, 403):
                # Invalid / wrong key — deactivate it so user knows to fix it
                logger.warning(
                    "Groq key_id=%s returned %s (invalid key) — deactivating: %s",
                    key_row.key_id, resp.status_code, resp.text[:200],
                )
                key_row.is_active = False
                key_row.label = (key_row.label or "") + " [INVALID KEY]"
                self.db.add(key_row)
                self.db.flush()
                return None
                
            if resp.status_code == 400:
                try:
                    error_code = resp.json().get("error", {}).get("code")
                    if error_code in ("organization_restricted", "invalid_api_key"):
                        logger.warning("Groq key_id=%s is restricted or invalid.", key_row.key_id)
                        key_row.is_active = False
                        key_row.label = (key_row.label or "") + " [RESTRICTED]"
                        self.db.add(key_row)
                        self.db.flush()
                        return None
                except Exception:
                    pass

                # Application error (e.g. bad payload, model unavailable, context too large)
                # DO NOT deactivate the key for this unless it's a known restriction.
                logger.error(
                    "Groq key_id=%s returned 400 Bad Request: %s",
                    key_row.key_id, resp.text[:500],
                )
                return None

        except httpx.TimeoutException:
            logger.warning("Groq request timed out for key_id=%s", key_row.key_id)
            return None
        except httpx.RequestError as exc:
            logger.warning("Groq network error for key_id=%s: %s", key_row.key_id, exc)
            return None
