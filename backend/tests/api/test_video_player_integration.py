"""Exercise upload, real media processing, and player endpoints together."""

from collections.abc import Iterator
from pathlib import Path
import shutil
import subprocess

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


@pytest.fixture
def client(test_database_url: str, tmp_path: Path) -> Iterator[TestClient]:
    app = create_app(Settings(
        database_url=test_database_url,
        jwt_secret_key="test-signing-key-with-at-least-32-characters",
        access_token_minutes=30,
        initial_admin_email="player-admin@example.com",
        initial_admin_password="initial-admin-password-123",
        video_storage_path=tmp_path / "videos" / "original",
    ))
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def sample_video(tmp_path: Path) -> bytes:
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("FFmpeg and ffprobe are needed for the media integration test")
    video_path = tmp_path / "sample.mp4"
    subprocess.run(
        [
            "ffmpeg", "-v", "error", "-f", "lavfi", "-i",
            "color=c=blue:s=160x90:r=10", "-t", "2", "-c:v", "libx264",
            "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-y",
            str(video_path),
        ],
        check=True,
        capture_output=True,
    )
    return video_path.read_bytes()


def test_upload_processing_playback_and_cleanup(client: TestClient, sample_video: bytes) -> None:
    login = client.post("/api/auth/login", json={
        "email": "player-admin@example.com", "password": "initial-admin-password-123",
    })
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    uploaded = client.post(
        "/api/videos/upload", headers=headers,
        files={"upload": ("integration.mp4", sample_video, "video/mp4")},
    )
    assert uploaded.status_code == 201, uploaded.text
    video_id = uploaded.json()["id"]
    base = f"/api/videos/{video_id}"

    # TestClient waits for FastAPI background tasks before returning.
    listed = client.get("/api/videos", headers=headers)
    assert listed.status_code == 200, listed.text
    assert listed.json()[0]["status"] == "COMPLETED"

    client.headers.update(headers)
    stream = client.get(f"{base}/stream")
    assert stream.status_code == 200
    assert stream.content == sample_video
    assert stream.headers["content-type"].startswith("video/mp4")

    timeline = client.get(f"{base}/timeline")
    assert timeline.status_code == 200, timeline.text
    assert timeline.json()["frame_count"] >= 15
    assert timeline.json()["duration"] == pytest.approx(2, abs=0.2)

    frame = client.get(f"{base}/frame", params={"time": 1.0})
    assert frame.status_code == 200, frame.text
    assert 8 <= frame.json()["frame"] <= 12
    frame_time = client.get(f"{base}/frame-time", params={"frame": 0})
    assert frame_time.status_code == 200, frame_time.text
    assert frame_time.json()["time"] == pytest.approx(0, abs=0.1)

    for index in (1, 12):
        thumbnail = client.get(f"{base}/thumbnails/{index}")
        assert thumbnail.status_code == 200, thumbnail.text
        assert thumbnail.headers["content-type"].startswith("image/jpeg")
        assert thumbnail.content.startswith(b"\xff\xd8")

    deleted = client.delete(base, headers=headers)
    assert deleted.status_code == 204, deleted.text
    assert client.get("/api/videos", headers=headers).json() == []
    assert client.get(f"{base}/stream").status_code == 404


def test_processing_failure_preserves_reason(client, sample_video, monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError("Thumbnail generation failed")
    monkeypatch.setattr("app.services.video_processing.generate_thumbnails", fail)
    token = client.post("/api/auth/login", json={"email": "player-admin@example.com", "password": "initial-admin-password-123"}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    response = client.post("/api/videos/upload", headers=headers, files={"upload": ("failure.mp4", sample_video, "video/mp4")})
    assert response.status_code == 201
    video = client.get("/api/videos", headers=headers).json()[0]
    assert video["status"] == "FAILED"
    assert "Thumbnail generation failed" in video["processing_error"]
