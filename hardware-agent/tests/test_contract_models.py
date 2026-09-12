from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import get_args
from uuid import uuid4

import pytest
import yaml
from agent.normalize.contracts import (
    FindingPayload,
    HostPayload,
    ModbusAddressRangePayload,
    ModbusDeviceIdentificationPayload,
    ModbusTcpServicePayload,
    ModbusUnitPayload,
    OperatingSystemDetection,
    PortPayload,
    ScanPayload,
)
from agent.scanner.models import HostInfo, OperatingSystemInfo
from agent.scanner.stages import build_host_payload
from agent.transport.command_channel import (
    AgentCommand,
    AgentHello,
    AgentStatus,
    AvailableSubnet,
)
from pydantic import ValidationError

CONTRACT_MODELS = (
    ("ScanIngestRequest", ScanPayload),
    ("HostPayload", HostPayload),
    ("OperatingSystemDetection", OperatingSystemDetection),
    ("ModbusTcpServicePayload", ModbusTcpServicePayload),
    ("ModbusUnitPayload", ModbusUnitPayload),
    ("ModbusDeviceIdentificationPayload", ModbusDeviceIdentificationPayload),
    ("PortPayload", PortPayload),
    ("FindingPayload", FindingPayload),
    ("AvailableSubnet", AvailableSubnet),
    ("AgentHelloFrame", AgentHello),
    ("AgentCommandFrame", AgentCommand),
    ("AgentStatusFrame", AgentStatus),
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
        hosts=[
            HostPayload(
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

    assert payload.hosts[0].mac is None
    assert payload.findings[0].cve_id == "CVE-2024-12345"


def test_scan_payload_accepts_modbus_inventory() -> None:
    host = HostPayload(
        ip="192.168.10.30",
        mac=None,
        hostname="plc-lab",
        vendor="Schneider Electric",
        industrial_services=[
            ModbusTcpServicePayload(
                port=502,
                confidence="confirmed",
                evidence_sources=["modbus-discover", "pymodbus"],
                units=[
                    ModbusUnitPayload(
                        unit_id=1,
                        status="responding",
                        device_identification=ModbusDeviceIdentificationPayload(
                            vendor_name="Schneider Electric",
                            product_code="BMX P34",
                            major_minor_revision="2.60",
                        ),
                    )
                ],
            )
        ],
    )

    dumped = host.model_dump(mode="json")

    assert dumped["industrial_services"][0]["protocol"] == "modbus_tcp"
    assert dumped["industrial_services"][0]["units"][0][
        "device_identification"
    ]["product_code"] == "BMX P34"


@pytest.mark.parametrize("accuracy", [0, 100])
def test_operating_system_detection_accepts_accuracy_boundaries(
    accuracy: int,
) -> None:
    detection = OperatingSystemDetection(name="Linux", accuracy=accuracy)

    assert detection.accuracy == accuracy
    assert detection.vendor is None
    assert detection.family is None
    assert detection.generation is None
    assert detection.device_type is None
    assert detection.cpes == []


def test_operating_system_detection_accepts_explicit_null_optional_fields() -> None:
    detection = OperatingSystemDetection.model_validate(
        {
            "name": "Linux",
            "accuracy": 96,
            "vendor": None,
            "family": None,
            "generation": None,
            "device_type": None,
            "cpes": [],
        }
    )

    assert detection.model_dump(mode="json") == {
        "name": "Linux",
        "accuracy": 96,
        "vendor": None,
        "family": None,
        "generation": None,
        "device_type": None,
        "cpes": [],
    }


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("name", ""),
        ("name", None),
        ("accuracy", -1),
        ("accuracy", 101),
        ("accuracy", 96.0),
        ("accuracy", 96.5),
        ("accuracy", "96"),
        ("accuracy", True),
        ("cpes", [""]),
        ("cpes", None),
        ("vendor", 1),
        ("unexpected", True),
    ],
)
def test_operating_system_detection_rejects_invalid_values(field, value) -> None:
    values = {"name": "Linux", "accuracy": 96, "cpes": ["cpe:/o:linux:linux_kernel"]}
    values[field] = value

    with pytest.raises(ValidationError):
        OperatingSystemDetection.model_validate(values)


@pytest.mark.parametrize("missing_field", ["name", "accuracy"])
def test_operating_system_detection_requires_core_fields(missing_field: str) -> None:
    values = {"name": "Linux", "accuracy": 96}
    del values[missing_field]

    with pytest.raises(ValidationError):
        OperatingSystemDetection.model_validate(values)


def test_operating_system_detection_is_exported_from_normalize() -> None:
    from agent.normalize import OperatingSystemDetection as ExportedDetection

    assert ExportedDetection is OperatingSystemDetection


@pytest.mark.parametrize(
    "host_values",
    [
        pytest.param({}, id="omitted"),
        pytest.param({"operating_system": None}, id="explicit-null"),
    ],
)
def test_host_payload_operating_system_defaults_to_none(host_values: dict) -> None:
    host = HostPayload.model_validate(
        {
            "ip": "192.168.0.20",
            "hostname": "host",
            "vendor": "unknown",
            **host_values,
        }
    )

    assert host.operating_system is None


def test_build_host_payload_maps_operating_system_losslessly() -> None:
    host = HostInfo(
        ip="192.168.0.20",
        hostname="controller.local",
        operating_system=OperatingSystemInfo(
            name="Linux 5.4 - 5.10",
            accuracy=96,
            vendor="Linux",
            family="Linux",
            generation="5.X",
            device_type="general purpose",
            cpes=[
                "cpe:/o:linux:linux_kernel:5",
                "cpe:/o:linux:linux_kernel:6",
            ],
        ),
    )

    payload = build_host_payload(host)

    assert payload.operating_system is not None
    assert payload.operating_system.model_dump(mode="json") == {
        "name": "Linux 5.4 - 5.10",
        "accuracy": 96,
        "vendor": "Linux",
        "family": "Linux",
        "generation": "5.X",
        "device_type": "general purpose",
        "cpes": [
            "cpe:/o:linux:linux_kernel:5",
            "cpe:/o:linux:linux_kernel:6",
        ],
    }


def test_build_host_payload_preserves_missing_operating_system() -> None:
    payload = build_host_payload(HostInfo(ip="192.168.0.20", hostname=None))

    assert payload.operating_system is None


def test_agent_operating_system_schema_matches_published_contract() -> None:
    spec = yaml.safe_load(OPENAPI_PATH.read_text(encoding="utf-8"))
    contract_schema = spec["components"]["schemas"]["OperatingSystemDetection"]
    model_schema = OperatingSystemDetection.model_json_schema()

    assert contract_schema["additionalProperties"] is False
    assert model_schema["additionalProperties"] is False
    assert set(contract_schema["required"]) == set(model_schema["required"]) == {
        "name",
        "accuracy",
    }
    assert set(contract_schema["properties"]) == set(model_schema["properties"])

    for schema in (contract_schema, model_schema):
        properties = schema["properties"]
        assert properties["name"]["type"] == "string"
        assert properties["name"]["minLength"] == 1
        assert properties["accuracy"]["type"] == "integer"
        assert properties["accuracy"]["minimum"] == 0
        assert properties["accuracy"]["maximum"] == 100
        assert properties["cpes"]["type"] == "array"
        assert properties["cpes"]["items"]["type"] == "string"
        assert properties["cpes"]["items"]["minLength"] == 1

    for field in ("vendor", "family", "generation", "device_type"):
        contract_types = contract_schema["properties"][field]["type"]
        model_types = {
            candidate["type"]
            for candidate in model_schema["properties"][field]["anyOf"]
        }
        assert set(contract_types) == model_types == {"string", "null"}


def test_published_host_operating_system_is_optional_and_nullable() -> None:
    spec = yaml.safe_load(OPENAPI_PATH.read_text(encoding="utf-8"))
    host_schema = spec["components"]["schemas"]["HostPayload"]
    operating_system = host_schema["properties"]["operating_system"]

    assert "operating_system" not in host_schema["required"]
    assert operating_system["anyOf"] == [
        {"$ref": "#/components/schemas/OperatingSystemDetection"},
        {"type": "null"},
    ]


def test_scan_payload_accepts_extensive_nspi_and_max() -> None:
    for mode in ("extensive", "nspi", "max"):
        payload = ScanPayload(
            scan_id=uuid4(),
            timestamp=datetime.now(timezone.utc),
            subnet="192.168.0.0/24",
            scan_mode=mode,
            hosts=[],
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


def test_openapi_has_no_device_payload_or_devices_received() -> None:
    text = OPENAPI_PATH.read_text(encoding="utf-8")
    assert "DevicePayload" not in text
    assert "devices_received" not in text


def test_host_summary_requires_first_seen_at() -> None:
    spec = yaml.safe_load(OPENAPI_PATH.read_text(encoding="utf-8"))
    schema = spec["components"]["schemas"]["HostSummary"]
    assert "first_seen_at" in schema["required"]
    assert schema["properties"]["first_seen_at"]["format"] == "date-time"


def test_scan_host_view_requires_host_id_and_is_used_by_scan_detail_response() -> (
    None
):
    spec = yaml.safe_load(OPENAPI_PATH.read_text(encoding="utf-8"))
    scan_host_view = spec["components"]["schemas"]["ScanHostView"]
    assert "host_id" in scan_host_view["required"]
    assert scan_host_view["properties"]["host_id"]["format"] == "uuid"

    detail_response = spec["components"]["schemas"]["ScanDetailResponse"]
    assert detail_response["properties"]["hosts"]["items"] == {
        "$ref": "#/components/schemas/ScanHostView"
    }


def test_scan_ingest_example_uses_hosts_not_devices() -> None:
    example_path = (
        Path(__file__).resolve().parents[2]
        / "contracts"
        / "examples"
        / "scan_result.example.json"
    )
    payload = json.loads(example_path.read_text(encoding="utf-8"))
    assert "hosts" in payload
    assert "devices" not in payload
    assert "target_mode" not in payload
    assert "scan_profile" not in payload
    assert "scan_mode" in payload


def test_host_payload_importable_from_contracts_and_normalize() -> None:
    from agent.normalize import HostPayload as NormalizeHostPayload
    from agent.normalize.contracts import HostPayload as ContractsHostPayload

    assert NormalizeHostPayload is ContractsHostPayload


def test_scan_payload_hosts_accepts_host_payload_list() -> None:
    payload = ScanPayload(
        scan_id=uuid4(),
        timestamp=datetime.now(timezone.utc),
        subnet="192.168.0.0/24",
        scan_mode="quick",
        hosts=[HostPayload(ip="192.168.0.20", hostname="host", vendor="unknown")],
        findings=[],
    )
    assert isinstance(payload.hosts[0], HostPayload)


def test_scan_payload_rejects_devices_keyword() -> None:
    payload = ScanPayload(
        scan_id=uuid4(),
        timestamp=datetime.now(timezone.utc),
        subnet="192.168.0.0/24",
        scan_mode="quick",
        devices=[HostPayload(ip="192.168.0.20", hostname="host", vendor="unknown")],
        findings=[],
    )
    assert payload.hosts == []
    assert not hasattr(payload, "devices")


def test_agent_models_emit_no_field_the_contract_forbids() -> None:
    spec = yaml.safe_load(OPENAPI_PATH.read_text(encoding="utf-8"))
    for schema_name, model in CONTRACT_MODELS:
        schema = spec["components"]["schemas"][schema_name]
        assert schema["additionalProperties"] is False
        unknown = set(model.model_fields) - set(schema["properties"])
        assert not unknown, f"{schema_name} would reject {sorted(unknown)}"


def test_agent_models_emit_every_field_the_contract_requires() -> None:
    spec = yaml.safe_load(OPENAPI_PATH.read_text(encoding="utf-8"))
    for schema_name, model in CONTRACT_MODELS:
        schema = spec["components"]["schemas"][schema_name]
        missing = set(schema.get("required", [])) - set(model.model_fields)
        assert not missing, f"{schema_name} requires {sorted(missing)}"


def test_port_payload_preserves_optional_cpes_for_backend_enrichment() -> None:
    spec = yaml.safe_load(OPENAPI_PATH.read_text(encoding="utf-8"))
    schema = spec["components"]["schemas"]["PortPayload"]
    assert "cpes" in schema["properties"]
    assert "cpes" not in schema["required"]
    assert "cpes" in PortPayload.model_fields
    assert PortPayload(
        port=502,
        protocol="tcp",
        state="open",
        service="modbus",
    ).cpes == []


def test_modbus_wire_models_forbid_removed_process_fields() -> None:
    spec = yaml.safe_load(OPENAPI_PATH.read_text(encoding="utf-8"))
    range_schema = spec["components"]["schemas"]["ModbusAddressRangePayload"]
    unit_schema = spec["components"]["schemas"]["ModbusUnitPayload"]

    for field in (
        "values",
        "nonzero_count",
        "value_min",
        "value_max",
        "value_sha256",
    ):
        assert field not in range_schema["properties"]
        assert field not in ModbusAddressRangePayload.model_fields

    assert "validations" not in unit_schema["properties"]
    assert "validations" not in ModbusUnitPayload.model_fields
    assert "ModbusValidationPayload" not in spec["components"]["schemas"]


def test_modbus_wire_models_forbid_unknown_fields() -> None:
    observed_at = datetime.now(timezone.utc)
    with pytest.raises(ValidationError):
        ModbusAddressRangePayload.model_validate(
            {
                "address_space": "coil",
                "start_address": 0,
                "count": 4,
                "status": "readable",
                "observed_at": observed_at,
                "values": [0, 1, 0, 1],
            }
        )


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
