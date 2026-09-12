"""Tests for agent.tui.screens.scan_view — S7 full scan view."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import agent.tui.app as _agent_app
import pytest
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
from agent.tui.screens.scan_view import NOTICE_MANY, NOTICE_ONE, ScanViewScreen
from textual.app import App
from textual.widgets import Static


class _Harness(App[None]):
    CSS_PATH = Path(_agent_app.__file__).parent / "app.tcss"

    def __init__(self, screen: ScanViewScreen) -> None:
        super().__init__()
        self._target_screen = screen

    def on_mount(self) -> None:
        self.push_screen(self._target_screen)


@pytest.fixture(autouse=True)
def _no_animations(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TEXTUAL_ANIMATIONS", "none")


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


def test_render_contains_full_operating_system_detection_in_fixed_order():
    payload = _make_payload()
    payload.hosts[0].operating_system = OperatingSystemDetection(
        name="Linux 5.10 - 5.15",
        accuracy=98,
        vendor="Linux",
        family="Linux",
        generation="5.X",
        device_type="specialized",
        cpes=[
            "cpe:/o:linux:linux_kernel:5",
            "cpe:/o:linux:linux_kernel:5.15",
        ],
    )

    rendered = ScanViewScreen(payload=payload)._render_payload(payload)

    expected_block = "\n".join(
        [
            "  Operating system:",
            "    Detected: Linux 5.10 - 5.15 (98% confidence)",
            "    Vendor: Linux",
            "    Family: Linux",
            "    Generation: 5.X",
            "    Device type: specialized",
            "    Platform IDs:",
            "      - cpe:/o:linux:linux_kernel:5",
            "      - cpe:/o:linux:linux_kernel:5.15",
            "  Ports:",
        ]
    )
    assert expected_block in rendered
    assert rendered.count("    Platform IDs:") == 1


def test_render_minimal_operating_system_omits_optional_labels():
    payload = _make_payload()
    payload.hosts[0].operating_system = OperatingSystemDetection(
        name="FreeBSD 13.2",
        accuracy=87,
    )

    rendered = ScanViewScreen(payload=payload)._render_payload(payload)

    assert (
        "  Operating system:\n"
        "    Detected: FreeBSD 13.2 (87% confidence)\n"
        "  Ports:" in rendered
    )
    assert "    Vendor:" not in rendered
    assert "    Family:" not in rendered
    assert "    Generation:" not in rendered
    assert "    Device type:" not in rendered
    assert "    Platform IDs:" not in rendered


def test_render_absent_and_legacy_operating_system_as_not_detected():
    payload = _make_payload()
    legacy_data = payload.model_dump(mode="json")
    legacy_data["hosts"][0].pop("operating_system")
    legacy_payload = ScanPayload.model_validate(legacy_data)

    current_rendered = ScanViewScreen(payload=payload)._render_payload(payload)
    legacy_rendered = ScanViewScreen(payload=legacy_payload)._render_payload(
        legacy_payload
    )

    assert current_rendered.count("  Operating system: Not detected") == 1
    assert legacy_rendered.count("  Operating system: Not detected") == 1
    assert "  Operating system: Not detected\n  Ports:" in current_rendered
    assert "  Operating system: Not detected\n  Ports:" in legacy_rendered


def test_render_keeps_mixed_host_operating_systems_associated():
    payload = _make_payload()
    payload.hosts[0].operating_system = OperatingSystemDetection(
        name="RouterOS 7",
        accuracy=95,
    )
    payload.hosts.append(
        HostPayload(
            ip="192.168.1.2",
            hostname="printer.local",
            vendor="HP",
            ports=[],
        )
    )

    rendered = ScanViewScreen(payload=payload)._render_payload(payload)
    router_start = rendered.index("192.168.1.1")
    printer_start = rendered.index("192.168.1.2")
    router_section = rendered[router_start:printer_start]
    printer_section = rendered[printer_start:]

    assert "Detected: RouterOS 7 (95% confidence)" in router_section
    assert "Operating system: Not detected" not in router_section
    assert "Operating system: Not detected" in printer_section
    assert "Detected: RouterOS 7" not in printer_section
    assert rendered.count("  Operating system:") == 2


def test_render_partial_payload_shows_available_operating_system_evidence():
    payload = _make_payload()
    payload.metadata = {
        "partial_result": True,
        "terminated_by": "timeout",
        "interrupted_stage": "deep_inspection",
    }
    payload.hosts[0].operating_system = OperatingSystemDetection(
        name="Linux 6.1",
        accuracy=92,
    )
    payload.hosts.append(
        HostPayload(
            ip="192.168.1.2",
            hostname="legacy-plc.local",
            vendor="Schneider Electric",
            ports=[
                PortPayload(
                    port=502,
                    protocol="tcp",
                    state="open",
                    service="modbus",
                )
            ],
        )
    )

    rendered = ScanViewScreen(payload=payload)._render_payload(payload)
    detected_start = rendered.index("192.168.1.1")
    absent_start = rendered.index("192.168.1.2")
    detected_section = rendered[detected_start:absent_start]
    absent_section = rendered[absent_start:]

    assert "Detected: Linux 6.1 (92% confidence)" in detected_section
    assert "Operating system: Not detected" not in detected_section
    assert "Operating system: Not detected\n  Ports:" in absent_section
    assert "502/tcp" in absent_section
    assert "Detected: Linux 6.1" not in absent_section
    assert "timeout" not in rendered


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
            mapping_source="generic_baseline",
            units=[
                ModbusUnitPayload(
                    unit_id=7,
                    status="responding",
                    device_identification=ModbusDeviceIdentificationPayload(
                        vendor_name="Schneider Electric",
                        product_code="BMX P34",
                        major_minor_revision="2.60",
                    ),
                    address_ranges=[
                        ModbusAddressRangePayload(
                            address_space="holding_register",
                            start_address=0,
                            count=4,
                            status="readable",
                            value_digest=(
                                "hmac-sha256:"
                                "a1b2c3d4e5f6789012345678901234567890abcdef1234567890abcdef123456"
                            ),
                            observed_at=datetime.now(timezone.utc),
                        )
                    ],
                )
            ],
        )
    ]

    rendered = ScanViewScreen(payload=payload)._render_payload(payload)

    assert "Industrial inventory:" in rendered
    assert "Modbus TCP 502 - CONFIRMED" in rendered
    assert "Mapping plan: generic_baseline" in rendered
    assert "Unit ID 7: responding" in rendered
    assert "vendor Schneider Electric" in rendered
    assert "product BMX P34" in rendered
    assert "firmware 2.60" in rendered
    assert "holding_register 0-3: readable" in rendered
    assert "digest a1b2c3d4" in rendered
    assert "Modbus services:        1" in rendered
    assert "Modbus Unit IDs:        1" in rendered
    assert "Modbus mapped ranges:   1" in rendered


def test_render_no_raw_json():
    rendered = ScanViewScreen(payload=_make_payload())._render_payload(_make_payload())
    assert '": ' not in rendered
    assert '{"' not in rendered


def test_load_from_file(tmp_path):
    payload = _make_payload()
    payload.hosts[0].operating_system = OperatingSystemDetection(
        name="Linux 5.10 - 5.15",
        accuracy=98,
        cpes=["cpe:/o:linux:linux_kernel:5"],
    )
    file_path = tmp_path / "scan.json"
    file_path.write_text(
        json.dumps(payload.model_dump(mode="json"), indent=2), encoding="utf-8"
    )
    screen = ScanViewScreen(scan_path=file_path)
    loaded = screen._load_payload()
    assert loaded is not None
    assert loaded.subnet == "192.168.1.0/24"
    assert len(loaded.hosts) == 1
    assert loaded.hosts[0].operating_system == payload.hosts[0].operating_system
    assert (
        "  Operating system:\n"
        "    Detected: Linux 5.10 - 5.15 (98% confidence)\n"
        "    Platform IDs:\n"
        "      - cpe:/o:linux:linux_kernel:5\n"
        "  Ports:" in screen._render_payload(loaded)
    )


def test_load_prefers_payload_over_file(tmp_path):
    payload = _make_payload()
    file_path = tmp_path / "scan.json"
    file_path.write_text("{}", encoding="utf-8")
    screen = ScanViewScreen(scan_path=file_path, payload=payload)
    loaded = screen._load_payload()
    assert loaded is not None
    assert loaded.subnet == "192.168.1.0/24"


def test_render_escapes_hostile_vendor_markup():
    payload = _make_payload()
    payload.hosts[0].vendor = "Acme [/nope] Ltd"

    rendered = ScanViewScreen(payload=payload)._render_payload(payload)

    assert "\\[/nope]" in rendered


@pytest.mark.asyncio
async def test_mount_renders_hostile_vendor_without_markup_error():
    payload = _make_payload()
    payload.hosts[0].vendor = "Acme [/nope] Ltd"
    screen = ScanViewScreen(payload=payload)

    async with _Harness(screen).run_test() as pilot:
        await pilot.pause()
        content = screen.query_one("#scan-view-content", Static)
        assert "[/nope]" in str(content.render())


def test_render_modbus_range_has_no_process_statistics():
    payload = _make_payload()
    payload.scan_mode = "nspi"
    payload.hosts[0].industrial_services = [
        ModbusTcpServicePayload(
            port=502,
            confidence="confirmed",
            units=[
                ModbusUnitPayload(
                    unit_id=1,
                    status="responding",
                    address_ranges=[
                        ModbusAddressRangePayload(
                            address_space="holding_register",
                            start_address=0,
                            count=16,
                            status="readable",
                            value_digest=(
                                "hmac-sha256:"
                                "a1b2c3d4e5f6789012345678901234567890abcdef1234567890abcdef123456"
                            ),
                            observed_at=datetime.now(timezone.utc),
                        )
                    ],
                )
            ],
        )
    ]

    rendered = ScanViewScreen(payload=payload)._render_payload(payload)

    assert "digest a1b2c3d4" in rendered
    assert "nonzero " not in rendered
    assert "min " not in rendered
    assert "max " not in rendered


def test_render_readable_range_without_digest_shows_not_recorded():
    payload = _make_payload()
    payload.scan_mode = "nspi"
    payload.hosts[0].industrial_services = [
        ModbusTcpServicePayload(
            port=502,
            confidence="confirmed",
            units=[
                ModbusUnitPayload(
                    unit_id=1,
                    status="responding",
                    address_ranges=[
                        ModbusAddressRangePayload(
                            address_space="holding_register",
                            start_address=0,
                            count=4,
                            status="readable",
                            observed_at=datetime.now(timezone.utc),
                        )
                    ],
                )
            ],
        )
    ]

    rendered = ScanViewScreen(payload=payload)._render_payload(payload)

    assert "digest not recorded" in rendered


@pytest.mark.asyncio
async def test_mount_shows_notice_when_values_shortened():
    payload = _make_payload()
    payload.hosts[0].vendor = "V" * 70
    screen = ScanViewScreen(payload=payload)

    async with _Harness(screen).run_test() as pilot:
        await pilot.pause()
        notice = screen.query_one("#scan-view-notice", Static)
        assert notice.display is True
        assert NOTICE_ONE in str(notice.render())


@pytest.mark.asyncio
async def test_mount_shows_plural_notice_when_multiple_values_shortened():
    payload = _make_payload()
    payload.hosts[0].vendor = "V" * 70
    payload.hosts[0].hostname = "h" * 70
    screen = ScanViewScreen(payload=payload)

    async with _Harness(screen).run_test() as pilot:
        await pilot.pause()
        notice = screen.query_one("#scan-view-notice", Static)
        assert notice.display is True
        assert NOTICE_MANY.format(count=2) in str(notice.render())


@pytest.mark.asyncio
async def test_mount_hides_notice_when_nothing_shortened():
    screen = ScanViewScreen(payload=_make_payload())

    async with _Harness(screen).run_test() as pilot:
        await pilot.pause()
        notice = screen.query_one("#scan-view-notice", Static)
        assert notice.display is False


@pytest.mark.asyncio
async def test_mount_shows_process_note_when_address_ranges_exist():
    payload = _make_payload()
    payload.scan_mode = "nspi"
    payload.hosts[0].industrial_services = [
        ModbusTcpServicePayload(
            port=502,
            confidence="confirmed",
            units=[
                ModbusUnitPayload(
                    unit_id=1,
                    status="responding",
                    address_ranges=[
                        ModbusAddressRangePayload(
                            address_space="coil",
                            start_address=0,
                            count=1,
                            status="readable",
                            observed_at=datetime.now(timezone.utc),
                        )
                    ],
                )
            ],
        )
    ]
    screen = ScanViewScreen(payload=payload)

    async with _Harness(screen).run_test() as pilot:
        await pilot.pause()
        note = screen.query_one("#scan-view-process-note", Static)
        assert note.display is True


def test_render_limits_line_from_metadata_flag():
    payload = _make_payload()
    payload.metadata = {
        "elapsed_seconds": 187,
        "modbus_stage_deadline_reached": True,
        "modbus_stage_deadline_seconds": 90,
    }

    rendered = ScanViewScreen(payload=payload)._render_payload(payload)

    assert (
        "Limits:   Time limit reached during Modbus inventory (90s)" in rendered
    )


def test_render_omits_limits_line_without_metadata_flag():
    payload = _make_payload()
    payload.metadata = {"elapsed_seconds": 12}

    rendered = ScanViewScreen(payload=payload)._render_payload(payload)

    assert "Limits:" not in rendered
