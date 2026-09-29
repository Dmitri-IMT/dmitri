from __future__ import annotations

from uuid import UUID

import pydantic
import pytest
from api.core.machine_type import MACHINE_TYPES
from api.schemas import HostPayload
from api.schemas.read import (
    FindingListResponse,
    FindingRead,
    HostDetailResponse,
    HostListResponse,
    HostPort,
    HostScanHistoryEntry,
    HostSummary,
    IndustrialServiceView,
    Port,
    ScanDetailResponse,
    ScanHostView,
    ScanListResponse,
    ScanSummary,
)


def _scan_host_view_payload(**overrides: object) -> dict:
    payload = {
        "host_id": "b9a2de1d-6cb0-4d1c-9f19-8f313cfa9c77",
        "ip": "192.168.1.10",
        "mac": "B8:27:EB:44:55:66",
        "hostname": "lab-camera",
        "vendor": "Raspberry Pi Trading Ltd",
        "ports": [],
        "machine_type": None,
        "device_profile": None,
    }
    payload.update(overrides)
    return payload


def _host_summary_payload(**overrides: object) -> dict:
    payload = {
        "host_id": "b9a2de1d-6cb0-4d1c-9f19-8f313cfa9c77",
        "ip": "192.168.1.10",
        "mac": "B8:27:EB:44:55:66",
        "hostname": "lab-camera",
        "vendor": "Raspberry Pi Trading Ltd",
        "first_seen_at": "2026-03-05T14:12:45Z",
        "last_seen_at": "2026-03-05T14:12:45Z",
        "open_ports_count": 0,
        "machine_type": "camera",
        "device_profile": None,
        "vulnerability_count": 0,
    }
    payload.update(overrides)
    return payload


def _scan_summary_payload(**overrides: object) -> dict:
    payload = {
        "scan_id": "b9a2de1d-6cb0-4d1c-9f19-8f313cfa9c77",
        "timestamp": "2026-03-05T14:12:45Z",
        "subnet": "192.168.1.0/24",
        "scan_mode": "standard",
        "status": "completed",
        "host_count": 12,
        "finding_count": 4,
        "highest_severity": "critical",
    }
    payload.update(overrides)
    return payload


def _operating_system_payload() -> dict[str, object]:
    return {
        "name": "Linux 5.4 - 5.10",
        "accuracy": 96,
        "vendor": "Linux",
        "cpes": ["cpe:/o:linux:linux_kernel:5"],
    }


def test_all_eleven_read_models_importable():
    models = [
        Port,
        ScanHostView,
        FindingRead,
        HostSummary,
        HostScanHistoryEntry,
        HostDetailResponse,
        ScanDetailResponse,
        ScanSummary,
        ScanListResponse,
        HostListResponse,
        FindingListResponse,
    ]
    assert len(models) == 11
    for model in models:
        assert issubclass(model, pydantic.BaseModel)


def test_scan_host_view_host_id_required():
    payload = _scan_host_view_payload()
    del payload["host_id"]

    with pytest.raises(pydantic.ValidationError):
        ScanHostView.model_validate(payload)


def test_scan_host_view_host_id_present_and_typed():
    host = ScanHostView.model_validate(_scan_host_view_payload())

    assert isinstance(host.host_id, UUID)


def test_host_summary_first_seen_at_required():
    payload = _host_summary_payload()
    del payload["first_seen_at"]

    with pytest.raises(pydantic.ValidationError):
        HostSummary.model_validate(payload)


def test_host_summary_first_seen_at_present():
    summary = HostSummary.model_validate(_host_summary_payload())

    assert summary.first_seen_at is not None


def test_scan_host_view_is_distinct_from_ingest_host():
    assert ScanHostView is not HostPayload
    assert not issubclass(ScanHostView, HostPayload)
    assert not issubclass(HostPayload, ScanHostView)


def test_scan_host_view_rejects_missing_hostname():
    payload = _scan_host_view_payload()
    del payload["hostname"]

    with pytest.raises(pydantic.ValidationError):
        ScanHostView.model_validate(payload)


def test_host_list_response_envelope_shape():
    envelope = HostListResponse.model_validate(
        {
            "data": [_host_summary_payload()],
            "total": 1,
            "quiet_total": 0,
            "page": 1,
        }
    )

    assert envelope.total == 1
    assert isinstance(envelope.data[0], HostSummary)


def test_finding_list_response_envelope_shape():
    envelope = FindingListResponse.model_validate({"data": [], "total": 0, "page": 1})

    assert envelope.data == []


def test_scan_detail_response_nests_scan_host_view_and_finding_read():
    detail = ScanDetailResponse.model_validate(
        {
            "scan_id": "b9a2de1d-6cb0-4d1c-9f19-8f313cfa9c77",
            "timestamp": "2026-03-05T14:12:45Z",
            "subnet": "192.168.1.0/24",
            "scan_mode": "standard",
            "hosts": [_scan_host_view_payload()],
            "findings": [],
            "assessment_status": "unavailable",
            "assessment_policy_version": None,
            "exposures": [],
            "status": "completed",
            "host_count": 1,
            "finding_count": 0,
        }
    )

    assert isinstance(detail.hosts[0], ScanHostView)


def test_scan_summary_subnet_accepts_unpatterned_string():
    summary = ScanSummary.model_validate(_scan_summary_payload(subnet="not-a-cidr"))

    assert summary.subnet == "not-a-cidr"


