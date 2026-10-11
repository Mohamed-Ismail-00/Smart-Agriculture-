"""User-declared crop ground truth."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user_declared_crop import UserDeclaredCrop
from app.trust.types import DetectionMethod


def get_primary_declaration(db: Session, land_id: int) -> Optional[UserDeclaredCrop]:
    stmt = (
        select(UserDeclaredCrop)
        .where(UserDeclaredCrop.land_id == land_id, UserDeclaredCrop.is_primary == True)  # noqa: E712
        .order_by(UserDeclaredCrop.updated_at.desc())
        .limit(1)
    )
    return db.execute(stmt).scalar_one_or_none()


def list_declarations(db: Session, land_id: int) -> list[UserDeclaredCrop]:
    stmt = (
        select(UserDeclaredCrop)
        .where(UserDeclaredCrop.land_id == land_id)
        .order_by(UserDeclaredCrop.is_primary.desc(), UserDeclaredCrop.updated_at.desc())
    )
    return list(db.execute(stmt).scalars().all())


def upsert_primary_declaration(
    db: Session,
    land_id: int,
    crop_type: str,
    *,
    user_id: Optional[int] = None,
    notes: Optional[str] = None,
) -> UserDeclaredCrop:
    existing = get_primary_declaration(db, land_id)
    if existing:
        existing.crop_type = crop_type.strip()
        existing.notes = notes
        existing.declared_by = user_id
        db.flush()
        return existing

    row = UserDeclaredCrop(
        land_id=land_id,
        crop_type=crop_type.strip(),
        is_primary=True,
        notes=notes,
        declared_by=user_id,
    )
    db.add(row)
    db.flush()
    return row


def delete_primary_declaration(db: Session, land_id: int) -> bool:
    existing = get_primary_declaration(db, land_id)
    if not existing:
        return False
    db.delete(existing)
    db.flush()
    return True


def primary_detection_method() -> str:
    return DetectionMethod.USER_CONFIRMED.value