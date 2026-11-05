"""FastAPI application entry point."""

from __future__ import annotations
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from contextlib import closing
from typing import AsyncGenerator

from fastapi import FastAPI

from app.api.router import api_router
from app.core.config import Settings
from app.core.security import hash_password
from app.db.database import Database
from app.repositories.user_repository import (
    create_user,
    find_user_role_by_email,
)
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
    with closing(database.connect()) as connection:
        existing_role = find_user_role_by_email(connection, user.email)
        if existing_role is not None:
            if existing_role != Role.ADMINISTRATOR.value:
                raise ValueError("INITIAL_ADMIN_EMAIL belongs to a non-administrator account")
            return
        create_user(
            connection,
            email=user.email,
            full_name=user.full_name,
            role=Role.ADMINISTRATOR.value,
            password_hash=hash_password(user.password),
        )


def create_app(settings: Settings | None = None) -> FastAPI:
    application_settings = settings or Settings.from_environment()
    database = Database(application_settings.database_url)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncGenerator[None, None]:
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

    application.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
    
    application.state.database = database
    application.state.settings = application_settings
    application.include_router(api_router)

    @application.get("/api/health", tags=["health"])
    def healthcheck() -> dict[str, str]:
        return {"status": "ok"}

    return application


app = create_app()
