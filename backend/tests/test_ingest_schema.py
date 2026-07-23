from __future__ import annotations

import pydantic
import pytest
from api.schemas import Host, ScanResult
from api.schemas.persistence import PersistedScanDetail, PersistedScanSummary


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


def test_scan_result_validates_scan_mode_and_hosts_payload():
    result = ScanResult.model_validate(_base_payload())

    assert result.scan_mode == "standard"
    assert isinstance(result.hosts[0], Host)
    assert result.hosts[0].hostname == "lab-camera"


def test_scan_result_rejects_target_mode_and_scan_profile():
    payload = _base_payload(target_mode="subnet", scan_profile="lan")

    with pytest.raises(pydantic.ValidationError):
        ScanResult.model_validate(payload)


def test_scan_result_rejects_devices_field_without_hosts():
    payload = _base_payload()
    del payload["hosts"]
    payload["devices"] = payload.pop("hosts", [])

    with pytest.raises(pydantic.ValidationError):
        ScanResult.model_validate(payload)


def test_host_importable_from_api_schemas():
    host = Host(ip="10.0.0.1", hostname="router", vendor="Acme", mac=None)

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
        artifacts=[],
        enrichment_jobs=[],
    )

    assert detail.scan_mode == "standard"
    assert detail.status == "complete"
