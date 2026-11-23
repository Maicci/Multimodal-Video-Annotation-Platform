"""Load and save a user's whole-video summary."""

from uuid import UUID

from fastapi import APIRouter, HTTPException

from app.api.dependencies import Connection, CurrentUser
from app.api.video_access import require_video_access
from app.repositories.video_summary_repository import find_video_summary, save_video_summary
from app.schemas.video_summary import VideoSummaryInput, VideoSummaryResponse


router = APIRouter(prefix="/api/videos/{video_id}/summary", tags=["summaries"])



@router.get("", response_model=VideoSummaryResponse)
def get_summary(video_id: UUID, connection: Connection, user: CurrentUser):
    require_video_access(connection, video_id, user)
    video_id_str = str(video_id)
    author_id = str(user["id"])
    return find_video_summary(connection, video_id_str, author_id) or {
        "video_id": video_id,
        "author_id": user["id"],
        "summary": "",
        "version": 0,
    }


@router.put("", response_model=VideoSummaryResponse)
def put_summary(
    video_id: UUID, payload: VideoSummaryInput, connection: Connection,
    user: CurrentUser,
):
    if user["role"] not in ("administrator", "annotator"):
        raise HTTPException(status_code=403, detail="Annotator role required")
    require_video_access(connection, video_id, user)
    saved = save_video_summary(
        connection, str(video_id), str(user["id"]), payload.summary, payload.version,
    )

    if saved is None:
        raise HTTPException(409, "This summary changed in another session. Reload before saving.")
    return saved
