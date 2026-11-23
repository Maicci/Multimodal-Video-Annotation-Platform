"""Human-written whole-video summary for one annotator."""

from uuid import UUID

from pydantic import BaseModel, Field


class VideoSummaryInput(BaseModel):
    summary: str = Field(max_length=20000)


class VideoSummaryResponse(VideoSummaryInput):
    video_id: UUID
    author_id: UUID
