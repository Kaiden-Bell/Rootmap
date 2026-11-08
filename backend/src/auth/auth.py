"""Token management and authentication utilities (the "Token Manager").

Clients authenticate with ``Authorization: Bearer <token>``. Tokens are
256-bit random values, only ``sha256(token)`` is stored in ``host_tokens`` 
the plaintext is shown exactly once, when issued.
Lookup is by hash (indexed via the UNIQUE column), not by scanning rows.

Rules enforced here:
  * Missing/invalid/revoked/expired token (or inactive host) -> 401 with
    ``WWW-Authenticate: Bearer`` and one identical body, so the response does
    not reveal which case it was.
  * Authenticated but not permitted -> 403.
  * Tokens are read from the Authorization header only, never the URL.
  * Tokens and the Authorization header are never logged.
"""

import hashlib
import hmac
import secrets
from datetime import datetime

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.db.connection import get_connection
from src.models.models import ClientIdentity

# Currently: every valid host token may fetch this script and nothing else.
# Remove once script registry is built.
DEFAULT_ALLOWED_SCRIPTS = frozenset({"system_collector"})

_bearer = HTTPBearer(auto_error=False)

def generate_token() -> str:
    """Generate a new random token (256 bits, URL-safe)."""
    return secrets.token_urlsafe(32)

def hash_token(token: str) -> str:
    """SHA-256 hex digest of a token; this is what gets stored."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()

def issue_token(connection, host_id: int, expires_at: datetime | None = None) -> str:
    """Create a token for a host, store only its hash, return the plaintext once."""
    token = generate_token()
    connection.execute(
        "INSERT INTO host_tokens (host_id, token_hash, expires_at) VALUES (%s, %s, %s)",
        (host_id, hash_token(token), expires_at),
    )
    return token

def revoke_token(connection, token_id: int) -> None:
    """Revoke a single token (kept in the table for audit)."""
    connection.execute(
        "UPDATE host_tokens SET is_revoked = TRUE WHERE token_id = %s",
        (token_id,),
    )

def revoke_host_tokens(connection, host_id: int) -> None:
    """Revoke every token belonging to a host."""
    connection.execute(
        "UPDATE host_tokens SET is_revoked = TRUE WHERE host_id = %s",
        (host_id,),
    )

def revoke_other_tokens(connection, host_id: int, keep_token: str) -> None:
    """Revoke every token of a host except the one matching ``keep_token``.
    Used by rotation once the new token is confirmed on the host.
    """
    connection.execute(
        "UPDATE host_tokens SET is_revoked = TRUE "
        "WHERE host_id = %s AND token_hash <> %s",
        (host_id, hash_token(keep_token)),
    )

def authenticate(connection, token: str) -> ClientIdentity | None:
    """Return the client identity for a valid token, or None.

    Valid means: hash found, not revoked, not expired, and the host is active.
    """
    presented = hash_token(token)
    row = connection.execute(
        """
        SELECT t.host_id, t.token_hash
        FROM host_tokens t
        JOIN hosts h ON h.host_id = t.host_id
        WHERE t.token_hash = %s
          AND NOT t.is_revoked
          AND (t.expires_at IS NULL OR t.expires_at > now())
          AND h.is_active
        """,
        (presented,),
    ).fetchone()

    if row is None or not hmac.compare_digest(row["token_hash"], presented): return None

    return ClientIdentity(
        client_id=f"host:{row['host_id']}",
        host_id=row["host_id"],
        allowed_scripts=DEFAULT_ALLOWED_SCRIPTS,
        can_read_reports=False,
    )

def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing token.",
        headers={"WWW-Authenticate": "Bearer"},
    )

def get_current_client(credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> ClientIdentity:
    """Authenticate the bearer token or raise 401.
    The DB connection is opened only after a bearer credential is present, so
    a request with no header never touches the database.
    """
    if credentials is None or not credentials.credentials:
        raise _unauthorized()

    with get_connection() as connection:
        client = authenticate(connection, credentials.credentials)

    if client is None:
        raise _unauthorized()
    return client

def require_script(script_id: str, client: ClientIdentity = Depends(get_current_client),
) -> ClientIdentity:
    """Dependency for ``/scripts/{script_id}``: 401 if unauthenticated, 403 if
    this client may not fetch that script. ``script_id`` comes from the path."""
    if script_id not in client.allowed_scripts:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not permitted to access this script.",
        )
    return client

def require_report_read(client: ClientIdentity = Depends(get_current_client),
) -> ClientIdentity:
    """Dependency for ``GET /reports/{id}``: 403 unless the client may read reports."""
    if not client.can_read_reports:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not permitted to read reports.",
        )
    return client