"""
public_ids.py
-------------
UUID-based public identifier system to hide internal database IDs.

This directly addresses IDOR and enumeration attacks.

Strategy:
- Internal: fast integer `id`
- Public: random UUID `public_id`
- All external APIs and frontend URLs use only `public_id`
"""

import uuid
from typing import Optional, Type

from sqlalchemy.orm import Session

def generate_public_id() -> str:
    """Generate a new random UUID for public use."""
    return str(uuid.uuid4())

def get_by_public_id(
    db: Session,
    model_class: Type,
    public_id: str,
    id_column: str = "public_id",
) -> Optional[object]:
    """
    Generic safe lookup by public UUID.

    Example:
        land = get_by_public_id(db, Land, "550e8400-e29b-41d4-a716-446655440000")
    """
    if not public_id:
        return None
    return (
        db.query(model_class)
        .filter(getattr(model_class, id_column) == public_id)
        .first()
    )

def get_land_by_public_id(db: Session, public_id: str):
    """Convenience wrapper."""
    from app.models.land import Land
    return get_by_public_id(db, Land, public_id)
