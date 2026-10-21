from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import get_args
from uuid import uuid4

import pytest
import yaml
from agent.assessment.policy import (
    ASSESSMENT_CONFIDENCES,
    EVIDENCE_KINDS,
    EXPOSURE_ATTENTIONS,
    EXPOSURE_CONFIDENCES,
    EXPOSURE_ROLES,
    LOCAL_ASSESSMENT_POLICY_VERSION,
    MACHINE_TYPES,
)
from agent.normalize.contracts import (
    AssessmentEvidencePayload,
    CoverageObservationPayload,
    CoverageUnitPayload,
    DeviceProfilePayload,
    ExposurePayload,
    FindingEvidenceObservationPayload,
    FindingPayload,
    HostPayload,
    ModbusAddressRangePayload,
    ModbusDeviceIdentificationPayload,
    ModbusTcpServicePayload,
    ModbusUnitPayload,
    OpcUaEndpointPayload,
    OpcUaIdentityPayload,
    OpcUaMappedNodePayload,
    OpcUaMappingPayload,
    OpcUaObservationPayload,
    OpcUaPhasePayload,
    OpcUaTcpServicePayload,
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
    ("OpcUaTcpServicePayload", OpcUaTcpServicePayload),
    ("OpcUaObservationPayload", OpcUaObservationPayload),
    ("OpcUaEndpointPayload", OpcUaEndpointPayload),
    ("OpcUaIdentityPayload", OpcUaIdentityPayload),
    ("OpcUaMappedNodePayload", OpcUaMappedNodePayload),
    ("OpcUaMappingPayload", OpcUaMappingPayload),
    ("ModbusUnitPayload", ModbusUnitPayload),
    ("ModbusDeviceIdentificationPayload", ModbusDeviceIdentificationPayload),
    ("PortPayload", PortPayload),
    ("FindingPayload", FindingPayload),
    ("FindingEvidenceObservationPayload", FindingEvidenceObservationPayload),
    ("CoverageUnitPayload", CoverageUnitPayload),
    ("CoverageObservationPayload", CoverageObservationPayload),
    ("AvailableSubnet", AvailableSubnet),
    ("AgentHelloFrame", AgentHello),
    ("AgentCommandFrame", AgentCommand),
    ("AgentStatusFrame", AgentStatus),
)

