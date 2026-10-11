# Security Layer Design — Attack Coverage

This document proves that the `app/security/` layer is designed to mitigate the most common web and API attacks.

## 1. Broken Access Control (OWASP A01)
**Mitigation:**
- `permissions.require_land_access(public_id)` — always verifies ownership using `public_id`.
- Never trusts client-supplied integer IDs.
- Uses `ResourceNotFoundOrForbidden` (returns 404) to avoid leaking whether a resource exists.

## 2. Identification & Authentication Failures (A07)
**Mitigation:**
- Strong JWT access + refresh tokens in `auth.py`
- `get_current_active_user` dependency
- Short-lived access tokens + longer refresh
- Role checks via `require_role("admin")`

## 3. Insecure Direct Object References / IDOR
**Mitigation:**
- All public routes use `public_id` (UUID) instead of sequential `land_id`
- `public_ids.py` provides safe lookup
- Ownership enforced in `require_land_access`

## 4. Security Misconfiguration (A05)
**Mitigation:**
- `SecurityHeadersMiddleware` adds:
  - X-Frame-Options
  - X-Content-Type-Options
  - CSP
  - Referrer-Policy
- CORS is configurable (currently permissive for dev)

## 5. Rate Limiting & Brute Force
**Mitigation:**
- `RateLimitMiddleware` (per-IP, configurable)
- Can be easily upgraded to Redis-backed

## 6. Information Disclosure
**Mitigation:**
- `ResourceNotFoundOrForbidden` never distinguishes between "not found" and "no permission"
- Error messages are generic in production paths
- `audit.py` for sensitive events

## 7. Insufficient Logging & Monitoring (A09)
**Mitigation:**
- `log_security_event()` for access denials, auth failures, privilege abuse
- Reuses existing `ActivityLog` table

## 8. Injection
**Mitigation:**
- `validators.py` (sanitization helpers)
- Pydantic models for all input (already strong)
- SQLAlchemy ORM (parameterized queries)

## 9. Frontend Protection
- `src/security/sanitizers.js`
- `routeProtection.js` (ProtectedRoute)
- `idUtils.js` (validation of public IDs)

## Summary
This layer directly targets:
- IDOR / Broken Access Control
- Enumeration
- Authentication weaknesses
- Rate abuse
- Information leakage
- Misconfiguration

It is designed to be **imported and depended on**, not duplicated across the codebase.
