"""Application configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    database_path: Path
    jwt_secret_key: str
    access_token_minutes: int
    initial_admin_email: str | None = None
    initial_admin_password: str | None = None
    initial_admin_name: str = "Administrator"

    @classmethod
    def from_environment(cls) -> Settings:
        backend_root = Path(__file__).resolve().parents[2]
        token_minutes = int(os.getenv("ACCESS_TOKEN_MINUTES", "30"))
        if token_minutes < 1:
            raise ValueError("ACCESS_TOKEN_MINUTES must be positive")

        return cls(
            database_path=Path(
                os.getenv("DATABASE_PATH", str(backend_root / "data" / "app.sqlite3"))
            ),
            jwt_secret_key=os.getenv("JWT_SECRET_KEY", ""),
            access_token_minutes=token_minutes,
            initial_admin_email=os.getenv("INITIAL_ADMIN_EMAIL"),
            initial_admin_password=os.getenv("INITIAL_ADMIN_PASSWORD"),
            initial_admin_name=os.getenv("INITIAL_ADMIN_NAME", "Administrator"),
        )

    def validate(self) -> None:
        if len(self.jwt_secret_key) < 32:
            raise ValueError("JWT_SECRET_KEY must contain at least 32 characters")
        if bool(self.initial_admin_email) != bool(self.initial_admin_password):
            raise ValueError(
                "INITIAL_ADMIN_EMAIL and INITIAL_ADMIN_PASSWORD must be set together"
            )
        if self.initial_admin_password and len(self.initial_admin_password) < 12:
            raise ValueError("INITIAL_ADMIN_PASSWORD must contain at least 12 characters")
