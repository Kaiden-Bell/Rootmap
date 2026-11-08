"""POST /reports: authenticated report ingestion.

All tests need a real Postgres (the `db` fixture, via TEST_DATABASE_URL).
"""

import pytest
from fastapi.testclient import TestClient

from main import app
from src.auth import issue_token, revoke_host_tokens

COLLECTOR_REPORT = {
    "Operating System": "Ubuntu",
    "OS Release": "22.04.3 LTS (Jammy Jellyfish)",
    "Hostname": "hatchery",
    "IP Address": "192.168.220.76",
    "Subnet Mask": "24",
}

def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}

def add_host(conn, name="web01", ip="10.0.0.5") -> int:
    host_id = conn.execute(
        """
        INSERT INTO hosts (host_name, host_ip, collection_interval)
        VALUES (%s, %s, 300) RETURNING host_id
        """,
        (name, ip),
    ).fetchone()["host_id"]
    conn.commit()
    return host_id

@pytest.fixture
def api(db):
    return TestClient(app)

def host_row(conn, host_id):
    return conn.execute("SELECT * FROM hosts WHERE host_id = %s", (host_id,)).fetchone()

def scan_count(conn, host_id) -> int:
    return conn.execute(
        "SELECT count(*) AS n FROM scans WHERE host_id = %s", (host_id,)
    ).fetchone()["n"]

# auth
@pytest.mark.db
def test_no_token_is_401(api, db):
    add_host(db)

    response = api.post("/reports", json=COLLECTOR_REPORT)

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"

@pytest.mark.db
def test_unknown_token_is_401(api, db):
    add_host(db)

    response = api.post("/reports", json=COLLECTOR_REPORT, headers=bearer("nope"))

    assert response.status_code == 401

@pytest.mark.db
def test_revoked_token_is_401(api, db):
    host_id = add_host(db)
    token = issue_token(db, host_id)
    revoke_host_tokens(db, host_id)
    db.commit()

    response = api.post("/reports", json=COLLECTOR_REPORT, headers=bearer(token))

    assert response.status_code == 401


# valid report ingestion
@pytest.mark.db
def test_valid_report_returns_201_with_scan_id(api, db):
    host_id = add_host(db)
    token = issue_token(db, host_id)
    db.commit()

    response = api.post("/reports", json=COLLECTOR_REPORT, headers=bearer(token))

    assert response.status_code == 201
    body = response.json()
    assert set(body) == {"scan_id"}
    assert isinstance(body["scan_id"], int)

@pytest.mark.db
def test_valid_report_updates_os_fields_only(api, db):
    host_id = add_host(db, name="web01", ip="10.0.0.5")
    token = issue_token(db, host_id)
    db.commit()

    api.post("/reports", json=COLLECTOR_REPORT, headers=bearer(token))

    row = host_row(db, host_id)
    assert row["operating_system"] == "Ubuntu"
    assert row["os_release"] == "22.04.3 LTS (Jammy Jellyfish)"
    assert row["subnet_mask"] == 24
    assert row["host_name"] == "web01"
    assert row["host_ip"] == "10.0.0.5"

@pytest.mark.db
def test_valid_report_records_a_completed_scan(api, db):
    host_id = add_host(db)
    token = issue_token(db, host_id)
    db.commit()

    response = api.post("/reports", json=COLLECTOR_REPORT, headers=bearer(token))

    scan = db.execute(
        "SELECT scan_id, status, host_id FROM scans WHERE scan_id = %s",
        (response.json()["scan_id"],),
    ).fetchone()
    assert scan["status"] == "completed"
    assert scan["host_id"] == host_id

@pytest.mark.db
def test_each_report_adds_a_scan(api, db):
    host_id = add_host(db)
    token = issue_token(db, host_id)
    db.commit()

    api.post("/reports", json=COLLECTOR_REPORT, headers=bearer(token))
    api.post("/reports", json=COLLECTOR_REPORT, headers=bearer(token))

    assert scan_count(db, host_id) == 2

@pytest.mark.db
def test_token_only_updates_its_own_host(api, db):
    host_a = add_host(db, name="a", ip="10.0.0.1")
    host_b = add_host(db, name="b", ip="10.0.0.2")
    token_a = issue_token(db, host_a)
    db.commit()

    api.post("/reports", json=COLLECTOR_REPORT, headers=bearer(token_a))

    assert host_row(db, host_b)["operating_system"] is None
    assert scan_count(db, host_b) == 0

# invalid report ingestion
@pytest.mark.db
@pytest.mark.parametrize(
    "mutate",
    [
        lambda r: r.pop("Hostname"),
        lambda r: r.update({"Unexpected": "x"}),
        lambda r: r.update({"Subnet Mask": ""}),
        lambda r: r.update({"Subnet Mask": "40"}),
        lambda r: r.update({"IP Address": "XXX.XXX.XXX.XXX"}),
    ],
    ids=["missing-key", "extra-key", "empty-subnet", "subnet-out-of-range", "placeholder-ip"],
)
def test_invalid_report_is_422_and_writes_nothing(api, db, mutate):
    host_id = add_host(db)
    token = issue_token(db, host_id)
    db.commit()
    body = dict(COLLECTOR_REPORT)
    mutate(body)

    response = api.post("/reports", json=body, headers=bearer(token))

    assert response.status_code == 422
    assert host_row(db, host_id)["operating_system"] is None
    assert scan_count(db, host_id) == 0
