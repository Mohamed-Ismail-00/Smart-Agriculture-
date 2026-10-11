"""
core/config.py
--------------
Central configuration loader for the Smart Agriculture Data Platform backend.
Reads from .env.backend via environment variables.
All other modules should import settings from here — never read os.getenv directly.
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Application
    APP_ENV: str = "development"

    # Database
    DATABASE_URL: str = "postgresql+psycopg2://agri_user:agri_pass@postgres:5432/agriculture"

    # JWT / Auth
    SECRET_KEY: str = "change-this-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Admin account created on first startup (leave empty to create none)
    ADMIN_EMAIL: str = ""
    ADMIN_PASSWORD: str = ""

    # Security — API key encryption at rest (Fernet symmetric)
    # Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    # IMPORTANT: Set this in .env.backend in production — never use the default!
    ENCRYPTION_KEY: str = "HZxV7QmRx6NfBz3kYvP9CG1oTqLU5WwD4JdAeI2nMs0="

    # CORS — comma-separated list of allowed origins (empty = allow all, dev only!)
    # Example: "http://localhost:5173,https://yourapp.com"
    CORS_ORIGINS: str = ""

    # External services
    OPENAI_API_KEY: str = ""
    LOG_LEVEL: str = "INFO"
    LAND_MONITOR_INTERVAL_MINUTES: int = 1440

    # AI — auto-analyze interval for the scheduler (hours between stale insight refresh)
    AI_AUTO_ANALYZE_HOURS: int = 6
    # AI insights are considered stale after this many hours
    AI_INSIGHT_STALE_HOURS: int = 24

    # Sentinel-2 / Copernicus Data Space
    COPERNICUS_CLIENT_ID: str = ""
    COPERNICUS_CLIENT_SECRET: str = ""

    # Google OAuth 2.0 — Web client ID used as ID-token audience (must match frontend)
    GOOGLE_CLIENT_ID: str = ""
    # Optional extra audiences (comma-separated web client IDs), e.g. Firebase web client
    GOOGLE_CLIENT_IDS: str = ""
    GOOGLE_CLIENT_SECRET: str = ""  # Optional, used if switching to full OAuth code flow later

    # Satellite monitoring
    SATELLITE_IMAGE_INTERVAL_DAYS: int = 5
    SATELLITE_MAX_CLOUD_COVER_PCT: float = 30.0

    # Analysis thresholds
    NDVI_ANOMALY_DROP_THRESHOLD: float = 0.15
    CLIMATE_STRESS_TEMP_THRESHOLD: float = 40.0
    DROUGHT_RAINFALL_THRESHOLD_MM: float = 2.0

    # Reference data path
    CROP_PROFILES_PATH: str = "data/reference/crop_profiles.json"

    model_config = {"env_file": ".env.backend", "extra": "ignore"}


# Singleton instance — import this everywhere
settings = Settings()
