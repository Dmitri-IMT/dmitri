from __future__ import annotations

import json
from pathlib import Path

import pydantic
import pytest
from api.schemas import (
    HostPayload,
    OperatingSystemDetection,
    PortPayload,
    ScanIngestAcceptedResponse,
    ScanIngestRequest,
)
from api.schemas.persistence import PersistedScanDetail, PersistedScanSummary
from api.schemas.read import Port

EXAMPLE_PATH = (
    Path(__file__).resolve().parents[2]
    / "contracts"
    / "examples"
    / "scan_result.example.json"
)


def _base_payload(**overrides: object) -> dict:
    payload = {
        "scan_id": "b9a2de1d-6cb0-4d1c-9f19-8f313cfa9c77",
        "timestamp": "2026-03-05T14:12:45Z",
        "subnet": "192.168.1.0/24",
        "scan_mode": "standard",
        "hosts": [
            {
                "ip": "192.168.1.10",
                "mac": "B8:27:EB:44:55:66",
                "hostname": "lab-camera",
                "vendor": "Raspberry Pi Trading Ltd",
                "ports": [],
            }
        ],
    }
    payload.update(overrides)
    return payload


def _current_payload(**overrides: object) -> dict:
    payload = _base_payload(
        findings=[],
        assessment_policy_version="2026-09-15.1",
        exposures=[
            {
                "ip": "192.168.1.10",
                "port": 22,
                "protocol": "tcp",
                "observed_service": "ssh",
                "observed_version": "OpenSSH 9.0",
                "role": "remote_access",
                "attention": "review",
                "confidence": "high",
                "reason": "Remote access service is reachable.",
                "evidence": [
                    {"kind": "port", "source": "endpoint", "value": "tcp/22"}
                ],
            }
        ],
    )
    payload["hosts"][0]["ports"] = [
        {
            "port": 22,
            "protocol": "tcp",
            "state": "open",
            "service": "ssh",
        }
    ]
    payload["hosts"][0]["machine_type"] = "computer"
    payload["hosts"][0]["device_profile"] = {
        "manufacturer": "Raspberry Pi Trading Ltd",
        "product_family": None,
        "model": None,
        "confidence": "medium",
        "evidence": [
            {
                "kind": "manufacturer",
                "source": "vendor",
                "value": "Raspberry Pi Trading Ltd",
            }
        ],
        "conflicts": [],
        "limitations": ["Exact model was not observed."],
    }
    payload.update(overrides)
    return payload


def test_scan_result_validates_scan_mode_and_hosts_payload():
    payload = _base_payload(findings=[])
    result = ScanIngestRequest.model_validate(payload)

    assert result.scan_mode == "standard"
    assert isinstance(result.hosts[0], HostPayload)
    assert result.hosts[0].hostname == "lab-camera"


def test_scan_result_rejects_target_mode_and_scan_profile():
    payload = _base_payload(target_mode="subnet", scan_profile="lan")

    with pytest.raises(pydantic.ValidationError):
        ScanIngestRequest.model_validate(payload)


def test_scan_result_rejects_devices_field_without_hosts():
    payload = _base_payload()
    del payload["hosts"]
    payload["devices"] = payload.pop("hosts", [])

    with pytest.raises(pydantic.ValidationError):
        ScanIngestRequest.model_validate(payload)


def test_scan_result_rejects_ipv6_host_address():
    payload = _base_payload(findings=[])
    payload["hosts"][0]["ip"] = "2001:db8::1"

    with pytest.raises(pydantic.ValidationError):
        ScanIngestRequest.model_validate(payload)


def test_scan_result_rejects_ipv6_finding_address():
    payload = _base_payload(
        findings=[
            {
                "ip": "2001:db8::1",
                "severity": "high",
                "title": "Vulnerable service",
                "description": "A vulnerable service was found.",
                "recommendation": "Patch it.",
                "evidence": "Some evidence.",
            }
        ]
    )

    with pytest.raises(pydantic.ValidationError):
        ScanIngestRequest.model_validate(payload)


def test_host_importable_from_api_schemas():
    host = HostPayload(
        ip="10.0.0.1", hostname="router", vendor="Acme", mac=None, ports=[]
    )

    assert host.hostname == "router"


def test_persisted_scan_summary_uses_scan_mode():
    summary = PersistedScanSummary(
        scan_id="b9a2de1d-6cb0-4d1c-9f19-8f313cfa9c77",
        timestamp="2026-03-05T14:12:45Z",
        subnet="192.168.1.0/24",
        scan_mode="standard",
        device_count=1,
        finding_count=0,
    )

    assert summary.scan_mode == "standard"


