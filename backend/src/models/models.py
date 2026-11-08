"""Pydantic request/response contracts for the RootMap backend.

The report model mirrors the JSON written by ``host_scripts/system_collector.py``
so the collector can stay unchanged; aliases map its display-style keys to
snake_case Python attributes.
"""

import hashlib
from ipaddress import IPv4Address
from typing import Annotated
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    computed_field,
)

CidrPrefix = Annotated[int, Field(ge=0, le=32)]

# Reports
class SystemReport(BaseModel):
    """Body of ``POST /reports``: the collector's ``system_info.json``.

    Accepts the collector's original keys (``"Operating System"`` ...) as well
    as the snake_case attribute names, and serializes back to the original keys
    so the stored JSON stays identical to what the collector produced.
    """
    model_config = ConfigDict(
        populate_by_name=True,
        serialize_by_alias=True,
        extra="forbid",
        str_strip_whitespace=True,
    )
    operating_system: str = Field(alias="Operating System")
    os_release: str = Field(alias="OS Release")
    hostname: Annotated[str, StringConstraints(min_length=1, max_length=253)] = Field(
        alias="Hostname"
    )
    ip_address: IPv4Address = Field(alias="IP Address")
    subnet_mask: CidrPrefix = Field(
        alias="Subnet Mask",
        description="CIDR prefix length (e.g. 24).",
    )

class ReportCreated(BaseModel):
    """Response of ``POST /reports`` (``201``). The report is recorded as a scan row."""
    scan_id: int

# Scripts
class ScriptResponse(BaseModel):
    """Response of ``GET /scripts/{script_id}``.

    ``sha256`` is derived from ``content`` so the two can never disagree; the
    client loader recomputes it over the received bytes before executing.
    """
    script_id: str
    content: str

    @computed_field
    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.content.encode("utf-8")).hexdigest()

# Auth
class ClientIdentity(BaseModel):
    """An authenticated client and what it is permitted to do (never holds the token)."""
    model_config = ConfigDict(frozen=True)
    client_id: str
    host_id: int
    allowed_scripts: frozenset[str] = frozenset()
    can_read_reports: bool = False

# Health check
class HealthResponse(BaseModel):
    """Response of unauthenticated ``GET /health``."""
    status: str
    database: bool

# Response error
class ErrorResponse(BaseModel):
    """Shape of FastAPI ``HTTPException`` bodies, for OpenAPI ``responses=``."""
    detail: str
