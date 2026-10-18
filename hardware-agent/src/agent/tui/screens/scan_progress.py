"""Scan progress screen (S4) — bar, spinner, and activity log in real time."""

from __future__ import annotations

import os
from pathlib import Path
from time import monotonic
from typing import Literal

from rich.measure import measure_renderables
from rich.segment import Segment
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.strip import Strip
from textual.widgets import Button, ProgressBar, RichLog, Static

from agent.config import NspiSubmode
from agent.paths import load_config
from agent.scanner.errors import UnsupportedScanDepth
from agent.scanner.progress import ProgressMapper, ScanEvent
from agent.scanner.runner import ScanRunner
from agent.scanner.scan_lock import ScanLease
from agent.tui.screens.base import DmitriScreen
from agent.tui.screens.scan_view import MODE_LABELS
from agent.tui.widgets import SPINNER_FRAMES


class ScanProgressScreen(DmitriScreen):
    """S4: real-time pipeline progress with cancellation."""

    _PCT_STEP = 5.0

    _STOPPED_REASONS = {
        "user_cancel": "stopped by you; partial results kept",
        "timeout": "a step timed out; partial results kept",
        "error": "scan stopped early; partial results kept",
    }

    _BADGE_CLASSES = (
        "badge-incomplete",
        "badge-stopped",
        "badge-failed",
        "badge-refused",
        "badge-cancelling",
    )

    _INTERRUPTED_STAGE_LABELS = {
        "discovery": "host discovery",
        "ports": "port scanning",
        "port_scan": "port scanning",
        "deep_inspection": "deep inspection",
        "ot_inspection": "Modbus inventory",
        "targeted_assessment": "targeted service assessment",
        "normalize": "results generation",
    }

    BINDINGS = [
        Binding("ctrl+x", "abort", "Abort scan", priority=True),
        Binding("escape", "no_op", show=False),
        Binding("ctrl+t", "no_op", show=False),
        Binding("j", "focus_next_btn", show=False),
        Binding("k", "focus_prev_btn", show=False),
        Binding("up", "focus_prev_btn", "↑↓ Navigate", show=False),
        Binding("down", "focus_next_btn", show=False),
        Binding("enter", "press_focused", "Enter Select", show=False),
    ]

    class ProgressUpdated(Message):
        def __init__(self, event: ScanEvent) -> None:
            self.event = event
            super().__init__()

    class ScanCompleted(Message):
        def __init__(self, payload) -> None:
            self.payload = payload
            super().__init__()

    class ScanFailed(Message):
        def __init__(self, error: Exception) -> None:
            self.error = error
            super().__init__()

    class _ScreenReporter:
        def __init__(self, screen: "ScanProgressScreen") -> None:
            self._screen = screen

        def emit(self, event: ScanEvent) -> None:
            self._screen.post_message(ScanProgressScreen.ProgressUpdated(event))

    def __init__(
        self,
        subnet: str,
        scan_mode: Literal["quick", "standard", "extensive", "nspi", "max"],
        nspi_submode: NspiSubmode | None = None,
        scan_lease: ScanLease | None = None,
    ) -> None:
        super().__init__()
        self.subnet = subnet
        self.scan_mode = scan_mode
        self.nspi_submode: NspiSubmode = nspi_submode or "inventory"
        self.scan_lease = scan_lease
        self._runner: ScanRunner | None = None
        self._mapper = ProgressMapper(scan_mode)
        self._target_pct = 0.0
        self._display_pct = 0.0
        self._done = False
        self._state = "running"
        self._payload = None
        self._spinner_frame = 0
        self._stage_lines: dict[str, int] = {}
        self._active_stages: dict[str, str] = {}
        self._scripts_hosts_total = 0
        self._port_stage_started_at: float | None = None
        self._port_base_label = ""
        self._port_batches_done = 0
        self._port_batches_total = 0
        self._targeted_units_total = 0
        self._targeted_units_completed = 0
        self._targeted_units_failed = 0
        self._targeted_units_timed_out = 0
        self._targeted_units_skipped = 0

    def compose_body(self):
        with Vertical(id="progress-container"):
            yield Static("", id="scan-header")
            yield Static("", id="scan-badge")
            yield Static("", id="scan-refusal-detail")
            with Horizontal(id="progress-row"):
                yield ProgressBar(
                    total=100,
                    show_eta=False,
                    show_percentage=True,
                    id="progress-bar",
                )
            yield RichLog(
                highlight=False,
                markup=True,
                wrap=True,
                max_lines=200,
                id="activity-log",
            )
        with Vertical(id="scan-done-actions"):
            yield Button("View scan", id="btn-view-scan", variant="primary")
            yield Button("Back to Home", id="btn-back-home")

    def on_mount(self) -> None:
        self.query_one("#scan-done-actions").display = False
        self.query_one("#scan-refusal-detail", Static).display = False
        mode_label = MODE_LABELS.get(self.scan_mode, self.scan_mode.capitalize())
        if self.scan_mode == "nspi":
            submode_label = {
                "inventory": "Inventory",
                "read_only_mapping": "Read-only mapping",
                "active_validation": "Active validation",
            }[self.nspi_submode]
            mode_label = f"{mode_label} · {submode_label}"
        self.query_one("#scan-header", Static).update(
            f"Mode: {mode_label} · {self.subnet}"
        )
        self.set_interval(0.05, self._tick)
        self._start_scan()

    def _start_scan(self) -> None:
        config = load_config()
        workspace_root = Path(config.results_dir) if config else None
        try:
            self._runner = ScanRunner(
                subnet=self.subnet,
                scan_mode=self.scan_mode,
                reporter=self._ScreenReporter(self),
                on_complete=self._on_worker_complete,
                on_error=self._on_worker_error,
                workspace_root=workspace_root,
                nspi_submode=self.nspi_submode,
                scan_lease=self.scan_lease,
            )
        except UnsupportedScanDepth as exc:
            self._handle_refused(exc.refused_depth)
            return
        self._runner.start()

    def _on_worker_complete(self, payload) -> None:
        self.app.call_from_thread(self._handle_complete, payload)

    def _on_worker_error(self, error: Exception) -> None:
        self.app.call_from_thread(self._handle_error, error)

    def _tick(self) -> None:
        if self._display_pct < self._target_pct:
            self._display_pct = min(
                self._display_pct + self._PCT_STEP, self._target_pct
            )
            self.query_one("#progress-bar", ProgressBar).update(
                progress=self._display_pct
            )
        if self._active_stages:
            self._spinner_frame = (self._spinner_frame + 1) % len(SPINNER_FRAMES)
            self._refresh_active_stage_lines()

    def _spinner_glyph(self) -> str:
        if os.environ.get("TEXTUAL_ANIMATIONS") == "none":
            return SPINNER_FRAMES[0]
        return SPINNER_FRAMES[self._spinner_frame]

    def _spinner_line(self, label: str) -> str:
        return f"[yellow]{self._spinner_glyph()}[/yellow] {label}"

    def _render_log_strip(self, log: RichLog, content: str) -> Strip:
        renderable = log._make_renderable(content)
        console = self.app.console
        render_options = console.options.update(overflow="ignore", no_wrap=True)
        render_width = max(
            measure_renderables(console, render_options, [renderable]).maximum,
            log.min_width,
        )
        render_options = render_options.update_width(render_width)
        segments = console.render(renderable, render_options)
        lines = list(Segment.split_lines(segments))
        if not lines:
            return Strip.blank(render_width)
        strips = Strip.from_lines(lines)
        strip = strips[0]
        strip.adjust_cell_length(render_width)
        return strip

    def _append_log_line(self, log: RichLog, content: str) -> int:
        index = len(log.lines)
        log.write(content, scroll_end=True)
        return index

    def _replace_log_line(self, log: RichLog, index: int, content: str) -> None:
        if index < 0 or index >= len(log.lines):
            log.write(content, scroll_end=True)
            return
        log.lines[index] = self._render_log_strip(log, content)
        log._line_cache.clear()
        log.refresh()

    def _start_stage(self, stage: str, label: str) -> None:
        log = self.query_one("#activity-log", RichLog)
        line = self._spinner_line(label)
        index = self._append_log_line(log, line)
        self._stage_lines[stage] = index
        self._active_stages[stage] = label

    def _finish_stage(self, stage: str, content: str) -> None:
        self._active_stages.pop(stage, None)
        log = self.query_one("#activity-log", RichLog)
        if stage in self._stage_lines:
            self._replace_log_line(log, self._stage_lines.pop(stage), content)
        else:
            log.write(content, scroll_end=True)

    def _format_elapsed(self, seconds: float) -> str:
        total = max(int(seconds), 0)
        minutes, secs = divmod(total, 60)
        if minutes:
            return f"{minutes}m {secs}s"
        return f"{secs}s"

    def _port_stage_label(self) -> str:
        elapsed = self._format_elapsed(monotonic() - self._port_stage_started_at)
        if self._port_batches_total:
            return (
                f"{self._port_base_label} (batch "
                f"{self._port_batches_done}/{self._port_batches_total} · {elapsed})"
            )
        return f"{self._port_base_label} ({elapsed})"

    def _refresh_active_stage_lines(self) -> None:
        log = self.query_one("#activity-log", RichLog)
        if "ports" in self._active_stages and self._port_stage_started_at is not None:
            self._active_stages["ports"] = self._port_stage_label()
        for stage, label in self._active_stages.items():
            index = self._stage_lines.get(stage)
            if index is None or index >= len(log.lines):
                continue
            self._replace_log_line(log, index, self._spinner_line(label))

    def on_scan_progress_screen_progress_updated(
        self, message: "ScanProgressScreen.ProgressUpdated"
    ) -> None:
        event = message.event
        if event.kind.startswith("targeted_") and self.scan_mode not in (
            "extensive",
            "max",
            "nspi",
        ):
            return
        self._target_pct = self._mapper.update(event)
        if event.kind == "failed":
            self._active_stages.clear()
            if self._state != "cancelling" and not self._terminal():
                self.query_one("#activity-log", RichLog).write(
                    f"[red]✗ {event.message}[/red]"
                )
            return
        if event.kind == "completed":
            return

        log = self.query_one("#activity-log", RichLog)
        kind = event.kind

        if kind == "discovery_started":
            self._start_stage("discovery", "Finding hosts…")
            return
        if kind == "hosts_found":
            if event.hosts_total == 0:
                self._finish_stage("discovery", "[green]✓[/green] No hosts found")
            else:
                self._finish_stage(
                    "discovery",
                    f"[green]✓[/green] {event.hosts_total} hosts found",
                )
            return
        if kind == "port_stage_started":
            self._port_base_label = (
                "Scanning all ports…"
                if self.scan_mode in ("extensive", "max")
                else "Scanning ports…"
            )
            self._port_stage_started_at = monotonic()
            self._port_batches_done = 0
            self._port_batches_total = 0
            self._start_stage("ports", self._port_base_label)
            return
        if kind == "port_batch_done":
            self._port_batches_done = event.batches_done
            self._port_batches_total = event.batches_total
            return
        if kind == "port_stage_done":
            if event.units_skipped > 0:
                line = (
                    f"[yellow]⚠[/yellow] {event.ports_open} open ports found "
                    f"({event.units_skipped} of {event.units_total} hosts skipped)"
                )
            else:
                line = f"[green]✓[/green] {event.ports_open} open ports found"
            self._finish_stage("ports", line)
            return
        if kind == "deep_stage_started":
            self._scripts_hosts_total = event.hosts_total
            if event.hosts_total == 0:
                log.write("[dim]No hosts to inspect — skipping scripts[/dim]")
            else:
                self._start_stage("scripts", "Running scripts…")
            return
        if kind == "host_inspected":
            log.write(
                f"[dim]  ↳ Scanned {event.ip} "
                f"({event.hosts_done}/{event.hosts_total})[/dim]"
            )
            return
        if kind == "unit_timed_out":
            log.write(f"[yellow]  ↳ {event.ip} timed out (skipped)[/yellow]")
            return
        if kind == "unit_failed":
            log.write(f"[yellow]  ↳ {event.ip} failed (skipped)[/yellow]")
            return
        if kind == "deep_stage_done":
            if "scripts" not in self._stage_lines:
                return
            total = event.units_total
            if event.units_skipped > 0:
                scanned = total - event.units_skipped
                line = (
                    f"[yellow]⚠[/yellow] {scanned} of {total} hosts scanned "
                    f"({event.units_skipped} skipped)"
                )
            else:
                line = f"[green]✓[/green] {total} hosts scanned"
            self._finish_stage("scripts", line)
            return
        if kind == "ot_stage_started":
            if event.hosts_total == 0:
                log.write("[dim]No Modbus candidates found[/dim]")
            else:
                self._start_stage(
                    "ot",
                    (
                        "Mapping Modbus read-only ranges..."
                        if self.nspi_submode == "read_only_mapping"
                        else "Inventorying Modbus devices..."
                    ),
                )
            return
        if kind == "modbus_host_inspected":
            action = (
                "Mapped" if self.nspi_submode == "read_only_mapping" else "Inventoried"
            )
            log.write(
                f"[dim]  -> {action} {event.ip} "
                f"({event.hosts_done}/{event.hosts_total})[/dim]"
            )
            return
        if kind == "ot_stage_deadline":
            limit_seconds = event.deadline_seconds or "?"
            self._finish_stage(
                "ot",
                (
                    f"[yellow]⏱ Time limit reached during Modbus inventory "
                    f"({limit_seconds}s) — evidence gathered so far is kept[/yellow]"
                ),
            )
            return
        if kind == "ot_stage_done":
            if "ot" not in self._stage_lines:
                return
            inspected = event.units_total - event.units_skipped
            if event.units_skipped:
                line = (
                    f"[yellow]![/yellow] {inspected} Modbus hosts processed "
                    f"({event.units_skipped} skipped)"
                )
            else:
                action = (
                    "mapped"
                    if self.nspi_submode == "read_only_mapping"
                    else "inventoried"
                )
                line = f"[green]OK[/green] {inspected} Modbus hosts {action}"
            self._finish_stage("ot", line)
            return
        if kind == "targeted_stage_started":
            self._targeted_units_total = event.units_total
            self._targeted_units_completed = 0
            self._targeted_units_failed = 0
            self._targeted_units_timed_out = 0
            self._targeted_units_skipped = 0
            if event.units_total == 0:
                log.write("[dim]No supported services found[/dim]")
            else:
                self._start_stage(
                    "targeted",
                    f"Assessing services… (0/{event.units_total})",
                )
            return
        if kind == "targeted_unit_done":
            if "targeted" not in self._stage_lines:
                return
            label = f"Assessing services… ({event.units_done}/{event.units_total})"
            self._active_stages["targeted"] = label
            self._replace_log_line(
                log,
                self._stage_lines["targeted"],
                self._spinner_line(label),
            )
            return
        if kind == "targeted_stage_done":
            self._targeted_units_total = event.units_total
            self._targeted_units_completed = event.units_completed
            self._targeted_units_failed = event.units_failed
            self._targeted_units_timed_out = event.units_timed_out
            self._targeted_units_skipped = event.units_skipped
            if "targeted" not in self._stage_lines:
                return
            if (
                event.units_completed == event.units_total
                and event.units_failed == 0
                and event.units_timed_out == 0
                and event.units_skipped == 0
            ):
                line = (
                    f"[green]✓[/green] Targeted checks completed: "
                    f"{event.units_completed}"
                )
            else:
                line = self._targeted_degraded_line()
            self._finish_stage("targeted", line)
            return
        if kind == "normalize_started":
            if "scripts" in self._stage_lines:
                self._finish_stage(
                    "scripts",
                    f"[green]✓[/green] {self._scripts_hosts_total} hosts scanned",
                )
            if self._done and self._payload is not None:
                if (
                    "normalize" in self._stage_lines
                    or "normalize" in self._active_stages
                ):
                    self._finish_stage("normalize", self._done_line(self._payload))
            else:
                if "targeted" in self._stage_lines:
                    self._finish_stage("targeted", self._targeted_degraded_line())
                self._start_stage("normalize", "Generating results…")
            return

    def _targeted_degraded_line(self) -> str:
        return (
            f"[yellow]⚠[/yellow] Targeted checks: "
            f"{self._targeted_units_completed} completed, "
            f"{self._targeted_units_failed} failed, "
            f"{self._targeted_units_timed_out} timed out, "
            f"{self._targeted_units_skipped} skipped"
        )

    def _done_line(self, payload) -> str:
        devices = len(payload.hosts)
        findings = len(payload.findings)
        return (
            f"[bold green]✓ Done — {devices} devices, "
            f"{findings} vulnerabilities[/bold green]"
        )

    def _terminal(self) -> bool:
        return self._state in (
            "completed",
            "incomplete",
            "stopped",
            "partial",
            "fatal",
            "refused",
        )

    @staticmethod
    def _escape_display(value: str, *, limit: int) -> str:
        cleaned = "".join(
            "·" if ord(char) < 32 or ord(char) == 127 else char for char in value
        )
        cleaned = cleaned.replace("[", "[[]")
        if len(cleaned) > limit:
            return cleaned[: limit - 1] + "…"
        return cleaned

    def _set_badge(self, badge_class: str, text: str) -> None:
        badge = self.query_one("#scan-badge", Static)
        for cls in self._BADGE_CLASSES:
            badge.remove_class(cls)
        badge.add_class(badge_class)
        badge.update(text)
        badge.display = True

    def _refusal_lines(self, refused_depth: str) -> tuple[str, str]:
        if refused_depth == "active_validation":
            return (
                "NSPi active validation is not available in this version.",
                "No host was contacted. Choose Inventory or Read-only mapping "
                "and start again.",
            )
        safe_value = self._escape_display(refused_depth, limit=32)
        return (
            f"The requested NSPi mode is not permitted: {safe_value}",
            "No host was contacted. Choose Inventory or Read-only mapping "
            "and start again.",
        )

    def _enable_terminal_bindings(self, *, navigate: bool) -> None:
        self._bindings.bind("escape", "no_op", "Esc Back", show=True)
        if navigate:
            self._bindings.bind("up", "focus_prev_btn", "↑↓ Navigate", show=True)
            self._bindings.bind("down", "focus_next_btn", show=True)
            self._bindings.bind("enter", "press_focused", "Enter Select", show=True)

    def _handle_complete(self, payload) -> None:
        self._payload = payload
        self._active_stages.clear()
        metadata = getattr(payload, "metadata", None) or {}
        if metadata.get("partial_result") is True:
            if metadata.get("terminated_by") == "completed":
                self._handle_incomplete(payload)
            else:
                self._handle_stopped(payload)
        else:
            self._handle_success(payload)

    def _handle_success(self, payload) -> None:
        self._done = True
        self._state = "completed"
        self._target_pct = 100.0
        self._display_pct = 100.0
        self.query_one("#progress-bar", ProgressBar).update(progress=100)

        self._finish_stage("normalize", self._done_line(payload))

        self._enable_terminal_bindings(navigate=True)
        self.query_one("#scan-done-actions").display = True
        self.query_one("#btn-view-scan", Button).focus()

    def _handle_incomplete(self, payload) -> None:
        self._done = True
        self._state = "incomplete"
        self._target_pct = 100.0
        self._display_pct = 100.0
        self.query_one("#progress-bar", ProgressBar).update(progress=100)

        self._set_badge(
            "badge-incomplete",
            "[black on yellow] FINISHED [/] some hosts incomplete; all evidence kept",
        )

        devices = len(payload.hosts)
        findings = len(payload.findings)
        metadata = payload.metadata or {}
        hosts_skipped = metadata.get("hosts_skipped")
        hosts_total = metadata.get("hosts_total")
        if hosts_skipped is not None and hosts_total is not None:
            closing = (
                f"[yellow]⚠ Finished with incomplete evidence — {devices} devices, "
                f"{findings} vulnerabilities ({hosts_skipped} of {hosts_total} "
                f"hosts incomplete)[/yellow]"
            )
        elif devices == 0 and findings == 0:
            closing = "[bold green]✓ Done — 0 devices, 0 vulnerabilities[/bold green]"
        else:
            closing = (
                f"[yellow]⚠ Finished with incomplete evidence — {devices} devices, "
                f"{findings} vulnerabilities[/yellow]"
            )
        self.query_one("#activity-log", RichLog).write(closing)

        self._enable_terminal_bindings(navigate=True)
        self.query_one("#btn-view-scan", Button).label = "View scan"
        self.query_one("#scan-done-actions").display = True
        self.query_one("#btn-view-scan", Button).focus()

    def _handle_stopped(self, payload) -> None:
        if not payload.hosts:
            self.dismiss(None)
            return
        self._done = True
        self._state = "stopped"
        metadata = payload.metadata or {}
        reason = self._STOPPED_REASONS.get(
            metadata.get("terminated_by"), "partial results kept"
        )
        self._set_badge(
            "badge-stopped",
            f"[white on red] STOPPED [/] {reason}",
        )

        devices = len(payload.hosts)
        findings = len(payload.findings)
        interrupted_stage = metadata.get("interrupted_stage")
        stage_label = self._INTERRUPTED_STAGE_LABELS.get(interrupted_stage)
        if stage_label:
            closing = (
                f"[red]✗ Stopped during {stage_label} — {devices} devices, "
                f"{findings} vulnerabilities (partial results kept)[/red]"
            )
        else:
            closing = (
                f"[red]✗ Stopped — {devices} devices, "
                f"{findings} vulnerabilities (partial results kept)[/red]"
            )
        self.query_one("#activity-log", RichLog).write(closing)

        self._enable_terminal_bindings(navigate=True)
        view = self.query_one("#btn-view-scan", Button)
        view.label = "View partial scan"
        self.query_one("#scan-done-actions").display = True
        view.focus()

    def _handle_refused(self, refused_depth: str) -> None:
        self._state = "refused"
        self._set_badge(
            "badge-refused",
            "[bold red]⛔ SCAN REFUSED — no request was sent[/bold red]",
        )
        line1, line2 = self._refusal_lines(refused_depth)
        detail = self.query_one("#scan-refusal-detail", Static)
        detail.update(f"{line1}\n{line2}")
        detail.display = True
        self.query_one("#btn-view-scan", Button).display = False
        self._enable_terminal_bindings(navigate=False)
        self.query_one("#scan-done-actions").display = True
        self.query_one("#btn-back-home", Button).focus()

    def _handle_error(self, error: Exception) -> None:
        self._state = "fatal"
        self._active_stages.clear()
        self._set_badge(
            "badge-failed",
            "[bold red]✗ SCAN FAILED — nothing to keep[/bold red]",
        )
        self.query_one("#btn-view-scan", Button).display = False
        self._enable_terminal_bindings(navigate=False)
        self.query_one("#scan-done-actions").display = True
        self.query_one("#btn-back-home", Button).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-view-scan":
            self.dismiss((self._payload, True))
        elif event.button.id == "btn-back-home":
            self.dismiss((self._payload, False))

    def _enter_cancelling(self) -> None:
        self._state = "cancelling"
        self._set_badge(
            "badge-cancelling",
            "[black on yellow] CANCELLING [/] saving partial results…",
        )
        self.query_one("#activity-log", RichLog).write(
            "[yellow]● Stopping scan — saving partial results, "
            "no new probes will start…[/yellow]"
        )
        if self._runner:
            self._runner.request_cancel()

    def action_abort(self) -> None:
        if self._terminal():
            self.dismiss((self._payload, False))
            return
        if self._state == "cancelling":
            return
        self._enter_cancelling()

    def action_no_op(self) -> None:
        if self._terminal():
            self.dismiss((self._payload, False))

    def _terminal_buttons(self) -> list[Button]:
        buttons = []
        for button_id in ("btn-view-scan", "btn-back-home"):
            button = self.query_one(f"#{button_id}", Button)
            if button.display:
                buttons.append(button)
        return buttons

    def action_focus_next_btn(self) -> None:
        if not self._terminal():
            return
        buttons = self._terminal_buttons()
        if len(buttons) < 2:
            return
        btn_view, btn_home = buttons
        if btn_view.has_focus:
            btn_home.focus()
        else:
            btn_view.focus()

    def action_focus_prev_btn(self) -> None:
        if not self._terminal():
            return
        buttons = self._terminal_buttons()
        if len(buttons) < 2:
            return
        btn_view, btn_home = buttons
        if btn_home.has_focus:
            btn_view.focus()
        else:
            btn_home.focus()

    def action_press_focused(self) -> None:
        if not self._terminal():
            return
        btn_view = self.query_one("#btn-view-scan", Button)
        btn_home = self.query_one("#btn-back-home", Button)
        if btn_view.display and btn_view.has_focus:
            self.dismiss((self._payload, True))
        elif btn_home.has_focus:
            self.dismiss((self._payload, False))
