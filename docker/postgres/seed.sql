-- =====================================================================
-- SEED DATA
-- Fresh initialization with real-data readiness.
-- PostgreSQL compatible — no USE statement needed (DB is selected
-- automatically via POSTGRES_DB in docker-compose / .env.db).
-- =====================================================================

-- --- 0. Connection Verification Data ---------------------------------
INSERT INTO test_connection (status) VALUES ('Database Operational');

-- The admin account is not seeded here: the backend creates it on startup
-- from ADMIN_EMAIL / ADMIN_PASSWORD in .env.backend.
