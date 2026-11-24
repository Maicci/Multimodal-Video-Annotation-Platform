"""Administrator-only processing controls and automatic outputs."""
import os
from uuid import UUID, uuid4

import psycopg
from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from app.api.dependencies import Connection, CurrentUser
from app.repositories.video_repository import find_video_by_id
from app.services.transcription import run_transcription

router = APIRouter(tags=["processing"])


def require_admin(user):
    if user["role"] != "administrator":
        raise HTTPException(403, "Administrator role required")


@router.post("/api/videos/{video_id}/transcription", status_code=202)
def start(video_id: UUID, request: Request, connection: Connection,
          user: CurrentUser, tasks: BackgroundTasks):
    require_admin(user)
    video = find_video_by_id(connection, str(video_id))
    if video is None:
        raise HTTPException(404, "Video not found")
    if video.processing_status != "COMPLETED":
        raise HTTPException(409, "Wait for video processing to complete first")
    job_id = str(uuid4())
    try:
        with connection:
            job = connection.execute("""
                INSERT INTO processing_jobs (id, video_id, status, model)
                VALUES (%s, %s, 'QUEUED', %s)
                RETURNING id, video_id, status, model, created_at
            """, (job_id, str(video_id), os.getenv("WHISPER_MODEL", "tiny"))).fetchone()
    except psycopg.errors.UniqueViolation:
        raise HTTPException(409, "Transcription is already queued or running")
    tasks.add_task(run_transcription, request.app.state.settings.database_url, job_id)
    return job


@router.get("/api/processing/jobs/{job_id}")
def get_job(job_id: UUID, connection: Connection, user: CurrentUser):
    require_admin(user)
    job = connection.execute("SELECT * FROM processing_jobs WHERE id = %s", (str(job_id),)).fetchone()
    if job is None:
        raise HTTPException(404, "Processing job not found")
    return job
