"""FastAPI application entry point."""

from __future__ import annotations

from contextlib import asynccontextmanager, closing
import logging
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.api.videoplayer import router as videos_router
from app.services.transcription import recover_interrupted_jobs
from app.core.config import Settings
from app.core.security import hash_password
from app.db.database import Database
from app.repositories.user_repository import (
    create_user,
    find_user_role_by_email,
)
from app.schemas.user import Role, UserCreate


def _omit_access_log_query(record: logging.LogRecord) -> bool:
    # Uvicorn passes (client, method, request target, HTTP version, status).
    args = record.args
    if isinstance(args, tuple) and len(args) == 5 and isinstance(args[2], str):
        record.args = (*args[:2], args[2].partition("?")[0], *args[3:])
    return True


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
                raise ValueError(
                    "INITIAL_ADMIN_EMAIL belongs to a non-administrator account"
                )
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
        logging.getLogger("uvicorn.access").addFilter(_omit_access_log_query)
        application_settings.validate()
        database.initialize()
        _bootstrap_admin(database, application_settings)
        recover_interrupted_jobs(database)
        yield

    application = FastAPI(
        title="Multimodal Video Annotation Platform API",
        description="JWT-authenticated API for users, assigned videos, and annotations.",
        version="0.1.0",
        lifespan=lifespan,
    )

    @application.exception_handler(RequestValidationError)
    async def validation_error(_: Request, error: RequestValidationError) -> JSONResponse:
        # Send field diagnostics without echoing passwords or raw request bodies.
        detail = [{key: item[key] for key in ("loc", "msg", "type")} for item in error.errors()]
        return JSONResponse(status_code=422, content={"detail": detail})

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
    application.include_router(
        videos_router,
        prefix="/api",
    )

    @application.get("/api/health", tags=["health"])
    def healthcheck() -> dict[str, str]:
        return {"status": "ok"}

    return application


app = create_app()
