"""Submission lifecycle, immutable review snapshots, permissions and persistence."""
from pathlib import Path
from unittest.mock import Mock

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.db.database import Database
from app.main import create_app
from app.services.video_metadata import VideoMetadata


@pytest.fixture
def workflow(test_database_url, tmp_path, monkeypatch):
    monkeypatch.setattr("app.api.routes.videos.extract_video_metadata", Mock(return_value=VideoMetadata(
        duration_seconds=3, width=160, height=90, fps=10, codec="h264")))

    def process(video_id, database_url, video_path, timeline_path, thumbnails_dir):
        Path(timeline_path).parent.mkdir(parents=True, exist_ok=True)
        np.save(timeline_path, np.arange(0, 3, 0.1))
        with Database(database_url).connect() as connection:
            connection.execute("UPDATE videos SET processing_status = 'COMPLETED' WHERE id = %s", (video_id,))

    monkeypatch.setattr("app.api.routes.videos.process_video", process)
    settings = Settings(database_url=test_database_url,
        jwt_secret_key="test-signing-key-with-at-least-32-characters", access_token_minutes=30,
        initial_admin_email="admin@example.com", initial_admin_password="test-password-123",
        video_storage_path=tmp_path / "videos" / "original")
    with TestClient(create_app(settings)) as client:
        def login(email):
            response = client.post("/api/auth/login", json={"email": email, "password": "test-password-123"})
            assert response.status_code == 200
            return {"Authorization": f"Bearer {response.json()['access_token']}"}

        admin = login("admin@example.com")
        users = {}
        for name, role in [("annotator", "annotator"), ("other", "annotator"), ("reviewer", "reviewer")]:
            response = client.post("/api/users", headers=admin, json={"email": f"{name}@example.com",
                "full_name": name, "password": "test-password-123", "role": role})
            assert response.status_code == 201
            users[name] = {"id": response.json()["id"], "headers": login(f"{name}@example.com")}
        video = client.post("/api/videos/upload", headers=admin, files={"upload": ("review.mp4", b"test", "video/mp4")}).json()
        assigned = client.post("/api/assignments", headers=admin, json={"video_id": video["id"], "annotator_id": users["annotator"]["id"]})
        assert assigned.status_code == 200
        yield client, admin, users, f"/api/videos/{video['id']}", settings


def save_work(client, base, headers):
    segment = client.post(f"{base}/segments", headers=headers, json={"title": "Opening", "start_time": 0.1,
        "end_time": 2.5, "description": "Visible action", "audio_description": "Audible speech"})
    assert segment.status_code == 201
    assert client.put(f"{base}/summary", headers=headers, json={"summary": "Whole video", "version": 0}).status_code == 200
    return segment.json()


def test_playback_token_respects_current_video_access_after_role_change(workflow):
    client, admin, users, base, _ = workflow
    reviewer = users["reviewer"]
    issued = client.post(f"{base}/media-token", headers=reviewer["headers"])
    assert issued.status_code == 200
    playback = {"media_token": issued.json()["token"]}
    assert client.get(f"{base}/stream", params=playback).status_code == 200

    changed = client.patch(f"/api/users/{reviewer['id']}/role", headers=admin,
                           json={"role": "annotator"})
    assert changed.status_code == 200
    assert client.get(f"{base}/stream", params=playback).status_code == 403
    assert client.post(f"{base}/media-token", headers=reviewer["headers"]).status_code == 403


