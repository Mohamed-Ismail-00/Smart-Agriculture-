"""
api/users.py
------------
User management endpoints (admin-only).

Routes (all prefixed /api/v1 from main.py):
    GET    /users      → list all users
    GET    /users/{id} → get user by ID
    PUT    /users/{id} → update a user
    DELETE /users/{id} → delete a user

All routes require the caller to have admin role (via require_admin dependency).

Design rule: thin layer — no business logic, no DB queries.
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_db, require_admin
from app.models.user import User
from app.users import service as user_service
from app.users.schemas import APIResponse, UserResponse, UserUpdate

router = APIRouter(prefix="/users", tags=["User Management"])


# ---------------------------------------------------------------------------
# GET /users
# ---------------------------------------------------------------------------

@router.get(
    "/",
    response_model=APIResponse,
    summary="List all users (admin only)",
)
def list_users(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """Return a list of all registered users. Requires admin role."""
    users = user_service.get_all_users(db)
    return APIResponse(
        status="success",
        data=[UserResponse.model_validate(u).model_dump() for u in users],
        meta={"total": len(users)},
    )


# ---------------------------------------------------------------------------
# GET /users/{user_id}
# ---------------------------------------------------------------------------

@router.get(
    "/{user_id}",
    response_model=APIResponse,
    summary="Get a user by ID (admin only)",
)
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """Return a single user's profile by their numeric ID. Requires admin role."""
    user = user_service.get_user_by_id(db, user_id)
    return APIResponse(
        status="success",
        data=UserResponse.model_validate(user).model_dump(),
    )


# ---------------------------------------------------------------------------
# PUT /users/{user_id}
# ---------------------------------------------------------------------------

@router.put(
    "/{user_id}",
    response_model=APIResponse,
    summary="Update a user (admin only)",
)
def update_user(
    user_id: int,
    user_in: UserUpdate,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """
    Update one or more fields of an existing user.

    All fields in the request body are optional — only provided fields are
    updated. Omitted fields remain unchanged.
    """
    user = user_service.update_user(db, user_id, user_in)
    return APIResponse(
        status="success",
        data=UserResponse.model_validate(user).model_dump(),
        message="User updated successfully.",
    )


# ---------------------------------------------------------------------------
# DELETE /users/{user_id}
# ---------------------------------------------------------------------------

@router.delete(
    "/{user_id}",
    status_code=status.HTTP_200_OK,
    response_model=APIResponse,
    summary="Delete a user (admin only)",
)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """Permanently delete a user account. Requires admin role."""
    user_service.delete_user(db, user_id)
    return APIResponse(
        status="success",
        message=f"User with id={user_id} has been deleted.",
    )
