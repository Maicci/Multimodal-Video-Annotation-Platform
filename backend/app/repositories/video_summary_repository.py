"""Persistence for user-owned whole-video summaries."""

from typing import Any

import psycopg


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
) -> dict[str, Any]:
    with connection:
        row = connection.execute(
            """
            INSERT INTO video_summaries (video_id, author_id, summary)
            VALUES (%s, %s, %s)
            ON CONFLICT (video_id, author_id) DO UPDATE
            SET summary = EXCLUDED.summary, updated_at = CURRENT_TIMESTAMP,
                version = video_summaries.version + 1
            WHERE video_summaries.version = %s
            RETURNING video_id, author_id, summary, version
            """,
            (video_id, author_id, summary, version),
        ).fetchone()

        if row:
            connection.execute("UPDATE video_assignments SET status = 'in_progress', completed_at = NULL, updated_at = CURRENT_TIMESTAMP WHERE video_id = %s AND user_id = %s", (video_id, author_id))
        return row
