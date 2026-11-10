"""Shared fixtures.

Tests marked `db` talk to a real Postgres. Point TEST_DATABASE_URL at any
database you don't mind us creating a temporary schema in, e.g.

    export TEST_DATABASE_URL="postgresql://postgres:postgres@localhost:5432/postgres"

Each test gets its own throwaway schema (created from schema.sql and dropped
afterwards), so your real tables are never touched. If TEST_DATABASE_URL is
not set, the `db` tests are skipped.
"""

import os
import uuid

import psycopg
import pytest
from psycopg import sql
from psycopg.conninfo import make_conninfo

from src.db.connection import get_connection
from src.db.init_db import init_db


@pytest.fixture
def db(monkeypatch):
    """A connection to a fresh, isolated copy of the schema."""
    base_url = os.environ.get("DATABASE_URL")
    if not base_url:
        pytest.skip("DATABASE_URL not set")

    schema = f"test_{uuid.uuid4().hex[:12]}"
    admin = psycopg.connect(base_url, autocommit=True)

    try:
        admin.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))

        url = make_conninfo(base_url, options=f"-c search_path={schema}")
        monkeypatch.setenv("DATABASE_URL", url)

        init_db()
        conn = get_connection()
        try:
            yield conn
        finally:
            conn.close()
    finally:
        admin.execute(
            sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(sql.Identifier(schema))
        )
        admin.close()
