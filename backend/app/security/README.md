# Security Module

Centralized security layer for the entire application.

## Goals
- Hide internal IDs behind public UUIDs
- Prevent IDOR / enumeration
- Provide reusable authorization
- Apply common security headers, rate limiting, and audit logging
- Make security easy to "inherit" via dependencies and imports

## Usage

### Backend (FastAPI)
```python
from app.security import require_land_access, generate_public_id, log_security_event

@router.get("/lands/{public_id}")
def get_land(land = Depends(require_land_access)):
    ...
```

### Frontend (React)
```js
import { getLandRoute, withAuth } from '../security';

navigate(getLandRoute(publicId));
```

## Next Steps
1. Add `public_id` column to Land (and other resources)
2. Update all routes to use public_id
3. Wrap critical endpoints with `require_land_access`
4. Add middleware in main.py
```

Now I have the structure.

Time to respond with the plan and point to the new security/ folder.