"""Tests for agent.tui.screens.scan_view — S7 full scan view."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import uuid4

from agent.normalize.contracts import (
    FindingPayload,
    HostPayload,
    ModbusDeviceIdentificationPayload,
    ModbusTcpServicePayload,
    ModbusUnitPayload,
    PortPayload,
    ScanPayload,
)
from agent.tui.screens.scan_view import ScanViewScreen


def _make_payload() -> ScanPayload:
    return ScanPayload(
        scan_id=uuid4(),
        timestamp=datetime(2026, 5, 3, 14, 30, 0, tzinfo=timezone.utc),
        subnet="192.168.1.0/24",
        scan_mode="quick",
        hosts=[
            HostPayload(
                ip="192.168.1.1",
                hostname="router.local",
                vendor="Netgear",
                ports=[
                    PortPayload(
                        port=22,
                        protocol="tcp",
                        state="open",
                        service="ssh",
                        version="OpenSSH 8.9",
                    ),
                    PortPayload(
                        port=80,
                        protocol="tcp",
                        state="open",
                        service="http",
                        version="nginx 1.24",
                    ),
                ],
            ),
        ],
        findings=[
            FindingPayload(
                ip="192.168.1.1",
                port=22,
                protocol="tcp",
                service="ssh",
                severity="high",
                cve_id="CVE-2023-12345",
                cvss_score=8.5,
                title="Weak SSH key exchange",
                description="Server uses deprecated key exchange algorithm",
                recommendation="Update SSH config to disable weak algorithms",
                evidence="Key exchange: diffie-hellman-group1-sha1",
            ),
        ],
        metadata={"hosts_discovered": 1, "findings_count": 1, "elapsed_seconds": 12},
    )


def test_render_contains_target_and_date():
    screen = ScanViewScreen(payload=_make_payload())
    rendered = screen._render_payload(_make_payload())
    assert "192.168.1.0/24" in rendered
    assert "2026-05-03 14:30:00 UTC" in rendered
    assert "Quick" in rendered


def test_render_shows_max_mode_label():
    payload = _make_payload()
    payload.scan_mode = "max"
    rendered = ScanViewScreen(payload=payload)._render_payload(payload)
    assert "MAX" in rendered


def test_render_contains_device_info():
    rendered = ScanViewScreen(payload=_make_payload())._render_payload(_make_payload())
    assert "192.168.1.1" in rendered
    assert "router.local" in rendered
    assert "Netgear" in rendered


def test_render_contains_ports():
    rendered = ScanViewScreen(payload=_make_payload())._render_payload(_make_payload())
    assert "22/tcp" in rendered
    assert "ssh" in rendered
    assert "OpenSSH 8.9" in rendered
    assert "80/tcp" in rendered
    assert "http" in rendered


def test_render_contains_vulnerability():
    rendered = ScanViewScreen(payload=_make_payload())._render_payload(_make_payload())
    assert "CVE-2023-12345" in rendered
    assert "HIGH" in rendered
    assert "8.5" in rendered
    assert "Weak SSH key exchange" in rendered


def test_render_contains_summary():
    rendered = ScanViewScreen(payload=_make_payload())._render_payload(_make_payload())
    assert "Total devices:" in rendered
    assert "Total open ports:" in rendered
    assert "Vulnerabilities found:" in rendered


def test_render_contains_plain_language_modbus_inventory():
    payload = _make_payload()
    payload.scan_mode = "nspi"
    payload.hosts[0].industrial_services = [
        ModbusTcpServicePayload(
            port=502,
            confidence="confirmed",
            evidence_sources=["modbus-discover", "pymodbus"],
            units=[
                ModbusUnitPayload(
                    unit_id=7,
                    status="responding",
                    device_identification=ModbusDeviceIdentificationPayload(
                        vendor_name="Schneider Electric",
                        product_code="BMX P34",
                        major_minor_revision="2.60",
                    ),
                )
            ],
        )
    ]

    rendered = ScanViewScreen(payload=payload)._render_payload(payload)

    assert "Industrial inventory:" in rendered
    assert "Modbus TCP 502 - CONFIRMED" in rendered
    assert "Unit ID 7: responding" in rendered
    assert "vendor Schneider Electric" in rendered
    assert "product BMX P34" in rendered
    assert "firmware 2.60" in rendered
    assert "Modbus services:        1" in rendered
    assert "Modbus Unit IDs:        1" in rendered


def test_render_no_raw_json():
    rendered = ScanViewScreen(payload=_make_payload())._render_payload(_make_payload())
    assert '": ' not in rendered
    assert '{"' not in rendered


def test_load_from_file(tmp_path):
    payload = _make_payload()
    file_path = tmp_path / "scan.json"
    file_path.write_text(
        json.dumps(payload.model_dump(mode="json"), indent=2), encoding="utf-8"
    )
    screen = ScanViewScreen(scan_path=file_path)
    loaded = screen._load_payload()
    assert loaded is not None
    assert loaded.subnet == "192.168.1.0/24"
    assert len(loaded.hosts) == 1


def test_load_prefers_payload_over_file(tmp_path):
    payload = _make_payload()
    file_path = tmp_path / "scan.json"
    file_path.write_text("{}", encoding="utf-8")
    screen = ScanViewScreen(scan_path=file_path, payload=payload)
    loaded = screen._load_payload()
    assert loaded is not None
    assert loaded.subnet == "192.168.1.0/24"
