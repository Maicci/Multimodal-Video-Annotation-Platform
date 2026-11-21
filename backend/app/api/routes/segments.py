"""Create, list, edit, and delete annotations for a video."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.api.dependencies import Connection, CurrentUser
from app.repositories.segment_repository import (
    create_segment, delete_segment, list_segments, update_segment,
)
from app.repositories.video_repository import find_video_by_id
from app.schemas.segment import SegmentInput, SegmentResponse


router = APIRouter(prefix="/api/videos/{video_id}/segments", tags=["segments"])


def _video_or_404(connection: Connection, video_id: UUID):
    video = find_video_by_id(connection, str(video_id))
    if video is None:
        raise HTTPException(status_code=404, detail="Video not found")
    return video


def _validate_bounds(payload: SegmentInput, duration: float | None) -> None:
    if duration is not None and payload.end_time > duration:
        raise HTTPException(status_code=422, detail="Segment exceeds video duration")


def _require_editor(user: CurrentUser) -> None:
    if user["role"] not in ("administrator", "annotator"):
        raise HTTPException(status_code=403, detail="Annotator role required")


@router.get("", response_model=list[SegmentResponse])
def get_segments(video_id: UUID, connection: Connection, user: CurrentUser):
    _video_or_404(connection, video_id)
    return list_segments(connection, str(video_id), str(user["id"]))


@router.post("", response_model=SegmentResponse, status_code=status.HTTP_201_CREATED)
def add_segment(
    video_id: UUID, payload: SegmentInput, connection: Connection, user: CurrentUser,
):
    _require_editor(user)
    video = _video_or_404(connection, video_id)
    _validate_bounds(payload, video.duration_seconds)
    return create_segment(connection, str(video_id), str(user["id"]), payload)


@router.put("/{segment_id}", response_model=SegmentResponse)
def edit_segment(
    video_id: UUID, segment_id: UUID, payload: SegmentInput,
    connection: Connection, user: CurrentUser,
):
    _require_editor(user)
    video = _video_or_404(connection, video_id)
    _validate_bounds(payload, video.duration_seconds)
    saved = update_segment(
        connection, str(segment_id), str(video_id), str(user["id"]), payload,
    )
    if saved is None:
        raise HTTPException(status_code=404, detail="Segment not found")
    return saved


@router.delete("/{segment_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_segment(
    video_id: UUID, segment_id: UUID, connection: Connection, user: CurrentUser,
) -> None:
    _require_editor(user)
    _video_or_404(connection, video_id)
    deleted = delete_segment(
        connection, str(segment_id), str(video_id), str(user["id"]),
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="Segment not found")
