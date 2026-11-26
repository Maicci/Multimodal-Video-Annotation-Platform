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
        """
        SELECT id, password_hash, status
        FROM users
        WHERE email = %s
        """,
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


def find_user_by_email(
    connection: psycopg.Connection[dict[str, Any]], email: str
) -> dict[str, Any] | None:
    return connection.execute(
        """
        SELECT id, email, full_name, role, status, created_at
        FROM users
        WHERE email = %s
        """,
        (email.strip().lower(),),
    ).fetchone()


def find_user_by_id(
    connection: psycopg.Connection[dict[str, Any]], user_id: str
) -> dict[str, Any] | None:
    return connection.execute(
        """
        SELECT id, email, full_name, role, status, created_at
        FROM users
        WHERE id = %s
        """,
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
        """
        SELECT id, email, full_name, role, status, created_at
        FROM users
        ORDER BY email
        """
    ).fetchall()


def count_users_with_role(
    connection: psycopg.Connection[dict[str, Any]], role: str
) -> int:
    row = connection.execute(
        "SELECT COUNT(*) AS count FROM users WHERE role = %s AND status = 'active'",
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
    with connection.transaction():
        user = connection.execute(
            """
            INSERT INTO users (
                id,
                email,
                full_name,
                role,
                password_hash
            )
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id, email, full_name, role, status, created_at
            """,
            (
                str(uuid4()),
                email,
                full_name,
                role,
                password_hash,
            ),
        ).fetchone()
    connection.commit()
    return user


def create_pending_user(
    connection: psycopg.Connection[dict[str, Any]],
    *,
    email: str,
    full_name: str,
    password_hash: str,
) -> None:
    with connection.transaction():
        connection.execute(
            """
            INSERT INTO users (
                id,
                email,
                full_name,
                role,
                status,
                password_hash
            )
            VALUES (%s, %s, %s, NULL, 'pending', %s)
            ON CONFLICT (email) DO NOTHING
            """,
            (
                str(uuid4()),
                email,
                full_name,
                password_hash,
            ),
        )
    connection.commit()


def list_pending_users(
    connection: psycopg.Connection[dict[str, Any]],
) -> list[dict[str, Any]]:
    return connection.execute(
        """
        SELECT id, email, full_name, role, status, created_at
        FROM users
        WHERE status = 'pending'
        ORDER BY created_at
        """
    ).fetchall()


def approve_user(
    connection: psycopg.Connection[dict[str, Any]],
    user_id: str,
    role: str,
    approved_by: str,
) -> None:
    connection.execute(
        """
        UPDATE users
        SET role = %s,
            status = 'active',
            approved_by = %s,
            approved_at = CURRENT_TIMESTAMP
        WHERE id = %s
          AND status = 'pending'
        """,
        (role, approved_by, user_id),
    )

    connection.commit()


def reject_user(
    connection: psycopg.Connection[dict[str, Any]],
    user_id: str,
    approved_by: str,
) -> None:
    connection.execute(
        """
        UPDATE users
        SET status = 'rejected',
            approved_by = %s,
            approved_at = CURRENT_TIMESTAMP
        WHERE id = %s
          AND status = 'pending'
        """,
        (approved_by, user_id),
    )

    connection.commit()


def update_user_role(
    connection: psycopg.Connection[dict[str, Any]],
    user_id: str,
    role: str,
) -> None:
    connection.execute(
        "UPDATE users SET role = %s WHERE id = %s",
        (role, user_id),
    )
    connection.commit()


def delete_user(
    connection: psycopg.Connection[dict[str, Any]],
    user_id: str,
) -> None:
    connection.execute(
        "DELETE FROM users WHERE id = %s",
        (user_id,),
    )
    connection.commit()
