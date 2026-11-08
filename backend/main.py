import hashlib
import hmac
import secrets
from contextlib import asynccontextmanager
from typing import Annotated
import psycopg
from fastapi import Depends, FastAPI, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from src.auth import get_current_client
from src.db import get_connection
from src.db.init_db import init_db
from src.models.models import ClientIdentity, ReportCreated, SystemReport

# Set the number of password hashes
PASSWORD_HASH_ROUNDS = 100_000

# Hash password
def hash_password(password: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes.fromhex(salt), PASSWORD_HASH_ROUNDS
    )
    return f"{salt}${digest.hex()}"

# Check password against hashed password
def password_matches(password: str, stored_hash: str) -> bool:
    salt, expected_digest = stored_hash.split("$", maxsplit=1)
    actual_hash = hash_password(password, salt).split("$", maxsplit=1)[1]
    return hmac.compare_digest(actual_hash, expected_digest)

# Connect to PostgreSQL
def connect_to_database() -> psycopg.Connection:
    return get_connection()

# Create tables with initial admin account if missing
def initialize_database() -> None:
    init_db()

    with connect_to_database() as connection:
        connection.execute(
            """
            INSERT INTO roles (role_name, permissions)
            VALUES ('admin', '*')
            ON CONFLICT (role_name) DO NOTHING
            """
        )
        connection.execute(
            """
            INSERT INTO users (username, password_hash, role_name, must_change_pw)
            VALUES (%s, %s, 'admin', TRUE)
            ON CONFLICT (username) DO NOTHING
            """,
            ("Admin", hash_password("Password")),
        )

# Set up the database when API starts up
@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
    yield

# Create the API app
app = FastAPI(title="RootMap Dashboard API", lifespan=lifespan)

# Define the login request fields
class LoginRequest(BaseModel):
    username: Annotated[str, Field(min_length=1)]
    password: Annotated[str, Field(min_length=1)]

# Define the password-change request fields
class PasswordChangeRequest(BaseModel):
    username: Annotated[str, Field(min_length=1)]
    current_password: Annotated[str, Field(min_length=1)]
    new_password: Annotated[str, Field(min_length=8)]

# Define the host fields
class HostInput(BaseModel):
    hostname: Annotated[str, Field(min_length=1)]
    ip: Annotated[str, Field(min_length=1)]
    os: Annotated[str, Field(min_length=1)]

    # Reject fields containing only spaces.
    @field_validator("hostname", "ip", "os")
    @classmethod
    def values_must_not_be_only_whitespace(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError("This field cannot be blank.")
        return value

# Check if API is running
@app.get("/")
async def read_root() -> dict[str, str]:
    return {"message": "RootMap Dashboard API"}

# Check if password needs to be changed
@app.post("/api/login")
async def login(request: LoginRequest) -> dict[str, str | bool]:

    with connect_to_database() as connection:
        user = connection.execute(
            "SELECT password_hash, must_change_pw AS must_change_password "
            "FROM users WHERE username = %s",
            (request.username,),
        ).fetchone()

    if user is None or not password_matches(request.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Username or password is incorrect.",
        )
    return {
        "username": request.username,
        "must_change_password": bool(user["must_change_password"]),
    }

# Change account password
@app.post("/api/change-password")
async def change_password(request: PasswordChangeRequest) -> dict[str, str]:

    with connect_to_database() as connection:
        user = connection.execute(
            "SELECT password_hash FROM users WHERE username = %s",
            (request.username,),
        ).fetchone()

        if user is None or not password_matches(
            request.current_password, user["password_hash"]
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Current password is incorrect.",
            )

        connection.execute(
            """
            UPDATE users
            SET password_hash = %s, must_change_pw = FALSE
            WHERE username = %s
            """,
            (hash_password(request.new_password), request.username),
        )
    return {"message": "Password changed."}

# Return saved hosts
@app.get("/api/hosts")
async def list_hosts() -> list[dict[str, int | str]]:

    with connect_to_database() as connection:
        rows = connection.execute(
            "SELECT host_id AS id, host_name AS hostname, host_ip AS ip, "
            "operating_system AS os FROM hosts ORDER BY host_id DESC"
        ).fetchall()
    return [dict(row) for row in rows]

# Receive a collector report from an authenticated host.
# The host is taken from the token only, so a report can't name another host.
@app.post("/reports", status_code=status.HTTP_201_CREATED, response_model=ReportCreated)
def create_report(report: SystemReport, client: ClientIdentity = Depends(get_current_client),
) -> ReportCreated:
    with connect_to_database() as connection:
        connection.execute(
            """
            UPDATE hosts
            SET operating_system = %s, os_release = %s, subnet_mask = %s
            WHERE host_id = %s
            """,
            (
                report.operating_system,
                report.os_release,
                report.subnet_mask,
                client.host_id,
            ),
        )
        row = connection.execute(
            "INSERT INTO scans (status, host_id) VALUES ('completed', %s) RETURNING scan_id",
            (client.host_id,),
        ).fetchone()
    return ReportCreated(scan_id=row["scan_id"])

# Save host and return host
@app.post("/api/hosts", status_code=status.HTTP_201_CREATED)
async def create_host(host: HostInput) -> dict[str, int | str]:
    with connect_to_database() as connection:
        row = connection.execute(
            """
            INSERT INTO hosts (host_name, host_ip, operating_system)
            VALUES (%s, %s, %s)
            RETURNING host_id AS id, host_name AS hostname, host_ip AS ip,
                      operating_system AS os
            """,
            (host.hostname, host.ip, host.os),
        ).fetchone()
    return dict(row)
