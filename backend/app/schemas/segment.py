"""Request and response models for saved video segments."""

from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.text import DatabaseText


class SegmentInput(BaseModel):
    start_frame: int | None = Field(default=None, ge=0)
    end_frame: int | None = Field(default=None, ge=1)
    version: int = Field(default=1, ge=1)
    title: DatabaseText = Field(min_length=1, max_length=120)
    start_time: float = Field(ge=0, allow_inf_nan=False)
    end_time: float = Field(gt=0, allow_inf_nan=False)
    # The existing description field holds the visual description.
    description: DatabaseText = Field(default="", max_length=10000)
    audio_description: DatabaseText = Field(default="", max_length=10000)

    @field_validator("title")
    @classmethod
    def title_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Title is required")
        return value

    @model_validator(mode="after")
    def end_must_follow_start(self) -> "SegmentInput":
        if self.end_time <= self.start_time:
            raise ValueError("End time must be after start time")
        return self


class SegmentResponse(SegmentInput):
    id: UUID
    video_id: UUID
    author_id: UUID
