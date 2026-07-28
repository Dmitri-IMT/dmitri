from __future__ import annotations

from uuid import UUID

import pydantic
import pytest
from api.schemas import Host
from api.schemas.read import (
    FindingListResponse,
    FindingRead,
    HostDetailResponse,
    HostListResponse,
    HostScanHistoryEntry,
    HostSummary,
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
    assert ScanHostView is not Host
    assert not issubclass(ScanHostView, Host)
    assert not issubclass(Host, ScanHostView)


def test_scan_host_view_rejects_missing_hostname():
    payload = _scan_host_view_payload()
    del payload["hostname"]

    with pytest.raises(pydantic.ValidationError):
        ScanHostView.model_validate(payload)


def test_host_list_response_envelope_shape():
    envelope = HostListResponse.model_validate(
        {"data": [_host_summary_payload()], "total": 1, "page": 1}
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
