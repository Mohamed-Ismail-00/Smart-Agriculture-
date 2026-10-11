"""
middleware.py
-------------
Reusable security middlewares.

Apply in main.py:
    from app.security.middleware import (
        SecurityHeadersMiddleware,
        RateLimitMiddleware,
    )

    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RateLimitMiddleware, limit=100, window_seconds=60)
"""

import time
from collections import defaultdict
from typing import Dict, List

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Adds recommended security headers to every response."""

    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)

        # Prevent clickjacking
        response.headers["X-Frame-Options"] = "DENY"
        # Prevent MIME sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"
        # XSS Protection (legacy browsers)
        response.headers["X-XSS-Protection"] = "1; mode=block"
        # Referrer policy
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        # HSTS — tell browsers to always use HTTPS (1 year, includeSubDomains)
        # Note: this is safe to apply even on HTTP in dev; browsers only honour it on HTTPS responses
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        # Permissions policy — restrict powerful browser features
        response.headers["Permissions-Policy"] = (
            "geolocation=(self), "
            "camera=(), "
            "microphone=(), "
            "payment=(), "
            "usb=()"
        )
        # Tightened CSP — no unsafe-eval; allow 'unsafe-inline' only for legacy style/script bundles
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://accounts.google.com; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data: blob: https:; "
            "connect-src 'self' https://api.groq.com https://nominatim.openstreetmap.org https://accounts.google.com; "
            "frame-src 'none'; "
            "object-src 'none'; "
            "base-uri 'self';"
        )

        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Simple in-memory rate limiter.
    Good enough for development. Use Redis version in production.
    """

    def __init__(self, app, limit: int = 100, window_seconds: int = 60):
        super().__init__(app)
        self.limit = limit
        self.window = window_seconds
        self.requests: Dict[str, List[float]] = defaultdict(list)

    @staticmethod
    def _is_exempt(request: Request) -> bool:
        """Binary asset and health endpoints are auth-gated; skip IP throttle."""
        path = request.url.path
        if request.method == "GET" and path.endswith("/health"):
            return True
        if request.method == "GET" and "/images/" in path and path.endswith("/content"):
            return True
        return False

    async def dispatch(self, request: Request, call_next):
        if self._is_exempt(request):
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        now = time.time()

        # Clean old entries
        self.requests[client_ip] = [
            t for t in self.requests[client_ip] if now - t < self.window
        ]

        if len(self.requests[client_ip]) >= self.limit:
            return Response(
                content="Too Many Requests",
                status_code=429,
                headers={"Retry-After": str(self.window)},
            )

        self.requests[client_ip].append(now)
        return await call_next(request)
