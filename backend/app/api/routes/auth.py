"""Authentication API routes."""

from __future__ import annotations

from typing import Any

import psycopg
from fastapi import APIRouter, HTTPException, Request, status

from app.api.dependencies import Connection, CurrentUser
from app.core.config import Settings
from app.core.security import create_access_token, hash_password, verify_password
from app.repositories.user_repository import (
    create_pending_user,
    find_user_credentials_by_email,
)
from app.schemas.user import (
    CurrentUserResponse,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)

router = APIRouter(prefix="/api/auth", tags=["authentication"])


def _public_user(user: dict[str, Any]) -> CurrentUserResponse:
    return CurrentUserResponse(
        id=user["id"],
        email=user["email"],
        full_name=user["full_name"],
        role=user["role"],
        status=user["status"],
        created_at=user["created_at"],
    )


@router.post("/login", response_model=TokenResponse)
def login(
    payload: LoginRequest,
    request: Request,
    connection: Connection,
) -> TokenResponse:
    user = find_user_credentials_by_email(connection, payload.email)

    if user is None or not verify_password(
        payload.password,
        user["password_hash"],
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if user["status"] == "pending":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is waiting for administrator approval",
        )

    if user["status"] == "rejected":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account registration has been rejected",
        )

    settings: Settings = request.app.state.settings

    return TokenResponse(
        access_token=create_access_token(user["id"], settings)
    )


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(
    payload: RegisterRequest,
    connection: Connection,
) -> UserResponse:
    try:
        user = create_pending_user(
            connection,
            email=payload.email,
            full_name=payload.full_name,
            password_hash=hash_password(payload.password),
        )
    except psycopg.errors.UniqueViolation as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists",
        ) from error

    return UserResponse(
        id=user["id"],
        email=user["email"],
        full_name=user["full_name"],
        role=user["role"],
        status=user["status"],
        created_at=user["created_at"],
    )


@router.get("/me", response_model=CurrentUserResponse)
def read_current_user(user: CurrentUser) -> CurrentUserResponse:
    return _public_user(user)
