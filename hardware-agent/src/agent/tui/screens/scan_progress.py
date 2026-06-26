"""Scan progress screen (S4) — bar, spinner, and activity log in real time."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from rich.measure import measure_renderables
from rich.segment import Segment
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.strip import Strip
from textual.widgets import Button, ProgressBar, RichLog, Static

from agent.scanner.progress import ProgressMapper, ScanEvent
from agent.tui.config import load_config
from agent.tui.scanner import ScanRunner
from agent.tui.screens.base import DmitriScreen
from agent.tui.screens.scan_view import MODE_LABELS
from agent.tui.widgets import SPINNER_FRAMES


class ScanProgressScreen(DmitriScreen):
    """S4: real-time pipeline progress with cancellation."""

    _PCT_STEP = 5.0

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
    ) -> None:
        super().__init__()
        self.subnet = subnet
        self.scan_mode = scan_mode
        self._runner: ScanRunner | None = None
        self._mapper = ProgressMapper(scan_mode)
        self._target_pct = 0.0
        self._display_pct = 0.0
        self._done = False
        self._payload = None
        self._spinner_frame = 0
        self._stage_lines: dict[str, int] = {}
        self._active_stages: dict[str, str] = {}
        self._scripts_hosts_total = 0

    def compose_body(self):
        with Vertical(id="progress-container"):
            yield Static("", id="scan-header")
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
        mode_label = MODE_LABELS.get(self.scan_mode, self.scan_mode.capitalize())
        self.query_one("#scan-header", Static).update(
            f"Mode: {mode_label} · {self.subnet}"
        )
        self.set_interval(0.05, self._tick)
        self._start_scan()

    def _start_scan(self) -> None:
        config = load_config()
        workspace_root = Path(config.results_dir) if config else None
        self._runner = ScanRunner(
            subnet=self.subnet,
            scan_mode=self.scan_mode,
            reporter=self._ScreenReporter(self),
            on_complete=self._on_worker_complete,
            on_error=self._on_worker_error,
            workspace_root=workspace_root,
        )
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

    def _refresh_active_stage_lines(self) -> None:
        log = self.query_one("#activity-log", RichLog)
        for stage, label in self._active_stages.items():
            index = self._stage_lines.get(stage)
            if index is None or index >= len(log.lines):
                continue
            self._replace_log_line(log, index, self._spinner_line(label))

    def on_scan_progress_screen_progress_updated(
        self, message: "ScanProgressScreen.ProgressUpdated"
    ) -> None:
        event = message.event
        self._target_pct = self._mapper.update(event)
        if event.kind == "failed":
            self._active_stages.clear()
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
            if self.scan_mode in ("extensive", "max"):
                self._start_stage("ports", "Scanning all ports…")
            else:
                self._start_stage("ports", "Scanning ports…")
            return
        if kind == "port_stage_done":
            self._finish_stage(
                "ports",
                f"[green]✓[/green] {event.ports_open} open ports found",
            )
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
        if kind == "normalize_started":
            if self._scripts_hosts_total > 0:
                self._finish_stage(
                    "scripts",
                    f"[green]✓[/green] {self._scripts_hosts_total} hosts scanned",
                )
            if self._done and self._payload is not None:
                if "normalize" in self._stage_lines or "normalize" in self._active_stages:
                    self._finish_stage("normalize", self._done_line(self._payload))
            else:
                self._start_stage("normalize", "Generating results…")
            return

    def _done_line(self, payload) -> str:
        devices = len(payload.devices)
        findings = len(payload.findings)
        return (
            f"[bold green]✓ Done — {devices} devices, "
            f"{findings} vulnerabilities[/bold green]"
        )

    def _handle_complete(self, payload) -> None:
        self._done = True
        self._payload = payload
        self._active_stages.clear()

        self._target_pct = 100.0
        self._display_pct = 100.0
        self.query_one("#progress-bar", ProgressBar).update(progress=100)

        self._finish_stage("normalize", self._done_line(payload))

        self._bindings.bind("up", "focus_prev_btn", "↑↓ Navigate", show=True)
        self._bindings.bind("down", "focus_next_btn", show=True)
        self._bindings.bind("enter", "press_focused", "Enter Select", show=True)
        self._bindings.bind("escape", "no_op", "Esc Back", show=True)

        self.query_one("#scan-done-actions").display = True
        self.query_one("#btn-view-scan", Button).focus()

    def _handle_error(self, error: Exception) -> None:
        self.notify(f"Scan error: {error}", severity="error")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-view-scan":
            self.dismiss((self._payload, True))
        elif event.button.id == "btn-back-home":
            self.dismiss((self._payload, False))

    def action_abort(self) -> None:
        if self._done:
            self.dismiss((self._payload, False))
            return
        if self._runner:
            self._runner.request_cancel()
        self.dismiss(None)

    def action_no_op(self) -> None:
        if self._done:
            self.dismiss((self._payload, False))

    def action_focus_next_btn(self) -> None:
        if not self._done:
            return
        btn_view = self.query_one("#btn-view-scan", Button)
        btn_home = self.query_one("#btn-back-home", Button)
        if btn_view.has_focus:
            btn_home.focus()
        else:
            btn_view.focus()

    def action_focus_prev_btn(self) -> None:
        if not self._done:
            return
        btn_view = self.query_one("#btn-view-scan", Button)
        btn_home = self.query_one("#btn-back-home", Button)
        if btn_home.has_focus:
            btn_view.focus()
        else:
            btn_home.focus()

    def action_press_focused(self) -> None:
        if not self._done:
            return
        btn_view = self.query_one("#btn-view-scan", Button)
        btn_home = self.query_one("#btn-back-home", Button)
        if btn_view.has_focus:
            self.dismiss((self._payload, True))
        elif btn_home.has_focus:
            self.dismiss((self._payload, False))
