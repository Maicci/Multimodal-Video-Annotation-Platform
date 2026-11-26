"""Persistence for user-owned whole-video summaries."""

from typing import Any

import psycopg
from app.repositories.annotation_workflow import require_editable


def find_video_summary(
    connection: psycopg.Connection[Any], video_id: str, author_id: str,
) -> dict[str, Any] | None:
    return connection.execute(
        """
        SELECT video_id, author_id, summary, version
        FROM video_summaries
        WHERE video_id = %s AND author_id = %s
        """,
        (video_id, author_id),
    ).fetchone()


def save_video_summary(
    connection: psycopg.Connection[Any], video_id: str, author_id: str,
    summary: str, version: int,
) -> dict[str, Any] | None:
    with connection:
        require_editable(connection, video_id, author_id)
        if version == 0:
            row = connection.execute("""
                INSERT INTO video_summaries (video_id, author_id, summary)
                VALUES (%s, %s, %s) ON CONFLICT (video_id, author_id) DO NOTHING
                RETURNING video_id, author_id, summary, version
            """, (video_id, author_id, summary)).fetchone()
        else:
            row = connection.execute("""
                UPDATE video_summaries
                SET summary = %s, updated_at = CURRENT_TIMESTAMP, version = version + 1
                WHERE video_id = %s AND author_id = %s AND version = %s
                RETURNING video_id, author_id, summary, version
            """, (summary, video_id, author_id, version)).fetchone()

        if row:
            connection.execute("UPDATE video_assignments SET status = CASE WHEN status = 'returned' THEN status ELSE 'in_progress' END, completed_at = NULL, updated_at = CURRENT_TIMESTAMP WHERE video_id = %s AND user_id = %s", (video_id, author_id))
        return row