def test_return_revise_resubmit_approve_and_restart(workflow):
    client, admin, users, base, settings = workflow
    author = users["annotator"]["headers"]
    reviewer = users["reviewer"]["headers"]
    segment = save_work(client, base, author)
    submitted = client.post(f"{base}/annotation-session/submit", headers=author, json={"expected_version": 0})
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["status"] == "submitted"
    queue = client.get("/api/reviews", headers=reviewer).json()
    assert len(queue) == 1
    review = f"/api/reviews/{queue[0]['id']}"
    detail = client.get(review, headers=reviewer).json()
    assert detail["segments"][0]["description"] == "Visible action"
    assert detail["summary"] == "Whole video"
    assert detail["can_review"] is True
    assert client.post(f"{review}/return", headers=reviewer, json={"expected_version": 1, "comment": "  "}).status_code == 422
    returned = client.post(f"{review}/return", headers=reviewer, json={"expected_version": 1, "comment": " Describe the sound more precisely. "})
    assert returned.status_code == 200
    assert returned.json()["status"] == "returned"
    assert client.post(f"{review}/approve", headers=reviewer, json={"expected_version": 1}).status_code == 409
    edited = client.put(f"{base}/segments/{segment['id']}", headers=author, json={**segment, "audio_description": "Two people are speaking."})
    assert edited.status_code == 200
    assert client.get(f"{base}/annotation-session", headers=author).json()["status"] == "returned"
    # Reviewers see the previously submitted revision, never the live draft.
    assert client.get(review, headers=reviewer).json()["segments"][0]["audio_description"] == "Audible speech"
    assert client.post(f"{base}/annotation-session/submit", headers=author, json={"expected_version": 2}).status_code == 409
    assert client.post(f"{base}/annotation-session/resubmit", headers=author, json={"expected_version": 2}).status_code == 200
    assert client.get(review, headers=reviewer).json()["segments"][0]["audio_description"] == "Two people are speaking."
    approved = client.post(f"{review}/approve", headers=reviewer, json={"expected_version": 3, "comment": "Looks good."})
    assert approved.status_code == 200
    history = approved.json()["review_history"]
    assert [event["action"] for event in history] == ["submitted", "returned", "resubmitted", "approved"]
    assert [event["version"] for event in history] == [1, 2, 3, 4]
    assert history[1]["comment"] == "Describe the sound more precisely."
    assert history[1]["actor_id"] == users["reviewer"]["id"]
    assert history[0]["actor_id"] == users["annotator"]["id"]
    assert all(event["created_at"] for event in history)

    for name in ("annotator", "reviewer"):
        deletion = client.delete(f"/api/users/{users[name]['id']}", headers=admin)
        assert deletion.status_code == 409
    assert client.get(review, headers=reviewer).json()["review_history"] == history

    # A new application instance runs initialization/migrations against the same
    # stored database. The accepted revision, lock and audit history must survive.
    with TestClient(create_app(settings)) as restarted:
        persisted = restarted.get(review, headers=reviewer).json()
        assert persisted["status"] == "approved"
        assert persisted["review_history"] == history
        assert persisted["summary"] == "Whole video"
        assert persisted["segments"][0]["audio_description"] == "Two people are speaking."
        assert restarted.get("/api/me/assignments", headers=author).json()[0]["status"] == "approved"
        assert restarted.put(f"{base}/summary", headers=author, json={"summary": "Changed", "version": 1}).status_code == 409


@pytest.mark.parametrize("final_state", ["submitted", "approved"])
def test_submitted_and_approved_work_cannot_be_mutated(workflow, final_state):
    client, admin, users, base, _ = workflow
    author = users["annotator"]["headers"]
    reviewer = users["reviewer"]["headers"]
    segment = save_work(client, base, author)
    assert client.post(f"{base}/annotation-session/submit", headers=author, json={"expected_version": 0}).status_code == 200
    review_id = client.get("/api/reviews", headers=reviewer).json()[0]["id"]
    version = 1
    if final_state == "approved":
        assert client.post(f"/api/reviews/{review_id}/approve", headers=reviewer, json={"expected_version": 1}).status_code == 200
        version = 2
    assert client.post(f"{base}/segments", headers=author, json=segment).status_code == 409
    assert client.put(f"{base}/segments/{segment['id']}", headers=author, json=segment).status_code == 409
    assert client.delete(f"{base}/segments/{segment['id']}?version=1", headers=author).status_code == 409
    assert client.put(f"{base}/summary", headers=author, json={"summary": "Changed", "version": 1}).status_code == 409
    assert client.post(f"{base}/annotation-session/complete", headers=author).status_code == 409
    for action in ["submit", "resubmit", "skip"]:
        assert client.post(f"{base}/annotation-session/{action}", headers=author, json={"expected_version": version}).status_code == 409
    assert client.get(f"{base}/segments", headers=author).json()[0] == segment


