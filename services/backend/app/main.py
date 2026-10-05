"""
main.py
-------
FastAPI application entry point for the Smart Agriculture Data Platform backend.

Startup behaviour:
- Creates all database tables if they don't exist (SQLAlchemy create_all).
- Registers all API routers under /api/v1.
- Configures CORS for React frontend.

All future routers (crops, water, climate …) should be imported and registered here
following the same pattern as auth_router and users_router.
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
import logging

logger = logging.getLogger(__name__)

# Config
from app.core.config import settings

# Centralized security layer
from app.security import SecurityHeadersMiddleware, RateLimitMiddleware

# Import base so all models are registered with SQLAlchemy metadata
from app.db import base as _models_discovery  # noqa: F401

# Routers
from app.api.health import router as health_router
from app.api.auth import router as auth_router
from app.api.users import router as users_router
from app.api.climate import router as climate_router
from app.api.ingestion import router as ingestion_router
from app.api.pipeline import router as pipeline_router
from app.api.lands import router as lands_router
from app.api.crops import router as crops_router
from app.api.soil import router as soil_router
from app.api.ai import router as ai_router
from app.api.activity_logs import router as activity_logs_router
from app.api.notifications import router as notifications_router
from app.api.trust import router as trust_router

# ---------------------------------------------------------------------------
# App initialisation
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Smart Agriculture Data Platform API",
    description="RESTful backend for agricultural data analytics, AI recommendations, and CV processing.",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# ---------------------------------------------------------------------------
# CORS — configurable origins from settings (restrict in production!)
# ---------------------------------------------------------------------------

# Parse CORS_ORIGINS: empty string = allow all (dev only); else comma-separated list
_cors_origins = [
    o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()
] if settings.CORS_ORIGINS.strip() else ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "X-Requested-With"],
)

# Apply centralized security middlewares
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RateLimitMiddleware, limit=120, window_seconds=60)  # 120 req/min per IP

# ---------------------------------------------------------------------------
# Global Exception Handlers — turn unhandled DB/server errors into clean JSON
# instead of raw 500 Internal Server Error with no body.
# ---------------------------------------------------------------------------

from sqlalchemy.exc import SQLAlchemyError


@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
    """Return a clean 500 JSON response for any unhandled SQLAlchemy error."""
    logger.error("Database error on %s %s: %s", request.method, request.url.path, exc)
    return JSONResponse(
        status_code=500,
        content={"status": "error", "message": "A database error occurred. Please try again."},
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    """Catch-all for any other unhandled server-side error."""
    logger.error("Unhandled error on %s %s: %s", request.method, request.url.path, exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"status": "error", "message": "An unexpected server error occurred."},
    )


# ---------------------------------------------------------------------------
# Database table auto-creation (development convenience)
# For production: use Alembic migrations instead.
# ---------------------------------------------------------------------------

@app.on_event("startup")
def create_tables() -> None:
    """
    Create all SQLAlchemy-registered tables on startup if they don't exist.

    Silently skips if the database is unreachable (e.g. running tests locally
    without Docker). Tests use their own in-memory SQLite via dependency override.
    """
    try:
        from app.models.user import Base, User
        from app.db.session import get_engine
        from sqlalchemy.orm import Session
        from sqlalchemy import text

        engine = get_engine()
        Base.metadata.create_all(bind=engine)

        # ---------------------------------------------------------------------------
        # Schema Migration: add every column that exists in the ORM model but may
        # be missing from the live Azure database (created from an older init.sql).
        # Each statement is wrapped individually so one failure doesn't block others.
        # ---------------------------------------------------------------------------
        migrations = [
            # --- users ---
            "ALTER TABLE users ALTER COLUMN password_hash DROP NOT NULL",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_deleted BOOLEAN NOT NULL DEFAULT FALSE",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW()",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW()",

            # --- lands ---
            "ALTER TABLE lands ADD COLUMN IF NOT EXISTS public_id UUID DEFAULT gen_random_uuid() UNIQUE",
            "ALTER TABLE lands ADD COLUMN IF NOT EXISTS is_deleted BOOLEAN NOT NULL DEFAULT FALSE",
            "ALTER TABLE lands ADD COLUMN IF NOT EXISTS metadata_ JSONB DEFAULT '{}'",
            "ALTER TABLE lands ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW()",
            "ALTER TABLE lands ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW()",
            # Make source_id columns nullable (models changed them from NOT NULL)
            "ALTER TABLE land_climate ALTER COLUMN source_id DROP NOT NULL",
            "ALTER TABLE land_water ALTER COLUMN source_id DROP NOT NULL",
            "ALTER TABLE land_crops ALTER COLUMN source_id DROP NOT NULL",
            "ALTER TABLE land_soil ALTER COLUMN source_id DROP NOT NULL",
            "ALTER TABLE land_images ALTER COLUMN source_id DROP NOT NULL",
            "ALTER TABLE land_alerts ALTER COLUMN source_id DROP NOT NULL",
            "ALTER TABLE analytics_summaries ALTER COLUMN source_id DROP NOT NULL",

            # --- land_alerts ---
            "ALTER TABLE land_alerts ADD COLUMN IF NOT EXISTS user_id INT REFERENCES users(user_id)",
            "ALTER TABLE land_alerts ADD COLUMN IF NOT EXISTS is_read BOOLEAN NOT NULL DEFAULT FALSE",

            # --- land_crops (created_at was added later) ---
            "ALTER TABLE land_crops ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW()",

            # --- land_images (source_id nullable already handled above) ---
            "ALTER TABLE land_images ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW()",

            # --- land_climate (min/mean temperature columns) ---
            "ALTER TABLE land_climate ADD COLUMN IF NOT EXISTS temperature_min_c NUMERIC(10,4)",
            "ALTER TABLE land_climate ADD COLUMN IF NOT EXISTS temperature_mean_c NUMERIC(10,4)",

            # --- data trust layer ---
            "ALTER TABLE crop_zones ADD COLUMN IF NOT EXISTS detection_method VARCHAR(64)",
            "ALTER TABLE crop_zones ADD COLUMN IF NOT EXISTS trust_tier VARCHAR(16)",
            "ALTER TABLE crop_zones ADD COLUMN IF NOT EXISTS separation_score NUMERIC(6,4)",
            "ALTER TABLE crop_zones ADD COLUMN IF NOT EXISTS ambiguous BOOLEAN DEFAULT FALSE",
            "ALTER TABLE crop_zones ADD COLUMN IF NOT EXISTS suppressed BOOLEAN DEFAULT FALSE",
            "ALTER TABLE crop_zones ADD COLUMN IF NOT EXISTS zone_metadata JSONB",
            "ALTER TABLE land_crops ADD COLUMN IF NOT EXISTS trust_tier VARCHAR(16)",
            "ALTER TABLE land_crops ADD COLUMN IF NOT EXISTS is_synthetic BOOLEAN DEFAULT FALSE",
            "ALTER TABLE land_soil_profiles ADD COLUMN IF NOT EXISTS fetch_status VARCHAR(16)",
            "ALTER TABLE land_soil_profiles ADD COLUMN IF NOT EXISTS fetch_attempts INT DEFAULT 0",
            "ALTER TABLE land_soil_profiles ADD COLUMN IF NOT EXISTS last_fetch_error VARCHAR(512)",
            "ALTER TABLE land_soil_profiles ADD COLUMN IF NOT EXISTS trust_tier VARCHAR(16)",
        ]

        with engine.begin() as conn:
            for sql in migrations:
                try:
                    conn.execute(text(sql))
                except Exception:
                    pass  # Column may already exist — safe to ignore

        # ---------------------------------------------------------------------------
        # Admin account: created once from ADMIN_EMAIL / ADMIN_PASSWORD (.env.backend).
        # Registration cannot create admins, so this is the only way one appears.
        # ---------------------------------------------------------------------------
        with Session(engine) as session:
            if settings.ADMIN_EMAIL and settings.ADMIN_PASSWORD:
                from app.core.security import hash_password

                admin = session.query(User).filter_by(email=settings.ADMIN_EMAIL).first()
                if not admin:
                    session.add(User(
                        email=settings.ADMIN_EMAIL,
                        password_hash=hash_password(settings.ADMIN_PASSWORD),
                        role="admin",
                        is_active=True,
                    ))

            # Reset any lands that got stuck in intermediate processing states before our error handling fix
            from app.models.land import Land
            stuck_lands = session.query(Land).filter(
                Land.status.notin_(["active", "failed"])
            ).all()
            for l in stuck_lands:
                l.status = "failed (stuck in pipeline)"

            session.commit()

    except Exception:
        # DB not available (e.g. local test run without Docker) — safe to ignore.
        pass



# ---------------------------------------------------------------------------
# Router registration
# ---------------------------------------------------------------------------

# Existing health routes (no version prefix — keeps /api/health working)
app.include_router(health_router)

# Versioned auth & user management routes
app.include_router(auth_router, prefix="/api/v1")
app.include_router(users_router, prefix="/api/v1")
app.include_router(climate_router, prefix="/api/v1")
app.include_router(ingestion_router, prefix="/api/v1")
app.include_router(pipeline_router, prefix="/api/v1")
app.include_router(lands_router, prefix="/api/v1")
app.include_router(crops_router, prefix="/api/v1")
app.include_router(soil_router, prefix="/api/v1")
app.include_router(ai_router, prefix="/api/v1")
app.include_router(activity_logs_router, prefix="/api/v1")
app.include_router(notifications_router, prefix="/api/v1")
app.include_router(trust_router, prefix="/api/v1")

# ---------------------------------------------------------------------------
# Serve React Frontend (Single Page Application)
# ---------------------------------------------------------------------------

import os
from fastapi.responses import FileResponse

# Mount the 'assets' directory so Vite's /assets/... URLs work
assets_path = os.path.join(os.path.dirname(__file__), "..", "static", "assets")
if os.path.exists(assets_path):
    app.mount("/assets", StaticFiles(directory=assets_path), name="assets")

@app.get("/{full_path:path}")
async def serve_frontend(full_path: str):
    """
    Catch-all route for the React Single Page Application.
    If the requested file exists in the static directory (e.g. vite.svg), serve it.
    Otherwise, serve index.html and let React Router handle the URL.
    """
    static_dir = os.path.join(os.path.dirname(__file__), "..", "static")
    requested_file = os.path.join(static_dir, full_path)
    
    if os.path.isfile(requested_file):
        # Add a reasonably strict CSP for production static assets
        # (no unsafe-eval — requires that your prod build doesn't use eval)
        response = FileResponse(requested_file)
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https:; "   # unsafe-inline often still needed for some bundles
            "style-src 'self' 'unsafe-inline' https:; "
            "img-src 'self' data: blob: https:; "
            "connect-src 'self' https:; "
            "font-src 'self' https:; "
            "object-src 'none'; "
            "base-uri 'self'; "
            "frame-ancestors 'none';"
        )
        return response
    
    index_file = os.path.join(static_dir, "index.html")
    if os.path.isfile(index_file):
        response = FileResponse(index_file)
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https:; "
            "style-src 'self' 'unsafe-inline' https:; "
            "img-src 'self' data: blob: https:; "
            "connect-src 'self' https:; "
            "font-src 'self' https:; "
            "object-src 'none'; "
            "base-uri 'self'; "
            "frame-ancestors 'none';"
        )
        return response
        
    return {"detail": "Not Found"}
