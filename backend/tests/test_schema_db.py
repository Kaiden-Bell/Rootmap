"""Run schema.sql against a real Postgres and check it behaves as intended.

Skipped unless DATABASE_URL is set (see conftest.py).
"""

import datetime as dt
import psycopg
import pytest
from src.db.init_db import init_db, get_connection
from tests.test_schema_file import EXPECTED_TABLES

pytestmark = pytest.mark.db

# Helpers (Inserts data into tables, then returns the row's PK)
def add_host(conn, name="web01", ip="10.0.0.1"):
    return conn.execute(
        "INSERT INTO hosts (host_ip, host_name, operating_system, os_release, subnet_mask)"
        " VALUES (%s, %s, 'Ubuntu', '22.04.3 LTS (Jammy Jellyfish)', 24) RETURNING host_id",
        (ip, name),
    ).fetchone()["host_id"]

def add_service(conn, host_id, name="nginx"):
    return conn.execute(
        "INSERT INTO services (service_name, service_type, host_id)"
        " VALUES (%s, 'web', %s) RETURNING service_id",
        (name, host_id),
    ).fetchone()["service_id"]

def add_scan(conn, host_id):
    return conn.execute(
        "INSERT INTO scans (status, host_id) VALUES ('complete', %s) RETURNING scan_id",
        (host_id,),
    ).fetchone()["scan_id"]

def add_dependency(conn, source_id, target_id):
    return conn.execute(
        "INSERT INTO dependencies (source_service_id, target_service_id)"
        " VALUES (%s, %s) RETURNING dependency_id",
        (source_id, target_id),
    ).fetchone()["dependency_id"]

def add_script(conn, name="ports.sh"):
    return conn.execute(
        "INSERT INTO scripts (script_name, script_path, script_version, script_type)"
        " VALUES (%s, '/opt/scripts/x', 'ubuntu-24.04', 'ports') RETURNING script_id",
        (name,),
    ).fetchone()["script_id"]

def count(conn, table):
    return conn.execute(f"SELECT count(*) AS n FROM {table}").fetchone()["n"]

# Schema tests (Checks schema.sql created the right tables)
def test_all_tables_created(db):
    rows = db.execute(
        "SELECT table_name FROM information_schema.tables"
        " WHERE table_schema = current_schema()"
    ).fetchall()
    assert {r["table_name"] for r in rows} == EXPECTED_TABLES

def test_init_db_can_run_twice(db):
    init_db()
    assert count(db, "hosts") == 0

# Assess behavior of schema.sql (inserts, defaults, constraints, etc.)
def test_rows_come_back_as_dicts(db):
    add_host(db, name="web01")
    row = db.execute("SELECT host_name FROM hosts").fetchone()
    assert row == {"host_name": "web01"}

def test_host_defaults(db):
    host_id = add_host(db)
    host = db.execute("SELECT * FROM hosts WHERE host_id = %s", (host_id,)).fetchone()
    assert host["is_active"] is True
    assert host["ssh_port"] == 22
    assert host["collection_interval"] == 300

def test_host_stores_system_collector_fields(db):
    host_id = add_host(db, name="hatchery", ip="192.168.220.76")
    host = db.execute("SELECT * FROM hosts WHERE host_id = %s", (host_id,)).fetchone()
    assert host["host_name"] == "hatchery"
    assert host["host_ip"] == "192.168.220.76"
    assert host["operating_system"] == "Ubuntu"
    assert host["os_release"] == "22.04.3 LTS (Jammy Jellyfish)"
    assert host["subnet_mask"] == 24

def test_subnet_mask_is_optional_but_must_be_a_valid_prefix_length(db):
    db.execute(
        "INSERT INTO hosts (host_ip, host_name, operating_system, os_release)"
        " VALUES ('10.0.0.9', 'nomask', 'Ubuntu', '22.04')"
    )
    assert db.execute("SELECT subnet_mask FROM hosts").fetchone() == {"subnet_mask": None}
    with pytest.raises(psycopg.errors.CheckViolation):
        db.execute(
            "INSERT INTO hosts (host_ip, host_name, operating_system, os_release, subnet_mask)"
            " VALUES ('10.0.0.10', 'bad', 'Ubuntu', '22.04', 200)"
        )

def test_ids_auto_increment(db):
    first = add_host(db, "a", "10.0.0.1")
    second = add_host(db, "b", "10.0.0.2")
    assert second == first + 1

def test_timestamps_default_to_now_and_are_timezone_aware(db):
    add_script(db)
    row = db.execute("SELECT created_at, updated_at FROM scripts").fetchone()
    now = dt.datetime.now(dt.timezone.utc)
    assert abs(now - row["created_at"]) < dt.timedelta(minutes=1)
    assert row["updated_at"].tzinfo is not None

