from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import cast
from unittest.mock import Mock

import psycopg
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx2 import Response

from app.core.config import Settings
from app.main import create_app
from app.services.video_metadata import VideoMetadata, VideoMetadataError

ADMIN_EMAIL = "video-admin@example.com"
ADMIN_PASSWORD = "initial-admin-password-123"
VIDEO_BYTES = b"unchanged video bytes"


@pytest.fixture
def client(test_database_url: str, tmp_path: Path) -> Iterator[TestClient]:
    app = create_app(
        Settings(
            database_url=test_database_url,
            jwt_secret_key="test-signing-key-with-at-least-32-characters",
            access_token_minutes=30,
            initial_admin_email=ADMIN_EMAIL,
            initial_admin_password=ADMIN_PASSWORD,
            video_storage_path=tmp_path / "storage" / "videos" / "original",
            max_video_size_bytes=64,
        )
    )
    with TestClient(app) as test_client:
        yield test_client


def _token(client: TestClient) -> str:
    response = client.post(
        "/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def _app(client: TestClient) -> FastAPI:
    return cast(FastAPI, client.app)


def _upload(
    client: TestClient,
    token: str,
    filename: str = "sample.mp4",
    content: bytes = VIDEO_BYTES,
) -> Response:
    return client.post(
        "/api/videos/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={"upload": (filename, content, "video/mp4")},
    )


def _metadata() -> VideoMetadata:
    return VideoMetadata(
        duration_seconds=12.5,
        width=1920,
        height=1080,
        fps=29.97,
        codec="h264",
    )


def _metadata_for_existing_file(path: Path) -> VideoMetadata:
    assert path.is_file()
    return _metadata()


def test_upload_requires_authentication(client: TestClient) -> None:
    response = client.post(
        "/api/videos/upload",
        files={"upload": ("sample.mp4", VIDEO_BYTES, "video/mp4")},
    )
    assert response.status_code == 401


@pytest.mark.parametrize("filename", ["sample.mp4", "sample.MOV"])
def test_upload_video_persists_bytes_metadata_and_uploader(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    filename: str,
) -> None:
    queued = Mock()
    monkeypatch.setattr(
        "app.api.routes.videos.extract_video_metadata",
        Mock(side_effect=_metadata_for_existing_file),
    )
    monkeypatch.setattr("app.api.routes.videos.process_video", queued)
    token = _token(client)

    response = _upload(client, token, filename)

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["filename"] == filename
    assert body["status"] == "PENDING"
    assert body["duration"] == 12.5
    connection = _app(client).state.database.connect()
    try:
        row = connection.execute(
            "SELECT * FROM videos WHERE id = %s", (body["id"],)
        ).fetchone()
        user = connection.execute(
            "SELECT id FROM users WHERE email = %s", (ADMIN_EMAIL,)
        ).fetchone()
    finally:
        connection.close()

    assert row["uploader_id"] == user["id"]
    assert row["original_filename"] == filename
    assert row["duration_seconds"] == 12.5
    assert row["width"] == 1920
    assert row["height"] == 1080
    assert row["fps"] == 29.97
    assert row["codec"] == "h264"
    assert row["processing_status"] == "PENDING"
    stored_path = Path(row["storage_path"])
    assert stored_path.read_bytes() == VIDEO_BYTES
    queued.assert_called_once()
    args = queued.call_args.args
    assert args[0] == body["id"]
    assert args[1] == _app(client).state.settings.database_url
    assert args[2] == stored_path
    assert args[3] == stored_path.parent.parent / "timelines" / f"{stored_path.stem}.npy"
    assert args[4] == stored_path.parent.parent / "thumbnails" / stored_path.stem


def test_rejects_unsupported_file_type(client: TestClient) -> None:
    response = _upload(client, _token(client), "notes.txt")
    assert response.status_code == 415
    assert response.json() == {"error": "Unsupported video format"}


def test_rejects_upload_over_configured_size(client: TestClient) -> None:
    response = _upload(client, _token(client), content=b"x" * 65)
    assert response.status_code == 413
    assert response.json() == {"error": "File too large"}
    assert list(_app(client).state.settings.video_storage_path.glob("*")) == []


def test_duplicate_filename_does_not_replace_original(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.api.routes.videos.extract_video_metadata",
        Mock(side_effect=_metadata_for_existing_file),
    )
    monkeypatch.setattr(
        "app.api.routes.videos.process_video",
        Mock(),
    )
    token = _token(client)
    first = _upload(client, token, content=b"first upload")
    assert first.status_code == 201
    connection = _app(client).state.database.connect()
    try:
        row = connection.execute(
            "SELECT storage_path FROM videos WHERE id = %s", (first.json()["id"],)
        ).fetchone()
    finally:
        connection.close()
    first_path = Path(row["storage_path"])

    duplicate = _upload(client, token, content=b"replacement")

    assert duplicate.status_code == 409
    assert duplicate.json()["action_required"] is True
    assert duplicate.json()["video_id"] == first.json()["id"]
    assert first_path.read_bytes() == b"first upload"
    assert len(list(first_path.parent.iterdir())) == 1


def test_metadata_failure_returns_500_and_removes_file(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.api.routes.videos.extract_video_metadata",
        Mock(side_effect=VideoMetadataError("ffprobe failed")),
    )
    response = _upload(client, _token(client))

    assert response.status_code == 500
    assert response.json() == {"error": "Metadata extraction failed"}
    assert list(_app(client).state.settings.video_storage_path.glob("*")) == []


def test_storage_failure_returns_500(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.api.routes.videos.store_video",
        Mock(side_effect=OSError("disk unavailable")),
    )
    response = _upload(client, _token(client))

    assert response.status_code == 500
    assert response.json() == {"error": "Storage failure"}


def test_database_failure_returns_500_and_removes_file(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.api.routes.videos.extract_video_metadata",
        Mock(side_effect=_metadata_for_existing_file),
    )
    monkeypatch.setattr(
        "app.api.routes.videos.create_video",
        Mock(side_effect=psycopg.OperationalError("database unavailable")),
    )
    response = _upload(client, _token(client))

    assert response.status_code == 500
    assert response.json() == {"error": "Database failure"}
    assert list(_app(client).state.settings.video_storage_path.glob("*")) == []
    
