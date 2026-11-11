"""get_connection / init_db, with psycopg mocked out (no db req)."""

import psycopg
from psycopg.rows import dict_row
from src.db import connection, init_db


def test_passes_none_when_env_unset(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    calls = []
    monkeypatch.setattr(psycopg, "connect", lambda *a, **kw: calls.append((a, kw)))

    connection.get_connection()

    assert calls[0][0] == (None,)


def DATABASE_URL_env_var_overrides_default(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@db.example:5433/other")
    calls = []
    monkeypatch.setattr(psycopg, "connect", lambda *a, **kw: calls.append((a, kw)))

    connection.get_connection()

    assert calls[0][0] == ("postgresql://u:p@db.example:5433/other",)


def test_rows_are_returned_as_dicts(monkeypatch):
    calls = []
    monkeypatch.setattr(psycopg, "connect", lambda *a, **kw: calls.append((a, kw)))

    connection.get_connection()

    assert calls[0][1]["row_factory"] is dict_row


def test_init_db_executes_schema_file_in_one_connection(monkeypatch):
    executed = []

    class FakeConn:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def execute(self, query):
            executed.append(query)

    monkeypatch.setattr(init_db, "get_connection", FakeConn)

    init_db.init_db()

    assert executed == [init_db.SCHEMA_FILE.read_text()]
