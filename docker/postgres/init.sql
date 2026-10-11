-- ============================================================================
-- PostgreSQL Initialization Script
-- Smart Agriculture Data Platform
-- ============================================================================
-- Note: PostgreSQL Docker image automatically creates the database specified
-- in POSTGRES_DB. No CREATE DATABASE or USE statement needed here.
-- This script runs automatically on first container start via
-- /docker-entrypoint-initdb.d/
-- ============================================================================


-- ============================================================================
-- Helper: auto-update updated_at columns via trigger function
-- ============================================================================

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;


-- ============================================================================
-- 1. Core Tables
-- ============================================================================

CREATE TABLE IF NOT EXISTS test_connection (
    id          SERIAL PRIMARY KEY,
    status      VARCHAR(50)  NOT NULL,
    initialized_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS data_sources (
    source_id        SERIAL PRIMARY KEY,
    name             VARCHAR(255) NOT NULL UNIQUE,
    confidence_score DECIMAL(5,2) NULL,
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE OR REPLACE TRIGGER trg_data_sources_updated_at
    BEFORE UPDATE ON data_sources
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE IF NOT EXISTS users (
    user_id       SERIAL PRIMARY KEY,
    email         VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255),
    role          VARCHAR(50)  NOT NULL DEFAULT 'viewer',
    is_active     BOOLEAN      NOT NULL DEFAULT TRUE,
    is_deleted    BOOLEAN      NOT NULL DEFAULT FALSE,
    created_at    TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at    TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users (email);

CREATE OR REPLACE TRIGGER trg_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE IF NOT EXISTS locations (
    location_id  SERIAL PRIMARY KEY,
    governorate  VARCHAR(100) UNIQUE NOT NULL,
    region       VARCHAR(100) NULL,
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_locations_governorate ON locations (governorate);

CREATE TABLE IF NOT EXISTS ingestion_batches (
    batch_id       SERIAL PRIMARY KEY,
    source_system  VARCHAR(100) NOT NULL,
    source_version VARCHAR(100) NULL,
    started_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at   TIMESTAMP NULL,
    status         VARCHAR(50) NOT NULL
);

CREATE TABLE IF NOT EXISTS etl_errors (
    etl_error_id  SERIAL PRIMARY KEY,
    batch_id      INT          NULL REFERENCES ingestion_batches(batch_id),
    stage_name    VARCHAR(100) NOT NULL,
    record_key    VARCHAR(255) NULL,
    error_code    VARCHAR(100) NOT NULL,
    error_message TEXT         NOT NULL,
    is_retryable  BOOLEAN      NOT NULL DEFAULT FALSE,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS climate_records (
    climate_record_id    SERIAL PRIMARY KEY,
    location_id          INT          NOT NULL REFERENCES locations(location_id),
    year                 INT          NOT NULL,
    temperature_mean     DECIMAL(10,4) NULL,
    humidity_pct         DECIMAL(10,4) NULL,
    batch_id             INT          NOT NULL REFERENCES ingestion_batches(batch_id),
    source_system        VARCHAR(100) NOT NULL,
    ingestion_timestamp  TIMESTAMP    NOT NULL,
    created_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_climate_location_year_batch UNIQUE (location_id, year, batch_id)
);

CREATE TABLE IF NOT EXISTS water_records (
    water_record_id       SERIAL PRIMARY KEY,
    location_id           INT           NOT NULL REFERENCES locations(location_id),
    crop                  VARCHAR(100)  NOT NULL,
    year                  INT           NOT NULL,
    water_consumption_m3  DECIMAL(12,2) NULL,
    irrigation_type       VARCHAR(50)   NULL,
    batch_id              INT           NOT NULL REFERENCES ingestion_batches(batch_id),
    source_system         VARCHAR(100)  NOT NULL,
    ingestion_timestamp   TIMESTAMP     NOT NULL,
    created_at            TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_water_location_crop_year_batch UNIQUE (location_id, crop, year, batch_id)
);

CREATE TABLE IF NOT EXISTS lands (
    land_id                  SERIAL PRIMARY KEY,
    public_id                UUID          NOT NULL DEFAULT gen_random_uuid() UNIQUE,
    user_id                  INT           NULL REFERENCES users(user_id),
    name                     VARCHAR(255)  NOT NULL,
    latitude                 DECIMAL(10,8) NOT NULL,
    longitude                DECIMAL(11,8) NOT NULL,
    boundary_polygon         JSONB         NULL,
    area_hectares            DECIMAL(10,4) NULL,
    description              TEXT          NULL,
    status                   VARCHAR(128)  NOT NULL DEFAULT 'processing',
    monitoring_interval_days INT           NOT NULL DEFAULT 7,
    is_deleted               BOOLEAN       NOT NULL DEFAULT FALSE,
    metadata_                JSONB         NULL DEFAULT '{}',
    created_at               TIMESTAMPTZ   DEFAULT CURRENT_TIMESTAMP,
    updated_at               TIMESTAMPTZ   DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_lands_status  ON lands (status);
CREATE INDEX IF NOT EXISTS idx_lands_lat_lng ON lands (latitude, longitude);

CREATE OR REPLACE TRIGGER trg_lands_updated_at
    BEFORE UPDATE ON lands
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ============================================================================
-- 2. Data / Metrics Tables
-- ============================================================================

CREATE TABLE IF NOT EXISTS land_climate (
    id                  SERIAL PRIMARY KEY,
    land_id             INT           NOT NULL REFERENCES lands(land_id) ON DELETE CASCADE,
    timestamp           TIMESTAMPTZ   DEFAULT CURRENT_TIMESTAMP,
    temperature_celsius DECIMAL(10,4) NULL,
    humidity_pct        DECIMAL(10,4) NULL,
    rainfall_mm         DECIMAL(10,4) NULL,
    source_id           INT           NULL REFERENCES data_sources(source_id),
    created_at          TIMESTAMPTZ   DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_land_climate_land_time ON land_climate (land_id, timestamp);

CREATE TABLE IF NOT EXISTS land_water (
    id                            SERIAL PRIMARY KEY,
    land_id                       INT           NOT NULL REFERENCES lands(land_id) ON DELETE CASCADE,
    timestamp                     TIMESTAMPTZ   DEFAULT CURRENT_TIMESTAMP,
    estimated_water_usage_liters  DECIMAL(14,4) NULL,
    irrigation_status             VARCHAR(100)  NULL,
    crop_water_requirement_mm     DECIMAL(10,4) NULL,
    water_efficiency_ratio        DECIMAL(10,4) NULL,
    source_id                     INT           NULL REFERENCES data_sources(source_id),
    created_at                    TIMESTAMPTZ   DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_land_water_land_time ON land_water (land_id, timestamp);

CREATE TABLE IF NOT EXISTS crop_zones (
    zone_id              SERIAL PRIMARY KEY,
    land_id              INT           NOT NULL REFERENCES lands(land_id) ON DELETE CASCADE,
    crop_type            VARCHAR(100)  NOT NULL,
    area_hectares        DECIMAL(12,4) NULL,
    area_pct             DECIMAL(5,2)  NULL,
    boundary_polygon     JSONB         NULL,
    status               VARCHAR(32)   NOT NULL DEFAULT 'active',
    avg_confidence       DECIMAL(5,4)  NULL,
    latest_ndvi          DECIMAL(6,4)  NULL,
    latest_growth_stage  VARCHAR(50)   NULL,
    estimated_yield_tons DECIMAL(14,4) NULL,
    first_detected       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_updated         TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_crop_zones_land ON crop_zones (land_id);

CREATE OR REPLACE TRIGGER trg_crop_zones_last_updated
    BEFORE UPDATE ON crop_zones
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE IF NOT EXISTS land_crops (
    id                   SERIAL PRIMARY KEY,
    land_id              INT           NOT NULL REFERENCES lands(land_id) ON DELETE CASCADE,
    timestamp            TIMESTAMPTZ   DEFAULT CURRENT_TIMESTAMP,
    crop_type            VARCHAR(100)  NULL,
    ndvi_value           DECIMAL(10,4) NULL,
    dvi_value            DECIMAL(10,4) NULL,
    evi_value            DECIMAL(10,4) NULL,
    ndwi_value           DECIMAL(10,4) NULL,
    savi_value           DECIMAL(10,4) NULL,
    gndvi_value          DECIMAL(10,4) NULL,
    estimated_yield_tons DECIMAL(14,4) NULL,
    growth_stage         VARCHAR(50)   NULL,
    ndvi_trend           VARCHAR(20)   NULL,
    confidence           DECIMAL(5,4)  NULL,
    zone_id              INT           NULL REFERENCES crop_zones(zone_id) ON DELETE SET NULL,
    source_id            INT           NULL REFERENCES data_sources(source_id),
    created_at           TIMESTAMPTZ   DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_land_crops_land_time ON land_crops (land_id, timestamp);

CREATE TABLE IF NOT EXISTS land_soil (
    id                  SERIAL PRIMARY KEY,
    land_id             INT           NOT NULL REFERENCES lands(land_id) ON DELETE CASCADE,
    timestamp           TIMESTAMPTZ   DEFAULT CURRENT_TIMESTAMP,
    moisture_pct        DECIMAL(10,4) NULL,
    soil_type           VARCHAR(100)  NULL,
    ph_level            DECIMAL(5,2)  NULL,
    organic_matter_pct  DECIMAL(5,2)  NULL,
    suitability_score   DECIMAL(5,2)  NULL,
    source_id           INT           NULL REFERENCES data_sources(source_id),
    created_at          TIMESTAMPTZ   DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_land_soil_land_time ON land_soil (land_id, timestamp);

CREATE TABLE IF NOT EXISTS land_images (
    id                  SERIAL PRIMARY KEY,
    land_id             INT          NOT NULL REFERENCES lands(land_id) ON DELETE CASCADE,
    timestamp           TIMESTAMPTZ  DEFAULT CURRENT_TIMESTAMP,
    image_data          BYTEA        NOT NULL,
    image_type          VARCHAR(100) NOT NULL,
    cv_analysis_summary JSONB        NULL,
    ndvi_mean           DECIMAL(6,4) NULL,
    cloud_cover_pct     DECIMAL(5,2) NULL,
    source_id           INT          NULL REFERENCES data_sources(source_id),
    created_at          TIMESTAMPTZ  DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_land_images_land_time ON land_images (land_id, timestamp);

CREATE TABLE IF NOT EXISTS analytics_summaries (
    id              SERIAL PRIMARY KEY,
    land_id         INT       NOT NULL REFERENCES lands(land_id) ON DELETE CASCADE,
    timestamp       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    summary_text    TEXT      NOT NULL,
    summary_payload JSONB     NULL,
    source_id       INT       NOT NULL REFERENCES data_sources(source_id),
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_analytics_summaries_land_time ON analytics_summaries (land_id, timestamp);

CREATE TABLE IF NOT EXISTS land_ai_insights (
    insight_id      SERIAL PRIMARY KEY,
    land_id         INT          NOT NULL REFERENCES lands(land_id) ON DELETE CASCADE,
    insight_type    VARCHAR(64)  NOT NULL,
    title           VARCHAR(255) NOT NULL,
    body            TEXT         NOT NULL,
    structured_data JSONB        NULL,
    confidence      FLOAT        NULL,
    model_used      VARCHAR(128) NULL,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_land_ai_insights_land_created ON land_ai_insights (land_id, created_at DESC);

CREATE TABLE IF NOT EXISTS land_alerts (
    id          SERIAL PRIMARY KEY,
    land_id     INT          NOT NULL REFERENCES lands(land_id) ON DELETE CASCADE,
    user_id     INT          NULL REFERENCES users(user_id),
    timestamp   TIMESTAMPTZ  DEFAULT CURRENT_TIMESTAMP,
    alert_type  VARCHAR(100) NOT NULL,
    severity    VARCHAR(20)  NOT NULL,
    message     TEXT         NOT NULL,
    payload     JSONB        NULL,
    resolved_at TIMESTAMPTZ  NULL,
    is_read     BOOLEAN      NOT NULL DEFAULT FALSE,
    source_id   INT          NULL REFERENCES data_sources(source_id),
    created_at  TIMESTAMPTZ  DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_land_alerts_land_time ON land_alerts (land_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_land_alerts_severity  ON land_alerts (severity);

-- ============================================================================
-- 3. AI Tables
-- ============================================================================

CREATE TABLE IF NOT EXISTS ai_api_keys (
    key_id          SERIAL PRIMARY KEY,
    user_id         INT          NOT NULL REFERENCES users(user_id),
    api_key         VARCHAR(512) NOT NULL,
    label           VARCHAR(128) NULL,
    provider        VARCHAR(64)  NOT NULL DEFAULT 'grok',
    is_active       BOOLEAN      NOT NULL DEFAULT TRUE,
    quota_exceeded  BOOLEAN      NOT NULL DEFAULT FALSE,
    quota_reset_at  TIMESTAMP    NULL,
    sort_order      INT          NOT NULL DEFAULT 0,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_ai_api_keys_user ON ai_api_keys (user_id);

CREATE OR REPLACE TRIGGER trg_ai_api_keys_updated_at
    BEFORE UPDATE ON ai_api_keys
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE IF NOT EXISTS ai_chat_sessions (
    session_id  SERIAL PRIMARY KEY,
    land_id     INT          NOT NULL REFERENCES lands(land_id),
    user_id     INT          NULL REFERENCES users(user_id),
    title       VARCHAR(255) NULL,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_ai_chat_sessions_land ON ai_chat_sessions (land_id);
CREATE INDEX IF NOT EXISTS idx_ai_chat_sessions_user ON ai_chat_sessions (user_id);

CREATE OR REPLACE TRIGGER trg_ai_chat_sessions_updated_at
    BEFORE UPDATE ON ai_chat_sessions
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE IF NOT EXISTS ai_chat_messages (
    message_id  SERIAL PRIMARY KEY,
    session_id  INT       NOT NULL REFERENCES ai_chat_sessions(session_id),
    role        VARCHAR(32) NOT NULL,
    content     TEXT      NOT NULL,
    tokens_used INT       NULL,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_ai_chat_messages_session ON ai_chat_messages (session_id);

-- ============================================================================
-- 4. Soil Profile Table
-- ============================================================================

CREATE TABLE IF NOT EXISTS land_soil_profiles (
    id                SERIAL PRIMARY KEY,
    land_id           INT           NOT NULL UNIQUE REFERENCES lands(land_id) ON DELETE CASCADE,
    ph_h2o            DECIMAL(5,2)  NULL,
    soc_g_per_kg      DECIMAL(8,3)  NULL,
    clay_pct          DECIMAL(6,2)  NULL,
    sand_pct          DECIMAL(6,2)  NULL,
    silt_pct          DECIMAL(6,2)  NULL,
    bulk_density      DECIMAL(6,3)  NULL,
    nitrogen_g_per_kg DECIMAL(7,3)  NULL,
    cec_cmol          DECIMAL(8,3)  NULL,
    texture_class     VARCHAR(50)   NULL,
    depth_profile     JSONB         NULL,
    suitability_score DECIMAL(5,2)  NULL,
    fetched_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    source_id         INT           NULL REFERENCES data_sources(source_id)
);

CREATE INDEX IF NOT EXISTS idx_land_soil_profiles_land ON land_soil_profiles (land_id);

-- ============================================================================
-- 5. Audit / Event Table
-- ============================================================================

CREATE TABLE IF NOT EXISTS database_events (
    event_id   SERIAL PRIMARY KEY,
    event_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    table_name VARCHAR(100) NOT NULL,
    operation  VARCHAR(20)  NOT NULL,
    record_id  INT          NOT NULL,
    details    JSONB        NULL
);

-- ============================================================================
-- 6. Audit Triggers
-- ============================================================================

CREATE OR REPLACE FUNCTION audit_lands_insert()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO database_events (table_name, operation, record_id, details)
    VALUES ('lands', 'INSERT', NEW.land_id,
            jsonb_build_object('name', NEW.name, 'user_id', NEW.user_id));
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE TRIGGER after_lands_insert
    AFTER INSERT ON lands
    FOR EACH ROW EXECUTE FUNCTION audit_lands_insert();

CREATE OR REPLACE FUNCTION audit_lands_update()
RETURNS TRIGGER AS $$
BEGIN
    IF OLD.status IS DISTINCT FROM NEW.status THEN
        INSERT INTO database_events (table_name, operation, record_id, details)
        VALUES ('lands', 'UPDATE', NEW.land_id,
                jsonb_build_object('old_status', OLD.status, 'new_status', NEW.status));
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE TRIGGER after_lands_update
    AFTER UPDATE ON lands
    FOR EACH ROW EXECUTE FUNCTION audit_lands_update();

CREATE OR REPLACE FUNCTION audit_data_sources_insert()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO database_events (table_name, operation, record_id, details)
    VALUES ('data_sources', 'INSERT', NEW.source_id,
            jsonb_build_object('name', NEW.name, 'confidence_score', NEW.confidence_score));
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE TRIGGER after_data_sources_insert
    AFTER INSERT ON data_sources
    FOR EACH ROW EXECUTE FUNCTION audit_data_sources_insert();

-- ============================================================================
-- Permissions (adjust user/db names to match .env.db)
-- ============================================================================
-- GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO agri_user;
-- GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO agri_user;

-- ============================================================================
-- 7. User Activity Logs (Admin-only visibility)
-- ============================================================================

CREATE TABLE IF NOT EXISTS user_activity_logs (
    log_id        SERIAL PRIMARY KEY,
    user_id       INT          NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    action        VARCHAR(100) NOT NULL,           -- e.g. 'login', 'create_land', 'export', 'reanalyze', 'delete_land'
    target_type   VARCHAR(50),                     -- e.g. 'land', 'user', 'export'
    target_id     INT,
    details       JSONB,
    ip_address    VARCHAR(45),
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_activity_user_time ON user_activity_logs (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_activity_action ON user_activity_logs (action, created_at DESC);

