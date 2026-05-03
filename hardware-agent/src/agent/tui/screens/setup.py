"""Setup screen (S0) — first-run results directory configuration."""

from __future__ import annotations

from textual.binding import Binding
from textual.containers import Vertical
from textual.widgets import Button, Input, Label, Static

from agent.tui.config import (
    DmitriConfig,
    default_results_dir,
    resolve_display_path,
    save_config,
    validate_results_path,
)
from agent.tui.screens.base import DmitriScreen


class SetupScreen(DmitriScreen):
    """First-run setup: user picks where scan results are stored."""

    BINDINGS = [
        Binding("escape", "no_op", show=False),
    ]

    def compose_body(self):
        with Vertical(id="setup-container"):
            yield Static("First-time setup", id="setup-title")
            yield Static(
                "Choose where scan results will be saved.", id="setup-subtitle"
            )
            yield Label("Results directory:")
            yield Input(
                value=default_results_dir(),
                placeholder="Enter path...",
                id="path-input",
            )
            yield Button("Use default", id="btn-default", variant="default")
            yield Static("", id="resolved-path")
            yield Static("", id="error-msg")
            yield Button("Confirm", id="btn-confirm", variant="primary")

    def on_mount(self) -> None:
        self._update_resolved_path()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "path-input":
            self._update_resolved_path()
            self.query_one("#error-msg", Static).update("")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-default":
            self.query_one("#path-input", Input).value = default_results_dir()
        elif event.button.id == "btn-confirm":
            self._confirm()

    def _confirm(self) -> None:
        path_input = self.query_one("#path-input", Input)
        path_str = path_input.value.strip()
        error = validate_results_path(path_str)
        if error:
            self.query_one("#error-msg", Static).update(f"[red]{error}[/red]")
            path_input.focus()
            return
        resolved = resolve_display_path(path_str)
        save_config(DmitriConfig(results_dir=resolved))
        self.app.pop_screen()
        self.app.push_screen("home")

    def _update_resolved_path(self) -> None:
        path_str = self.query_one("#path-input", Input).value
        resolved = resolve_display_path(path_str)
        display = f"Scans will be saved to: [bold]{resolved}[/bold]" if resolved else ""
        self.query_one("#resolved-path", Static).update(display)

    def action_no_op(self) -> None:
        pass
