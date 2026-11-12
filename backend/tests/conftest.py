from __future__ import annotations

import os
from collections.abc import Iterator
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo
import pytest


@pytest.fixture
def test_database_url() -> Iterator[str]:
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.fail(
            "Set TEST_DATABASE_URL to a PostgreSQL test database before running "
            "the backend tests.",
            pytrace=False,
        )

    schema_name = f"test_{uuid4().hex}"
    with psycopg.connect(database_url) as connection:
        connection.execute(
            sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema_name))
        )

    isolated_database_url = make_conninfo(
        database_url,
        options=f"-c search_path={schema_name}",
    )
    try:
        yield isolated_database_url
    finally:
        with psycopg.connect(database_url) as connection:
            connection.execute(
                sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema_name))
            )
