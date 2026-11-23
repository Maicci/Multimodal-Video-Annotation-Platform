"""Create, list, edit, and delete annotations for a video."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.api.dependencies import Connection, CurrentUser
from app.api.video_access import require_video_access
from app.repositories.segment_repository import (
    create_segment, delete_segment, list_segments, update_segment,
)
from app.services.segment_timing import resolve_segment
from app.schemas.segment import SegmentInput, SegmentResponse


router = APIRouter(prefix="/api/videos/{video_id}/segments", tags=["segments"])



def _validate_bounds(payload: SegmentInput, duration: float | None) -> None:
    if duration is not None and payload.end_time > duration:
        raise HTTPException(status_code=422, detail="Segment exceeds video duration")


def _require_editor(user: CurrentUser) -> None:
    if user["role"] not in ("administrator", "annotator"):
        raise HTTPException(status_code=403, detail="Annotator role required")


@router.get("", response_model=list[SegmentResponse])
def get_segments(video_id: UUID, connection: Connection, user: CurrentUser):
    video = require_video_access(connection, video_id, user)
    rows = list_segments(connection, str(video_id), str(user["id"]))
    for row in rows:
        if row["start_frame"] is None or row["end_frame"] is None:
            try:
                normalized = resolve_segment(video, SegmentInput(**row))
            except HTTPException:
                continue  # Preserve legacy text/ranges until timing is available or the user edits them.
            connection.execute("UPDATE segments SET start_time = %s, end_time = %s, start_frame = %s, end_frame = %s, version = version + 1 WHERE id = %s AND version = %s", (normalized.start_time, normalized.end_time, normalized.start_frame, normalized.end_frame, str(row["id"]), row["version"]))
    connection.commit()
    return list_segments(connection, str(video_id), str(user["id"]))


@router.post("", response_model=SegmentResponse, status_code=status.HTTP_201_CREATED)
def add_segment(
    video_id: UUID, payload: SegmentInput, connection: Connection, user: CurrentUser,
):
    _require_editor(user)
    video = require_video_access(connection, video_id, user)
    _validate_bounds(payload, video.duration_seconds)
    payload = resolve_segment(video, payload)
    return create_segment(connection, str(video_id), str(user["id"]), payload)


@router.put("/{segment_id}", response_model=SegmentResponse)
def edit_segment(
    video_id: UUID, segment_id: UUID, payload: SegmentInput,
    connection: Connection, user: CurrentUser,
):
    _require_editor(user)
    video = require_video_access(connection, video_id, user)
    _validate_bounds(payload, video.duration_seconds)
    payload = resolve_segment(video, payload)
    existing = connection.execute("SELECT 1 FROM segments WHERE id = %s AND video_id = %s AND author_id = %s", (str(segment_id), str(video_id), str(user["id"]))).fetchone()
    saved = update_segment(
        connection, str(segment_id), str(video_id), str(user["id"]), payload,
    )
    if saved is None:
        if existing:
            raise HTTPException(409, "This segment changed in another session. Reload before saving.")
        raise HTTPException(status_code=404, detail="Segment not found")
    return saved


@router.delete("/{segment_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_segment(
    video_id: UUID, segment_id: UUID, connection: Connection, user: CurrentUser,
    version: int = 0,
) -> None:
    _require_editor(user)
    require_video_access(connection, video_id, user)
    existing = connection.execute("SELECT 1 FROM segments WHERE id = %s AND video_id = %s AND author_id = %s", (str(segment_id), str(video_id), str(user["id"]))).fetchone()
    deleted = delete_segment(
        connection, str(segment_id), str(video_id), str(user["id"]), version,
    )
    if not deleted:
        if existing:
            raise HTTPException(409, "This segment changed. Reload before deleting.")
        raise HTTPException(status_code=404, detail="Segment not found")
