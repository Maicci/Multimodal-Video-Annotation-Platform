"""Assignment requests use an active annotator's ID."""

from collections.abc import Iterator
from pathlib import Path
from unittest.mock import Mock
from uuid import uuid4

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
            duration_seconds=3.0, width=160, height=90, fps=10, codec="h264",
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


def test_assignment_uses_active_annotator_id(client: TestClient) -> None:
    login = client.post("/api/auth/login", json={
        "email": "admin@example.com", "password": "initial-admin-password-123",
    })
    admin = {"Authorization": f"Bearer {login.json()['access_token']}"}
    video = client.post(
        "/api/videos/upload", headers=admin,
        files={"upload": ("assignment.mp4", b"video bytes", "video/mp4")},
    )
    assert video.status_code == 201, video.text
    video_id = video.json()["id"]

    annotator = client.post("/api/users", headers=admin, json={
        "email": "assigned@example.com", "full_name": "Assigned User",
        "password": "secure-test-password-123", "role": "annotator",
    })
    assert annotator.status_code == 201, annotator.text
    annotator_id = annotator.json()["id"]
    payload = {"video_id": video_id, "annotator_id": annotator_id}
    assigned = client.post("/api/assignments", headers=admin, json=payload)
    assert assigned.status_code == 200, assigned.text
    assert assigned.json()["user_id"] == annotator_id
    assert client.post("/api/assignments", headers=admin, json=payload).status_code == 409

    annotator_login = client.post("/api/auth/login", json={
        "email": "assigned@example.com", "password": "secure-test-password-123",
    })
    annotator_headers = {"Authorization": f"Bearer {annotator_login.json()['access_token']}"}
    listed = client.get("/api/me/assignments", headers=annotator_headers)
    assert listed.status_code == 200, listed.text
    assert [assignment["video_id"] for assignment in listed.json()] == [video_id]
    assert client.post("/api/assignments", headers=annotator_headers, json=payload).status_code == 403

    pending = client.post("/api/auth/register", json={
        "email": "pending@example.com", "full_name": "Pending User",
        "password": "secure-test-password-123",
    })
    assert pending.status_code == 202, pending.text
    [pending_user] = client.get("/api/users/pending", headers=admin).json()
    assert client.post("/api/assignments", headers=admin, json={
        "video_id": video_id, "annotator_id": pending_user["id"],
    }).status_code == 400
    assert client.post("/api/assignments", headers=admin, json={
        "video_id": video_id, "annotator_id": str(uuid4()),
    }).status_code == 404
    assert client.post("/api/assignments", headers=admin, json={
        "video_id": str(uuid4()), "annotator_id": annotator_id,
    }).status_code == 404
