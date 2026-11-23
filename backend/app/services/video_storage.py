"""Local storage for unmodified source video files."""

from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO
from uuid import uuid4

logger = logging.getLogger(__name__)
CHUNK_SIZE_BYTES = 1024 * 1024


class VideoTooLargeError(Exception):
    """Raised when an upload exceeds the configured maximum size."""


@dataclass(frozen=True)
class StoredVideo:
    filename: str
    path: Path
    size_bytes: int


def store_video(
    source: BinaryIO,
    *,
    original_filename: str,
    storage_directory: Path,
    max_size_bytes: int,
) -> StoredVideo:
    suffix = Path(original_filename).suffix.lower()
    stored_filename = f"{uuid4()}{suffix}"
    storage_directory.mkdir(parents=True, exist_ok=True)
    destination = storage_directory / stored_filename
    size_bytes = 0

    try:
        with destination.open("xb") as output:
            while chunk := source.read(CHUNK_SIZE_BYTES):
                size_bytes += len(chunk)
                if size_bytes > max_size_bytes:
                    raise VideoTooLargeError
                output.write(chunk)
    except Exception:
        try:
            destination.unlink(missing_ok=True)
        except OSError:
            logger.exception("Could not remove incomplete video upload %s", destination)
        raise

    return StoredVideo(
        filename=stored_filename,
        path=destination,
        size_bytes=size_bytes,
    )


def remove_stored_video(stored_video: StoredVideo) -> None:
    try:
        stored_video.path.unlink(missing_ok=True)
    except OSError:
        logger.exception("Could not remove stored video %s", stored_video.path)


def remove_video_files(video_path: Path) -> None:
    """Delete a stored video and the related files.
    Layout
        <root>/original/<stem>.<ext>   the video itself
        <root>/timelines/<stem>.npy    frame timeline
        <root>/thumbnails/<stem>/      thumbnail images
    Missing files are fine; problems are logged, never raised.
    """
    root = video_path.parent.parent
    stem = video_path.stem
    try:
        video_path.unlink(missing_ok=True)
        (root / "waveforms" / f"{stem}.json").unlink(missing_ok=True)
        (root / "timelines" / f"{stem}.npy").unlink(missing_ok=True)
        shutil.rmtree(root / "thumbnails" / stem, ignore_errors=True)
    except OSError:
        logger.exception("Could not remove files of video %s", video_path)
