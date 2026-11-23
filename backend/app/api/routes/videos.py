"""Authenticated video upload route."""

from __future__ import annotations

import logging
import mimetypes
import psycopg
from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, File, UploadFile
from fastapi.responses import JSONResponse, Response

from app.api.dependencies import Connection, CurrentUser, get_settings
from app.core.config import Settings
from app.api.video_access import require_video_access, create_media_token
from app.repositories.video_repository import (
    create_video,
    delete_video,
    find_video_by_filename,
    list_videos,
)
from app.schemas.video import VideoListItem, VideoUploadResponse
from app.services.video_metadata import (
    VideoMetadataError,
    extract_video_metadata,
)
from app.services.video_processing import process_video
from app.services.video_storage import (
    VideoTooLargeError,
    remove_stored_video,
    remove_video_files,
    store_video,
)

logger = logging.getLogger(__name__)
ALLOWED_EXTENSIONS = {".mp4", ".mov"}

router = APIRouter(prefix="/api/videos", tags=["videos"])


def _error(status_code: int, error: str, **extra: object) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": error, **extra},
    )

@router.get("", response_model=list[VideoListItem])
def list_all_videos(
    connection: Connection,
    user: CurrentUser,
) -> list[VideoListItem]:
    videos = list_videos(connection)
    if user["role"] == "annotator":
        assigned = {str(row["video_id"]) for row in connection.execute(
            "SELECT video_id FROM video_assignments WHERE user_id = %s", (str(user["id"]),)
        ).fetchall()}
        videos = [video for video in videos if str(video.id) in assigned]
    jobs = {}
    if user["role"] == "administrator":
        jobs = {str(row["video_id"]): row for row in connection.execute(
            "SELECT DISTINCT ON (video_id) video_id, status, error FROM processing_jobs ORDER BY video_id, created_at DESC"
        ).fetchall()}
    return [
        VideoListItem(
            id=UUID(v.id),
            filename=v.original_filename,
            size_bytes=v.file_size_bytes,
            status=v.processing_status,
            uploaded_at=v.upload_time,
            duration=v.duration_seconds,
            processing_error=v.processing_error if user["role"] == "administrator" else None,
            transcription_status=jobs.get(v.id, {}).get("status"),
            transcription_error=jobs.get(v.id, {}).get("error"),
        )
        for v in videos
    ]

@router.delete(
    "/{video_id}",
    status_code=204,
    response_model=None,
    responses={
        403: {"description": "Administrator role required"},
        404: {"description": "Video not found"},
        409: {"description": "Video still has related data"},
    },
)
def remove_video(
    video_id: UUID,
    connection: Connection,
    user: CurrentUser,
) -> Response:
    if user.get("role") != "administrator":
        return _error(403, "Administrator role required")

    busy = connection.execute("SELECT 1 FROM processing_jobs WHERE video_id = %s AND status IN ('QUEUED', 'RUNNING')", (str(video_id),)).fetchone()
    if busy:
        return _error(409, "Wait for transcription to finish before deleting this video")
    try:
        video = delete_video(connection, str(video_id))
    except psycopg.errors.ForeignKeyViolation:
        return _error(409, "Video still has related data")
    except psycopg.Error:
        logger.exception("Could not delete video %s", video_id)
        return _error(500, "Database failure")

    if video is None:
        return _error(404, "Video not found")

    remove_video_files(Path(video.storage_path))
    return Response(status_code=204)

@router.post(
    "/upload",
    status_code=201,
    response_model=VideoUploadResponse,
    responses={
        401: {"description": "Authentication required"},
        409: {"description": "A video with this filename already exists"},
        413: {"description": "File too large"},
        415: {"description": "Unsupported video format"},
        500: {"description": "Storage, metadata, or database failure"},
    },
)


def upload_video(
    background_tasks: BackgroundTasks,
    upload: Annotated[UploadFile, File()],
    connection: Connection,
    user: CurrentUser,
    settings: Annotated[Settings, Depends(get_settings)],
) -> VideoUploadResponse | JSONResponse:

    if user["role"] != "administrator":
        return _error(403, "Administrator role required")

    # Check filename
    filename = (upload.filename or "").replace("\\", "/").rsplit("/", 1)[-1]

    if not filename or filename in {".", ".."}:
        return _error(400, "A valid filename is required")

    if Path(filename).suffix.lower() not in ALLOWED_EXTENSIONS:
        return _error(415, "Unsupported video format")

    duplicate_id = find_video_by_filename(connection, filename)

    if duplicate_id is not None:
        return _error(
            409,
            "Video with same filename already exists",
            video_id=duplicate_id,
            action_required=True,
        )

    # Store the video
    storage_directory = settings.video_storage_path

    if storage_directory is None:
        storage_directory = (
            Path(__file__).resolve().parents[3]
            / "storage"
            / "videos"
            / "original"
        )

    try:
        stored_video = store_video(
            upload.file,
            original_filename=filename,
            storage_directory=storage_directory,
            max_size_bytes=settings.max_video_size_bytes,
        )
    except VideoTooLargeError:
        return _error(413, "File too large")
    except OSError:
        logger.exception("Could not store uploaded video %s", filename)
        return _error(500, "Storage failure")

    # Extract metadata
    try:
        metadata = extract_video_metadata(stored_video.path)
    except VideoMetadataError:
        remove_stored_video(stored_video)
        return _error(500, "Metadata extraction failed")

    # Create database entry
    mime_type = upload.content_type or mimetypes.guess_type(filename)[0]

    try:
        video = create_video(
            connection,
            original_filename=filename,
            uploader_id=str(user["id"]),
            mime_type=mime_type or "application/octet-stream",
            stored_video=stored_video,
            metadata=metadata,
        )
    except psycopg.IntegrityError:
        remove_stored_video(stored_video)

        duplicate_id = find_video_by_filename(connection, filename)

        if duplicate_id is not None:
            return _error(
                409,
                "Video with same filename already exists",
                video_id=duplicate_id,
                action_required=True,
            )

        logger.exception("Could not create database record for %s", filename)
        return _error(500, "Database failure")

    except psycopg.Error:
        remove_stored_video(stored_video)
        logger.exception("Could not create database record for %s", filename)
        return _error(500, "Database failure")

    # Create path for frame timeline .npy file
    timeline_path = (
        storage_directory.parent
        / "timelines"
        / f"{Path(stored_video.filename).stem}.npy"
    )

    thumbnails_dir = (
    storage_directory.parent
    / "thumbnails"
    / Path(stored_video.filename).stem
    )

    # Start background processing job
    background_tasks.add_task(
        process_video,
        video.id,
        settings.database_url,
        stored_video.path,
        timeline_path,
        thumbnails_dir,
    )

    return VideoUploadResponse(
        id=UUID(video.id),
        filename=video.original_filename,
        status=video.processing_status,
        duration=video.duration_seconds,
    )


@router.post("/{video_id}/media-token")
def playback_token(video_id: UUID, connection: Connection, user: CurrentUser,
                   settings: Annotated[Settings, Depends(get_settings)]):
    require_video_access(connection, video_id, user)
    return {"token": create_media_token(video_id, user, settings), "expires_in": 300}
