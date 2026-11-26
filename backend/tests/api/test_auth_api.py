from __future__ import annotations

from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app

ADMIN_EMAIL = "admin@example.com"
ADMIN_PASSWORD = "initial-admin-password-123"


@pytest.fixture
def client(test_database_url: str, tmp_path: Path) -> Iterator[TestClient]:
    app = create_app(
        Settings(
            database_url=test_database_url,
            jwt_secret_key="test-signing-key-with-at-least-32-characters",
            access_token_minutes=30,
            initial_admin_email=ADMIN_EMAIL,
            initial_admin_password=ADMIN_PASSWORD,
        )
    )
    with TestClient(app) as test_client:
        yield test_client


def login(client: TestClient, email: str, password: str) -> str:
    response = client.post(
        "/api/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def create_user(
    client: TestClient,
    token: str,
    email: str,
    role: str,
) -> dict[str, Any]:
    response = client.post(
        "/api/users",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "email": email,
            "full_name": email.split("@")[0],
            "password": "secure-test-password-123",
            "role": role,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_login_me_and_user_management_access(client: TestClient) -> None:
    response = client.post(
        "/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    assert response.json()["token_type"] == "bearer"

    current_user = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert current_user.status_code == 200
    assert current_user.json()["role"] == "administrator"
    assert "password_hash" not in current_user.json()

    annotator = create_user(client, token, "annotator@example.com", "annotator")
    duplicate_user = client.post(
        "/api/users",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "email": "annotator@example.com",
            "full_name": "Another Annotator",
            "password": "secure-test-password-123",
            "role": "annotator",
        },
    )
    assert duplicate_user.status_code == 409, duplicate_user.text
    annotator_token = login(client, "annotator@example.com", "secure-test-password-123")
    assert client.get(
        "/api/users",
        headers={"Authorization": f"Bearer {annotator_token}"},
    ).status_code == 403
    assert UUID(annotator["id"])
    assert client.get("/api/auth/me").status_code == 401
    assert client.post(
        "/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": "wrong-password"},
    ).status_code == 401


def test_registration_persists_until_approval_or_rejection(client: TestClient) -> None:
    password = "registered-user-password-123"
    registered = client.post(
        "/api/auth/register",
        json={
            "email": "new-annotator@example.com",
            "full_name": "New Annotator",
            "password": password,
        },
    )
    assert registered.status_code == 202
    assert registered.content == b""

    def register_again(email):
        duplicate = client.post("/api/auth/register", json={
            "email": email, "full_name": "Different Name", "password": "different-password-123",
        })
        assert (duplicate.status_code, duplicate.content) == (registered.status_code, registered.content)

    register_again(" NEW-ANNOTATOR@example.com ")
    register_again(ADMIN_EMAIL)

    pending_login = client.post(
        "/api/auth/login",
        json={"email": "new-annotator@example.com", "password": password},
    )
    unknown_login = client.post("/api/auth/login", json={"email": "absent@example.com", "password": password})
    assert pending_login.status_code == unknown_login.status_code == 401
    assert pending_login.content == unknown_login.content

    admin_token = login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    headers = {"Authorization": f"Bearer {admin_token}"}
    pending = client.get("/api/users/pending", headers=headers)
    assert pending.status_code == 200
    [pending_user] = pending.json()
    assert pending_user["full_name"] == "New Annotator"
    assert pending_user["status"] == "pending"
    assert pending_user["role"] is None

    approved = client.patch(
        f"/api/users/{pending_user['id']}/approve",
        headers=headers,
        json={"role": "annotator"},
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "active"
    annotator_token = login(client, "new-annotator@example.com", password)
    current_user = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {annotator_token}"},
    )
    assert current_user.json()["role"] == "annotator"

    rejected = client.post(
        "/api/auth/register",
        json={
            "email": "rejected@example.com",
            "full_name": "Rejected User",
            "password": password,
        },
    )
    assert (rejected.status_code, rejected.content) == (registered.status_code, registered.content)
    [awaiting_review] = client.get("/api/users/pending", headers=headers).json()
    decision = client.patch(f"/api/users/{awaiting_review['id']}/reject", headers=headers)
    assert decision.status_code == 200, decision.text
    assert decision.json()["status"] == "rejected"
    register_again("rejected@example.com")
    assert client.get("/api/users/pending", headers=headers).json() == []
    rejected_login = client.post(
        "/api/auth/login",
        json={"email": "rejected@example.com", "password": password},
    )
    assert rejected_login.status_code == 401
    assert rejected_login.content == unknown_login.content
    


def test_admin_account_guards(client):
    token = login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    headers = {"Authorization": f"Bearer {token}"}
    first = client.get("/api/auth/me", headers=headers).json()
    second = create_user(client, token, "second@example.com", "administrator")
    assert client.delete(f"/api/users/{first['id']}", headers=headers).status_code == 409

    ready = Barrier(2)
    def demote(user):
        ready.wait(timeout=5)
        return client.patch(f"/api/users/{user['id']}/role", headers=headers,
                            json={"role": "annotator"}).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(pool.map(demote, (first, second)))
    assert statuses.count(200) == 1
    assert all(status in (200, 403, 409) for status in statuses)
    with client.app.state.database.connect() as connection:
        assert connection.execute("SELECT count(*) AS n FROM users WHERE role = 'administrator'").fetchone()["n"] == 1


def test_registration_returns_field_errors_without_echoing_input(client):
    response = client.post("/api/auth/register", json={
        "email": "user@localhost", "full_name": "   ", "password": "short",
    })
    assert response.status_code == 422
    assert {error["loc"][-1] for error in response.json()["detail"]} == {"email", "full_name", "password"}
    assert all("input" not in error for error in response.json()["detail"])
