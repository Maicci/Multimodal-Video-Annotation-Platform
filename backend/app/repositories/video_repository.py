"""Persistence operations for uploaded videos."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import psycopg

from app.db.models.video import Video
from app.services.video_metadata import VideoMetadata
from app.services.video_storage import StoredVideo

# TODO queries need to be updated when the database structure is decided


_VIDEO_COLUMNS = """
    id, original_filename, stored_filename, storage_path, uploader_id,
    upload_time, file_size_bytes, mime_type, duration_seconds, width,
    height, fps, codec, processing_status, metadata_extracted, processing_error
"""

def _row_to_video(row: dict[str, Any]) -> Video:
    return Video(
        id=str(row["id"]),
        original_filename=row["original_filename"],
        stored_filename=row["stored_filename"],
        storage_path=row["storage_path"],
        uploader_id=str(row["uploader_id"]),
        upload_time=row["upload_time"].isoformat(),
        file_size_bytes=row["file_size_bytes"],
        mime_type=row["mime_type"],
        duration_seconds=row["duration_seconds"],
        width=row["width"],
        height=row["height"],
        fps=row["fps"],
        codec=row["codec"],
        processing_status=row["processing_status"],
        metadata_extracted=row["metadata_extracted"],
        processing_error=row["processing_error"],
    )

def find_video_by_content_hash(
    connection: psycopg.Connection[dict[str, Any]], content_hash: str
) -> str | None:
    row = connection.execute(
        "SELECT id FROM videos WHERE content_hash = %s",
        (content_hash,),
    ).fetchone()
    return None if row is None else str(row["id"])

def find_video_by_id(
    connection: psycopg.Connection[dict[str, Any]],
    video_id: str,
) -> Video | None:
    row = connection.execute(
        f"SELECT {_VIDEO_COLUMNS} FROM videos WHERE id = %s",
        (video_id,),
    ).fetchone()
    return None if row is None else _row_to_video(row)


def list_videos(connection: psycopg.Connection[dict[str, Any]]) -> list[Video]:
    rows = connection.execute(
        f"SELECT {_VIDEO_COLUMNS} FROM videos ORDER BY upload_time DESC"
    ).fetchall()
    return [_row_to_video(row) for row in rows]


def create_video(
    connection: psycopg.Connection[dict[str, Any]],
    *,
    original_filename: str,
    uploader_id: str,
    mime_type: str,
    stored_video: StoredVideo,
    metadata: VideoMetadata,
    title: str | None = None,
    content_hash: str | None = None,
) -> Video:
    video_id = str(uuid4())
    upload_time = datetime.now(timezone.utc)
    with connection:
        row = connection.execute(
            f"""
            INSERT INTO videos (
                id, title, original_filename, stored_filename, storage_path,
                uploader_id, upload_time, file_size_bytes, mime_type,
                duration_seconds, width, height, fps, codec, processing_status,
                metadata_extracted, content_hash, updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    'QUEUED', TRUE, %s, %s)
            RETURNING {_VIDEO_COLUMNS}
            """,
            (
                video_id,
                title or original_filename,
                original_filename,
                stored_video.filename,
                str(stored_video.path),
                uploader_id,
                upload_time,
                stored_video.size_bytes,
                mime_type,
                metadata.duration_seconds,
                metadata.width,
                metadata.height,
                metadata.fps,
                metadata.codec,
                content_hash,
                upload_time,
            ),
        ).fetchone()

    if row is None:  # an INSERT ... RETURNING should always give the row back
        raise RuntimeError("Video insert returned no row")
    return _row_to_video(row)

def delete_video(
    connection: psycopg.Connection[dict[str, Any]], video_id: str
) -> Video | None:
    """Delete the row and return it (so the caller can remove its files).

    Returns None when no video with this id exists.
    """
    with connection:
        row = connection.execute(
            f"DELETE FROM videos WHERE id = %s RETURNING {_VIDEO_COLUMNS}",
            (video_id,),
        ).fetchone()
    return None if row is None else _row_to_video(row)


def start_video_processing(
    connection: psycopg.Connection, video_id: str
) -> bool:
    with connection:
        result = connection.execute(
            """
            UPDATE videos
            SET processing_status = 'RUNNING', updated_at = %s
            WHERE id = %s AND processing_status = 'QUEUED'
            """,
            (datetime.now(timezone.utc), video_id),
        )
    return result.rowcount == 1


def save_timeline_info(
    connection: psycopg.Connection,
    video_id: str,
    *,
    timeline_path: str,
    frame_count: int,
    is_vfr: bool,
) -> None:
    with connection:
        connection.execute(
            """
            UPDATE videos
            SET timeline_path = %s, frame_count = %s, is_vfr = %s, updated_at = %s
            WHERE id = %s
            """,
            (timeline_path, frame_count, is_vfr, datetime.now(timezone.utc), video_id),
        )


def fail_video_processing(connection: psycopg.Connection, video_id: str, error: str = "Processing failed") -> None:
    with connection:
        connection.execute(
            """
            UPDATE videos
            SET processing_status = 'FAILED', processing_error = %s, updated_at = %s
            WHERE id = %s
            """,
            (error, datetime.now(timezone.utc), video_id),
        )


def complete_video_processing(connection: psycopg.Connection, video_id: str) -> None:
    with connection:
        connection.execute(
            """
            UPDATE videos
            SET processing_status = 'COMPLETED', updated_at = %s
            WHERE id = %s AND processing_status = 'RUNNING'
            """,
            (datetime.now(timezone.utc), video_id),
        )