def test_persisted_scan_detail_uses_scan_mode_and_status():
    detail = PersistedScanDetail(
        scan_id="b9a2de1d-6cb0-4d1c-9f19-8f313cfa9c77",
        timestamp="2026-03-05T14:12:45Z",
        subnet="192.168.1.0/24",
        scan_mode="standard",
        status="complete",
        metadata=None,
        devices=[],
        findings=[],
        enrichment_jobs=[],
    )

    assert detail.scan_mode == "standard"
    assert detail.status == "complete"


def test_ingest_nested_models_forbid_unknown_fields_and_support_cpes():
    port = PortPayload(
        port=443,
        protocol="tcp",
        state="open",
        service="https",
        cpes=["cpe:2.3:a:x:y:1:*"],
    )
    assert port.cpes

    bad_port_payload = _base_payload(findings=[])
    bad_port_payload["hosts"][0]["ports"] = [
        {
            "port": 443,
            "protocol": "tcp",
            "state": "open",
            "service": "https",
            "unknown": True,
        }
    ]
    with pytest.raises(pydantic.ValidationError):
        ScanIngestRequest.model_validate(bad_port_payload)

    bad_finding_payload = _base_payload(
        findings=[
            {
                "severity": "high",
                "title": "Bad",
                "description": "Bad finding",
                "recommendation": "Fix it",
                "evidence": "Evidence",
                "unknown": True,
            }
        ]
    )
    with pytest.raises(pydantic.ValidationError):
        ScanIngestRequest.model_validate(bad_finding_payload)


def test_read_port_has_no_ingest_cpes_and_response_is_accepted():
    assert "cpes" not in Port.model_fields

    response = ScanIngestAcceptedResponse(
        message="scan received successfully",
        scan_id=_base_payload()["scan_id"],
        hosts_received=1,
        status="accepted",
    )
    with pytest.raises(pydantic.ValidationError):
        ScanIngestAcceptedResponse.model_validate(
            {**response.model_dump(), "extra": True}
        )


def test_ingest_host_entry_forbids_unknown_field():
    payload = _base_payload(findings=[])
    payload["hosts"][0]["unknown"] = True

    with pytest.raises(pydantic.ValidationError):
        ScanIngestRequest.model_validate(payload)


def test_ingest_accepts_and_exports_operating_system_detection() -> None:
    payload = _base_payload(findings=[])
    payload["hosts"][0]["operating_system"] = {
        "name": "Linux 5.4 - 5.10",
        "accuracy": 96,
        "vendor": "Linux",
        "family": "Linux",
        "generation": "5.X",
        "device_type": "general purpose",
        "cpes": ["cpe:/o:linux:linux_kernel:5"],
    }

    result = ScanIngestRequest.model_validate(payload)

    assert result.hosts[0].operating_system == OperatingSystemDetection(
        name="Linux 5.4 - 5.10",
        accuracy=96,
        vendor="Linux",
        family="Linux",
        generation="5.X",
        device_type="general purpose",
        cpes=["cpe:/o:linux:linux_kernel:5"],
    )


@pytest.mark.parametrize("accuracy", [0, 100])
def test_ingest_accepts_operating_system_accuracy_boundaries(accuracy: int) -> None:
    payload = _base_payload(findings=[])
    payload["hosts"][0]["operating_system"] = {
        "name": "Linux",
        "accuracy": accuracy,
    }

    result = ScanIngestRequest.model_validate(payload)

    assert result.hosts[0].operating_system is not None
    assert result.hosts[0].operating_system.accuracy == accuracy
    assert result.hosts[0].operating_system.cpes == []


def test_ingest_accepts_explicit_null_operating_system_details() -> None:
    payload = _base_payload(findings=[])
    payload["hosts"][0]["operating_system"] = {
        "name": "Linux",
        "accuracy": 96,
        "vendor": None,
        "family": None,
        "generation": None,
        "device_type": None,
        "cpes": [],
    }

    result = ScanIngestRequest.model_validate(payload)

    assert result.hosts[0].operating_system is not None
    assert result.hosts[0].operating_system.model_dump(mode="json") == payload[
        "hosts"
    ][0]["operating_system"]