OPENAPI_PATH = (
    Path(__file__).resolve().parents[2] / "contracts" / "openapi" / "openapi.yaml"
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
    assert (
        dumped["industrial_services"][0]["units"][0]["device_identification"][
            "product_code"
        ]
        == "BMX P34"
    )


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
    assert (
        set(contract_schema["required"])
        == set(model_schema["required"])
        == {
            "name",
            "accuracy",
        }
    )
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


def test_scan_host_view_requires_host_id_and_is_used_by_scan_detail_response() -> None:
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


def test_agent_models_emit_only_documented_contract_fields() -> None:
    spec = yaml.safe_load(OPENAPI_PATH.read_text(encoding="utf-8"))
    for schema_name, model in CONTRACT_MODELS:
        schema = spec["components"]["schemas"][schema_name]
        # The backend ignores legacy extras only in these nested Modbus objects.
        legacy_compatible = schema_name in {
            "ModbusAddressRangePayload",
            "ModbusUnitPayload",
        }
        assert schema.get("additionalProperties", True) is legacy_compatible
        emitted_fields = {
            name for name, field in model.model_fields.items() if not field.exclude
        }
        unknown = emitted_fields - set(schema["properties"])
        assert not unknown, f"{schema_name} does not document {sorted(unknown)}"


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
    assert (
        PortPayload(
            port=502,
            protocol="tcp",
            state="open",
            service="modbus",
        ).cpes
        == []
    )


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


def test_host_contract_accepts_legacy_modbus_and_strict_opcua_union() -> None:
    legacy = HostPayload.model_validate(
        {
            "ip": "192.168.0.20",
            "hostname": "host",
            "vendor": "unknown",
            "industrial_services": [
                {"port": 502, "confidence": "suspected", "units": []}
            ],
        }
    )
    assert isinstance(legacy.industrial_services[0], ModbusTcpServicePayload)
    ua = {
        "protocol": "opcua_tcp",
        "port": 4840,
        "confidence": "confirmed",
        "evidence_sources": ["opcua_get_endpoints"],
        "observation": {
            "schema_version": 1,
            "inventory_phase": {
                "status": "completed",
                "reason_codes": [],
                "truncated": False,
                "observed_at": datetime.now(timezone.utc),
            },
            "identity": {
                "application_uri": None,
                "product_uri": None,
                "application_name": None,
                "application_type": None,
            },
            "certificate_sha256": None,
            "endpoints": [],
        },
    }
    host = HostPayload.model_validate(
        {
            "ip": "192.168.0.20",
            "hostname": "host",
            "vendor": "unknown",
            "industrial_services": [ua],
        }
    )
    assert isinstance(host.industrial_services[0], OpcUaTcpServicePayload)
    assert "units" not in host.industrial_services[0].model_dump()
    phase = ua["observation"]["inventory_phase"]
    observation = ua["observation"]
    for reason in (
        "opaque_node_id_omitted",
        "observation_size_limit",
        "decode_error",
    ):
        OpcUaPhasePayload.model_validate({**phase, "reason_codes": [reason]})
    for field in ("reason_codes",):
        with pytest.raises(ValidationError):
            OpcUaPhasePayload.model_validate(
                {key: value for key, value in phase.items() if key != field}
            )
    for field in ("schema_version", "endpoints"):
        with pytest.raises(ValidationError):
            OpcUaObservationPayload.model_validate(
                {key: value for key, value in observation.items() if key != field}
            )
    phase_schema = OpcUaPhasePayload.model_json_schema()
    observation_schema = OpcUaObservationPayload.model_json_schema()
    openapi = yaml.safe_load(OPENAPI_PATH.read_text(encoding="utf-8"))
    components = openapi["components"]["schemas"]
    assert set(phase_schema["required"]) == set(
        components["OpcUaPhasePayload"]["required"]
    )
    assert set(observation_schema["required"]) == set(
        components["OpcUaObservationPayload"]["required"]
    )
    assert {"status", "reason_codes", "truncated", "observed_at"} <= set(
        phase_schema["required"]
    )
    assert {"schema_version", "inventory_phase", "endpoints"} <= set(
        observation_schema["required"]
    )
    assert (
        phase_schema["properties"]["status"]["enum"]
        == components["OpcUaPhasePayload"]["properties"]["status"]["enum"]
    )
    assert (
        phase_schema["properties"]["reason_codes"]["items"]["enum"]
        == components["OpcUaPhasePayload"]["properties"]["reason_codes"]["items"][
            "enum"
        ]
    )
    example_path = OPENAPI_PATH.parents[1] / "examples" / "scan_result.example.json"
    example = json.loads(example_path.read_text(encoding="utf-8"))
    ua_service = next(
        service
        for host_payload in example["hosts"]
        for service in host_payload.get("industrial_services", [])
        if service.get("protocol") == "opcua_tcp"
    )
    OpcUaTcpServicePayload.model_validate(ua_service)
    with pytest.raises(ValidationError):
        OpcUaObservationPayload.model_validate(
            {
                **ua["observation"],
                "inventory_phase": {
                    **ua["observation"]["inventory_phase"],
                    "reason_codes": ["arbitrary"],
                },
            }
        )
    with pytest.raises(ValidationError):
        OpcUaObservationPayload.model_validate(
            {
                **ua["observation"],
                "inventory_phase": {
                    key: value
                    for key, value in ua["observation"]["inventory_phase"].items()
                    if key != "truncated"
                },
            }
        )
    for invalid in (
        {key: value for key, value in ua.items() if key != "protocol"},
        {**ua, "unexpected": "field"},
        {**ua, "observation": {**ua["observation"], "process_data": "secret"}},
        {
            **ua,
            "observation": {
                **ua["observation"],
                "certificate_sha256": "subject=secret",
            },
        },
    ):
        with pytest.raises(ValidationError):
            OpcUaTcpServicePayload.model_validate(invalid)


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


def _assessment_host(*, state: str = "open") -> HostPayload:
    return HostPayload(
        ip="192.168.0.20",
        hostname="camera.local",
        vendor="Axis Communications",
        ports=[
            PortPayload(
                port=554,
                protocol="tcp",
                state=state,
                service="rtsp",
            )
        ],
        machine_type="camera",
        device_profile=DeviceProfilePayload(
            manufacturer="Axis Communications",
            product_family=None,
            model=None,
            confidence="medium",
            evidence=[],
            conflicts=[],
            limitations=["Available evidence does not support an exact model."],
        ),
    )


def _assessment_exposure() -> ExposurePayload:
    return ExposurePayload(
        ip="192.168.0.20",
        port=554,
        protocol="tcp",
        observed_service="rtsp",
        observed_version=None,
        role="media",
        attention="informational",
        confidence="low",
        reason="The endpoint is classified as media from an observed service.",
        evidence=[],
    )


def test_local_assessment_policy_version_is_frozen() -> None:
    assert LOCAL_ASSESSMENT_POLICY_VERSION == "2026-09-15.2"


def test_assessment_contract_vocabulary_is_exact() -> None:
    assert MACHINE_TYPES == (
        "router",
        "computer",
        "camera",
        "storage",
        "tv",
        "phone",
        "printer",
        "sensor",
        "unknown",
    )
    assert EXPOSURE_ROLES == (
        "administration",
        "data_store",
        "file_sharing",
        "remote_access",
        "proxy",
        "api",
        "device_control",
        "discovery",
        "media",
        "general_service",
        "unknown",
    )
    assert EXPOSURE_ATTENTIONS == ("informational", "review", "priority")
    assert ASSESSMENT_CONFIDENCES == ("unknown", "low", "medium", "high")
    assert EXPOSURE_CONFIDENCES == ("low", "medium", "high")
    assert EVIDENCE_KINDS == (
        "manufacturer",
        "hostname",
        "operating_system",
        "service",
        "version",
        "banner",
        "certificate",
        "protocol",
        "port",
        "cpe",
        "industrial",
        "web_path",
    )


def test_legacy_payload_defaults_to_assessment_unavailable() -> None:
    payload = ScanPayload(
        scan_id=uuid4(),
        timestamp=datetime.now(timezone.utc),
        subnet="192.168.0.0/24",
        scan_mode="quick",
        hosts=[
            HostPayload(
                ip="192.168.0.20",
                hostname="host",
                vendor="unknown",
            )
        ],
    )

    assert payload.assessment_policy_version is None
    assert payload.exposures == []
    assert payload.hosts[0].machine_type is None
    assert payload.hosts[0].device_profile is None


@pytest.mark.parametrize(
    "mutation",
    [
        pytest.param("missing_profile", id="missing-profile"),
        pytest.param("missing_type", id="missing-machine-type"),
        pytest.param("missing_exposure", id="missing-open-endpoint"),
        pytest.param("duplicate_exposure", id="duplicate-open-endpoint"),
        pytest.param("unmatched_exposure", id="unmatched-open-endpoint"),
    ],
)
def test_current_payload_rejects_incomplete_endpoint_assessment(mutation: str) -> None:
    host = _assessment_host()
    exposures = [_assessment_exposure()]
    if mutation == "missing_profile":
        host.device_profile = None
    elif mutation == "missing_type":
        host.machine_type = None
    elif mutation == "missing_exposure":
        exposures = []
    elif mutation == "duplicate_exposure":
        exposures.append(_assessment_exposure())
    elif mutation == "unmatched_exposure":
        exposures[0] = exposures[0].model_copy(update={"port": 8554})

    with pytest.raises(ValidationError):
        ScanPayload(
            scan_id=uuid4(),
            timestamp=datetime.now(timezone.utc),
            subnet="192.168.0.0/24",
            scan_mode="quick",
            hosts=[host],
            assessment_policy_version="2026-09-15.1",
            exposures=exposures,
        )


def test_legacy_payload_rejects_any_assessment_data() -> None:
    with pytest.raises(ValidationError):
        ScanPayload(
            scan_id=uuid4(),
            timestamp=datetime.now(timezone.utc),
            subnet="192.168.0.0/24",
            scan_mode="quick",
            hosts=[_assessment_host(state="closed")],
        )


def test_current_payload_accepts_exactly_one_exposure_per_open_endpoint() -> None:
    payload = ScanPayload(
        scan_id=uuid4(),
        timestamp=datetime.now(timezone.utc),
        subnet="192.168.0.0/24",
        scan_mode="quick",
        hosts=[_assessment_host()],
        assessment_policy_version="2026-09-15.1",
        exposures=[_assessment_exposure()],
    )

    assert payload.exposures[0].role == "media"


@pytest.mark.parametrize(
    ("model", "field", "value"),
    [
        (AssessmentEvidencePayload, "source", "s" * 81),
        (AssessmentEvidencePayload, "value", "v" * 161),
        (ExposurePayload, "port", 0),
        (ExposurePayload, "port", 65536),
        (ExposurePayload, "observed_service", "s" * 161),
        (ExposurePayload, "reason", "r" * 241),
        (DeviceProfilePayload, "manufacturer", "m" * 161),
    ],
)
def test_assessment_contract_rejects_bounds(model, field: str, value) -> None:
    fixtures = {
        AssessmentEvidencePayload: {
            "kind": "service",
            "source": "nmap",
            "value": "ssh",
        },
        ExposurePayload: _assessment_exposure().model_dump(),
        DeviceProfilePayload: _assessment_host().device_profile.model_dump(),
    }
    fixtures[model][field] = value

    with pytest.raises(ValidationError):
        model.model_validate(fixtures[model])


def test_assessment_evidence_is_deduplicated_and_stably_ordered() -> None:
    profile = DeviceProfilePayload(
        confidence="low",
        evidence=[
            {"kind": "service", "source": "22/tcp", "value": "SSH"},
            {"kind": "port", "source": "nmap", "value": "22/tcp open"},
            {"kind": "service", "source": "22/tcp", "value": "ssh"},
        ],
    )

    assert [(item.kind, item.source, item.value) for item in profile.evidence] == [
        ("port", "nmap", "22/tcp open"),
        ("service", "22/tcp", "SSH"),
    ]


def test_finding_evidence_observation_is_strict_and_bounded() -> None:
    observation = {
        "condition_key": "CVE-2026-1234",
        "method": "specific_check",
        "result": "negative",
        "source": "nmap",
        "rule_id": "nse:test-rule",
        "rule_version": "1",
        "evidence": "Structured response recorded.",
        "facts": {"state": "not_vulnerable", "attempted": False},
    }
    assert (
        FindingEvidenceObservationPayload.model_validate(observation).facts
        == observation["facts"]
    )

    for invalid in (
        {**observation, "facts": {"items": ["nested"]}},
        {**observation, "facts": {"value": 1.5}},
        {**observation, "facts": {"value": "x" * 161}},
        {**observation, "unexpected": True},
    ):
        with pytest.raises(ValidationError):
            FindingEvidenceObservationPayload.model_validate(invalid)


def test_finding_issue_key_is_bounded_and_serialized_when_present() -> None:
    data = {
        "severity": "high",
        "title": "Observed condition",
        "description": "The condition was tested.",
        "recommendation": "Review the result.",
        "evidence": "Existing evidence text.",
        "issue_key": "smb:signing",
    }
    finding = FindingPayload.model_validate(data)
    assert finding.issue_key == "smb:signing"
    assert finding.model_dump()["issue_key"] == "smb:signing"
    legacy = {key: value for key, value in data.items() if key != "issue_key"}
    assert FindingPayload.model_validate(legacy).model_dump()["issue_key"] is None
    for value in (" ", "x" * 257):
        with pytest.raises(ValidationError):
            FindingPayload.model_validate({**data, "issue_key": value})


def test_scan_payload_finding_evidence_requires_version_and_standalone_scope() -> None:
    observation = {
        "condition_key": "CVE-2026-1234",
        "method": "specific_check",
        "result": "negative",
        "source": "nmap",
        "rule_id": "nse:test-rule",
        "rule_version": "1",
        "evidence": "Structured response recorded.",
    }
    base = {
        "scan_id": uuid4(),
        "timestamp": datetime.now(timezone.utc),
        "subnet": "192.168.0.0/24",
        "scan_mode": "quick",
        "hosts": [HostPayload(ip="192.168.0.20", hostname="host", vendor="unknown")],
    }
    with pytest.raises(ValidationError):
        ScanPayload(**base, finding_observations=[observation])
    with pytest.raises(ValidationError):
        ScanPayload(
            **base,
            finding_evidence_policy_version="1",
            finding_observations=[{**observation, "ip": "192.168.0.21"}],
        )
    with pytest.raises(ValidationError):
        ScanPayload(
            **base,
            finding_evidence_policy_version="1",
            finding_observations=[{**observation, "result": "positive"}],
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("ip", "2001:db8::1"),
        ("port", 0),
        ("port", 65536),
        ("protocol", "icmp"),
        ("unit_id", -1),
        ("unit_id", 256),
        ("condition_key", ""),
        ("condition_key", "x" * 257),
        ("source", "x" * 65),
        ("source_script", "x" * 65),
        ("rule_id", "x" * 129),
        ("rule_version", "x" * 65),
        ("evidence", "x" * 513),
    ],
)
def test_finding_evidence_observation_rejects_invalid_field_bounds(
    field: str, value
) -> None:
    observation = {
        "condition_key": "CVE-2026-1234",
        "method": "specific_check",
        "result": "negative",
        "source": "nmap",
        "rule_id": "nse:test-rule",
        "rule_version": "1",
        "evidence": "Structured response recorded.",
    }
    observation[field] = value

    with pytest.raises(ValidationError):
        FindingEvidenceObservationPayload.model_validate(observation)


