"""
core/google_auth.py
-------------------
Google OAuth 2.0 ID token verification for "Sign in with Google".

Accepts one or more Web client IDs (token `aud` claim):
  - GOOGLE_CLIENT_ID          (single ID, or comma-separated list)
  - GOOGLE_CLIENT_IDS         (optional extra comma-separated IDs)

Website GIS and native Android may use different Web client IDs
(e.g. website project vs Firebase project). Both must be listed.
"""

import logging
from typing import Any

from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

from app.core.config import settings

logger = logging.getLogger(__name__)

def _split_ids(raw: str | None) -> list[str]:
    if not raw:
        return []
    out: list[str] = []
    for part in str(raw).replace(";", ",").split(","):
        p = part.strip().strip('"').strip("'")
        if p and p not in out:
            out.append(p)
    return out


def _allowed_client_ids() -> list[str]:
    """All Web client IDs that may appear as the ID-token audience."""
    ids: list[str] = []
    for source in (
        getattr(settings, "GOOGLE_CLIENT_ID", None),
        getattr(settings, "GOOGLE_CLIENT_IDS", None),
    ):
        for cid in _split_ids(source):
            if cid not in ids:
                ids.append(cid)
    return ids


def verify_google_token(token: str) -> dict[str, Any]:
    """
    Verify a Google ID token and return the payload.

    Raises:
        ValueError: if the token is invalid or audience doesn't match.
    """
    request = google_requests.Request()
    allowed = _allowed_client_ids()

    if not allowed:
        # No client ID configured: refuse rather than accept tokens issued for any app.
        raise ValueError("Google sign-in is not configured (GOOGLE_CLIENT_ID is empty)")

    try:
        last_error: Exception | None = None
        for audience in allowed:
            try:
                return id_token.verify_oauth2_token(token, request, audience=audience)
            except ValueError as e:
                last_error = e
                logger.info(
                    "Google token not valid for audience %s…: %s",
                    audience[:24],
                    e,
                )

        # Decode without audience only to report what aud was (still reject if none matched)
        try:
            unverified = id_token.verify_oauth2_token(token, request)
            got_aud = unverified.get("aud")
        except Exception:
            got_aud = None

        msg = (
            f"Invalid Google token: Token has wrong audience {got_aud}, "
            f"expected one of {allowed}"
        )
        logger.warning("%s (last library error: %s)", msg, last_error)
        raise ValueError(msg)
    except ValueError:
        raise
    except Exception as e:
        logger.error("Error verifying Google token: %s", e)
        raise ValueError("Failed to verify Google token") from e
