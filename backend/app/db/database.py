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
                role TEXT CHECK (
                role IN ('annotator', 'reviewer', 'administrator')
                ),
                status TEXT NOT NULL DEFAULT 'active' CHECK (
                status IN ('pending', 'active', 'rejected')
                ),
                password_hash TEXT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                approved_by UUID REFERENCES users (id),
                approved_at TIMESTAMPTZ
                )
                """
            )
            
            connection.execute(
                """
                ALTER TABLE users
                ALTER COLUMN role DROP NOT NULL
                """
                )
            
            connection.execute(
                """
                ALTER TABLE users
                ADD COLUMN IF NOT EXISTS status TEXT
                NOT NULL DEFAULT 'active'
                CHECK (status IN ('pending', 'active', 'rejected'))
                """
                )
            
            connection.execute(
                """
                ALTER TABLE users
                ADD COLUMN IF NOT EXISTS approved_by UUID REFERENCES users (id)
                """
                )
            
            connection.execute(
                """
                ALTER TABLE users
                ADD COLUMN IF NOT EXISTS approved_at TIMESTAMPTZ
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
                    timeline_path TEXT,
                    frame_count INTEGER,
                    is_vfr BOOLEAN,
                    updated_at TIMESTAMPTZ NOT NULL
                )
                """
            )
            connection.execute("ALTER TABLE videos ADD COLUMN IF NOT EXISTS timeline_path TEXT")
            connection.execute("ALTER TABLE videos ADD COLUMN IF NOT EXISTS frame_count INTEGER")
            connection.execute("ALTER TABLE videos ADD COLUMN IF NOT EXISTS is_vfr BOOLEAN")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS segments (
                    id UUID PRIMARY KEY,
                    video_id UUID NOT NULL REFERENCES videos (id) ON DELETE CASCADE,
                    author_id UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
                    title VARCHAR(120) NOT NULL,
                    start_time DOUBLE PRECISION NOT NULL CHECK (start_time >= 0),
                    end_time DOUBLE PRECISION NOT NULL CHECK (end_time > start_time),
                    description TEXT NOT NULL DEFAULT '',
                    audio_description TEXT NOT NULL DEFAULT '',
                    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            connection.execute(
                "ALTER TABLE segments ADD COLUMN IF NOT EXISTS audio_description "
                "TEXT NOT NULL DEFAULT ''"
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS video_summaries (
                    video_id UUID NOT NULL REFERENCES videos (id) ON DELETE CASCADE,
                    author_id UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
                    summary TEXT NOT NULL DEFAULT '',
                    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (video_id, author_id)
                )
                """
            )

            connection.execute("ALTER TABLE segments ADD COLUMN IF NOT EXISTS start_frame INTEGER")
            connection.execute("ALTER TABLE segments ADD COLUMN IF NOT EXISTS end_frame INTEGER")
            connection.execute("ALTER TABLE segments ADD COLUMN IF NOT EXISTS version INTEGER NOT NULL DEFAULT 1")
            connection.execute("ALTER TABLE video_summaries ADD COLUMN IF NOT EXISTS version INTEGER NOT NULL DEFAULT 1")
            connection.execute(
                "ALTER TABLE videos ADD COLUMN IF NOT EXISTS protocol_group TEXT "
                "NOT NULL DEFAULT 'individual' CHECK (protocol_group IN ('shared', 'individual'))"
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS video_assignments (
                    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    video_id     UUID NOT NULL REFERENCES videos (id) ON DELETE CASCADE,
                    user_id      UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
                    status       TEXT NOT NULL DEFAULT 'not_started'
                                CHECK (status IN ('not_started', 'in_progress', 'completed')),
                    assigned_at  TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at   TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMPTZ,
                    UNIQUE (video_id, user_id)
                )
                """
            )
