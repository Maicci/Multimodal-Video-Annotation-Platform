"""Administrator-only user management routes."""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

import psycopg
from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import Connection, require_roles
from app.core.security import hash_password
from app.repositories.user_repository import (
    approve_user,
    count_users_with_role,
    create_user as create_user_record,
    delete_user as delete_user_record,
    find_user_by_id,
    list_pending_users,
    list_users as list_user_records,
    reject_user,
    update_user_role,
)


from app.schemas.user import (
    Role,
    RoleUpdate,
    UserApprovalRequest,
    UserCreate,
    UserResponse,
)

router = APIRouter(
    prefix="/api/users",
    tags=["users"],
    dependencies=[Depends(require_roles(Role.ADMINISTRATOR))],
)


def _user_response(user: dict[str, Any]) -> UserResponse:
    return UserResponse(
        id=user["id"],
        email=user["email"],
        full_name=user["full_name"],
        role=user["role"],
        status=user["status"],
        created_at=user["created_at"],
    )
    
@router.get("/pending", response_model=list[UserResponse])
def get_pending_users(connection: Connection) -> list[UserResponse]:
    users = list_pending_users(connection)
    return [_user_response(user) for user in users]

@router.patch("/{user_id}/approve", response_model=UserResponse)
def approve_pending_user(
    user_id: UUID,
    payload: UserApprovalRequest,
    connection: Connection,
    actor: Annotated[
        dict[str, Any],
        Depends(require_roles(Role.ADMINISTRATOR)),
    ],
) -> UserResponse:
    user = find_user_by_id(connection, str(user_id))

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    if user["status"] != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User is not pending approval",
        )

    approve_user(
        connection,
        str(user_id),
        payload.role.value,
        actor["id"],
    )

    updated_user = find_user_by_id(connection, str(user_id))

    if updated_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return _user_response(updated_user)

@router.patch("/{user_id}/reject", response_model=UserResponse)
def reject_pending_user(
    user_id: UUID,
    connection: Connection,
    actor: Annotated[
        dict[str, Any],
        Depends(require_roles(Role.ADMINISTRATOR)),
    ],
) -> UserResponse:
    user = find_user_by_id(connection, str(user_id))

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    if user["status"] != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User is not pending approval",
        )

    reject_user(
        connection,
        str(user_id),
        actor["id"],
    )

    updated_user = find_user_by_id(connection, str(user_id))

    if updated_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return _user_response(updated_user)


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate, connection: Connection) -> UserResponse:
    try:
        user = create_user_record(
            connection,
            email=payload.email,
            full_name=payload.full_name,
            role=payload.role.value,
            password_hash=hash_password(payload.password),
        )
    except psycopg.errors.UniqueViolation as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists",
        ) from error

    return _user_response(user)


@router.get("", response_model=list[UserResponse])
def list_users(connection: Connection) -> list[UserResponse]:
    users = list_user_records(connection)
    return [_user_response(user) for user in users]


@router.patch("/{user_id}/role", response_model=UserResponse)
def change_user_role(
    user_id: UUID,
    payload: RoleUpdate,
    connection: Connection,
) -> UserResponse:
    connection.execute("LOCK TABLE users IN SHARE ROW EXCLUSIVE MODE")
    user = find_user_by_id(connection, str(user_id))
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if user["role"] == Role.ADMINISTRATOR.value and payload.role != Role.ADMINISTRATOR:
        admin_count = count_users_with_role(connection, Role.ADMINISTRATOR.value)
        if admin_count <= 1:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot demote the last administrator",
            )
    update_user_role(connection, str(user_id), payload.role.value)
    updated_user = find_user_by_id(connection, str(user_id))
    if updated_user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return _user_response(updated_user)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: UUID,
    connection: Connection,
    actor: Annotated[
        dict[str, Any],
        Depends(require_roles(Role.ADMINISTRATOR)),
    ],
) -> None:
    if actor["id"] == user_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Administrators cannot delete their own account",
        )

    connection.execute("LOCK TABLE users IN SHARE ROW EXCLUSIVE MODE")
    # Block new work referencing this author until the history check and delete finish.
    connection.execute("SELECT id FROM users WHERE id = %s FOR UPDATE", (user_id,))
    user = find_user_by_id(connection, str(user_id))

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    if user["role"] == Role.ADMINISTRATOR.value:
        admin_count = count_users_with_role(
            connection,
            Role.ADMINISTRATOR.value,
        )

        if admin_count <= 1:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot delete the last administrator",
            )

    if connection.execute("""
        SELECT EXISTS (SELECT FROM segments WHERE author_id = %(id)s)
            OR EXISTS (SELECT FROM video_summaries WHERE author_id = %(id)s)
            OR EXISTS (
                SELECT FROM annotation_review_events e
                JOIN video_assignments a ON a.id = e.assignment_id
                WHERE e.actor_id = %(id)s OR a.user_id = %(id)s
            ) AS has_work
    """, {"id": user_id}).fetchone()["has_work"]:
        raise HTTPException(409, "Cannot delete a user with annotations or review history")

    try:
        delete_user_record(connection, str(user_id))
    except psycopg.IntegrityError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete a user who has authored annotations or comments",
        ) from error
