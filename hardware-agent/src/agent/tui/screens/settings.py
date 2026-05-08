"""Settings screen (S1) — edit persisted preferences post-setup."""

from __future__ import annotations

from pathlib import Path

from textual.binding import Binding
from textual.containers import Vertical
from textual.widgets import Button, Input, Label, Static

from agent.scanner.workspace import ensure_workspace_layout
from agent.tui.config import (
    DmitriConfig,
    default_results_dir,
    load_config,
    resolve_display_path,
    save_config,
    validate_results_path,
)
from agent.tui.screens.base import DmitriScreen


class SettingsScreen(DmitriScreen):
    """Settings: user can change the results directory."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    def compose_body(self):
        current = load_config()
        current_dir = current.results_dir if current else default_results_dir()
        with Vertical(id="settings-container"):
            yield Static("Settings", id="settings-title")
            yield Static(
                "results/ — saved scan JSON (10 newest kept)\n"
                "logs/    — Nmap operational traces (10 newest kept)",
                id="settings-subtitle",
            )
            yield Label("Workspace directory:")
            yield Input(
                value=current_dir,
                placeholder="Enter path...",
                id="path-input",
            )
            yield Button("Use default", id="btn-default", variant="default")
            yield Static("", id="resolved-path")
            yield Static("", id="error-msg")
            yield Button("Save", id="btn-save", variant="primary")

    def on_mount(self) -> None:
        self._update_resolved_path()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "path-input":
            self._update_resolved_path()
            self.query_one("#error-msg", Static).update("")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-default":
            self.query_one("#path-input", Input).value = default_results_dir()
        elif event.button.id == "btn-save":
            self._save()

    def _save(self) -> None:
        path_input = self.query_one("#path-input", Input)
        path_str = path_input.value.strip()
        error = validate_results_path(path_str)
        if error:
            self.query_one("#error-msg", Static).update(f"[red]{error}[/red]")
            path_input.focus()
            return
        resolved = resolve_display_path(path_str)
        save_config(DmitriConfig(results_dir=resolved))
        ensure_workspace_layout(Path(resolved))
        self.dismiss()

    def action_cancel(self) -> None:
        self.dismiss()

    def _update_resolved_path(self) -> None:
        path_str = self.query_one("#path-input", Input).value
        resolved = resolve_display_path(path_str)
        display = f"Workspace: [bold]{resolved}[/bold]" if resolved else ""
        self.query_one("#resolved-path", Static).update(display)
