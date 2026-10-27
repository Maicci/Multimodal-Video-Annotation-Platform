"""Shared FastAPI dependencies."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable, Generator
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import Settings
from app.core.security import decode_access_token
from app.db.database import Database
from app.schemas.user import Role

bearer_scheme = HTTPBearer(auto_error=False)


def get_database(request: Request) -> Database:
    return request.app.state.database


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_connection(
    database: Annotated[Database, Depends(get_database)],
) -> Generator[sqlite3.Connection, None, None]:
    connection = database.connect()
    try:
        yield connection
    finally:
        connection.close()


def get_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(bearer_scheme)
    ],
    connection: Annotated[sqlite3.Connection, Depends(get_connection)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> sqlite3.Row:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing authentication credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise unauthorized

    try:
        user_id = decode_access_token(credentials.credentials, settings)
    except (jwt.InvalidTokenError, ValueError) as error:
        raise unauthorized from error

    user = connection.execute(
        "SELECT id, email, full_name, role, created_at FROM users WHERE id = ?",
        (str(user_id),),
    ).fetchone()
    if user is None:
        raise unauthorized
    return user


def require_roles(*roles: Role) -> Callable:
    allowed_roles = set(roles)

    def dependency(
        user: Annotated[sqlite3.Row, Depends(get_current_user)],
    ) -> sqlite3.Row:
        if user["role"] == Role.ADMINISTRATOR.value:
            return user
        if user["role"] not in {role.value for role in allowed_roles}:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return user

    return dependency


CurrentUser = Annotated[sqlite3.Row, Depends(get_current_user)]
Connection = Annotated[sqlite3.Connection, Depends(get_connection)]