def test_finding_evidence_accepts_future_version_and_rejects_incoherent_metadata() -> (
    None
):
    host = HostPayload(ip="192.168.0.20", hostname="host", vendor="unknown")
    base = {
        "scan_id": uuid4(),
        "timestamp": datetime.now(timezone.utc),
        "subnet": "192.168.0.0/24",
        "scan_mode": "quick",
        "hosts": [host],
    }
    observation = {
        "ip": "192.168.0.20",
        "condition_key": "CVE-2026-1234",
        "method": "specific_check",
        "result": "inconclusive",
        "source": "nmap",
        "rule_id": "nse:test-rule",
        "rule_version": "1",
        "evidence": "Structured response recorded.",
    }

    with pytest.raises(ValidationError):
        ScanPayload(**base, finding_observations_truncated=True)

    payload = ScanPayload(
        **base,
        finding_evidence_policy_version="future-policy",
        finding_observations=[observation],
    )
    assert payload.finding_evidence_policy_version == "future-policy"
    assert len(payload.finding_observations) == 1


@pytest.mark.parametrize(
    "mutation",
    [
        {"ip": "192.168.0.21"},
        {"port": 443},
        {"protocol": "udp"},
        {"unit_id": 2},
    ],
)
def test_finding_evidence_endpoint_fields_match_finding(mutation) -> None:
    observation = {
        "ip": "192.168.0.20",
        "port": 22,
        "protocol": "tcp",
        "unit_id": 1,
        "condition_key": "CVE-2026-1234",
        "method": "specific_check",
        "result": "positive",
        "source": "nmap",
        "rule_id": "nse:test-rule",
        "rule_version": "1",
        "evidence": "Structured response recorded.",
    }
    observation.update(mutation)
    finding = FindingPayload(
        ip="192.168.0.20",
        port=22,
        protocol="tcp",
        unit_id=1,
        severity="high",
        title="Observed condition",
        description="The condition was tested.",
        recommendation="Review the result.",
        evidence="Existing evidence text.",
        evidence_observations=[observation],
    )

    with pytest.raises(ValidationError):
        ScanPayload(
            scan_id=uuid4(),
            timestamp=datetime.now(timezone.utc),
            subnet="192.168.0.0/24",
            scan_mode="quick",
            hosts=[HostPayload(ip="192.168.0.20", hostname="host", vendor="unknown")],
            findings=[finding],
            finding_evidence_policy_version="1",
        )