@pytest.mark.parametrize(
    "include_null",
    [pytest.param(False, id="omitted"), pytest.param(True, id="explicit-null")],
)
def test_ingest_accepts_missing_operating_system(include_null: bool) -> None:
    payload = _base_payload(findings=[])
    if include_null:
        payload["hosts"][0]["operating_system"] = None

    result = ScanIngestRequest.model_validate(payload)

    assert result.hosts[0].operating_system is None


@pytest.mark.parametrize(
    "operating_system",
    [
        {"name": "", "accuracy": 96},
        {"name": None, "accuracy": 96},
        {"name": "Linux", "accuracy": -1},
        {"name": "Linux", "accuracy": 101},
        {"name": "Linux", "accuracy": 96.0},
        {"name": "Linux", "accuracy": 96.5},
        {"name": "Linux", "accuracy": "96"},
        {"name": "Linux", "accuracy": True},
        {"name": "Linux", "accuracy": 96, "cpes": [""]},
        {"name": "Linux", "accuracy": 96, "cpes": None},
        {"name": "Linux", "accuracy": 96, "vendor": 1},
        {"name": "Linux", "accuracy": 96, "unexpected": True},
        {"accuracy": 96},
        {"name": "Linux"},
    ],
)
def test_ingest_rejects_invalid_operating_system_detection(
    operating_system: dict,
) -> None:
    payload = _base_payload(findings=[])
    payload["hosts"][0]["operating_system"] = operating_system

    with pytest.raises(pydantic.ValidationError):
        ScanIngestRequest.model_validate(payload)


def test_ingest_requires_hosts_key():
    payload = _base_payload()
    del payload["hosts"]
    payload["findings"] = []

    with pytest.raises(pydantic.ValidationError):
        ScanIngestRequest.model_validate(payload)


def test_ingest_requires_findings_key():
    payload = _base_payload()

    with pytest.raises(pydantic.ValidationError):
        ScanIngestRequest.model_validate(payload)


def test_ingest_hosts_and_findings_may_be_empty_lists():
    payload = _base_payload(findings=[])
    payload["hosts"] = []

    result = ScanIngestRequest.model_validate(payload)

    assert result.hosts == []
    assert result.findings == []


def test_ingest_host_requires_mac_key_but_accepts_null():
    payload = _base_payload(findings=[])
    del payload["hosts"][0]["mac"]

    with pytest.raises(pydantic.ValidationError):
        ScanIngestRequest.model_validate(payload)

    payload["hosts"][0]["mac"] = None
    result = ScanIngestRequest.model_validate(payload)

    assert result.hosts[0].mac is None


def test_ingest_host_requires_ports_key():
    payload = _base_payload(findings=[])
    del payload["hosts"][0]["ports"]

    with pytest.raises(pydantic.ValidationError):
        ScanIngestRequest.model_validate(payload)


def test_ingest_rejects_top_level_artifacts_field():
    payload = _base_payload(findings=[], artifacts=[])

    with pytest.raises(pydantic.ValidationError):
        ScanIngestRequest.model_validate(payload)


def test_ingest_accepted_response_requires_status():
    payload = {
        "message": "scan received successfully",
        "scan_id": _base_payload()["scan_id"],
        "hosts_received": 1,
    }

    with pytest.raises(pydantic.ValidationError):
        ScanIngestAcceptedResponse.model_validate(payload)


def test_ingest_accepted_response_rejects_non_accepted_status():
    payload = {
        "message": "scan received successfully",
        "scan_id": _base_payload()["scan_id"],
        "hosts_received": 1,
        "status": "pending",
    }

    with pytest.raises(pydantic.ValidationError):
        ScanIngestAcceptedResponse.model_validate(payload)


def test_ingest_rejects_removed_modbus_process_fields() -> None:
    payload = _base_payload(findings=[])
    payload["hosts"][0]["industrial_services"] = [
        {
            "protocol": "modbus_tcp",
            "port": 502,
            "confidence": "confirmed",
            "units": [
                {
                    "unit_id": 1,
                    "status": "responding",
                    "address_ranges": [
                        {
                            "address_space": "coil",
                            "start_address": 0,
                            "count": 4,
                            "status": "readable",
                            "observed_at": "2026-09-12T14:03:11Z",
                            "values": [False, True, False, True],
                        }
                    ],
                }
            ],
        }
    ]

    with pytest.raises(pydantic.ValidationError):
        ScanIngestRequest.model_validate(payload)


