"""Unit tests for the local scan assessment summary."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import agent.tui.app as _agent_app
import pytest
from agent.normalize.contracts import (
    AssessmentEvidencePayload,
    DeviceProfilePayload,
    ExposurePayload,
    FindingPayload,
    HostPayload,
    PortPayload,
    ScanPayload,
)
from agent.tui.screens.scan_view import ScanViewScreen
from rich.text import Text
from textual.app import App
from textual.widgets import OptionList, Static


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


def _profile(confidence: str = "high") -> DeviceProfilePayload:
    return DeviceProfilePayload(
        manufacturer="Netgear",
        product_family="Router family",
        confidence=confidence,
        evidence=[
            AssessmentEvidencePayload(
                kind="manufacturer", source="mac_vendor", value="Netgear"
            )
        ],
    )


def _current_payload(*, findings: bool = True) -> ScanPayload:
    host = HostPayload(
        ip="192.168.1.1",
        hostname="router.local",
        vendor="Netgear",
        machine_type="router",
        device_profile=_profile(),
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
            ),
        ],
    )
    finding_list = (
        [
            FindingPayload(
                ip=host.ip,
                port=22,
                protocol="tcp",
                service="ssh",
                severity="high",
                cve_id="CVE-2023-12345",
                cvss_score=8.5,
                title="Weak SSH key exchange",
                description="A deprecated exchange is enabled",
                recommendation="Disable the deprecated exchange",
                evidence="diffie-hellman-group1-sha1",
            )
        ]
        if findings
        else []
    )
    return ScanPayload(
        scan_id=uuid4(),
        timestamp=datetime(2026, 5, 3, 14, 30, tzinfo=timezone.utc),
        subnet="192.168.1.0/24",
        scan_mode="quick",
        hosts=[host],
        findings=finding_list,
        assessment_policy_version="2026-09-15.1",
        exposures=[
            ExposurePayload(
                ip=host.ip,
                port=22,
                protocol="tcp",
                observed_service="ssh",
                observed_version="OpenSSH 8.9",
                role="remote_access",
                attention="review",
                confidence="high",
                reason="A remote-access service is reachable.",
            ),
            ExposurePayload(
                ip=host.ip,
                port=80,
                protocol="tcp",
                observed_service="http",
                role="general_service",
                attention="informational",
                confidence="low",
                reason="A general service is reachable.",
            ),
        ],
        metadata={"elapsed_seconds": 12},
    )


def _legacy_payload() -> ScanPayload:
    data = _current_payload(findings=False).model_dump(mode="json")
    data["assessment_policy_version"] = None
    data["exposures"] = []
    data["hosts"][0]["machine_type"] = None
    data["hosts"][0]["device_profile"] = None
    return ScanPayload.model_validate(data)


def test_summary_keeps_inventory_exposures_and_findings_separate() -> None:
    payload = _current_payload()

    rendered = Text.from_markup(
        ScanViewScreen(payload=payload)._render_payload(payload)
    ).plain

    assert "Inventory: 1 device · 2 open endpoints" in rendered
    assert "Attack surface: 2 exposures · 1 needs attention" in rendered
    assert "Vulnerability findings: 1 finding" in rendered
    assert "2 findings" not in rendered
    assert "safe" not in rendered.casefold()
    assert "clean" not in rendered.casefold()


def test_summary_counts_duplicate_raw_ports_as_one_endpoint() -> None:
    payload = _current_payload()
    payload.hosts[0].ports.append(payload.hosts[0].ports[0].model_copy(deep=True))

    rendered = Text.from_markup(
        ScanViewScreen(payload=payload)._render_payload(payload)
    ).plain

    assert "Inventory: 1 device · 2 open endpoints" in rendered


def test_summary_counts_endpoint_identity_across_hosts_protocols_and_states() -> None:
    payload = _current_payload()
    first = payload.hosts[0]
    first.ports.extend(
        [
            first.ports[0].model_copy(deep=True),
            PortPayload(port=443, protocol="tcp", state="closed", service="https"),
        ]
    )
    second = HostPayload(
        ip="192.168.1.2",
        hostname="second.local",
        vendor="Unknown",
        machine_type="unknown",
        device_profile=DeviceProfilePayload(confidence="low"),
        ports=[
            PortPayload(port=22, protocol="tcp", state="open", service="ssh"),
            PortPayload(port=22, protocol="udp", state="open", service="unknown"),
            PortPayload(port=53, protocol="udp", state="filtered", service="domain"),
        ],
    )
    payload.hosts.extend([second, second.model_copy(deep=True)])

    rendered = Text.from_markup(
        ScanViewScreen(payload=payload)._render_payload(payload)
    ).plain

    # Duplicate rows collapse, while host and protocol remain endpoint identity axes.
    assert "Inventory: 3 devices · 4 open endpoints" in rendered


def test_current_empty_is_zero_while_legacy_is_unavailable() -> None:
    current = ScanPayload(
        scan_id=uuid4(),
        timestamp=datetime(2026, 5, 3, tzinfo=timezone.utc),
        subnet="192.168.1.0/24",
        scan_mode="quick",
        assessment_policy_version="2026-09-15.1",
    )
    current_rendered = Text.from_markup(
        ScanViewScreen(payload=current)._render_payload(current)
    ).plain
    legacy = _legacy_payload()
    legacy_rendered = Text.from_markup(
        ScanViewScreen(payload=legacy)._render_payload(legacy)
    ).plain

    assert "Attack surface: 0 exposures · 0 need attention" in current_rendered
    assert "No devices were discovered." in current_rendered
    assert "Attack surface: Unavailable" in legacy_rendered
    assert "predates attack-surface analysis" in legacy_rendered
    assert "Profile unavailable · exposures unavailable" in legacy_rendered


@pytest.mark.parametrize(
    ("metadata", "expected", "unexpected"),
    [
        (
            {"partial_result": True, "terminated_by": "completed"},
            "⚠ INCOMPLETE EVIDENCE — The scan finished",
            "STOPPED SCAN",
        ),
        (
            {
                "partial_result": True,
                "terminated_by": "timeout",
                "interrupted_stage": "deep_inspection",
            },
            "■ STOPPED SCAN — Deep inspection did not finish.",
            "INCOMPLETE EVIDENCE",
        ),
        (
            {"partial_result": True, "terminated_by": "error"},
            "■ STOPPED SCAN — The scan did not finish.",
            "INCOMPLETE EVIDENCE",
        ),
    ],
)
def test_partial_terminal_semantics(
    metadata: dict[str, str | bool], expected: str, unexpected: str
) -> None:
    payload = _current_payload(findings=False)
    payload.metadata = metadata

    rendered = ScanViewScreen(payload=payload)._render_payload(payload)

    assert expected in rendered
    assert unexpected not in rendered
    assert "Counts use accepted evidence only." in rendered


@pytest.mark.asyncio
async def test_mount_uses_stable_ids_focuses_devices_and_hides_legacy_note() -> None:
    screen = ScanViewScreen(payload=_current_payload())

    async with _Harness(screen).run_test() as pilot:
        await pilot.pause()
        for widget_id in (
            "#scan-view-scroll",
            "#scan-view-container",
            "#scan-result-header",
            "#scan-partial-banner",
            "#scan-category-summary",
            "#scan-enrichment-note",
            "#scan-devices-title",
            "#scan-device-list",
            "#scan-devices-empty",
        ):
            assert screen.query_one(widget_id) is not None
        devices = screen.query_one("#scan-device-list", OptionList)
        assert devices.has_focus
        assert devices.display is True
        assert screen.query_one("#scan-devices-empty").display is False
        assert screen.query_one("#scan-enrichment-note").display is False
        summary = str(screen.query_one("#scan-category-summary", Static).render())
        assert "2 exposures" in summary
        assert "1 finding" in summary


@pytest.mark.asyncio
async def test_keyboard_navigation_opens_selected_device_and_preserves_selection(
) -> None:
    payload = _current_payload(findings=False)
    payload.hosts.append(
        HostPayload(
            ip="192.168.1.2",
            hostname="second.local",
            vendor="Unknown",
            machine_type="unknown",
            device_profile=DeviceProfilePayload(confidence="low"),
        )
    )
    screen = ScanViewScreen(payload=payload)

    async with _Harness(screen).run_test() as pilot:
        await pilot.pause()
        devices = screen.query_one("#scan-device-list", OptionList)

        await pilot.press("down")
        assert devices.highlighted == 1
        await pilot.press("up")
        assert devices.highlighted == 0
        await pilot.press("j")
        assert devices.highlighted == 1
        await pilot.press("k")
        assert devices.highlighted == 0
        await pilot.press("down", "enter")
        await pilot.pause()

        detail = pilot.app.screen
        assert detail.__class__.__name__ == "DeviceDetailScreen"
        assert detail._host.ip == payload.hosts[1].ip

        await pilot.press("escape")
        await pilot.pause()
        assert pilot.app.screen is screen
        assert devices.highlighted == 1

        await pilot.press("escape")
        await pilot.pause()
        assert pilot.app.screen is not screen


@pytest.mark.asyncio
async def test_zero_host_mount_hides_list() -> None:
    payload = ScanPayload(
        scan_id=uuid4(),
        timestamp=datetime(2026, 5, 3, tzinfo=timezone.utc),
        subnet="192.168.1.0/24",
        scan_mode="quick",
        assessment_policy_version="2026-09-15.1",
    )
    screen = ScanViewScreen(payload=payload)

    async with _Harness(screen).run_test() as pilot:
        await pilot.pause()
        assert screen.query_one("#scan-device-list").display is False
        assert screen.query_one("#scan-devices-empty").display is True
        assert "No devices were discovered." in str(
            screen.query_one("#scan-devices-empty", Static).render()
        )


def test_load_saved_current_and_legacy_payloads(tmp_path: Path) -> None:
    for payload in (_current_payload(), _legacy_payload()):
        scan_path = tmp_path / f"{payload.scan_id}.json"
        scan_path.write_text(
            json.dumps(payload.model_dump(mode="json")), encoding="utf-8"
        )

        loaded = ScanViewScreen(scan_path=scan_path)._load_payload()

        assert loaded == payload


def test_device_prompt_uses_exact_profile_and_singular_copy() -> None:
    payload = _current_payload()

    prompt = ScanViewScreen(payload=payload)._device_prompt(payload, payload.hosts[0])

    assert prompt == (
        "192.168.1.1 · Router · confidence high · 2 exposures · 1 finding"
    )
