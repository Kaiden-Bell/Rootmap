"""Sanity checks on schema.sql that need no database."""

import re

from src.db.init_db import SCHEMA_FILE

EXPECTED_TABLES = {
    "hosts",
    "scripts",
    "scans",
    "services",
    "dependencies",
    "evidence",
    "scan_scripts",
    "host_tokens",
    "roles",
    "users",
}

SQL = SCHEMA_FILE.read_text()

def _table_blocks() -> dict[str, str]:
    """Map table name -> the text of its CREATE TABLE statement, in file order."""
    pattern = re.compile(
        r"CREATE TABLE IF NOT EXISTS\s+(\w+)\s*\((.*?)\n\);", re.DOTALL
    )
    return {m.group(1): m.group(2) for m in pattern.finditer(SQL)}

def test_schema_file_exists():
    assert SCHEMA_FILE.is_file()

def test_defines_exactly_the_expected_tables():
    assert set(_table_blocks()) == EXPECTED_TABLES

def test_is_idempotent_by_construction():
    """Every CREATE must be IF NOT EXISTS so init_db can be re-run safely."""
    creates = re.findall(r"^\s*CREATE\s+(?:UNIQUE\s+)?(TABLE|INDEX)\s+(.*)$", SQL, re.M)
    assert creates, "no CREATE statements found"
    for kind, rest in creates:
        assert rest.startswith("IF NOT EXISTS"), f"{kind} {rest!r} is not idempotent"

def test_foreign_keys_point_at_tables_defined_earlier():
    """Postgres rejects a REFERENCES to a table that doesn't exist yet."""
    seen: set[str] = set()
    for name, body in _table_blocks().items():
        for target in re.findall(r"REFERENCES\s+(\w+)", body):
            assert target in seen, f"{name} references {target} before it is created"
        seen.add(name)

def test_every_foreign_key_column_has_an_index():
    """Postgres doesn't index FK columns for you; deletes/joins get slow without."""
    indexed = set(re.findall(r"CREATE INDEX IF NOT EXISTS \w+\s+ON (\w+) \((\w+)\)", SQL))
    for table, body in _table_blocks().items():
        for column in re.findall(r"^\s*(\w+)\s+[\w()]+\s+(?:NOT NULL\s+)?REFERENCES", body, re.M):
            assert (table, column) in indexed, f"{table}.{column} has no index"
