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

def find_video_by_filename(
    connection: psycopg.Connection[dict[str, Any]], original_filename: str
) -> str | None:
    row = connection.execute(
        "SELECT id FROM videos WHERE original_filename = %s",
        (original_filename,),
    ).fetchone()
    return None if row is None else str(row["id"])

def find_video_by_id(
    connection: psycopg.Connection[dict[str, Any]],
    video_id: str,
) -> Video | None:
    row = connection.execute(
        """
        SELECT
            id,
            original_filename,
            stored_filename,
            storage_path,
            uploader_id,
            upload_time,
            file_size_bytes,
            mime_type,
            duration_seconds,
            width,
            height,
            fps,
            codec,
            processing_status,
            metadata_extracted
        FROM videos
        WHERE id = %s
        """,
        (video_id,),
    ).fetchone()

    if row is None:
        return None

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
    )


def create_video(
    connection: psycopg.Connection,
    *,
    original_filename: str,
    uploader_id: str,
    mime_type: str,
    stored_video: StoredVideo,
    metadata: VideoMetadata,
) -> Video:
    video_id = str(uuid4())
    upload_time = datetime.now(timezone.utc)
    with connection:
        connection.execute(
            """
            INSERT INTO videos (
                id, title, original_filename, stored_filename, storage_path,
                uploader_id, upload_time, file_size_bytes, mime_type,
                duration_seconds, width, height, fps, codec, processing_status,
                metadata_extracted, updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    'PENDING', TRUE, %s)
            """,
            (
                video_id,
                original_filename,
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
                upload_time,
            ),
        )
    return Video(
        id=video_id,
        original_filename=original_filename,
        stored_filename=stored_video.filename,
        storage_path=str(stored_video.path),
        uploader_id=uploader_id,
        upload_time=upload_time.isoformat(),
        file_size_bytes=stored_video.size_bytes,
        mime_type=mime_type,
        duration_seconds=metadata.duration_seconds,
        width=metadata.width,
        height=metadata.height,
        fps=metadata.fps,
        codec=metadata.codec,
        processing_status="PENDING",
        metadata_extracted=True,
    )


def start_video_processing(
    connection: psycopg.Connection, video_id: str
) -> bool:
    with connection:
        result = connection.execute(
            """
            UPDATE videos
            SET processing_status = 'PROCESSING', updated_at = %s
            WHERE id = %s AND processing_status = 'PENDING'
            """,
            (datetime.now(timezone.utc), video_id),
        )
    return result.rowcount == 1
