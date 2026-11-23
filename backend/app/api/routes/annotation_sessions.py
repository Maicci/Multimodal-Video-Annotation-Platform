"""Resume and complete the current annotator's work."""
from uuid import UUID
from fastapi import APIRouter, HTTPException
from app.api.dependencies import Connection, CurrentUser
from app.api.video_access import require_video_access
from app.repositories.segment_repository import list_segments
from app.repositories.video_summary_repository import find_video_summary

router = APIRouter(prefix="/api/videos/{video_id}/annotation-session", tags=["annotations"])


@router.get("")
def session(video_id: UUID, connection: Connection, user: CurrentUser):
    require_video_access(connection, video_id, user)
    assignment = connection.execute("SELECT status FROM video_assignments WHERE video_id = %s AND user_id = %s", (str(video_id), str(user["id"]))).fetchone()
    return {
        "segments": list_segments(connection, str(video_id), str(user["id"])),
        "summary": find_video_summary(connection, str(video_id), str(user["id"])),
        "status": assignment["status"] if assignment else "unassigned",
    }


@router.post("/complete")
def complete(video_id: UUID, connection: Connection, user: CurrentUser):
    require_video_access(connection, video_id, user)
    if user["role"] != "annotator":
        raise HTTPException(403, "Annotator role required")
    with connection:
        connection.execute("SELECT 1 FROM video_assignments WHERE video_id = %s AND user_id = %s FOR UPDATE", (str(video_id), str(user["id"])))
        segments = list_segments(connection, str(video_id), str(user["id"]))
        summary = find_video_summary(connection, str(video_id), str(user["id"]))
        if not segments or any(not s["description"].strip() or not s["audio_description"].strip() for s in segments) or not summary or not summary["summary"].strip():
            raise HTTPException(422, "Save at least one segment with both descriptions and a whole-video summary before completing.")
        connection.execute("UPDATE video_assignments SET status = 'completed', completed_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE video_id = %s AND user_id = %s", (str(video_id), str(user["id"])))
    return {"status": "completed"}