def test_example_payload_validates_against_tightened_model():
    payload = json.loads(EXAMPLE_PATH.read_text())

    result = ScanIngestRequest.model_validate(payload)

    assert result.hosts[0].ports[0].cpes == []
    assert result.hosts[0].operating_system == OperatingSystemDetection(
        name="Linux 5.4 - 5.10",
        accuracy=96,
        vendor="Linux",
        family="Linux",
        generation="5.X",
        device_type="general purpose",
        cpes=["cpe:/o:linux:linux_kernel:5"],
    )


def test_current_assessment_payload_validates_exact_endpoint_coverage() -> None:
    result = ScanIngestRequest.model_validate(_current_payload())

    assert result.assessment_policy_version == "2026-09-15.1"
    assert result.hosts[0].machine_type == "computer"
    assert result.hosts[0].device_profile is not None
    assert len(result.exposures) == 1


@pytest.mark.parametrize(
    "mutation",
    [
        pytest.param("exposure", id="exposure-with-null-version"),
        pytest.param("machine_type", id="machine-type-with-null-version"),
        pytest.param("device_profile", id="profile-with-null-version"),
    ],
)
def test_legacy_payload_rejects_assessment_content(mutation: str) -> None:
    current = _current_payload()
    payload = _base_payload(findings=[], assessment_policy_version=None)
    if mutation == "exposure":
        payload["exposures"] = current["exposures"]
    else:
        payload["hosts"][0][mutation] = current["hosts"][0][mutation]

    with pytest.raises(pydantic.ValidationError, match="legacy payloads"):
        ScanIngestRequest.model_validate(payload)


@pytest.mark.parametrize(
    "field",
    [pytest.param("machine_type"), pytest.param("device_profile")],
)
def test_current_payload_requires_complete_host_assessment(field: str) -> None:
    payload = _current_payload()
    payload["hosts"][0].pop(field)

    with pytest.raises(pydantic.ValidationError, match="every host"):
        ScanIngestRequest.model_validate(payload)


@pytest.mark.parametrize(
    "mutation",
    [
        pytest.param("missing", id="missing-open-endpoint"),
        pytest.param("duplicate", id="duplicate-open-endpoint"),
        pytest.param("unmatched", id="unmatched-endpoint"),
        pytest.param("closed", id="closed-endpoint"),
    ],
)
def test_current_payload_rejects_invalid_exposure_coverage(mutation: str) -> None:
    payload = _current_payload()
    if mutation == "missing":
        payload["exposures"] = []
    elif mutation == "duplicate":
        payload["exposures"].append(dict(payload["exposures"][0]))
    elif mutation == "unmatched":
        payload["exposures"][0]["port"] = 23
    else:
        payload["hosts"][0]["ports"][0]["state"] = "closed"

    with pytest.raises(pydantic.ValidationError, match="exposure|endpoint"):
        ScanIngestRequest.model_validate(payload)


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("hosts", 0, "machine_type"), "toaster"),
        (("hosts", 0, "device_profile", "confidence"), "certain"),
        (("exposures", 0, "role"), "vulnerability"),
        (("exposures", 0, "attention"), "high"),
        (("exposures", 0, "confidence"), "unknown"),
        (("exposures", 0, "evidence", 0, "kind"), "secret"),
    ],
)
def test_assessment_models_reject_values_outside_exact_enums(
    path: tuple[object, ...], value: str
) -> None:
    payload = _current_payload()
    target: object = payload
    for part in path[:-1]:
        target = target[part]  # type: ignore[index]
    target[path[-1]] = value  # type: ignore[index]

    with pytest.raises(pydantic.ValidationError):
        ScanIngestRequest.model_validate(payload)


def test_assessment_models_enforce_string_and_collection_bounds() -> None:
    too_long_source = _current_payload()
    too_long_source["exposures"][0]["evidence"][0]["source"] = "s" * 81
    with pytest.raises(pydantic.ValidationError):
        ScanIngestRequest.model_validate(too_long_source)

    too_many_evidence = _current_payload()
    too_many_evidence["exposures"][0]["evidence"] = [
        {"kind": "port", "source": f"endpoint-{index}", "value": "tcp/22"}
        for index in range(13)
    ]
    with pytest.raises(pydantic.ValidationError):
        ScanIngestRequest.model_validate(too_many_evidence)

    too_many_conflicts = _current_payload()
    too_many_conflicts["hosts"][0]["device_profile"]["conflicts"] = [
        f"conflict-{index}" for index in range(6)
    ]
    with pytest.raises(pydantic.ValidationError):
        ScanIngestRequest.model_validate(too_many_conflicts)
