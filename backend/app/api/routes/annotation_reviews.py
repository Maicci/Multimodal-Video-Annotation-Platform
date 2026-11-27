"""Persisted submission snapshots and reviewer decisions."""
from uuid import UUID

from fastapi import APIRouter, HTTPException
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, Field, field_validator
from psycopg.types.json import Jsonb
from fastapi.responses import JSONResponse, Response

from app.api.dependencies import Connection, CurrentUser
from app.api.video_access import require_video_access
from app.repositories.annotation_workflow import lock_assignment, review_history
from app.repositories.segment_repository import list_segments
from app.repositories.video_summary_repository import find_video_summary
from app.schemas.segment import SegmentInput
from app.schemas.text import DatabaseText
from app.services.segment_timing import resolve_segment, timeline_for
import csv
import io
router = APIRouter(tags=["annotation reviews"])


class WorkflowAction(BaseModel):
    expected_version: int = Field(ge=0)
    comment: DatabaseText = Field(default="", max_length=10000)

    @field_validator("comment")
    @classmethod
    def trim_comment(cls, value):
        return value.strip()


def require_reviewer(user):
    if user["role"] not in ("reviewer", "administrator"):
        raise HTTPException(403, "Administrator role required")


def check_version(assignment, payload):
    if assignment["workflow_version"] != payload.expected_version:
        raise HTTPException(409, "The workflow changed. Refresh before trying again.")


