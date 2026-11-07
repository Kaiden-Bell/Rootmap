"""Token Manager (src/auth).

Pure helpers and the no-credentials paths run without a database. Everything
that looks a token up in `host_tokens` uses the `db` fixture (real Postgres via
TEST_DATABASE_URL, skipped otherwise).
"""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from src.auth import (
    DEFAULT_ALLOWED_SCRIPTS,
    authenticate,
    generate_token,
    get_current_client,
    hash_token,
    issue_token,
    require_report_read,
    require_script,
    revoke_host_tokens,
    revoke_token,
)
from src.models.models import ClientIdentity

UNAUTHORIZED_BODY = {"detail": "Invalid or missing token."}

def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture
def client():
    """Test FastAPI app w/ auth dependencies, no DB needed for the 401 paths."""
    app = FastAPI()

    @app.get("/me")
    def me(who: ClientIdentity = Depends(get_current_client)):
        return {"client_id": who.client_id}

    @app.get("/scripts/{script_id}")
    def script(script_id: str, who: ClientIdentity = Depends(require_script)):
        return {"script_id": script_id}

    @app.get("/reports")
    def reports(who: ClientIdentity = Depends(require_report_read)):
        return {"ok": True}

    return TestClient(app)


def add_host(conn, *, active: bool = True) -> int:
    host_id = conn.execute(
        """
        INSERT INTO hosts (host_name, host_ip, is_active)
        VALUES ('web01', '10.0.0.5', %s) RETURNING host_id
        """,
        (active,),
    ).fetchone()["host_id"]
    conn.commit()  # get_current_client uses its own connection
    return host_id

# helpers (no DB)
def test_generate_token_is_unique_and_long():
    tokens = {generate_token() for _ in range(50)}
    assert len(tokens) == 50
    assert all(len(t) >= 43 for t in tokens)  # 32 bytes, urlsafe base64

def test_hash_token_is_deterministic_and_not_the_token():
    token = generate_token()
    assert hash_token(token) == hash_token(token)
    assert hash_token(token) != token
    assert len(hash_token(token)) == 64

def test_default_grant_is_system_collector_only():
    assert DEFAULT_ALLOWED_SCRIPTS == frozenset({"system_collector"})


# 401 tests without credentials (no DB touched)

@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"Authorization": "Basic dXNlcjpwYXNz"},
        {"Authorization": "Bearer "},
        {"Authorization": "Bearer"},
    ],
    ids=["no-header", "wrong-scheme", "empty-bearer", "scheme-only"],
)
def test_missing_or_malformed_credentials_return_401(client, headers):
    response = client.get("/me", headers=headers)

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json() == UNAUTHORIZED_BODY

def test_unauthenticated_request_never_opens_a_db_connection(client, monkeypatch):
    def boom():
        raise AssertionError("DB opened without credentials")

    monkeypatch.setattr("src.auth.auth.get_connection", boom)

    assert client.get("/me").status_code == 401
    assert client.get("/scripts/system_collector").status_code == 401


# issue / authenticate (DB)

@pytest.mark.db
def test_issue_token_stores_only_the_hash(db):
    host_id = add_host(db)

    token = issue_token(db, host_id)

    stored = [r["token_hash"] for r in db.execute("SELECT token_hash FROM host_tokens")]
    assert stored == [hash_token(token)]
    assert token not in stored

@pytest.mark.db
def test_authenticate_valid_token_returns_identity(db):
    host_id = add_host(db)
    token = issue_token(db, host_id)

    identity = authenticate(db, token)

    assert identity == ClientIdentity(
        client_id=f"host:{host_id}",
        allowed_scripts=DEFAULT_ALLOWED_SCRIPTS,
        can_read_reports=False,
    )

@pytest.mark.db
def test_authenticate_unknown_token_returns_none(db):
    add_host(db)
    assert authenticate(db, generate_token()) is None

@pytest.mark.db
def test_authenticate_is_not_fooled_by_the_stored_hash(db):
    """Presenting the hash itself must not authenticate."""
    host_id = add_host(db)
    token = issue_token(db, host_id)

    assert authenticate(db, hash_token(token)) is None

@pytest.mark.db
def test_expired_token_is_rejected(db):
    host_id = add_host(db)
    past = datetime.now(timezone.utc) - timedelta(minutes=1)
    token = issue_token(db, host_id, expires_at=past)

    assert authenticate(db, token) is None

@pytest.mark.db
def test_unexpired_token_is_accepted(db):
    host_id = add_host(db)
    future = datetime.now(timezone.utc) + timedelta(hours=1)
    token = issue_token(db, host_id, expires_at=future)

    assert authenticate(db, token) is not None

