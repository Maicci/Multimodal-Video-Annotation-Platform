"""Authentication API routes."""

from __future__ import annotations

import sqlite3
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.api.dependencies import Connection, CurrentUser
from app.core.config import Settings
from app.core.security import create_access_token, verify_password
from app.schemas.user import CurrentUserResponse, LoginRequest, TokenResponse

router = APIRouter(prefix="/api/auth", tags=["authentication"])


def _public_user(user: sqlite3.Row) -> CurrentUserResponse:
    return CurrentUserResponse(
        id=user["id"],
        email=user["email"],
        full_name=user["full_name"],
        role=user["role"],
        created_at=user["created_at"],
    )


@router.post("/login", response_model=TokenResponse)
def login(
    payload: LoginRequest,
    request: Request,
    connection: Connection,
) -> TokenResponse:
    user = connection.execute(
        "SELECT id, password_hash FROM users WHERE email = ?",
        (payload.email,),
    ).fetchone()
    if user is None or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    settings: Settings = request.app.state.settings
    return TokenResponse(access_token=create_access_token(user["id"], settings))


@router.get("/me", response_model=CurrentUserResponse)
def read_current_user(user: CurrentUser) -> CurrentUserResponse:
    return _public_user(user)
