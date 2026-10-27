"""Administrator-only user management routes."""

from __future__ import annotations

import sqlite3
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlite3 import IntegrityError

from app.api.dependencies import Connection, require_roles
from app.core.security import hash_password
from app.schemas.user import Role, RoleUpdate, UserCreate, UserResponse

router = APIRouter(
    prefix="/api/users",
    tags=["users"],
    dependencies=[Depends(require_roles(Role.ADMINISTRATOR))],
)


def _user_response(user: sqlite3.Row) -> UserResponse:
    return UserResponse(
        id=user["id"],
        email=user["email"],
        full_name=user["full_name"],
        role=user["role"],
        created_at=user["created_at"],
    )


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate, connection: Connection) -> UserResponse:
    user_id = str(uuid4())
    try:
        with connection:
            connection.execute(
                """
                INSERT INTO users (id, email, full_name, role, password_hash)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    payload.email,
                    payload.full_name,
                    payload.role.value,
                    hash_password(payload.password),
                ),
            )
    except IntegrityError as error:
        if "users.email" in str(error):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A user with this email already exists",
            ) from error
        raise

    user = connection.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return _user_response(user)


@router.get("", response_model=list[UserResponse])
def list_users(connection: Connection) -> list[UserResponse]:
    users = connection.execute(
        "SELECT id, email, full_name, role, created_at FROM users ORDER BY email"
    ).fetchall()
    return [_user_response(user) for user in users]


@router.patch("/{user_id}/role", response_model=UserResponse)
def change_user_role(
    user_id: UUID,
    payload: RoleUpdate,
    connection: Connection,
) -> UserResponse:
    user = connection.execute("SELECT * FROM users WHERE id = ?", (str(user_id),)).fetchone()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if user["role"] == Role.ADMINISTRATOR.value and payload.role != Role.ADMINISTRATOR:
        admin_count = connection.execute(
            "SELECT COUNT(*) FROM users WHERE role = ?",
            (Role.ADMINISTRATOR.value,),
        ).fetchone()[0]
        if admin_count <= 1:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot demote the last administrator",
            )
    with connection:
        connection.execute(
            "UPDATE users SET role = ? WHERE id = ?",
            (payload.role.value, str(user_id)),
        )
    updated_user = connection.execute(
        "SELECT * FROM users WHERE id = ?", (str(user_id),)
    ).fetchone()
    return _user_response(updated_user)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: UUID,
    connection: Connection,
    actor: Annotated[sqlite3.Row, Depends(require_roles(Role.ADMINISTRATOR))],
) -> None:
    if actor["id"] == str(user_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Administrators cannot delete their own account",
        )
    user = connection.execute(
        "SELECT role FROM users WHERE id = ?", (str(user_id),)
    ).fetchone()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if user["role"] == Role.ADMINISTRATOR.value:
        admin_count = connection.execute(
            "SELECT COUNT(*) FROM users WHERE role = ?",
            (Role.ADMINISTRATOR.value,),
        ).fetchone()[0]
        if admin_count <= 1:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot delete the last administrator",
            )
    try:
        with connection:
            connection.execute("DELETE FROM users WHERE id = ?", (str(user_id),))
    except IntegrityError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete a user who has authored annotations or comments",
        ) from error
