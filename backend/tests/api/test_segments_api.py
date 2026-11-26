"""Saved segment behavior and user isolation."""

from collections.abc import Iterator
from pathlib import Path
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.services.video_metadata import VideoMetadata


@pytest.fixture
def client(test_database_url: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setattr(
        "app.api.routes.videos.extract_video_metadata",
        Mock(return_value=VideoMetadata(
            duration_seconds=12.5, width=640, height=480, fps=25, codec="h264",
        )),
    )
    def timing(video_id, database_url, video_path, timeline_path, thumbnails_dir):
        import numpy as np
        Path(timeline_path).parent.mkdir(parents=True, exist_ok=True)
        np.save(timeline_path, np.arange(0, 12.5, 0.04))
    monkeypatch.setattr("app.api.routes.videos.process_video", timing)
    app = create_app(Settings(
        database_url=test_database_url,
        jwt_secret_key="test-signing-key-with-at-least-32-characters",
        access_token_minutes=30,
        initial_admin_email="admin@example.com",
        initial_admin_password="initial-admin-password-123",
        video_storage_path=tmp_path / "videos" / "original",
    ))
    with TestClient(app) as test_client:
        yield test_client


def _login(client: TestClient, email: str, password: str) -> str:
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return response.json()["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_segments_save_reload_edit_and_isolate_users(client: TestClient) -> None:
    admin = _login(client, "admin@example.com", "initial-admin-password-123")
    upload = client.post(
        "/api/videos/upload", headers=_auth(admin),
        files={"upload": ("test.mp4", b"video bytes", "video/mp4")},
    )
    assert upload.status_code == 201, upload.text
    video_id = upload.json()["id"]
    url = f"/api/videos/{video_id}/segments"

    assert client.get(url).status_code == 401
    assert client.get(url, headers=_auth(admin)).json() == []
    payload = {
        "title": "Opening", "start_time": 1.0,
        "end_time": 3.5, "description": "A person enters the room.",
        "audio_description": "Footsteps are audible.",
    }
    created = client.post(url, headers=_auth(admin), json=payload)
    assert created.status_code == 201, created.text
    segment_id = created.json()["id"]
    assert created.json()["description"] == payload["description"]
    assert created.json()["audio_description"] == payload["audio_description"]
    assert client.get(url, headers=_auth(admin)).json()[0]["id"] == segment_id

    edited = client.put(
        f"{url}/{segment_id}", headers=_auth(admin),
        json={**payload, "title": "First scene", "end_time": 4.0,
              "audio_description": "A door closes."},
    )
    assert edited.status_code == 200, edited.text
    assert client.get(url, headers=_auth(admin)).json()[0]["title"] == "First scene"
    assert client.get(url, headers=_auth(admin)).json()[0]["audio_description"] == "A door closes."

    assert client.post(url, headers=_auth(admin), json={**payload, "end_time": 13.0}).status_code == 422
    assert client.post(url, headers=_auth(admin), json={**payload, "end_time": 0.5}).status_code == 422

    user = client.post("/api/users", headers=_auth(admin), json={
        "email": "other@example.com", "full_name": "Other",
        "password": "secure-test-password-123", "role": "annotator",
    })
    assert user.status_code == 201, user.text
    other = _login(client, "other@example.com", "secure-test-password-123")
    assert client.get(url, headers=_auth(other)).status_code == 403
    assigned = client.post("/api/assignments", headers=_auth(admin), json={
        "video_id": video_id, "annotator_id": user.json()["id"],
    })
    assert assigned.status_code == 200, assigned.text
    assert client.get(url, headers=_auth(other)).json() == []
    assert client.put(f"{url}/{segment_id}", headers=_auth(other), json=payload).status_code == 404
    assert client.delete(f"{url}/{segment_id}", headers=_auth(other)).status_code == 404
    assert client.get(url, headers=_auth(admin)).json()[0]["id"] == segment_id

    deleted = client.delete(f"{url}/{segment_id}?version=2", headers=_auth(admin))
    assert deleted.status_code == 204, deleted.text
    assert client.get(url, headers=_auth(admin)).json() == []
    assert client.delete(f"{url}/{segment_id}", headers=_auth(admin)).status_code == 404


def test_video_summary_is_saved_and_isolated_per_annotator(client: TestClient) -> None:
    admin = _login(client, "admin@example.com", "initial-admin-password-123")
    upload = client.post(
        "/api/videos/upload", headers=_auth(admin),
        files={"upload": ("test.mp4", b"video bytes", "video/mp4")},
    )
    assert upload.status_code == 201, upload.text
    url = f"/api/videos/{upload.json()['id']}/summary"

    assert client.get(url).status_code == 401
    assert client.get(url, headers=_auth(admin)).json()["summary"] == ""
    saved = client.put(url, headers=_auth(admin), json={"summary": "Opening scene."})
    assert saved.status_code == 200, saved.text
    assert client.get(url, headers=_auth(admin)).json()["summary"] == "Opening scene."
    assert client.put(url, headers=_auth(admin), json={"summary": "Revised summary.", "version": 1}).status_code == 200
    assert client.get(url, headers=_auth(admin)).json()["summary"] == "Revised summary."

    user = client.post("/api/users", headers=_auth(admin), json={
        "email": "summary@example.com", "full_name": "Second Annotator",
        "password": "secure-test-password-123", "role": "annotator",
    })
    assert user.status_code == 201, user.text
    other = _login(client, "summary@example.com", "secure-test-password-123")
    assert client.get(url, headers=_auth(other)).status_code == 403
    assigned = client.post("/api/assignments", headers=_auth(admin), json={
        "video_id": upload.json()["id"], "annotator_id": user.json()["id"],
    })
    assert assigned.status_code == 200, assigned.text
    assert client.get(url, headers=_auth(other)).json()["summary"] == ""
    assert client.put(url, headers=_auth(other), json={"summary": "Another view."}).status_code == 200
    assert client.get(url, headers=_auth(admin)).json()["summary"] == "Revised summary."
    assert client.get(url, headers=_auth(other)).json()["summary"] == "Another view."


def test_first_summary_save_requires_version_zero(client: TestClient) -> None:
    headers = _auth(_login(client, "admin@example.com", "initial-admin-password-123"))
    upload = client.post(
        "/api/videos/upload", headers=headers,
        files={"upload": ("summary.mp4", b"video bytes", "video/mp4")},
    )
    assert upload.status_code == 201, upload.text
    url = f"/api/videos/{upload.json()['id']}/summary"
    initial = client.get(url, headers=headers).json()
    assert initial["version"] == 0

    response = client.put(url, headers=headers, json={"summary": "Draft", "version": 1})

    assert response.status_code == 409, response.text
    assert client.get(url, headers=headers).json() == initial


def test_access_media_scope_and_stale_saves(client: TestClient) -> None:
    admin = _login(client, "admin@example.com", "initial-admin-password-123")
    headers = _auth(admin)
    video = client.post("/api/videos/upload", headers=headers, files={"upload": ("access.mp4", b"video", "video/mp4")}).json()
    base = f"/api/videos/{video['id']}"
    assert client.get(f"{base}/stream").status_code == 401
    token = client.post(f"{base}/media-token", headers=headers).json()["token"]
    assert client.get(f"{base}/stream", params={"media_token": token}).status_code == 200
    assert client.get("/api/auth/me", headers=_auth(token)).status_code == 401
    from uuid import uuid4
    assert client.get(f"/api/videos/{uuid4()}/stream", params={"media_token": token}).status_code == 401
    data = {"title": "Scene", "start_time": 0, "end_time": 1, "description": "Visible", "audio_description": "Silent"}
    segment = client.post(f"{base}/segments", headers=headers, json=data).json()
    url = f"{base}/segments/{segment['id']}"
    assert client.put(url, headers=headers, json={**data, "version": segment["version"]}).status_code == 200
    assert client.put(url, headers=headers, json={**data, "version": segment["version"]}).status_code == 409
    assert client.delete(url, headers=headers, params={"version": segment["version"]}).status_code == 409
    assert client.put(f"{base}/summary", headers=headers, json={"summary": "First", "version": 0}).status_code == 200
    assert client.put(f"{base}/summary", headers=headers, json={"summary": "Stale", "version": 0}).status_code == 409
    assert client.get(f"{base}/summary", headers=headers).json()["summary"] == "First"


def test_summary_progress_and_completion(client: TestClient) -> None:
    admin = _login(client, "admin@example.com", "initial-admin-password-123")
    headers = _auth(admin)
    video = client.post("/api/videos/upload", headers=headers, files={"upload": ("complete.mp4", b"video", "video/mp4")}).json()
    base = f"/api/videos/{video['id']}"
    user = client.post("/api/users", headers=headers, json={"email": "completion@example.com", "full_name": "Annotator", "password": "secure-test-password-123", "role": "annotator"}).json()
    annotator = _auth(_login(client, "completion@example.com", "secure-test-password-123"))
    assert client.get("/api/videos", headers=annotator).json() == []
    assert client.get(f"{base}/stream", headers=annotator).status_code == 403
    client.post("/api/assignments", headers=headers, json={"video_id": video["id"], "annotator_id": user["id"]})
    assert client.get(f"{base}/stream", headers=annotator).status_code == 200
    assert client.post(f"{base}/annotation-session/complete", headers=annotator).status_code == 422
    client.put(f"{base}/summary", headers=annotator, json={"summary": "My summary"})
    assert client.get("/api/me/assignments", headers=annotator).json()[0]["status"] == "in_progress"
    data = {"title": "Scene", "start_time": 0, "end_time": 1, "description": "Visible", "audio_description": "Silent"}
    segment = client.post(f"{base}/segments", headers=annotator, json=data).json()
    assert client.post(f"{base}/annotation-session/complete", headers=annotator).status_code == 200
    assert client.get(f"{base}/annotation-session", headers=annotator).json()["status"] == "completed"
    client.put(f"{base}/segments/{segment['id']}", headers=annotator, json={**data, "version": segment["version"]})
    assert client.get(f"{base}/annotation-session", headers=annotator).json()["status"] == "in_progress"
