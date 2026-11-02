"""Shared FastAPI dependencies."""

from __future__ import annotations

from collections.abc import Callable, Generator
from typing import Annotated, Any

import jwt
import psycopg
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import Settings
from app.core.security import decode_access_token
from app.db.database import Database
from app.repositories.user_repository import find_user_by_id
from app.schemas.user import Role

bearer_scheme = HTTPBearer(auto_error=False)


def get_database(request: Request) -> Database:
    return request.app.state.database


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_connection(
    database: Annotated[Database, Depends(get_database)],
) -> Generator[psycopg.Connection[Any], None, None]:
    connection = database.connect()
    try:
        yield connection
    finally:
        connection.close()


def get_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(bearer_scheme)
    ],
    connection: Annotated[psycopg.Connection[Any], Depends(get_connection)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
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

    user = find_user_by_id(connection, str(user_id))
    if user is None:
        raise unauthorized
    return user


def require_roles(*roles: Role) -> Callable:
    allowed_roles = set(roles)

    def dependency(
        user: Annotated[dict[str, Any], Depends(get_current_user)],
    ) -> dict[str, Any]:
        if user["role"] == Role.ADMINISTRATOR.value:
            return user
        if user["role"] not in {role.value for role in allowed_roles}:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return user

    return dependency


CurrentUser = Annotated[dict[str, Any], Depends(get_current_user)]
Connection = Annotated[psycopg.Connection[Any], Depends(get_connection)]
