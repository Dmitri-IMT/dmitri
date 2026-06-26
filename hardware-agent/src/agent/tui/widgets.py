"""Shared widgets for the Dmitri TUI."""

from __future__ import annotations

import os

from rich.text import Text
from textual.widgets import Static

APP_VERSION = "0.1.4"

SPINNER_FRAMES = ("◐", "◓", "◑", "◒")


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


class CircleSpinner(Static):
    """Single-character rotating circle spinner."""

    DEFAULT_CSS = """
    CircleSpinner {
        width: 2;
        height: 1;
        color: yellow;
        content-align: left middle;
    }
    """

    def on_mount(self) -> None:
        self._frame = 0
        self.set_interval(0.08, self._advance)

    def _advance(self) -> None:
        if os.environ.get("TEXTUAL_ANIMATIONS") == "none":
            return
        self._frame = (self._frame + 1) % len(SPINNER_FRAMES)
        self.refresh()

    def render(self) -> Text:
        frame = SPINNER_FRAMES[self._frame % len(SPINNER_FRAMES)]
        return Text(frame, style="yellow")
