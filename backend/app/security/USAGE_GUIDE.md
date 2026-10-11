# Using the Security Layer

## 1. Protecting a Land Route (Recommended Pattern)

```python
from app.security import require_land_access
from fastapi import Depends

@router.get("/lands/{public_id}")
def get_land(
    public_id: str,
    land = Depends(require_land_access),   # ← does ownership + safe lookup
    current_user = Depends(get_current_user),
):
    return land
```

## 2. Using Public IDs

```python
from app.security import generate_public_id

land.public_id = generate_public_id()
```

## 3. Adding Security Middleware

Already done in `main.py`:
```python
from app.security import SecurityHeadersMiddleware, RateLimitMiddleware
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RateLimitMiddleware, limit=120, window_seconds=60)
```

## 4. Logging Security Events

```python
from app.security import log_security_event

log_security_event(
    db,
    user_id=user.user_id,
    action="suspicious_activity",
    details={"ip": request.client.host}
)
```

## Protection Summary

| Attack                        | Protected By                              |
|------------------------------|-------------------------------------------|
| IDOR / Broken Access Control | `require_land_access` + public_id        |
| ID Enumeration               | UUID `public_id` instead of int          |
| Brute Force / DoS            | `RateLimitMiddleware`                    |
| Clickjacking / Injection     | `SecurityHeadersMiddleware` + CSP        |
| Info Leakage                 | `ResourceNotFoundOrForbidden`            |
| Weak Auth                    | `get_current_active_user`                |
| No Audit                     | `log_security_event`                     |
