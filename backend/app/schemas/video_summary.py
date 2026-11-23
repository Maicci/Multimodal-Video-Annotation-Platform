"""Human-written whole-video summary for one annotator."""

from uuid import UUID

from pydantic import BaseModel, Field


class VideoSummaryInput(BaseModel):
    version: int = Field(default=0, ge=0)
    summary: str = Field(max_length=20000)


class VideoSummaryResponse(VideoSummaryInput):
    video_id: UUID
    author_id: UUID