def test_scan_summary_highest_severity_optional():
    summary = ScanSummary.model_validate(
        _scan_summary_payload(finding_count=0, highest_severity=None)
    )

    assert summary.highest_severity is None


@pytest.mark.parametrize(
    "terminated_by",
    ["completed", "user_cancel", "timeout", "error", None],
)
def test_scan_summary_terminated_by_accepts_runner_values(terminated_by):
    summary = ScanSummary.model_validate(
        _scan_summary_payload(terminated_by=terminated_by)
    )
    assert summary.terminated_by == terminated_by


def test_scan_summary_terminated_by_optional():
    without = ScanSummary.model_validate(_scan_summary_payload())
    assert without.terminated_by is None


def test_scan_summary_rejects_extra_fields():
    with pytest.raises(pydantic.ValidationError):
        ScanSummary.model_validate(_scan_summary_payload(extra_field="nope"))


def test_scan_list_response_envelope_shape():
    envelope = ScanListResponse.model_validate(
        {"data": [_scan_summary_payload()], "total": 1, "page": 1}
    )

    assert envelope.total == 1
    assert isinstance(envelope.data[0], ScanSummary)
    assert "per_page" not in ScanListResponse.model_fields


def test_host_summary_rejects_a_negative_vulnerability_count():
    with pytest.raises(pydantic.ValidationError):
        HostSummary.model_validate(_host_summary_payload(vulnerability_count=-1))


def test_host_summary_machine_type_is_closed_to_the_nine_values():
    assert len(MACHINE_TYPES) == 9
    for machine_type in MACHINE_TYPES:
        summary = HostSummary.model_validate(
            _host_summary_payload(machine_type=machine_type)
        )
        assert summary.machine_type == machine_type

    with pytest.raises(pydantic.ValidationError):
        HostSummary.model_validate(_host_summary_payload(machine_type="toaster"))


def test_host_list_response_rejects_a_negative_quiet_total():
    with pytest.raises(pydantic.ValidationError):
        HostListResponse.model_validate(
            {"data": [], "total": 0, "quiet_total": -1, "page": 1}
        )


def test_host_port_carries_the_two_dates_and_no_state():
    assert "state" not in HostPort.model_fields
    payload = {
        "port": 554,
        "protocol": "tcp",
        "service": "rtsp",
        "version": None,
        "first_seen_at": "2026-03-05T14:12:45Z",
        "last_seen_at": "2026-03-06T14:12:45Z",
    }
    port = HostPort.model_validate(payload)

    assert port.first_seen_at < port.last_seen_at
    with pytest.raises(pydantic.ValidationError):
        HostPort.model_validate({**payload, "state": "open"})


@pytest.mark.parametrize(
    ("model", "payload"),
    (
        (ScanHostView, _scan_host_view_payload()),
        (HostSummary, _host_summary_payload()),
        (
            HostScanHistoryEntry,
            {
                "scan_id": "b9a2de1d-6cb0-4d1c-9f19-8f313cfa9c77",
                "timestamp": "2026-03-05T14:12:45Z",
                "scan_mode": "standard",
                "open_ports_count": 0,
            },
        ),
        (
            HostDetailResponse,
            {
                **_host_summary_payload(),
                "assessment_status": "unavailable",
                "assessment_policy_version": None,
                "exposures": [],
                "ports": [],
                "scan_history": [],
            },
        ),
    ),
)
def test_host_read_models_accept_optional_nullable_operating_system(
    model, payload: dict[str, object]
) -> None:
    omitted = model.model_validate(payload)
    assert omitted.operating_system is None

    explicit_null = model.model_validate({**payload, "operating_system": None})
    assert explicit_null.operating_system is None

    detected = model.model_validate(
        {**payload, "operating_system": _operating_system_payload()}
    )
    assert detected.operating_system.name == "Linux 5.4 - 5.10"


@pytest.mark.parametrize(
    ("model", "payload"),
    (
        (ScanHostView, _scan_host_view_payload()),
        (HostSummary, _host_summary_payload()),
        (
            HostScanHistoryEntry,
            {
                "scan_id": "b9a2de1d-6cb0-4d1c-9f19-8f313cfa9c77",
                "timestamp": "2026-03-05T14:12:45Z",
                "scan_mode": "standard",
                "open_ports_count": 0,
            },
        ),
        (
            HostDetailResponse,
            {
                **_host_summary_payload(),
                "assessment_status": "unavailable",
                "assessment_policy_version": None,
                "exposures": [],
                "ports": [],
                "scan_history": [],
            },
        ),
    ),
)
def test_host_read_models_reject_malformed_operating_system(
    model, payload: dict[str, object]
) -> None:
    with pytest.raises(pydantic.ValidationError):
        model.model_validate(
            {
                **payload,
                "operating_system": {
                    "name": "Linux",
                    "accuracy": 101,
                    "unexpected": True,
                },
            }
        )


def test_industrial_read_views_have_no_process_value_fields() -> None:
    schema = IndustrialServiceView.model_json_schema()
    assert "values" not in schema["properties"]
    assert "value_min" not in schema["properties"]
    assert "value_max" not in schema["properties"]
    assert "nonzero_count" not in schema["properties"]
    assert "validations" not in schema["properties"]
    unit = ScanHostView.model_fields["industrial_services"]
    assert unit is not None
