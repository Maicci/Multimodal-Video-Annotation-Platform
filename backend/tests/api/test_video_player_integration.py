"""Exercise upload, real media processing, and player endpoints together."""

from collections.abc import Iterator
import json
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

    for invalid_frame in (-1, timeline.json()["frame_count"]):
        assert client.get(f"{base}/frame-time", params={"frame": invalid_frame}).status_code == 422
    assert client.get(f"{base}/frame", params={"time": "NaN"}).status_code == 422

    for index in (1, 12):
        thumbnail = client.get(f"{base}/thumbnails/{index}")
        assert thumbnail.status_code == 200, thumbnail.text
        assert thumbnail.headers["content-type"].startswith("image/jpeg")
        assert thumbnail.content.startswith(b"\xff\xd8")

    deleted = client.delete(base, headers=headers)
    assert deleted.status_code == 204, deleted.text
    assert client.get("/api/videos", headers=headers).json() == []
    assert client.get(f"{base}/stream").status_code == 404


def test_trimmed_mp4_timeline_matches_displayed_frames(client, sample_video, tmp_path):
    source = tmp_path / "source.mp4"
    source.write_bytes(sample_video)
    clip = tmp_path / "trimmed.mp4"
    # A cut between keyframes keeps earlier packets for decoding.
    subprocess.run([
        "ffmpeg", "-v", "error", "-ss", "0.7", "-i", str(source),
        "-c", "copy", str(clip),
    ], check=True, timeout=15)
    decoded = subprocess.run([
        "ffprobe", "-v", "error", "-select_streams", "v:0", "-show_frames",
        "-show_entries", "frame=best_effort_timestamp_time", "-of", "json", str(clip),
    ], check=True, capture_output=True, text=True, timeout=15)
    timestamps = [float(frame["best_effort_timestamp_time"])
                  for frame in json.loads(decoded.stdout)["frames"]]
    assert timestamps and timestamps[0] == 0

    login = client.post("/api/auth/login", json={
        "email": "player-admin@example.com", "password": "initial-admin-password-123",
    })
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    upload = client.post("/api/videos/upload", headers=headers,
                         files={"upload": (clip.name, clip.read_bytes(), "video/mp4")})
    assert upload.status_code == 201, upload.text
    timeline = client.get(f"/api/videos/{upload.json()['id']}/timeline", headers=headers)
    assert timeline.status_code == 200, timeline.text
    assert timeline.json()["boundaries"][:-1] == pytest.approx(timestamps)


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


def test_unreadable_video_is_rejected_and_removed(client):
    login = client.post("/api/auth/login", json={
        "email": "player-admin@example.com", "password": "initial-admin-password-123",
    })
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    result = client.post("/api/videos/upload", headers=headers,
                         files={"upload": ("empty.mp4", b"", "video/mp4")})
    assert result.status_code == 422
    assert client.get("/api/videos", headers=headers).json() == []
    assert list(client.app.state.settings.video_storage_path.iterdir()) == []


@pytest.mark.parametrize("frames", [1, 2])
def test_can_submit_every_frame_of_a_short_clip(client, tmp_path, frames):
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("FFmpeg and ffprobe are needed for the media integration test")
    path = tmp_path / "short.mp4"
    subprocess.run([
        "ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=s=64x64:r=24",
        "-frames:v", str(frames), str(path),
    ], check=True)

    def login(email, password):
        result = client.post("/api/auth/login", json={"email": email, "password": password})
        return {"Authorization": f"Bearer {result.json()['access_token']}"}

    admin = login("player-admin@example.com", "initial-admin-password-123")
    account = {"email": "author@example.com", "password": "author-password-123",
               "full_name": "Author", "role": "annotator"}
    author_id = client.post("/api/users", json=account, headers=admin).json()["id"]
    author = login(account["email"], account["password"])
    uploaded = client.post("/api/videos/upload", headers=admin,
                           files={"upload": (path.name, path.read_bytes(), "video/mp4")})
    assert uploaded.status_code == 201
    video = uploaded.json()
    base = f"/api/videos/{video['id']}"
    assert client.post("/api/assignments", headers=admin,
                       json={"annotator_id": author_id, "video_id": video["id"]}).is_success
    limits = client.get(f"{base}/timeline", headers=author).json()["boundaries"]
    assert limits[-1] == video["duration"]
    segment = client.post(f"{base}/segments", headers=author, json={
        "title": "Entire clip", "description": "Still image", "audio_description": "Silent",
        "start_time": 0, "end_time": limits[-1],
    })
    assert segment.status_code == 201, segment.text
    assert segment.json()["end_frame"] == frames
    assert client.put(f"{base}/summary", headers=author, json={"summary": "Still image"}).is_success
    submitted = client.post(f"{base}/annotation-session/submit", headers=author, json={"expected_version": 0})
    assert submitted.status_code == 200, submitted.text
