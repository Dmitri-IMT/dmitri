from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from agent.normalize.contracts import (
    DevicePayload,
    FindingPayload,
    PortPayload,
    ScanPayload,
)
from agent.scanner.progress import ScanEvent
from agent.tui.screens.scan_progress import ScanProgressScreen
from textual.app import App
from textual.css.query import NoMatches
from textual.widgets import ProgressBar, RichLog, Static


class _Harness(App[None]):
    def __init__(self, screen: ScanProgressScreen) -> None:
        super().__init__()
        self._target_screen = screen

    def on_mount(self) -> None:
        self.push_screen(self._target_screen)


@pytest.fixture(autouse=True)
def _no_animations(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TEXTUAL_ANIMATIONS", "none")


@pytest.fixture(autouse=True)
def _no_real_scan(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "agent.tui.screens.scan_progress.ScanRunner.start", lambda self: None
    )
    monkeypatch.setattr(
        "agent.tui.screens.scan_progress.load_config", lambda: None
    )


def _make_screen(scan_mode: str = "max", subnet: str = "192.168.1.0/24"):
    return ScanProgressScreen(subnet, scan_mode)


def _log_text(screen: ScanProgressScreen) -> str:
    log = screen.query_one("#activity-log", RichLog)
    return "\n".join(strip.text for strip in log.lines)


async def _post(pilot, screen: ScanProgressScreen, event: ScanEvent) -> None:
    screen.post_message(ScanProgressScreen.ProgressUpdated(event))
    await pilot.pause()


def _make_payload(n_devices: int, n_findings: int) -> ScanPayload:
    devices = [
        DevicePayload(
            ip=f"192.168.1.{i + 1}",
            hostname=f"host-{i}.local",
            vendor="ACME",
            ports=[
                PortPayload(
                    port=22,
                    protocol="tcp",
                    state="open",
                    service="ssh",
                    version="OpenSSH 8.9",
                ),
            ],
        )
        for i in range(n_devices)
    ]
    findings = [
        FindingPayload(
            ip=f"192.168.1.{i + 1}",
            port=22,
            protocol="tcp",
            service="ssh",
            severity="high",
            cve_id=f"CVE-2023-000{i}",
            cvss_score=8.5,
            title="Weak SSH key exchange",
            description="Server uses deprecated key exchange algorithm",
            recommendation="Update SSH config",
            evidence="diffie-hellman-group1-sha1",
        )
        for i in range(n_findings)
    ]
    return ScanPayload(
        scan_id=uuid4(),
        timestamp=datetime(2026, 5, 3, 14, 30, 0, tzinfo=timezone.utc),
        subnet="192.168.1.0/24",
        scan_mode="max",
        devices=devices,
        findings=findings,
        metadata={"hosts_discovered": n_devices, "findings_count": n_findings},
    )


class TestMountLayout:
    @pytest.mark.asyncio
    async def test_core_widgets_present_on_mount(self) -> None:
        screen = _make_screen()
        async with _Harness(screen).run_test() as pilot:
            await pilot.pause()
            assert screen.query_one("#scan-header", Static)
            assert screen.query_one("#progress-row")
            assert screen.query_one("#progress-bar", ProgressBar)
            assert screen.query_one("#activity-log", RichLog)

    @pytest.mark.asyncio
    async def test_phase_widgets_removed(self) -> None:
        screen = _make_screen()
        async with _Harness(screen).run_test() as pilot:
            await pilot.pause()
            for phase in (
                "#phase-discovery",
                "#phase-port_scan",
                "#phase-deep_inspection",
                "#phase-normalizing",
                "#phase-completed",
            ):
                with pytest.raises(NoMatches):
                    screen.query_one(phase)

    @pytest.mark.asyncio
    async def test_done_actions_hidden_on_mount(self) -> None:
        screen = _make_screen()
        async with _Harness(screen).run_test() as pilot:
            await pilot.pause()
            assert screen.query_one("#scan-done-actions").display is False

    @pytest.mark.asyncio
    async def test_header_renders_mode_label_and_subnet(self) -> None:
        screen = _make_screen(scan_mode="max", subnet="192.168.1.0/24")
        async with _Harness(screen).run_test() as pilot:
            await pilot.pause()
            header = screen.query_one("#scan-header", Static)
            assert "Mode: MAX · 192.168.1.0/24" in str(header.render())


class TestActivityLog:
    @pytest.mark.asyncio
    async def test_discovery_line_replaced_on_complete(self) -> None:
        screen = _make_screen()
        async with _Harness(screen).run_test() as pilot:
            await pilot.pause()
            await _post(pilot, screen, ScanEvent(kind="discovery_started"))
            await _post(
                pilot, screen, ScanEvent(kind="hosts_found", hosts_total=3)
            )
            text = _log_text(screen)
            assert "3 hosts found" in text
            assert "Finding hosts" not in text

    @pytest.mark.asyncio
    async def test_no_hosts_line(self) -> None:
        screen = _make_screen()
        async with _Harness(screen).run_test() as pilot:
            await pilot.pause()
            await _post(
                pilot, screen, ScanEvent(kind="hosts_found", hosts_total=0)
            )
            assert "No hosts found" in _log_text(screen)

    @pytest.mark.asyncio
    async def test_host_inspected_line(self) -> None:
        screen = _make_screen()
        async with _Harness(screen).run_test() as pilot:
            await pilot.pause()
            await _post(
                pilot,
                screen,
                ScanEvent(
                    kind="host_inspected",
                    hosts_done=2,
                    hosts_total=4,
                    ip="192.168.1.5",
                ),
            )
            assert "Scanned 192.168.1.5 (2/4)" in _log_text(screen)

    @pytest.mark.asyncio
    async def test_port_stage_all_ports_for_max(self) -> None:
        screen = _make_screen(scan_mode="max")
        async with _Harness(screen).run_test() as pilot:
            await pilot.pause()
            await _post(pilot, screen, ScanEvent(kind="port_stage_started"))
            assert "Scanning all ports" in _log_text(screen)

    @pytest.mark.asyncio
    async def test_port_stage_default_copy_for_quick(self) -> None:
        screen = _make_screen(scan_mode="quick")
        async with _Harness(screen).run_test() as pilot:
            await pilot.pause()
            await _post(pilot, screen, ScanEvent(kind="port_stage_started"))
            text = _log_text(screen)
            assert "Scanning ports" in text
            assert "all ports" not in text


class TestProgressTarget:
    @pytest.mark.asyncio
    async def test_target_pct_after_port_stage_done_max(self) -> None:
        screen = _make_screen(scan_mode="max")
        async with _Harness(screen).run_test() as pilot:
            await pilot.pause()
            await _post(pilot, screen, ScanEvent(kind="port_stage_done", ports_open=7))
            assert screen._target_pct == 60.0

    @pytest.mark.asyncio
    async def test_target_pct_after_port_stage_done_quick(self) -> None:
        screen = _make_screen(scan_mode="quick")
        async with _Harness(screen).run_test() as pilot:
            await pilot.pause()
            await _post(pilot, screen, ScanEvent(kind="port_stage_done", ports_open=2))
            assert screen._target_pct == 65.0


class TestCompletion:
    @pytest.mark.asyncio
    async def test_complete_replaces_generating_results_line(self) -> None:
        screen = _make_screen()
        payload = _make_payload(2, 3)
        async with _Harness(screen).run_test() as pilot:
            await pilot.pause()
            await _post(pilot, screen, ScanEvent(kind="normalize_started"))
            screen._handle_complete(payload)
            await pilot.pause()
            text = _log_text(screen)
            assert "Done — 2 devices, 3 vulnerabilities" in text
            assert "Generating results" not in text

    @pytest.mark.asyncio
    async def test_complete_before_normalize_started_skips_spinner_line(self) -> None:
        screen = _make_screen()
        payload = _make_payload(2, 3)
        async with _Harness(screen).run_test() as pilot:
            await pilot.pause()
            screen._handle_complete(payload)
            await _post(pilot, screen, ScanEvent(kind="normalize_started"))
            await pilot.pause()
            text = _log_text(screen)
            assert "Done — 2 devices, 3 vulnerabilities" in text
            assert "Generating results" not in text

    @pytest.mark.asyncio
    async def test_complete_sets_terminal_state(self) -> None:
        screen = _make_screen()
        payload = _make_payload(2, 3)
        async with _Harness(screen).run_test() as pilot:
            await pilot.pause()
            screen._handle_complete(payload)
            await pilot.pause()
            assert screen.query_one("#progress-bar", ProgressBar).progress == 100
            assert screen.query_one("#scan-done-actions").display is True
            assert (
                "Done — 2 devices, 3 vulnerabilities" in _log_text(screen)
            )
            assert screen._done is True


class TestFailure:
    @pytest.mark.asyncio
    async def test_error_handler_does_not_dismiss_or_complete(self) -> None:
        screen = _make_screen()
        async with _Harness(screen).run_test() as pilot:
            await pilot.pause()
            await _post(pilot, screen, ScanEvent(kind="discovery_started"))
            await _post(
                pilot, screen, ScanEvent(kind="hosts_found", hosts_total=3)
            )
            screen._handle_error(RuntimeError("boom"))
            await pilot.pause()
            assert pilot.app.screen is screen
            assert screen.query_one("#progress-bar", ProgressBar).progress != 100
            assert screen._done is False

    @pytest.mark.asyncio
    async def test_failed_event_writes_line(self) -> None:
        screen = _make_screen()
        async with _Harness(screen).run_test() as pilot:
            await pilot.pause()
            await _post(
                pilot,
                screen,
                ScanEvent(kind="failed", message="Scan failed: boom"),
            )
            assert "Scan failed: boom" in _log_text(screen)
            assert screen.query_one("#progress-bar", ProgressBar).progress != 100
