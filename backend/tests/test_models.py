import hashlib
import json
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from src.models.models import (
    ClientIdentity,
    ReportRecord,
    ScriptResponse,
    SystemReport,
)

# Exactly what host_scripts/system_collector.py writes (see design.md).
COLLECTOR_OUTPUT = {
    "Operating System": "Ubuntu",
    "OS Release": "22.04.3 LTS (Jammy Jellyfish)",
    "Hostname": "hatchery",
    "IP Address": "192.168.220.76",
    "Subnet Mask": "24",
}


def test_accepts_collector_output_with_original_keys():
    r = SystemReport.model_validate(COLLECTOR_OUTPUT)
    assert r.operating_system == "Ubuntu"
    assert r.hostname == "hatchery"
    assert str(r.ip_address) == "192.168.220.76"
    assert r.subnet_mask == 24  # "24" string coerced to int prefix length


def test_accepts_snake_case_names():
    r = SystemReport(
        operating_system="Debian",
        os_release="12",
        hostname="h",
        ip_address="10.0.0.1",
        subnet_mask=8,
    )
    assert r.subnet_mask == 8


def test_roundtrip_serializes_to_original_keys():
    r = SystemReport.model_validate(COLLECTOR_OUTPUT)
    assert r.model_dump(mode="json") == COLLECTOR_OUTPUT | {"Subnet Mask": 24}
    # JSON-safe for the JSONB column, and re-validatable.
    assert SystemReport.model_validate(json.loads(r.model_dump_json())) == r


@pytest.mark.parametrize("missing", list(COLLECTOR_OUTPUT))
def test_missing_field_rejected(missing):
    body = {k: v for k, v in COLLECTOR_OUTPUT.items() if k != missing}
    with pytest.raises(ValidationError):
        SystemReport.model_validate(body)


def test_unknown_field_rejected():
    with pytest.raises(ValidationError):
        SystemReport.model_validate(COLLECTOR_OUTPUT | {"Extra": "x"})


@pytest.mark.parametrize(
    "override",
    [
        {"IP Address": "XXX.XXX.XXX.XXX"},  # collector's failure placeholder
        {"IP Address": "999.1.1.1"},
        {"Subnet Mask": ""},  # collector leaves "" if the `ip` lookup fails
        {"Subnet Mask": "255.255.255.0"},  # dotted mask, not a prefix length
        {"Subnet Mask": "33"},
        {"Subnet Mask": "-1"},
        {"Hostname": ""},
        {"Hostname": "   "},
    ],
)
def test_invalid_values_rejected(override):
    with pytest.raises(ValidationError):
        SystemReport.model_validate(COLLECTOR_OUTPUT | override)


def test_script_response_sha256_matches_content():
    content = "print('hi')\n"
    s = ScriptResponse(script_id="system_collector", content=content)
    expected = hashlib.sha256(content.encode()).hexdigest()
    assert s.sha256 == expected
    assert s.model_dump()["sha256"] == expected  # included in the response body


def test_report_record_nests_report():
    rec = ReportRecord(
        report_id=uuid4(),
        collected_at=datetime.now(timezone.utc),
        report=SystemReport.model_validate(COLLECTOR_OUTPUT),
    )
    assert rec.model_dump(mode="json")["report"]["Hostname"] == "hatchery"


def test_client_identity_is_immutable_and_defaults_deny():
    c = ClientIdentity(client_id="c1")
    assert c.allowed_scripts == frozenset()
    assert c.can_read_reports is False
    with pytest.raises(ValidationError):
        c.client_id = "other"
