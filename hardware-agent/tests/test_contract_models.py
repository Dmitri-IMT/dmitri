from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import get_args
from uuid import uuid4

import yaml
from agent.normalize.contracts import (
    DevicePayload,
    FindingPayload,
    PortPayload,
    ScanPayload,
)

OPENAPI_PATH = (
    Path(__file__).resolve().parents[2]
    / "contracts"
    / "openapi"
    / "openapi.yaml"
)


def test_scan_payload_accepts_optional_mac_and_enriched_findings() -> None:
    payload = ScanPayload(
        scan_id=uuid4(),
        timestamp=datetime.now(timezone.utc),
        subnet="192.168.0.0/24",
        scan_mode="quick",
        devices=[
            DevicePayload(
                ip="192.168.0.20",
                mac=None,
                hostname="192.168.0.20",
                vendor="unknown",
                ports=[
                    PortPayload(
                        port=80,
                        protocol="tcp",
                        state="open",
                        service="http",
                        version="nginx 1.24.0",
                    )
                ],
            )
        ],
        findings=[
            FindingPayload(
                ip="192.168.0.20",
                port=80,
                protocol="tcp",
                service="http",
                source="nmap_vulners",
                source_script="vulners",
                cve_id="CVE-2024-12345",
                cvss_score=9.1,
                severity="critical",
                title="Known CVE detected via vulners: CVE-2024-12345",
                description="A known CVE was correlated to the detected HTTP service.",
                recommendation="Patch the vulnerable software.",
                evidence="vulners correlated the service to CVE-2024-12345.",
                references=["https://vulners.com/cve/CVE-2024-12345"],
            )
        ],
        metadata={"elapsed_seconds": 12.5},
    )

    assert payload.devices[0].mac is None
    assert payload.findings[0].cve_id == "CVE-2024-12345"


def test_scan_payload_accepts_extensive_nspi_and_max() -> None:
    for mode in ("extensive", "nspi", "max"):
        payload = ScanPayload(
            scan_id=uuid4(),
            timestamp=datetime.now(timezone.utc),
            subnet="192.168.0.0/24",
            scan_mode=mode,
            devices=[],
            findings=[],
        )
        assert payload.scan_mode == mode


def test_schema_enum_matches_pydantic_literal() -> None:
    spec = yaml.safe_load(OPENAPI_PATH.read_text(encoding="utf-8"))
    enum = set(spec["components"]["schemas"]["ScanMode"]["enum"])
    literal = set(get_args(ScanPayload.model_fields["scan_mode"].annotation))
    assert enum == literal
    assert {"extensive", "nspi", "max"} <= enum
    assert "full" not in enum


def test_openapi_ingest_example_uses_a_real_scan_mode() -> None:
    spec = yaml.safe_load(OPENAPI_PATH.read_text(encoding="utf-8"))
    enum = set(spec["components"]["schemas"]["ScanMode"]["enum"])
    example = spec["components"]["examples"]["ScanIngestRequestExample"]["value"]
    assert example["scan_mode"] in enum


def test_health_response_example_uses_backend_release_version() -> None:
    spec = yaml.safe_load(OPENAPI_PATH.read_text(encoding="utf-8"))
    health_ok = spec["paths"]["/api/v1/health"]["get"]["responses"]["200"]
    example = health_ok["content"]["application/json"]["examples"]["ok"]["value"]
    assert example == {"status": "ok", "version": "0.1.0"}

    schema = spec["components"]["schemas"]["HealthResponse"]
    assert set(schema["properties"]) == {"status", "version"}
    assert schema["additionalProperties"] is False


def test_health_503_references_database_unavailable_error() -> None:
    spec = yaml.safe_load(OPENAPI_PATH.read_text(encoding="utf-8"))
    health_responses = spec["paths"]["/api/v1/health"]["get"]["responses"]
    assert health_responses["503"] == {
        "$ref": "#/components/responses/DatabaseUnavailableError"
    }

    component = spec["components"]["responses"]["DatabaseUnavailableError"]
    schema = component["content"]["application/json"]["schema"]
    assert schema["allOf"][0] == {"$ref": "#/components/schemas/ErrorResponse"}
    pinned_code = schema["allOf"][1]["properties"]["error"]["properties"]["code"]
    assert pinned_code["const"] == "database_unreachable"

    example = component["content"]["application/json"]["examples"][
        "databaseUnavailable"
    ]["value"]
    assert example == {
        "error": {
            "code": "database_unreachable",
            "message": "Database connection failed.",
            "details": {},
        }
    }
