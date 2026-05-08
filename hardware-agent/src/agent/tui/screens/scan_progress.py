"""Scan progress screen (S4) — shows pipeline phases in real time."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from textual.binding import Binding
from textual.containers import Vertical
from textual.message import Message
from textual.widgets import Button, Static

from agent.tui.config import load_config
from agent.tui.scanner import ProgressSnapshot, ScanRunner
from agent.tui.screens.base import DmitriScreen

STAGES: list[str] = [
    "discovery",
    "port_scan",
    "deep_inspection",
    "normalizing",
    "completed",
]

STAGE_LABELS: dict[str, str] = {
    "discovery": "Finding open ports...",
    "port_scan": "Scanning ports...",
    "deep_inspection": "Running scripts...",
    "normalizing": "Normalizing results...",
    "completed": "DONE!",
}


class ScanProgressScreen(DmitriScreen):
    """S4: real-time pipeline progress with cancellation."""

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
        def __init__(self, snapshot: ProgressSnapshot) -> None:
            self.snapshot = snapshot
            super().__init__()

    class ScanCompleted(Message):
        def __init__(self, payload) -> None:
            self.payload = payload
            super().__init__()

    class ScanFailed(Message):
        def __init__(self, error: Exception) -> None:
            self.error = error
            super().__init__()

    def __init__(
        self,
        subnet: str,
        scan_mode: Literal["quick", "full"],
    ) -> None:
        super().__init__()
        self.subnet = subnet
        self.scan_mode = scan_mode
        self._runner: ScanRunner | None = None
        self._quit_after_abort = False
        self._completed_details: dict[str, str] = {}
        self._current_stage: str = ""
        self._done = False
        self._payload = None

    def compose_body(self):
        with Vertical(id="progress-container"):
            yield Static("", id="phase-discovery")
            yield Static("", id="phase-port_scan")
            yield Static("", id="phase-deep_inspection")
            yield Static("", id="phase-normalizing")
            yield Static("", id="phase-completed")
        with Vertical(id="scan-done-actions"):
            yield Button("View scan", id="btn-view-scan", variant="primary")
            yield Button("Back to Home", id="btn-back-home")

    def on_mount(self) -> None:
        self.query_one("#scan-done-actions").display = False
        self._update_phase("discovery", "pending")
        self._start_scan()

    def _start_scan(self) -> None:
        config = load_config()
        workspace_root = Path(config.results_dir) if config else None
        self._runner = ScanRunner(
            subnet=self.subnet,
            scan_mode=self.scan_mode,
            on_progress=self._on_worker_progress,
            on_complete=self._on_worker_complete,
            on_error=self._on_worker_error,
            workspace_root=workspace_root,
        )
        self._runner.start()

    def _on_worker_progress(self, snapshot: ProgressSnapshot) -> None:
        self.app.call_from_thread(self._handle_progress, snapshot)

    def _on_worker_complete(self, payload) -> None:
        self.app.call_from_thread(self._handle_complete, payload)

    def _on_worker_error(self, error: Exception) -> None:
        self.app.call_from_thread(self._handle_error, error)

    def _handle_progress(self, snapshot: ProgressSnapshot) -> None:
        if snapshot.completed:
            self._completed_details[snapshot.stage] = snapshot.detail
        else:
            self._current_stage = snapshot.stage

        if self._current_stage in STAGES:
            stage_idx = STAGES.index(self._current_stage)
        else:
            stage_idx = -1
        for i, stage in enumerate(STAGES):
            widget = self.query_one(f"#phase-{stage}", Static)
            if stage in self._completed_details:
                label = STAGE_LABELS[stage]
                detail = self._completed_details[stage]
                suffix = f"  {detail}" if detail else ""
                widget.update(f"[green]✓[/green] {label}{suffix}")
            elif i == stage_idx:
                widget.update(f"[yellow]●[/yellow] {STAGE_LABELS[stage]}")
            else:
                widget.update(f"  {STAGE_LABELS[stage]}")

    def _handle_complete(self, payload) -> None:
        self._done = True
        self._payload = payload

        for stage in STAGES:
            widget = self.query_one(f"#phase-{stage}", Static)
            if stage == "completed":
                widget.update("[bold green]DONE![/bold green]")
            elif stage in self._completed_details:
                detail = self._completed_details[stage]
                suffix = f"  {detail}" if detail else ""
                widget.update(f"[green]✓[/green] {STAGE_LABELS[stage]}{suffix}")
            else:
                widget.update(f"[green]✓[/green] {STAGE_LABELS[stage]}")

        self._bindings.bind("up", "focus_prev_btn", "↑↓ Navigate", show=True)
        self._bindings.bind("down", "focus_next_btn", show=True)
        self._bindings.bind("enter", "press_focused", "Enter Select", show=True)
        self._bindings.bind("escape", "no_op", "Esc Back", show=True)

        self.query_one("#scan-done-actions").display = True
        self.query_one("#btn-view-scan", Button).focus()

    def _handle_error(self, error: Exception) -> None:
        self.notify(f"Scan error: {error}", severity="error")
        self.dismiss(None)

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

    def _update_phase(self, stage: str, state: str) -> None:
        for s in STAGES:
            widget = self.query_one(f"#phase-{s}", Static)
            widget.update(f"  {STAGE_LABELS[s]}")