def test_user_must_change_pw_defaults_true(db):
    db.execute("INSERT INTO roles (role_name, permissions) VALUES ('admin', '*')")
    db.execute(
        "INSERT INTO users (username, password_hash, role_name)"
        " VALUES ('kaiden', 'hash', 'admin')"
    )
    assert db.execute("SELECT must_change_pw FROM users").fetchone()["must_change_pw"] is True

def test_optional_columns_accept_null(db):
    host_id = add_host(db)
    add_service(db, host_id)
    row = db.execute("SELECT config_path, service_port FROM services").fetchone()
    assert row == {"config_path": None, "service_port": None}

def test_required_columns_reject_null(db):
    with pytest.raises(psycopg.errors.NotNullViolation):
        db.execute(
            "INSERT INTO hosts (host_ip, operating_system, os_release)"
            " VALUES ('1.1.1.1', 'Ubuntu', '22.04')"
        )

def test_username_must_be_unique(db):
    db.execute("INSERT INTO roles (role_name, permissions) VALUES ('admin', '*')")
    insert = "INSERT INTO users (username, password_hash, role_name) VALUES ('bob', 'h', 'admin')"
    db.execute(insert)
    with pytest.raises(psycopg.errors.UniqueViolation):
        db.execute(insert)

def test_token_hash_must_be_unique(db):
    host_id = add_host(db)
    insert = "INSERT INTO host_tokens (host_id, token_hash) VALUES (%s, 'abc')"
    db.execute(insert, (host_id,))
    with pytest.raises(psycopg.errors.UniqueViolation):
        db.execute(insert, (host_id,))

def test_service_requires_existing_host(db):
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        add_service(db, host_id=9999)

def test_user_requires_existing_role(db):
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        db.execute(
            "INSERT INTO users (username, password_hash, role_name)"
            " VALUES ('x', 'h', 'nonexistent')"
        )

def test_deleting_host_removes_everything_under_it(db):
    host_id = add_host(db)
    svc_a = add_service(db, host_id, "nginx")
    svc_b = add_service(db, host_id, "postgres")
    scan_id = add_scan(db, host_id)
    dep_id = add_dependency(db, svc_a, svc_b)
    db.execute(
        "INSERT INTO evidence (dependency_id, scan_id, source_type) VALUES (%s, %s, 'config')",
        (dep_id, scan_id),
    )
    script_id = add_script(db)
    db.execute(
        "INSERT INTO scan_scripts (scan_id, script_id, execution_status)"
        " VALUES (%s, %s, 'ok')",
        (scan_id, script_id),
    )
    db.execute("INSERT INTO host_tokens (host_id, token_hash) VALUES (%s, 'h')", (host_id,))

    db.execute("DELETE FROM hosts WHERE host_id = %s", (host_id,))

    for table in ("services", "scans", "dependencies", "evidence", "scan_scripts", "host_tokens"):
        assert count(db, table) == 0, f"{table} not cleaned up"
    assert count(db, "scripts") == 1

def test_deleting_one_service_removes_only_its_dependencies(db):
    host_id = add_host(db)
    a, b, c = (add_service(db, host_id, n) for n in "abc")
    add_dependency(db, a, b)
    add_dependency(db, b, c)
    add_dependency(db, a, c)

    db.execute("DELETE FROM services WHERE service_id = %s", (b,))

    remaining = db.execute(
        "SELECT source_service_id, target_service_id FROM dependencies"
    ).fetchall()
    assert remaining == [{"source_service_id": a, "target_service_id": c}]

def test_cannot_delete_script_that_a_scan_used(db):
    """scan_scripts.script_id has no ON DELETE CASCADE, to protect scan history."""
    host_id = add_host(db)
    scan_id = add_scan(db, host_id)
    script_id = add_script(db)
    db.execute(
        "INSERT INTO scan_scripts (scan_id, script_id, execution_status) VALUES (%s, %s, 'ok')",
        (scan_id, script_id),
    )
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        db.execute("DELETE FROM scripts WHERE script_id = %s", (script_id,))

# Test connection context behavior (commits on success, rolls back on error)
def test_with_block_rolls_back_on_error(db):

    with pytest.raises(RuntimeError):
        with get_connection() as conn:
            add_host(conn)
            raise RuntimeError("boom")

    assert count(db, "hosts") == 0

def test_with_block_commits_on_success(db):
    
    with get_connection() as conn:
        add_host(conn)

    assert count(db, "hosts") == 1
