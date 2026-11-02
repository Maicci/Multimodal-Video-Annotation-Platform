"""Application configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import psycopg
from psycopg.conninfo import conninfo_to_dict


@dataclass(frozen=True)
class Settings:
    database_url: str
    jwt_secret_key: str
    access_token_minutes: int
    initial_admin_email: str | None = None
    initial_admin_password: str | None = None
    initial_admin_name: str = "Administrator"
    video_storage_path: Path | None = None
    max_video_size_bytes: int = 500 * 1024 * 1024

    @classmethod
    def from_environment(cls) -> Settings:
        backend_root = Path(__file__).resolve().parents[2]
        token_minutes = int(os.getenv("ACCESS_TOKEN_MINUTES", "30"))
        if token_minutes < 1:
            raise ValueError("ACCESS_TOKEN_MINUTES must be positive")
        max_video_size_mb = int(os.getenv("MAX_VIDEO_SIZE_MB", "500"))
        if max_video_size_mb < 1:
            raise ValueError("MAX_VIDEO_SIZE_MB must be positive")

        return cls(
            database_url=os.getenv("DATABASE_URL", ""),
            jwt_secret_key=os.getenv("JWT_SECRET_KEY", ""),
            access_token_minutes=token_minutes,
            initial_admin_email=os.getenv("INITIAL_ADMIN_EMAIL"),
            initial_admin_password=os.getenv("INITIAL_ADMIN_PASSWORD"),
            initial_admin_name=os.getenv("INITIAL_ADMIN_NAME", "Administrator"),
            video_storage_path=Path(
                os.getenv(
                    "VIDEO_STORAGE_PATH",
                    str(backend_root.parent / "storage" / "videos" / "original"),
                )
            ),
            max_video_size_bytes=max_video_size_mb * 1024 * 1024,
        )

    def validate(self) -> None:
        try:
            is_valid_conninfo = bool(conninfo_to_dict(self.database_url))
        except psycopg.ProgrammingError:
            is_valid_conninfo = False
        if not is_valid_conninfo:
            raise ValueError("DATABASE_URL must be a PostgreSQL connection URL")
        if len(self.jwt_secret_key) < 32:
            raise ValueError("JWT_SECRET_KEY must contain at least 32 characters")
        if self.max_video_size_bytes < 1:
            raise ValueError("max_video_size_bytes must be positive")
        if bool(self.initial_admin_email) != bool(self.initial_admin_password):
            raise ValueError(
                "INITIAL_ADMIN_EMAIL and INITIAL_ADMIN_PASSWORD must be set together"
            )
        if self.initial_admin_password and len(self.initial_admin_password) < 12:
            raise ValueError("INITIAL_ADMIN_PASSWORD must contain at least 12 characters")