@pytest.mark.db
def test_revoke_token_only_affects_that_token(db):
    host_id = add_host(db)
    keep = issue_token(db, host_id)
    drop = issue_token(db, host_id)
    token_id = db.execute(
        "SELECT token_id FROM host_tokens WHERE token_hash = %s", (hash_token(drop),)
    ).fetchone()["token_id"]

    revoke_token(db, token_id)

    assert authenticate(db, drop) is None
    assert authenticate(db, keep) is not None

@pytest.mark.db
def test_revoke_host_tokens_revokes_all_of_a_hosts_tokens(db):
    host_id = add_host(db)
    other_host = add_host(db)
    a, b = issue_token(db, host_id), issue_token(db, host_id)
    other = issue_token(db, other_host)

    revoke_host_tokens(db, host_id)

    assert authenticate(db, a) is None
    assert authenticate(db, b) is None
    assert authenticate(db, other) is not None
    # kept for audit, not deleted
    assert db.execute("SELECT count(*) AS n FROM host_tokens").fetchone()["n"] == 3

@pytest.mark.db
def test_token_of_inactive_host_is_rejected(db):
    host_id = add_host(db, active=False)
    token = issue_token(db, host_id)

    assert authenticate(db, token) is None


# w/ FastAPI (DB)
@pytest.mark.db
def test_valid_token_returns_200_with_client_id(db, client):
    host_id = add_host(db)
    token = issue_token(db, host_id)
    db.commit()

    response = client.get("/me", headers=bearer(token))

    assert response.status_code == 200
    assert response.json() == {"client_id": f"host:{host_id}"}

@pytest.mark.db
def test_bad_token_returns_401_identical_to_missing(db, client):
    add_host(db)

    response = client.get("/me", headers=bearer(generate_token()))

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json() == UNAUTHORIZED_BODY

@pytest.mark.db
def test_revoked_expired_and_inactive_are_indistinguishable_401s(db, client):
    host_id = add_host(db)
    inactive_host = add_host(db, active=False)
    revoked = issue_token(db, host_id)
    expired = issue_token(
        db, host_id, expires_at=datetime.now(timezone.utc) - timedelta(minutes=1)
    )
    inactive = issue_token(db, inactive_host)
    revoked_id = db.execute(
        "SELECT token_id FROM host_tokens WHERE token_hash = %s", (hash_token(revoked),)
    ).fetchone()["token_id"]
    revoke_token(db, revoked_id)
    db.commit()

    responses = [client.get("/me", headers=bearer(t)) for t in (revoked, expired, inactive)]

    assert [r.status_code for r in responses] == [401, 401, 401]
    assert {r.text for r in responses} == {client.get("/me").text}

@pytest.mark.db
def test_token_in_query_string_is_ignored(db, client):
    host_id = add_host(db)
    token = issue_token(db, host_id)
    db.commit()

    response = client.get("/me", params={"token": token})

    assert response.status_code == 401

@pytest.mark.db
def test_allowed_script_returns_200(db, client):
    token = issue_token(db, add_host(db))
    db.commit()

    response = client.get("/scripts/system_collector", headers=bearer(token))

    assert response.status_code == 200
    assert response.json() == {"script_id": "system_collector"}

@pytest.mark.db
def test_valid_token_for_unlisted_script_returns_403(db, client):
    token = issue_token(db, add_host(db))
    db.commit()

    response = client.get("/scripts/something_else", headers=bearer(token))

    assert response.status_code == 403

@pytest.mark.db
def test_traversal_looking_script_id_is_not_authorized(db, client):
    """A single-segment id that merely looks like traversal is just an unlisted id."""
    token = issue_token(db, add_host(db))
    db.commit()

    response = client.get("/scripts/..%5c..%5cetc%5cpasswd", headers=bearer(token))

    assert response.status_code == 403

@pytest.mark.db
def test_encoded_slash_traversal_never_reaches_the_handler(db, client):
    """%2f is decoded before routing, so this matches no `/scripts/{id}` route."""
    token = issue_token(db, add_host(db))
    db.commit()

    response = client.get("/scripts/..%2f..%2fetc%2fpasswd", headers=bearer(token))

    assert response.status_code == 404

@pytest.mark.db
def test_invalid_token_on_script_route_is_401_not_403(db, client):
    add_host(db)

    response = client.get("/scripts/something_else", headers=bearer("nope"))

    assert response.status_code == 401

@pytest.mark.db
def test_report_read_is_403_for_default_host_token(db, client):
    token = issue_token(db, add_host(db))
    db.commit()

    response = client.get("/reports", headers=bearer(token))

    assert response.status_code == 403

def test_report_read_allowed_when_identity_has_permission(client):
    """Permission logic in isolation: override the identity, no DB needed."""
    client.app.dependency_overrides[get_current_client] = lambda: ClientIdentity(
        client_id="host:1", can_read_reports=True
    )

    assert client.get("/reports").status_code == 200