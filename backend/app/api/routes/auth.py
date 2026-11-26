"""Authentication API routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response, status

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
)

router = APIRouter(prefix="/api/auth", tags=["authentication"])
# Verify one Argon2 hash even when the lookup returns no account.
_DUMMY_PASSWORD_HASH = hash_password("unused login verification value")


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

    password_matches = verify_password(
        payload.password, user["password_hash"] if user else _DUMMY_PASSWORD_HASH
    )
    if user is None or not password_matches or user["status"] != "active":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unable to sign in with those credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    settings: Settings = request.app.state.settings

    return TokenResponse(
        access_token=create_access_token(user["id"], settings)
    )


@router.post(
    "/register",
    response_class=Response,
    status_code=status.HTTP_202_ACCEPTED,
)
def register(
    payload: RegisterRequest,
    connection: Connection,
) -> Response:
    create_pending_user(
        connection,
        email=payload.email,
        full_name=payload.full_name,
        password_hash=hash_password(payload.password),
    )
    return Response(status_code=status.HTTP_202_ACCEPTED)


@router.get("/me", response_model=CurrentUserResponse)
def read_current_user(user: CurrentUser) -> CurrentUserResponse:
    return _public_user(user)
