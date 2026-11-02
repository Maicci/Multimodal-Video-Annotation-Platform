"""PostgreSQL database setup and connections."""

from __future__ import annotations

from typing import Any, cast

import psycopg
from psycopg.rows import dict_row


class Database:
    def __init__(self, database_url: str) -> None:
        self.database_url = database_url

    def connect(self) -> psycopg.Connection[dict[str, Any]]:
        return cast(
            psycopg.Connection[dict[str, Any]],
            psycopg.connect(
                self.database_url,
                row_factory=dict_row,  # pyright: ignore[reportArgumentType]
            ),
        )

    def initialize(self) -> None:
        # TODO This is just a draft, modify to create all necessary tables
        with self.connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id UUID PRIMARY KEY,
                    email VARCHAR(254) NOT NULL UNIQUE,
                    full_name VARCHAR(120) NOT NULL,
                    role TEXT NOT NULL CHECK (
                        role IN ('annotator', 'reviewer', 'administrator')
                    ),
                    password_hash TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS videos (
                    id UUID PRIMARY KEY,
                    title TEXT NOT NULL,
                    original_filename TEXT NOT NULL,
                    stored_filename TEXT NOT NULL,
                    storage_path TEXT NOT NULL,
                    uploader_id UUID NOT NULL REFERENCES users (id),
                    upload_time TIMESTAMPTZ NOT NULL,
                    file_size_bytes BIGINT NOT NULL CHECK (file_size_bytes >= 0),
                    mime_type TEXT NOT NULL,
                    duration_seconds DOUBLE PRECISION,
                    width INTEGER,
                    height INTEGER,
                    fps DOUBLE PRECISION,
                    codec TEXT,
                    processing_status TEXT NOT NULL,
                    metadata_extracted BOOLEAN NOT NULL DEFAULT FALSE,
                    updated_at TIMESTAMPTZ NOT NULL
                )
                """
            )