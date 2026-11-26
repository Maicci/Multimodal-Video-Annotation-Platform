"""Database operations for user-owned video segments."""

from typing import Any
from uuid import uuid4

import psycopg
from fastapi import HTTPException

from app.schemas.segment import SegmentInput
from app.repositories.annotation_workflow import LOCKED_STATES, require_editable
from app.services.segment_timing import resolve_segment, timeline_for


def list_segments(
    connection: psycopg.Connection[Any], video_id: str, author_id: str
) -> list[dict[str, Any]]:
    return connection.execute(
        """
        SELECT id, video_id, author_id, title, start_time, end_time,
               description, audio_description, version, start_frame, end_frame
        FROM segments
        WHERE video_id = %s AND author_id = %s
        ORDER BY start_time, created_at
        """,
        (video_id, author_id),
    ).fetchall()


def list_normalized_segments(connection, video, author_id, assignment):
    rows = list_segments(connection, video.id, str(author_id))
    if not rows or (assignment and assignment["status"] in LOCKED_STATES):
        return rows
    try:
        timeline = timeline_for(video)
    except HTTPException:
        return rows  # Legacy text remains available before timing is ready.
    changed = False
    for row in rows:
        missing_frames = row["start_frame"] is None or row["end_frame"] is None
        old_final = row["end_frame"] == timeline.frame_count and row["end_time"] != timeline.end_time
        if not (missing_frames or old_final or timeline.preroll_frames):
            continue
        segment = SegmentInput(**row)
        try:
            normalized = resolve_segment(video, segment, stored=True, timeline=timeline)
        except HTTPException:
            continue
        if normalized != segment:
            connection.execute("""
                UPDATE segments SET start_time = %s, end_time = %s, start_frame = %s,
                    end_frame = %s, version = version + 1 WHERE id = %s AND version = %s
            """, (normalized.start_time, normalized.end_time, normalized.start_frame,
                  normalized.end_frame, row["id"], row["version"]))
            changed = True
    return list_segments(connection, video.id, str(author_id)) if changed else rows


def create_segment(
    connection: psycopg.Connection[Any], video_id: str, author_id: str,
    payload: SegmentInput,
) -> dict[str, Any]:
    with connection:
        require_editable(connection, video_id, author_id)
        row = connection.execute(
            """
            INSERT INTO segments (
                id, video_id, author_id, title, start_time, end_time,
                description, audio_description, start_frame, end_frame
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id, video_id, author_id, title, start_time, end_time,
                      description, audio_description, version, start_frame, end_frame
            """,
            (
                str(uuid4()), video_id, author_id, payload.title,
                payload.start_time, payload.end_time, payload.description,
                payload.audio_description, payload.start_frame, payload.end_frame,
            ),
        ).fetchone()
        if row:
            connection.execute("UPDATE video_assignments SET status = CASE WHEN status = 'returned' THEN status ELSE 'in_progress' END, completed_at = NULL, updated_at = CURRENT_TIMESTAMP WHERE video_id = %s AND user_id = %s", (video_id, author_id))
        return row


def update_segment(
    connection: psycopg.Connection[Any], segment_id: str, video_id: str,
    author_id: str, payload: SegmentInput,
) -> dict[str, Any] | None:
    with connection:
        require_editable(connection, video_id, author_id)
        row = connection.execute(
            """
            UPDATE segments
            SET title = %s, start_time = %s, end_time = %s,
                description = %s, audio_description = %s, start_frame = %s, end_frame = %s,
                updated_at = CURRENT_TIMESTAMP, version = version + 1
            WHERE id = %s AND video_id = %s AND author_id = %s AND version = %s
            RETURNING id, video_id, author_id, title, start_time, end_time,
                      description, audio_description, version, start_frame, end_frame
            """,
            (
                payload.title, payload.start_time, payload.end_time,
                payload.description, payload.audio_description, payload.start_frame, payload.end_frame,
                segment_id, video_id, author_id, payload.version,
            ),
        ).fetchone()
        if row:
            connection.execute("UPDATE video_assignments SET status = CASE WHEN status = 'returned' THEN status ELSE 'in_progress' END, completed_at = NULL, updated_at = CURRENT_TIMESTAMP WHERE video_id = %s AND user_id = %s", (video_id, author_id))
        return row


def delete_segment(
    connection: psycopg.Connection[Any], segment_id: str, video_id: str,
    author_id: str, version: int,
) -> bool:
    with connection:
        require_editable(connection, video_id, author_id)
        row = connection.execute(
            """
            DELETE FROM segments
            WHERE id = %s AND video_id = %s AND author_id = %s AND version = %s
            RETURNING id
            """,
            (segment_id, video_id, author_id, version),
        ).fetchone()
        if row:
            connection.execute("UPDATE video_assignments SET status = CASE WHEN status = 'returned' THEN status ELSE 'in_progress' END, completed_at = NULL, updated_at = CURRENT_TIMESTAMP WHERE video_id = %s AND user_id = %s", (video_id, author_id))
    return row is not None