def test_permissions_validation_and_skip_resume(workflow):
    client, admin, users, base, _ = workflow
    author = users["annotator"]["headers"]
    reviewer = users["reviewer"]["headers"]
    assert client.post(f"{base}/annotation-session/submit", json={"expected_version": 0}).status_code == 401
    for headers in [reviewer, admin, users["other"]["headers"]]:
        assert client.post(f"{base}/annotation-session/submit", headers=headers, json={"expected_version": 0}).status_code == 403
    assert client.post(f"{base}/annotation-session/submit", headers=author, json={"expected_version": 0}).status_code == 422
    assert client.post(f"{base}/annotation-session/resubmit", headers=author, json={"expected_version": 0}).status_code == 409
    skipped = client.post(f"{base}/annotation-session/skip", headers=author, json={"expected_version": 0, "comment": "Need to check the audio later."})
    assert skipped.status_code == 200
    assert client.get("/api/me/assignments", headers=author).json()[0]["status"] == "skipped"
    assert client.post(f"{base}/annotation-session/submit", headers=author, json={"expected_version": 1}).status_code == 409
    segment = save_work(client, base, author)
    assert client.get(f"{base}/annotation-session", headers=author).json()["status"] == "in_progress"
    assert client.post(f"{base}/annotation-session/submit", headers=author, json={"expected_version": 0}).status_code == 409
    assert client.post(f"{base}/annotation-session/submit", headers=author, json={"expected_version": 1}).status_code == 200
    review_id = client.get("/api/reviews", headers=reviewer).json()[0]["id"]
    assert client.get("/api/reviews", headers=author).status_code == 403
    assert client.get(f"/api/reviews/{review_id}", headers=users["other"]["headers"]).status_code == 403
    assert client.post(f"/api/reviews/{review_id}/approve", headers=author, json={"expected_version": 2}).status_code == 403
    assert client.put(f"{base}/segments/{segment['id']}", headers=reviewer, json=segment).status_code == 403
    # Role changes do not allow self-approval of a previously authored submission.
    assert client.patch(f"/api/users/{users['annotator']['id']}/role", headers=admin, json={"role": "reviewer"}).status_code == 200
    assert client.post(f"/api/reviews/{review_id}/approve", headers=author, json={"expected_version": 2}).status_code == 403
    assert client.post(f"/api/reviews/{review_id}/approve", headers=admin, json={"expected_version": 2}).status_code == 200


def test_admin_can_export_annotation_as_json(workflow):
    client, admin, users, base, _ = workflow
    author = users["annotator"]["headers"]
    save_work(client, base, author)
    assert client.post(f"{base}/annotation-session/submit", headers=author,
                       json={"expected_version": 0}).status_code == 200
    review_id = client.get("/api/reviews", headers=admin).json()[0]["id"]
    response = client.get(f"/api/reviews/{review_id}/export/json", headers=admin)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert response.headers["content-disposition"] == f'attachment; filename="annotation-{review_id}.json"'
    data = response.json()
    assert data["video"]["filename"] == "review.mp4"
    assert data["annotator"]["email"] == "annotator@example.com"
    assert data["annotation"]["summary"] == "Whole video"
    assert data["annotation"]["segments"][0]["title"] == "Opening"


def test_admin_can_export_annotation_as_csv(workflow):
    client, admin, users, base, _ = workflow
    author = users["annotator"]["headers"]
    save_work(client, base, author)
    assert client.post(f"{base}/annotation-session/submit", headers=author,
                       json={"expected_version": 0}).status_code == 200
    review_id = client.get("/api/reviews", headers=admin).json()[0]["id"]
    response = client.get(f"/api/reviews/{review_id}/export/csv", headers=admin)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert response.headers["content-disposition"] == f'attachment; filename="annotation-{review_id}.csv"'
    assert "review.mp4" in response.text
    assert "annotator@example.com" in response.text
    assert "Opening" in response.text
    assert "Whole video" in response.text


@pytest.mark.parametrize("format", ["json", "csv"])
def test_annotator_cannot_export_annotations(workflow, format):
    client, admin, users, base, _ = workflow
    author = users["annotator"]["headers"]
    save_work(client, base, author)
    assert client.post(f"{base}/annotation-session/submit", headers=author,
                       json={"expected_version": 0}).status_code == 200
    review_id = client.get("/api/reviews", headers=admin).json()[0]["id"]
    assert client.get(f"/api/reviews/{review_id}/export/{format}",
                      headers=author).status_code == 403
