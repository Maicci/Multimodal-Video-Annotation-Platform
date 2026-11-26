"""Resume and complete the current annotator's work."""
from uuid import UUID
from fastapi import APIRouter, HTTPException
from app.api.dependencies import Connection, CurrentUser
from app.api.video_access import require_video_access
from app.repositories.segment_repository import list_normalized_segments, list_segments
from app.repositories.video_summary_repository import find_video_summary
from app.repositories.annotation_workflow import lock_assignment, require_editable, review_history

router = APIRouter(prefix="/api/videos/{video_id}/annotation-session", tags=["annotations"])


@router.get("")
def session(video_id: UUID, connection: Connection, user: CurrentUser):
    video = require_video_access(connection, video_id, user)
    with connection:
        assignment = lock_assignment(connection, video_id, user["id"])
        return {
            "segments": list_normalized_segments(connection, video, user["id"], assignment),
            "summary": find_video_summary(connection, str(video_id), str(user["id"])),
            "status": assignment["status"] if assignment else "unassigned",
            "workflow_version": assignment["workflow_version"] if assignment else 0,
            "review_history": review_history(connection, assignment["id"]) if assignment else [],
        }


@router.post("/complete")
def complete(video_id: UUID, connection: Connection, user: CurrentUser):
    require_video_access(connection, video_id, user)
    if user["role"] != "annotator":
        raise HTTPException(403, "Annotator role required")
    with connection:
        assignment = require_editable(connection, video_id, user["id"])
        if not assignment:
            raise HTTPException(403, "Video is not assigned to you")
        if assignment["status"] in ("returned", "skipped"):
            raise HTTPException(409, "Edit and resubmit returned work, or resume skipped work before completing.")
        segments = list_segments(connection, str(video_id), str(user["id"]))
        summary = find_video_summary(connection, str(video_id), str(user["id"]))
        if not segments or any(not s["description"].strip() or not s["audio_description"].strip() for s in segments) or not summary or not summary["summary"].strip():
            raise HTTPException(422, "Save at least one segment with both descriptions and a whole-video summary before completing.")
        connection.execute("UPDATE video_assignments SET status = 'completed', completed_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE video_id = %s AND user_id = %s", (str(video_id), str(user["id"])))
    return {"status": "completed"}
