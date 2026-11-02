"""Authenticated video upload route."""

from __future__ import annotations

import logging
import mimetypes
import psycopg
from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, File, UploadFile
from fastapi.responses import JSONResponse

from app.api.dependencies import Connection, CurrentUser, get_settings
from app.core.config import Settings
from app.repositories.video_repository import (
    create_video,
    find_video_by_filename,
)
from app.schemas.video import VideoUploadResponse
from app.services.video_metadata import (
    VideoMetadataError,
    extract_video_metadata,
)
from app.services.video_processing import process_video
from app.services.video_storage import (
    VideoTooLargeError,
    remove_stored_video,
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

    # Start backround processing job
    background_tasks.add_task(process_video, video.id, settings.database_url)
    return VideoUploadResponse(
        id=UUID(video.id),
        filename=video.original_filename,
        status=video.processing_status,
        duration=video.duration_seconds,
    )
