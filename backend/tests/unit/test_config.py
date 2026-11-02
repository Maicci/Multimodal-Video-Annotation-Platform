from __future__ import annotations

import pytest
from psycopg.conninfo import make_conninfo

from app.core.config import Settings


def _settings(database_url: str) -> Settings:
    return Settings(
        database_url=database_url,
        jwt_secret_key="a" * 32,
        access_token_minutes=30,
    )


@pytest.mark.parametrize(
    "database_url",
    [
        "postgresql://localhost/video_annotation_test",
        "postgres://localhost/video_annotation_test",
        make_conninfo(
            user="postgres",
            dbname="video_annotation_test",
            host="localhost",
        ),
    ],
)
def test_validate_accepts_postgresql_connection_strings(database_url: str) -> None:
    _settings(database_url).validate()


@pytest.mark.parametrize(
    "database_url",
    [
        "sqlite:///video_annotation.db",
        "postgresql://",
        "postgres://",
    ],
)
def test_validate_rejects_invalid_connection_strings(database_url: str) -> None:
    with pytest.raises(ValueError, match="DATABASE_URL"):
        _settings(database_url).validate()