def record_event(connection, assignment, user, action, status, payload, snapshot=None):
    updated = connection.execute("""
        UPDATE video_assignments SET status = %s, workflow_version = workflow_version + 1,
            updated_at = CURRENT_TIMESTAMP,
            completed_at = CASE WHEN %s IN ('submitted', 'approved') THEN CURRENT_TIMESTAMP ELSE NULL END
        WHERE id = %s RETURNING status, workflow_version
    """, (status, status, assignment["id"])).fetchone()
    connection.execute("""
        INSERT INTO annotation_review_events
            (assignment_id, version, action, actor_id, actor_name, comment, snapshot)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, (assignment["id"], updated["workflow_version"], action, user["id"],
          user["full_name"], payload.comment, Jsonb(jsonable_encoder(snapshot)) if snapshot is not None else None))
    return {**updated, "review_history": review_history(connection, assignment["id"])}


def submit_work(video_id, connection, user, payload, resubmit=False):
    if user["role"] != "annotator":
        raise HTTPException(403, "Annotator role required")
    video = require_video_access(connection, video_id, user)
    with connection:
        assignment = lock_assignment(connection, video_id, user["id"])
        if not assignment:
            raise HTTPException(403, "Video is not assigned to you")
        check_version(assignment, payload)
        allowed = {"returned"} if resubmit else {"not_started", "in_progress", "completed"}
        if assignment["status"] not in allowed:
            raise HTTPException(409, "This annotation cannot be submitted from its current state.")
        segments = list_segments(connection, str(video_id), str(user["id"]))
        summary = find_video_summary(connection, str(video_id), str(user["id"]))
        if not segments or any(not s["description"].strip() or not s["audio_description"].strip() for s in segments) or not summary or not summary["summary"].strip():
            raise HTTPException(422, "Save at least one segment with both descriptions and a whole-video summary before submitting.")
        if video.processing_status != "COMPLETED":
            raise HTTPException(409, "Wait for video processing before submitting.")
        timeline = timeline_for(video)
        normalized = []
        for segment in segments:
            timing = resolve_segment(video, SegmentInput(**segment), stored=True, timeline=timeline)
            normalized.append({**segment, **timing.model_dump()})
        return record_event(connection, assignment, user, "resubmitted" if resubmit else "submitted",
                            "submitted", payload, {"segments": normalized, "summary": summary["summary"]})


@router.post("/api/videos/{video_id}/annotation-session/submit")
def submit(video_id: UUID, payload: WorkflowAction, connection: Connection, user: CurrentUser):
    return submit_work(video_id, connection, user, payload)


@router.post("/api/videos/{video_id}/annotation-session/resubmit")
def resubmit(video_id: UUID, payload: WorkflowAction, connection: Connection, user: CurrentUser):
    return submit_work(video_id, connection, user, payload, resubmit=True)


@router.post("/api/videos/{video_id}/annotation-session/skip")
def skip(video_id: UUID, payload: WorkflowAction, connection: Connection, user: CurrentUser):
    if user["role"] != "annotator":
        raise HTTPException(403, "Annotator role required")
    require_video_access(connection, video_id, user)
    with connection:
        assignment = lock_assignment(connection, video_id, user["id"])
        if not assignment:
            raise HTTPException(403, "Video is not assigned to you")
        check_version(assignment, payload)
        if assignment["status"] not in {"not_started", "in_progress", "completed", "returned"}:
            raise HTTPException(409, "This annotation cannot be skipped from its current state.")
        return record_event(connection, assignment, user, "skipped", "skipped", payload)


@router.get("/api/reviews")
def queue(connection: Connection, user: CurrentUser):
    require_reviewer(user)
    return connection.execute("""
        SELECT a.id, a.video_id, a.user_id AS author_id, a.status, a.workflow_version,
            a.updated_at, v.original_filename AS filename, u.full_name AS author_name
        FROM video_assignments a JOIN videos v ON v.id = a.video_id JOIN users u ON u.id = a.user_id
        WHERE a.status IN ('submitted', 'returned', 'approved')
        ORDER BY (a.status = 'submitted') DESC, a.updated_at, a.id
    """).fetchall()


@router.get("/api/reviews/{assignment_id}")
def detail(assignment_id: UUID, connection: Connection, user: CurrentUser):
    require_reviewer(user)
    # Hold the same row lock as decisions so metadata, snapshot and history agree.
    with connection:
        assignment = connection.execute("""
            SELECT a.*, u.full_name AS author_name, v.original_filename AS filename
            FROM video_assignments a JOIN users u ON u.id = a.user_id JOIN videos v ON v.id = a.video_id
            WHERE a.id = %s FOR UPDATE OF a
        """, (str(assignment_id),)).fetchone()
        if not assignment:
            raise HTTPException(404, "Review not found")
        submission = connection.execute("""
            SELECT snapshot, created_at, version FROM annotation_review_events
            WHERE assignment_id = %s AND snapshot IS NOT NULL ORDER BY version DESC LIMIT 1
        """, (str(assignment_id),)).fetchone()
        if not submission:
            raise HTTPException(404, "No submitted annotation is available for review")
        return {"id": assignment["id"], "video_id": assignment["video_id"],
                "author_id": assignment["user_id"], "author_name": assignment["author_name"],
                "filename": assignment["filename"], "status": assignment["status"],
                "workflow_version": assignment["workflow_version"],
                "submitted_at": submission["created_at"], "submission_version": submission["version"],
                **submission["snapshot"], "review_history": review_history(connection, assignment_id),
                "can_review": str(user["id"]) != str(assignment["user_id"]) and assignment["status"] == "submitted"}
        
        
@router.get("/api/reviews/{assignment_id}/export/json")
def export_json(
    assignment_id: UUID,
    connection: Connection,
    user: CurrentUser,
):
    require_reviewer(user)

    assignment = connection.execute(
        """
        SELECT
            a.id,
            a.video_id,
            a.user_id,
            a.status,
            v.original_filename AS filename,
            u.full_name AS author_name,
            u.email AS author_email
        FROM video_assignments a
        JOIN videos v ON v.id = a.video_id
        JOIN users u ON u.id = a.user_id
        WHERE a.id = %s
        """,
        (str(assignment_id),),
    ).fetchone()

    if not assignment:
        raise HTTPException(404, "Review not found")

    submission = connection.execute(
        """
        SELECT snapshot, created_at, version
        FROM annotation_review_events
        WHERE assignment_id = %s
          AND snapshot IS NOT NULL
        ORDER BY version DESC
        LIMIT 1
        """,
        (str(assignment_id),),
    ).fetchone()

    if not submission:
        raise HTTPException(
            404,
            "No submitted annotation is available for export",
        )

    export_data = {
        "assignment_id": assignment["id"],
        "video": {
            "id": assignment["video_id"],
            "filename": assignment["filename"],
        },
        "annotator": {
            "id": assignment["user_id"],
            "name": assignment["author_name"],
            "email": assignment["author_email"],
        },
        "status": assignment["status"],
        "submission_version": submission["version"],
        "submitted_at": submission["created_at"],
        "annotation": submission["snapshot"],
    }

    return JSONResponse(
        content=jsonable_encoder(export_data),
        headers={
            "Content-Disposition":
                f'attachment; filename="annotation-{assignment_id}.json"'
        },
    )
    
    
@router.get("/api/reviews/{assignment_id}/export/csv")
def export_csv(
    assignment_id: UUID,
    connection: Connection,
    user: CurrentUser,
):
    require_reviewer(user)

    assignment = connection.execute(
        """
        SELECT
            a.id,
            a.video_id,
            a.user_id,
            a.status,
            v.original_filename AS filename,
            u.full_name AS author_name,
            u.email AS author_email
        FROM video_assignments a
        JOIN videos v ON v.id = a.video_id
        JOIN users u ON u.id = a.user_id
        WHERE a.id = %s
        """,
        (str(assignment_id),),
    ).fetchone()

    if not assignment:
        raise HTTPException(404, "Review not found")

    submission = connection.execute(
        """
        SELECT snapshot, created_at, version
        FROM annotation_review_events
        WHERE assignment_id = %s
          AND snapshot IS NOT NULL
        ORDER BY version DESC
        LIMIT 1
        """,
        (str(assignment_id),),
    ).fetchone()

    if not submission:
        raise HTTPException(
            404,
            "No submitted annotation is available for export",
        )

    snapshot = submission["snapshot"]
    segments = snapshot.get("segments", [])

    output = io.StringIO()

    writer = csv.writer(output)

    writer.writerow([
        "video_id",
        "filename",
        "annotator_name",
        "annotator_email",
        "segment_id",
        "title",
        "start_time",
        "end_time",
        "description",
        "audio_description",
        "summary",
    ])

    for segment in segments:
        writer.writerow([
            assignment["video_id"],
            assignment["filename"],
            assignment["author_name"],
            assignment["author_email"],
            segment.get("id", ""),
            segment.get("title", ""),
            segment.get("start_time", ""),
            segment.get("end_time", ""),
            segment.get("description", ""),
            segment.get("audio_description", ""),
            snapshot.get("summary", ""),
        ])

    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={
            "Content-Disposition":
                f'attachment; filename="annotation-{assignment_id}.csv"'
        },
    )


def decide(assignment_id, payload, connection, user, decision):
    require_reviewer(user)
    if decision == "returned" and not payload.comment:
        raise HTTPException(422, "Explain what needs changing before returning the annotation.")
    with connection:
        assignment = connection.execute("SELECT * FROM video_assignments WHERE id = %s FOR UPDATE", (str(assignment_id),)).fetchone()
        if not assignment:
            raise HTTPException(404, "Review not found")
        if str(assignment["user_id"]) == str(user["id"]):
            raise HTTPException(403, "You cannot review your own annotation")
        check_version(assignment, payload)
        if assignment["status"] != "submitted":
            raise HTTPException(409, "Only submitted annotations can be reviewed.")
        return record_event(connection, assignment, user, decision, decision, payload)


@router.post("/api/reviews/{assignment_id}/approve")
def approve(assignment_id: UUID, payload: WorkflowAction, connection: Connection, user: CurrentUser):
    return decide(assignment_id, payload, connection, user, "approved")


@router.post("/api/reviews/{assignment_id}/return")
def return_work(assignment_id: UUID, payload: WorkflowAction, connection: Connection, user: CurrentUser):
    return decide(assignment_id, payload, connection, user, "returned")
