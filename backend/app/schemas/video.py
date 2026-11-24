"""Video upload API schemas."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel


class VideoUploadResponse(BaseModel):
    id: UUID
    filename: str
    status: str
    duration: float | None

class VideoListItem(BaseModel):
    id: UUID
    filename: str
    size_bytes: int
    status: str
    uploaded_at: str
    duration: float | None = None

    processing_error: str | None = None
    transcription_status: str | None = None
    transcription_error: str | None = None
    transcription_job_id: UUID | None = None
