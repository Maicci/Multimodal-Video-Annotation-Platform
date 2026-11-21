"""Database operations for user-owned video segments."""

from typing import Any
from uuid import uuid4

import psycopg

from app.schemas.segment import SegmentInput


def list_segments(
    connection: psycopg.Connection[Any], video_id: str, author_id: str
) -> list[dict[str, Any]]:
    return connection.execute(
        """
        SELECT id, video_id, author_id, title, start_time, end_time, description
        FROM segments
        WHERE video_id = %s AND author_id = %s
        ORDER BY start_time, created_at
        """,
        (video_id, author_id),
    ).fetchall()


def create_segment(
    connection: psycopg.Connection[Any], video_id: str, author_id: str,
    payload: SegmentInput,
) -> dict[str, Any]:
    with connection:
        return connection.execute(
            """
            INSERT INTO segments (
                id, video_id, author_id, title, start_time, end_time, description
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id, video_id, author_id, title, start_time, end_time, description
            """,
            (
                str(uuid4()), video_id, author_id, payload.title,
                payload.start_time, payload.end_time, payload.description,
            ),
        ).fetchone()


def update_segment(
    connection: psycopg.Connection[Any], segment_id: str, video_id: str,
    author_id: str, payload: SegmentInput,
) -> dict[str, Any] | None:
    with connection:
        return connection.execute(
            """
            UPDATE segments
            SET title = %s, start_time = %s, end_time = %s,
                description = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s AND video_id = %s AND author_id = %s
            RETURNING id, video_id, author_id, title, start_time, end_time, description
            """,
            (
                payload.title, payload.start_time, payload.end_time,
                payload.description, segment_id, video_id, author_id,
            ),
        ).fetchone()


def delete_segment(
    connection: psycopg.Connection[Any], segment_id: str, video_id: str,
    author_id: str,
) -> bool:
    with connection:
        row = connection.execute(
            """
            DELETE FROM segments
            WHERE id = %s AND video_id = %s AND author_id = %s
            RETURNING id
            """,
            (segment_id, video_id, author_id),
        ).fetchone()
    return row is not None
