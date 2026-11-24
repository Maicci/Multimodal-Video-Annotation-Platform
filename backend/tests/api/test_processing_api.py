from pathlib import Path
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from app.core.config import Settings
from app.db.database import Database
from app.main import create_app
from app.services.transcription import recover_interrupted_jobs
from app.services.video_metadata import VideoMetadata


@pytest.fixture
def setup(test_database_url, tmp_path: Path, monkeypatch):
    monkeypatch.setattr("app.api.routes.videos.extract_video_metadata", Mock(return_value=VideoMetadata(
        duration_seconds=2, width=160, height=90, fps=10, codec="h264")))
    def process(video_id, database_url, *args):
        with Database(database_url).connect() as connection:
            connection.execute("UPDATE videos SET processing_status = 'COMPLETED' WHERE id = %s", (video_id,))
    monkeypatch.setattr("app.api.routes.videos.process_video", process)
    app = create_app(Settings(database_url=test_database_url,
        jwt_secret_key="test-signing-key-with-at-least-32-characters", access_token_minutes=30,
        initial_admin_email="admin@example.com", initial_admin_password="test-password-123",
        video_storage_path=tmp_path / "videos" / "original"))
    with TestClient(app) as client:
        token = client.post("/api/auth/login", json={"email": "admin@example.com", "password": "test-password-123"}).json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        video = client.post("/api/videos/upload", headers=headers, files={"upload": ("speech.mp4", b"test", "video/mp4")}).json()
        yield client, headers, video["id"], Database(test_database_url)


@pytest.mark.parametrize("role", ["annotator", "reviewer"])
def test_transcription_persists_results_and_hides_them_from_other_roles(setup, monkeypatch, role):
    client, headers, video_id, database = setup
    monkeypatch.setattr("app.services.transcription.transcribe", Mock(return_value={"segments": [{"text": "test transcript", "start_seconds": 0, "end_seconds": 1}]}))
    response = client.post(f"/api/videos/{video_id}/transcription", headers=headers)
    assert response.status_code == 202, response.text
    assert response.json()["status"] == "QUEUED"
    job_url = f"/api/processing/jobs/{response.json()['id']}"
    job = client.get(job_url, headers=headers).json()
    assert job["status"] == "COMPLETED"
    assert job["result"]["segments"][0]["text"] == "test transcript"
    assert job["started_at"] and job["finished_at"]
    video = client.get("/api/videos", headers=headers).json()[0]
    assert video["transcription_job_id"] == response.json()["id"]
    assert video["transcription_status"] == "COMPLETED"
    assert client.get(job_url).status_code == 401
    created = client.post("/api/users", headers=headers, json={"email": f"{role}@example.com", "full_name": role, "password": "test-password-123", "role": role})
    assert created.status_code == 201
    if role == "annotator":
        assigned = client.post("/api/assignments", headers=headers, json={"video_id": video_id, "annotator_id": created.json()["id"]})
        assert assigned.is_success
    token = client.post("/api/auth/login", json={"email": f"{role}@example.com", "password": "test-password-123"}).json()["access_token"]
    other_user = {"Authorization": f"Bearer {token}"}
    assert client.get(job_url, headers=other_user).status_code == 403
    assert client.post(f"/api/videos/{video_id}/transcription", headers=other_user).status_code == 403
    visible_video = client.get("/api/videos", headers=other_user).json()[0]
    assert visible_video["id"] == video_id
    assert visible_video["transcription_job_id"] is None
    assert visible_video["transcription_status"] is None
    assert visible_video["transcription_error"] is None
    recover_interrupted_jobs(database)
    assert client.get(job_url, headers=headers).json()["status"] == "COMPLETED"


def test_failed_jobs_are_visible_and_retryable(setup, monkeypatch):
    client, headers, video_id, _ = setup
    monkeypatch.setattr("app.services.transcription.transcribe", Mock(side_effect=RuntimeError("Model could not load")))
    response = client.post(f"/api/videos/{video_id}/transcription", headers=headers)
    job = client.get(f"/api/processing/jobs/{response.json()['id']}", headers=headers).json()
    assert job["status"] == "FAILED"
    assert "Model could not load" in job["error"]
    video = client.get("/api/videos", headers=headers).json()[0]
    assert video["status"] == "COMPLETED"
    assert video["transcription_status"] == "FAILED"
    assert "Model could not load" in video["transcription_error"]
    retried = client.post(f"/api/videos/{video_id}/transcription", headers=headers)
    assert retried.status_code == 202
    assert retried.json()["id"] != response.json()["id"]
    assert client.get("/api/videos", headers=headers).json()[0]["transcription_job_id"] == retried.json()["id"]


def test_duplicate_jobs_and_restart_recovery(setup, monkeypatch):
    client, headers, video_id, database = setup
    monkeypatch.setattr("app.api.routes.processing.run_transcription", Mock())
    first = client.post(f"/api/videos/{video_id}/transcription", headers=headers)
    assert first.status_code == 202
    assert client.post(f"/api/videos/{video_id}/transcription", headers=headers).status_code == 409
    assert client.delete(f"/api/videos/{video_id}", headers=headers).status_code == 409
    recover_interrupted_jobs(database)
    job = client.get(f"/api/processing/jobs/{first.json()['id']}", headers=headers).json()
    assert job["status"] == "FAILED"
    assert "restart" in job["error"]
