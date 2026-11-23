"""Opt-in real-model test. Downloads the tiny model into the Docker cache."""
import os
import subprocess
import pytest
from fastapi.testclient import TestClient
from app.core.config import Settings
from app.main import create_app


@pytest.mark.skipif(os.getenv("RUN_WHISPER_SMOKE") != "1", reason="Set RUN_WHISPER_SMOKE=1 for the real model test")
def test_real_speech_transcription(test_database_url, tmp_path):
    video = tmp_path / "speech.mp4"
    subprocess.run([
        "ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=c=blue:s=160x90:r=10",
        "-f", "lavfi", "-i", "flite=text='Hello world. This is a test of video annotation.':voice=slt",
        "-shortest", "-c:v", "libx264", "-c:a", "aac", "-y", str(video),
    ], check=True, capture_output=True)
    app = create_app(Settings(database_url=test_database_url,
        jwt_secret_key="test-signing-key-with-at-least-32-characters", access_token_minutes=30,
        initial_admin_email="admin@example.com", initial_admin_password="test-password-123",
        video_storage_path=tmp_path / "stored" / "original"))
    with TestClient(app) as client:
        token = client.post("/api/auth/login", json={"email": "admin@example.com", "password": "test-password-123"}).json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        uploaded = client.post("/api/videos/upload", headers=headers, files={"upload": ("speech.mp4", video.read_bytes(), "video/mp4")})
        assert uploaded.status_code == 201, uploaded.text
        job = client.post(f"/api/videos/{uploaded.json()['id']}/transcription", headers=headers)
        assert job.status_code == 202, job.text
        result = client.get(f"/api/processing/jobs/{job.json()['id']}", headers=headers).json()
        assert result["status"] == "COMPLETED", result.get("error")
        transcript = " ".join(s["text"] for s in result["result"]["segments"]).lower()
        assert "hello" in transcript and "test" in transcript, transcript
