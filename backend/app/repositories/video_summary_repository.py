"""Persistence for user-owned whole-video summaries."""

from typing import Any

import psycopg


def find_video_summary(
    connection: psycopg.Connection[Any], video_id: str, author_id: str,
) -> dict[str, Any] | None:
    return connection.execute(
        """
        SELECT video_id, author_id, summary
        FROM video_summaries
        WHERE video_id = %s AND author_id = %s
        """,
        (video_id, author_id),
    ).fetchone()


def save_video_summary(
    connection: psycopg.Connection[Any], video_id: str, author_id: str,
    summary: str,
) -> dict[str, Any]:
    with connection:
        return connection.execute(
            """
            INSERT INTO video_summaries (video_id, author_id, summary)
            VALUES (%s, %s, %s)
            ON CONFLICT (video_id, author_id) DO UPDATE
            SET summary = EXCLUDED.summary, updated_at = CURRENT_TIMESTAMP
            RETURNING video_id, author_id, summary
            """,
            (video_id, author_id, summary),
        ).fetchone()
