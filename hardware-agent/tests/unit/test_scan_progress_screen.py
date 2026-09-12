from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import agent.tui.app as _agent_app
import pytest
from agent.normalize.contracts import (
    FindingPayload,
    HostPayload,
    PortPayload,
    ScanPayload,
)
from agent.scanner.progress import ScanEvent
from agent.tui.screens.scan_progress import ScanProgressScreen
from textual.app import App
from textual.css.query import NoMatches
from textual.widgets import Button, ProgressBar, RichLog, Static


class _Harness(App[None]):
    CSS_PATH = Path(_agent_app.__file__).parent / "app.tcss"

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


def _make_screen(
    scan_mode: str = "max",
    subnet: str = "192.168.1.0/24",
    nspi_submode: str | None = None,
):
    return ScanProgressScreen(subnet, scan_mode, nspi_submode=nspi_submode)


def _log_text(screen: ScanProgressScreen) -> str:
    log = screen.query_one("#activity-log", RichLog)
    return "\n".join(strip.text for strip in log.lines)


async def _post(pilot, screen: ScanProgressScreen, event: ScanEvent) -> None:
    screen.post_message(ScanProgressScreen.ProgressUpdated(event))
    await pilot.pause()


def _make_payload(n_devices: int, n_findings: int) -> ScanPayload:
    devices = [
        HostPayload(
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
        hosts=devices,
        findings=findings,
        metadata={"hosts_discovered": n_devices, "findings_count": n_findings},
    )


def _make_partial_payload(
    n_devices: int,
    n_findings: int,
    terminated_by: str,
    interrupted_stage: str | None,
    **metadata_extra,
) -> ScanPayload:
    base = _make_payload(n_devices, n_findings)
    metadata = {
        "partial_result": True,
        "terminated_by": terminated_by,
        **metadata_extra,
    }
    if interrupted_stage is not None:
        metadata["interrupted_stage"] = interrupted_stage
    return base.model_copy(update={"metadata": metadata})


def _badge_classes(screen: ScanProgressScreen) -> set[str]:
    badge = screen.query_one("#scan-badge", Static)
    return set(badge.classes)


def _badge_text(screen: ScanProgressScreen) -> str:
    return str(screen.query_one("#scan-badge", Static).render())


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

    @pytest.mark.asyncio
    async def test_modbus_inventory_stage_is_visible(self) -> None:
        screen = _make_screen(scan_mode="nspi")
        async with _Harness(screen).run_test() as pilot:
            await pilot.pause()
            await _post(
                pilot,
                screen,
                ScanEvent(kind="ot_stage_started", hosts_total=1),
            )
            await _post(
                pilot,
                screen,
                ScanEvent(
                    kind="modbus_host_inspected",
                    hosts_done=1,
                    hosts_total=1,
                    ip="192.168.1.30",
                ),
            )
            await _post(
                pilot,
                screen,
                ScanEvent(kind="ot_stage_done", units_total=1),
            )

            text = _log_text(screen)
            assert "Inventoried 192.168.1.30 (1/1)" in text
            assert "1 Modbus hosts inventoried" in text
            assert screen._target_pct == 95.0


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


class TestScanBadge:
    @pytest.mark.asyncio
    async def test_badge_hidden_while_running(self) -> None:
        screen = _make_screen()
        async with _Harness(screen).run_test() as pilot:
            await pilot.pause()
            assert screen.query_one("#scan-badge", Static).display is False

    @pytest.mark.asyncio
    async def test_badge_hidden_on_success(self) -> None:
        screen = _make_screen()
        payload = _make_payload(2, 3)
        async with _Harness(screen).run_test() as pilot:
            await pilot.pause()
            screen._handle_complete(payload)
            await pilot.pause()
            assert screen.query_one("#scan-badge", Static).display is False

    @pytest.mark.asyncio
    async def test_badge_stopped_string_for_timeout(self) -> None:
        screen = _make_screen()
        payload = _make_partial_payload(12, 7, "timeout", "deep_inspection")
        async with _Harness(screen).run_test() as pilot:
            await pilot.pause()
            screen._handle_complete(payload)
            await pilot.pause()
            badge = screen.query_one("#scan-badge", Static)
            assert badge.display is True
            text = _badge_text(screen)
            assert "STOPPED" in text
            assert "a step timed out; partial results kept" in text
            assert "badge-stopped" in _badge_classes(screen)

    @pytest.mark.asyncio
    async def test_badge_stopped_string_for_user_cancel(self) -> None:
        screen = _make_screen()
        payload = _make_partial_payload(12, 7, "user_cancel", "deep_inspection")
        async with _Harness(screen).run_test() as pilot:
            await pilot.pause()
            screen._handle_complete(payload)
            await pilot.pause()
            assert "STOPPED" in _badge_text(screen)
            assert "stopped by you; partial results kept" in _badge_text(screen)
            assert "badge-stopped" in _badge_classes(screen)

    @pytest.mark.asyncio
    async def test_badge_fatal_string(self) -> None:
        screen = _make_screen()
        async with _Harness(screen).run_test() as pilot:
            await pilot.pause()
            screen._handle_error(RuntimeError("boom"))
            await pilot.pause()
            badge = screen.query_one("#scan-badge", Static)
            assert badge.display is True
            assert "✗ SCAN FAILED — nothing to keep" in _badge_text(screen)


class TestEndActions:
    @pytest.mark.asyncio
    async def test_view_button_hidden_in_fatal(self) -> None:
        screen = _make_screen()
        async with _Harness(screen).run_test() as pilot:
            await pilot.pause()
            screen._handle_error(RuntimeError("boom"))
            await pilot.pause()
            assert screen.query_one("#btn-view-scan", Button).display is False
            assert screen.query_one("#btn-back-home", Button).display is True
            assert screen.query_one("#scan-done-actions").display is True

    @pytest.mark.asyncio
    async def test_fatal_shows_only_back_home(self) -> None:
        screen = _make_screen()
        async with _Harness(screen).run_test() as pilot:
            await pilot.pause()
            screen._handle_error(RuntimeError("boom"))
            await pilot.pause()
            visible = [
                button_id
                for button_id in ("btn-view-scan", "btn-back-home")
                if screen.query_one(f"#{button_id}", Button).display
            ]
            assert visible == ["btn-back-home"]

    @pytest.mark.asyncio
    async def test_view_button_shown_and_labelled_in_partial(self) -> None:
        screen = _make_screen()
        payload = _make_partial_payload(12, 7, "timeout", "deep_inspection")
        async with _Harness(screen).run_test() as pilot:
            await pilot.pause()
            screen._handle_complete(payload)
            await pilot.pause()
            view = screen.query_one("#btn-view-scan", Button)
            assert view.display is True
            assert str(view.label) == "View partial scan"
            assert screen.query_one("#scan-done-actions").display is True


class TestProgressBarTerminal:
    @pytest.mark.asyncio
    async def test_bar_not_100_in_partial(self) -> None:
        screen = _make_screen()
        payload = _make_partial_payload(12, 7, "timeout", "deep_inspection")
        async with _Harness(screen).run_test() as pilot:
            await pilot.pause()
            bar = screen.query_one("#progress-bar", ProgressBar)
            bar.update(progress=62)
            screen._display_pct = 62.0
            screen._target_pct = 62.0
            screen._handle_complete(payload)
            await pilot.pause()
            assert bar.progress == 62
            assert bar.progress != 100

    @pytest.mark.asyncio
    async def test_bar_not_100_in_fatal(self) -> None:
        screen = _make_screen()
        async with _Harness(screen).run_test() as pilot:
            await pilot.pause()
            bar = screen.query_one("#progress-bar", ProgressBar)
            bar.update(progress=6)
            screen._display_pct = 6.0
            screen._target_pct = 6.0
            screen._handle_error(RuntimeError("boom"))
            await pilot.pause()
            assert bar.progress == 6
            assert bar.progress != 100

    @pytest.mark.asyncio
    async def test_bar_100_only_on_completed(self) -> None:
        screen = _make_screen()
        payload = _make_payload(2, 3)
        async with _Harness(screen).run_test() as pilot:
            await pilot.pause()
            screen._handle_complete(payload)
            await pilot.pause()
            assert screen.query_one("#progress-bar", ProgressBar).progress == 100


class TestCancelling:
    @pytest.mark.asyncio
    async def test_abort_while_running_enters_cancelling(self) -> None:
        screen = _make_screen()
        async with _Harness(screen).run_test() as pilot:
            await pilot.pause()
            await _post(pilot, screen, ScanEvent(kind="port_stage_started"))
            calls = []
            screen._runner.request_cancel = lambda: calls.append(1)
            await pilot.press("ctrl+x")
            assert screen._state == "cancelling"
            assert screen._terminal() is False
            assert (
                "Stopping scan — saving partial results, no new probes will start…"
                in _log_text(screen)
            )
            badge = screen.query_one("#scan-badge", Static)
            assert badge.display is True
            badge_text = _badge_text(screen)
            assert "CANCELLING" in badge_text
            assert "saving partial results…" in badge_text
            assert "ports" in screen._active_stages
            assert calls == [1]
            assert pilot.app.screen is screen

    @pytest.mark.asyncio
    async def test_second_ctrl_x_ignored_while_cancelling(self) -> None:
        screen = _make_screen()
        async with _Harness(screen).run_test() as pilot:
            await pilot.pause()
            calls = []
            screen._runner.request_cancel = lambda: calls.append(1)
            await pilot.press("ctrl+x")
            await pilot.press("ctrl+x")
            assert calls == [1]
            assert screen._state == "cancelling"
            assert pilot.app.screen is screen

    @pytest.mark.asyncio
    async def test_cancelling_resolves_to_partial_on_callback(self) -> None:
        screen = _make_screen()
        payload = _make_partial_payload(12, 7, "user_cancel", "deep_inspection")
        async with _Harness(screen).run_test() as pilot:
            await pilot.pause()
            screen._runner.request_cancel = lambda: None
            await pilot.press("ctrl+x")
            assert screen._state == "cancelling"
            screen._handle_complete(payload)
            await pilot.pause()
            assert screen._state == "stopped"
            assert screen.query_one("#scan-badge", Static).display is True


class TestIncompleteEvidence:
    @pytest.mark.asyncio
    async def test_completed_partial_shows_finished_not_stopped(self) -> None:
        screen = _make_screen()
        payload = _make_partial_payload(12, 7, "completed", None)
        async with _Harness(screen).run_test() as pilot:
            await pilot.pause()
            screen._handle_complete(payload)
            await pilot.pause()
            assert screen._state == "incomplete"
            text = _badge_text(screen)
            assert "FINISHED" in text
            assert "some hosts incomplete" in text
            assert "badge-incomplete" in _badge_classes(screen)
            assert "an earlier stage" not in _log_text(screen)

    @pytest.mark.asyncio
    async def test_stopped_without_stage_omits_stage_clause(self) -> None:
        screen = _make_screen()
        payload = _make_partial_payload(12, 7, "error", None)
        async with _Harness(screen).run_test() as pilot:
            await pilot.pause()
            screen._handle_complete(payload)
            await pilot.pause()
            log = _log_text(screen)
            assert "Stopped —" in log
            assert "an earlier stage" not in log
            assert "Stopped during" not in log

    @pytest.mark.asyncio
    async def test_ot_ceiling_does_not_force_incomplete_badge(self) -> None:
        screen = _make_screen(scan_mode="nspi")
        payload = _make_payload(6, 1)
        payload = payload.model_copy(
            update={
                "scan_mode": "nspi",
                "metadata": {
                    "partial_result": False,
                    "terminated_by": "completed",
                    "modbus_stage_deadline_reached": True,
                    "modbus_stage_deadline_seconds": 90,
                },
            }
        )
        async with _Harness(screen).run_test() as pilot:
            await pilot.pause()
            screen._handle_complete(payload)
            await pilot.pause()
            assert "badge-incomplete" not in _badge_classes(screen)
            assert screen.query_one("#scan-badge", Static).display is False


class TestRefusedDepth:
    @pytest.mark.asyncio
    async def test_active_validation_refused_on_mount(self) -> None:
        screen = _make_screen(
            scan_mode="nspi",
            nspi_submode="active_validation",
        )
        async with _Harness(screen).run_test() as pilot:
            await pilot.pause()
            assert screen._state == "refused"
            badge = screen.query_one("#scan-badge", Static)
            assert badge.display is True
            assert "badge-refused" in _badge_classes(screen)
            assert "⛔ SCAN REFUSED — no request was sent" in _badge_text(screen)
            detail = screen.query_one("#scan-refusal-detail", Static)
            assert detail.display is True
            assert (
                "NSPi active validation is not available in this version."
                in str(detail.render())
            )
            assert screen.query_one("#btn-view-scan", Button).display is False
            assert screen.query_one("#btn-back-home", Button).has_focus is True
            assert screen.query_one("#progress-bar", ProgressBar).progress == 0
            assert len(screen.query_one("#activity-log", RichLog).lines) == 0


class TestOtStageDeadline:
    @pytest.mark.asyncio
    async def test_ot_stage_deadline_live_line(self) -> None:
        screen = _make_screen(scan_mode="nspi")
        async with _Harness(screen).run_test() as pilot:
            await pilot.pause()
            await _post(
                pilot,
                screen,
                ScanEvent(kind="ot_stage_started", hosts_total=3),
            )
            await _post(
                pilot,
                screen,
                ScanEvent(
                    kind="ot_stage_deadline",
                    message="Time limit reached during Modbus inventory (90s)",
                    units_skipped=1,
                    units_total=3,
                ),
            )
            text = _log_text(screen)
            assert "Time limit reached during Modbus inventory (90s)" in text
            assert "⏱" in text


class TestPortStageHeartbeat:
    @pytest.mark.asyncio
    async def test_elapsed_counter_advances_without_moving_bar_on_tick(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        screen = _make_screen(scan_mode="nspi")
        fake_now = [1000.0]
        monkeypatch.setattr(
            "agent.tui.screens.scan_progress.monotonic", lambda: fake_now[0]
        )
        async with _Harness(screen).run_test() as pilot:
            await pilot.pause()
            await _post(pilot, screen, ScanEvent(kind="port_stage_started"))
            bar = screen.query_one("#progress-bar", ProgressBar)
            for _ in range(5):
                screen._tick()
            await pilot.pause()
            settled_progress = bar.progress

            fake_now[0] += 5
            screen._tick()
            await pilot.pause()
            text_after_first = _log_text(screen)

            fake_now[0] += 7
            screen._tick()
            await pilot.pause()
            text_after_second = _log_text(screen)

            assert "Scanning ports…" in text_after_second
            assert "(5s)" in text_after_first
            assert "(12s)" in text_after_second
            assert text_after_first != text_after_second
            assert bar.progress == settled_progress

    @pytest.mark.asyncio
    async def test_batch_done_updates_fraction_and_advances_bar(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        screen = _make_screen(scan_mode="nspi")
        fake_now = [2000.0]
        monkeypatch.setattr(
            "agent.tui.screens.scan_progress.monotonic", lambda: fake_now[0]
        )
        async with _Harness(screen).run_test() as pilot:
            await pilot.pause()
            await _post(pilot, screen, ScanEvent(kind="port_stage_started"))
            bar = screen.query_one("#progress-bar", ProgressBar)
            for _ in range(5):
                screen._tick()
            await pilot.pause()
            progress_before_batch = bar.progress

            fake_now[0] += 80
            await _post(
                pilot,
                screen,
                ScanEvent(kind="port_batch_done", batches_done=3, batches_total=8),
            )
            for _ in range(5):
                screen._tick()
            await pilot.pause()
            text = _log_text(screen)

            assert "batch 3/8" in text
            assert "1m 20s" in text
            assert bar.progress > progress_before_batch


class TestDegradedFinishLines:
    @pytest.mark.asyncio
    async def test_port_stage_degraded_line_with_skips(self) -> None:
        screen = _make_screen()
        async with _Harness(screen).run_test() as pilot:
            await pilot.pause()
            await _post(pilot, screen, ScanEvent(kind="port_stage_started"))
            await _post(
                pilot,
                screen,
                ScanEvent(
                    kind="port_stage_done",
                    ports_open=41,
                    units_skipped=3,
                    units_total=20,
                ),
            )
            text = _log_text(screen)
            assert "41 open ports found (3 of 20 hosts skipped)" in text

    @pytest.mark.asyncio
    async def test_port_stage_clean_line_when_no_skips(self) -> None:
        screen = _make_screen()
        async with _Harness(screen).run_test() as pilot:
            await pilot.pause()
            await _post(pilot, screen, ScanEvent(kind="port_stage_started"))
            await _post(
                pilot,
                screen,
                ScanEvent(
                    kind="port_stage_done",
                    ports_open=41,
                    units_skipped=0,
                    units_total=20,
                ),
            )
            text = _log_text(screen)
            assert "41 open ports found" in text
            assert "skipped" not in text

    @pytest.mark.asyncio
    async def test_deep_stage_degraded_line_with_skips(self) -> None:
        screen = _make_screen()
        async with _Harness(screen).run_test() as pilot:
            await pilot.pause()
            await _post(
                pilot, screen, ScanEvent(kind="deep_stage_started", hosts_total=20)
            )
            await _post(
                pilot,
                screen,
                ScanEvent(
                    kind="deep_stage_done",
                    units_skipped=2,
                    units_total=20,
                ),
            )
            text = _log_text(screen)
            assert "18 of 20 hosts scanned (2 skipped)" in text

    @pytest.mark.asyncio
    async def test_deep_stage_clean_line_when_no_skips(self) -> None:
        screen = _make_screen()
        async with _Harness(screen).run_test() as pilot:
            await pilot.pause()
            await _post(
                pilot, screen, ScanEvent(kind="deep_stage_started", hosts_total=20)
            )
            await _post(
                pilot,
                screen,
                ScanEvent(
                    kind="deep_stage_done",
                    units_skipped=0,
                    units_total=20,
                ),
            )
            text = _log_text(screen)
            assert "20 hosts scanned" in text
            assert "skipped" not in text

    @pytest.mark.asyncio
    async def test_unit_timed_out_and_failed_lines(self) -> None:
        screen = _make_screen()
        async with _Harness(screen).run_test() as pilot:
            await pilot.pause()
            await _post(
                pilot,
                screen,
                ScanEvent(kind="unit_timed_out", ip="192.168.1.11"),
            )
            await _post(
                pilot,
                screen,
                ScanEvent(kind="unit_failed", ip="192.168.1.12"),
            )
            text = _log_text(screen)
            assert "192.168.1.11 timed out (skipped)" in text
            assert "192.168.1.12 failed (skipped)" in text
