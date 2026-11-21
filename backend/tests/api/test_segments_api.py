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
    monkeypatch.setattr("app.api.routes.videos.process_video", Mock())
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
    }
    created = client.post(url, headers=_auth(admin), json=payload)
    assert created.status_code == 201, created.text
    segment_id = created.json()["id"]
    assert created.json()["description"] == payload["description"]
    assert client.get(url, headers=_auth(admin)).json()[0]["id"] == segment_id

    edited = client.put(
        f"{url}/{segment_id}", headers=_auth(admin),
        json={**payload, "title": "First scene", "end_time": 4.0},
    )
    assert edited.status_code == 200, edited.text
    assert client.get(url, headers=_auth(admin)).json()[0]["title"] == "First scene"

    assert client.post(url, headers=_auth(admin), json={**payload, "end_time": 13.0}).status_code == 422
    assert client.post(url, headers=_auth(admin), json={**payload, "end_time": 0.5}).status_code == 422

    user = client.post("/api/users", headers=_auth(admin), json={
        "email": "other@example.com", "full_name": "Other",
        "password": "secure-test-password-123", "role": "annotator",
    })
    assert user.status_code == 201, user.text
    other = _login(client, "other@example.com", "secure-test-password-123")
    assert client.get(url, headers=_auth(other)).json() == []
    assert client.put(f"{url}/{segment_id}", headers=_auth(other), json=payload).status_code == 404
