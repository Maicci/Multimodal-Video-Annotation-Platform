from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

AnnotationStatus = Literal["not_started", "in_progress", "completed", "submitted", "returned", "approved", "skipped"]


class AssignmentOut(BaseModel):
    video_id: UUID
    title: str
    original_filename: str
    duration_seconds: float | None
    protocol_group: Literal["shared", "individual"]
    status: AnnotationStatus
    segment_count: int
    assigned_at: datetime
    updated_at: datetime


class AssignmentCreate(BaseModel):
    video_id: UUID
    annotator_id: UUID


class ProgressCount(BaseModel):
    dimension: Literal["video", "annotator"]
    id: UUID
    name: str
    status: AnnotationStatus
    total: int
