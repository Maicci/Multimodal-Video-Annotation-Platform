"""FastAPI application entry point."""

from __future__ import annotations

from contextlib import asynccontextmanager
from contextlib import closing
from typing import AsyncIterator
from uuid import uuid4

from fastapi import FastAPI

from app.api.router import api_router
from app.core.config import Settings
from app.core.security import hash_password
from app.db.database import Database
from app.schemas.user import Role, UserCreate


def _bootstrap_admin(database: Database, settings: Settings) -> None:
    if settings.initial_admin_email is None or settings.initial_admin_password is None:
        return

    email = settings.initial_admin_email.strip().lower()
    user = UserCreate(
        email=email,
        full_name=settings.initial_admin_name,
        password=settings.initial_admin_password,
        role=Role.ADMINISTRATOR,
    )
    with closing(database.connect()) as connection, connection:
        existing = connection.execute(
            "SELECT role FROM users WHERE email = ?", (user.email,)
        ).fetchone()
        if existing is not None:
            if existing["role"] != Role.ADMINISTRATOR.value:
                raise ValueError("INITIAL_ADMIN_EMAIL belongs to a non-administrator account")
            return
        connection.execute(
            """
            INSERT INTO users (id, email, full_name, role, password_hash)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                str(uuid4()),
                user.email,
                user.full_name,
                Role.ADMINISTRATOR.value,
                hash_password(user.password),
            ),
        )


def create_app(settings: Settings | None = None) -> FastAPI:
    application_settings = settings or Settings.from_environment()
    database = Database(application_settings.database_path)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        application_settings.validate()
        database.initialize()
        _bootstrap_admin(database, application_settings)
        yield

    application = FastAPI(
        title="Multimodal Video Annotation Platform API",
        description="JWT-authenticated API for users, assigned videos, and annotations.",
        version="0.1.0",
        lifespan=lifespan,
    )
    application.state.database = database
    application.state.settings = application_settings
    application.include_router(api_router)

    @application.get("/api/health", tags=["health"])
    def healthcheck() -> dict[str, str]:
        return {"status": "ok"}

    return application


app = create_app()
