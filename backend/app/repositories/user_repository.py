"""Persistence operations for users."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import psycopg

# TODO queries need to be updated when the database structure is decided

def find_user_credentials_by_email(
    connection: psycopg.Connection[dict[str, Any]], email: str
) -> dict[str, Any] | None:
    return connection.execute(
        "SELECT id, password_hash FROM users WHERE email = %s",
        (email,),
    ).fetchone()


def find_user_role_by_email(
    connection: psycopg.Connection[dict[str, Any]], email: str
) -> str | None:
    row = connection.execute(
        "SELECT role FROM users WHERE email = %s",
        (email,),
    ).fetchone()
    return None if row is None else row["role"]


def find_user_by_id(
    connection: psycopg.Connection[dict[str, Any]], user_id: str
) -> dict[str, Any] | None:
    return connection.execute(
        "SELECT id, email, full_name, role, created_at FROM users WHERE id = %s",
        (user_id,),
    ).fetchone()


def find_user_role_by_id(
    connection: psycopg.Connection[dict[str, Any]], user_id: str
) -> str | None:
    row = connection.execute(
        "SELECT role FROM users WHERE id = %s",
        (user_id,),
    ).fetchone()
    return None if row is None else row["role"]


def list_users(
    connection: psycopg.Connection[dict[str, Any]],
) -> list[dict[str, Any]]:
    return connection.execute(
        "SELECT id, email, full_name, role, created_at FROM users ORDER BY email"
    ).fetchall()


def count_users_with_role(
    connection: psycopg.Connection[dict[str, Any]], role: str
) -> int:
    row = connection.execute(
        "SELECT COUNT(*) AS count FROM users WHERE role = %s",
        (role,),
    ).fetchone()
    return row["count"]


def create_user(
    connection: psycopg.Connection[dict[str, Any]],
    *,
    email: str,
    full_name: str,
    role: str,
    password_hash: str,
) -> dict[str, Any]:
    with connection:
        return connection.execute(
            """
            INSERT INTO users (id, email, full_name, role, password_hash)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id, email, full_name, role, created_at
            """,
            (str(uuid4()), email, full_name, role, password_hash),
        ).fetchone()


def update_user_role(
    connection: psycopg.Connection[dict[str, Any]], user_id: str, role: str
) -> None:
    with connection:
        connection.execute(
            "UPDATE users SET role = %s WHERE id = %s",
            (role, user_id),
        )


def delete_user(
    connection: psycopg.Connection[dict[str, Any]], user_id: str
) -> None:
    with connection:
        connection.execute("DELETE FROM users WHERE id = %s", (user_id,))
