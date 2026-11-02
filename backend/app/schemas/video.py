"""Video upload API schemas."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel


class VideoUploadResponse(BaseModel):
    id: UUID
    filename: str
    status: str
    duration: float | None
