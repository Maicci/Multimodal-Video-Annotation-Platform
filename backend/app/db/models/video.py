"""Video database record."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Video:
    id: str
    original_filename: str
    stored_filename: str
    storage_path: str
    uploader_id: str
    upload_time: str
    file_size_bytes: int
    mime_type: str
    duration_seconds: float | None
    width: int | None
    height: int | None
    fps: float | None
    codec: str | None
    processing_status: str
    metadata_extracted: bool
