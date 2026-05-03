"""Base screen with shared chrome for all Dmitri screens."""

from __future__ import annotations

from textual.screen import Screen
from textual.widgets import Footer

from agent.tui.widgets import DmitriHeader


class DmitriScreen(Screen):
    """Base screen that provides the global header and footer."""

    def compose(self):
        yield DmitriHeader()
        yield from self.compose_body()
        yield Footer()

    def compose_body(self):
        """Override in subclasses to provide screen-specific content."""
        return []
