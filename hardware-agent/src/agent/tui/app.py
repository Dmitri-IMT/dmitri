"""Dmitri Textual application."""

from __future__ import annotations

from pathlib import Path

from textual.app import App
from textual.binding import Binding

from agent.tui.config import load_config
from agent.tui.screens.home import HomeScreen
from agent.tui.screens.scan_progress import ScanProgressScreen
from agent.tui.screens.settings import SettingsScreen
from agent.tui.screens.setup import SetupScreen


class DmitriApp(App[None]):
    """Root Textual application for Dmitri."""

    TITLE = "Dmitri"
    CSS_PATH = Path("app.tcss")

    BINDINGS = [
        Binding("ctrl+q", "quit_app", "Quit", priority=True),
        Binding("ctrl+t", "settings", "Settings", priority=True),
    ]

    SCREENS = {
        "home": HomeScreen,
        "setup": SetupScreen,
    }

    def on_ready(self) -> None:
        config = load_config()
        if config is None:
            self.push_screen("setup")
        else:
            self.push_screen("home")

    def action_quit_app(self) -> None:
        if isinstance(self.screen, ScanProgressScreen):
            self.screen.action_abort()
        self.exit()

    def action_settings(self) -> None:
        if isinstance(self.screen, ScanProgressScreen):
            return
        self.push_screen(SettingsScreen())
