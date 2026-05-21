"""Shared widgets for the Dmitri TUI."""

from __future__ import annotations

from textual.widgets import Static

APP_VERSION = "0.1.1"


class DmitriHeader(Static):
    """Global header bar shown on every screen."""

    DEFAULT_CSS = """
    DmitriHeader {
        dock: top;
        width: 100%;
        height: 1;
        background: $accent;
        color: $text;
        text-style: bold;
        content-align: center middle;
    }
    """

    def __init__(self) -> None:
        super().__init__(f"Dmitri (v{APP_VERSION})")
