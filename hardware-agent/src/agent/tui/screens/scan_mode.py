"""Scan mode screen (S3) — pick scan intensity."""

from __future__ import annotations

from typing import Literal

from textual.binding import Binding
from textual.containers import Vertical
from textual.widgets import OptionList, Static
from textual.widgets.option_list import Option

from agent.tui.screens.base import DmitriScreen

_GENERAL_OPTIONS = [
    Option("Quick      —  Top 1000 ports · CVE detection · ~2–5 min", id="quick"),
    Option("Standard   —  Top 1000 ports · Service scripts · ~5–10 min", id="standard"),
    Option(
        "Extensive  —  Top 10000 ports · Full security analysis · ~20–35 min",
        id="extensive",
    ),
    Option("MAX        —  Coming soon", id="max", disabled=True),
]

_NSPI_OPTIONS = [
    Option(
        "NSPi Standard  —  Industrial ports · OT + security scripts · ~20–30 min",
        id="nspi",
    ),
]


class ScanModeScreen(DmitriScreen):
    """Wizard step 2: user picks quick or full scan mode."""

    BINDINGS = [
        Binding("escape", "back", "Back"),
        Binding("j", "cursor_down", show=False, priority=True),
        Binding("k", "cursor_up", show=False, priority=True),
        Binding("up", "cursor_up", "↑↓ Navigate", show=True, priority=True),
        Binding("down", "cursor_down", show=False, priority=True),
        Binding("enter", "select", "Enter Select", show=True, priority=True),
    ]

    def __init__(self, category: Literal["general", "nspi"] = "general") -> None:
        super().__init__()
        self._category = category

    def compose_body(self):
        title = "Select NSPi mode" if self._category == "nspi" else "Select scan mode"
        options = _NSPI_OPTIONS if self._category == "nspi" else _GENERAL_OPTIONS
        with Vertical(id="scanmode-container"):
            yield Static(title, id="scanmode-title")
            yield OptionList(*options, id="scanmode-list")

    def on_mount(self) -> None:
        self.query_one("#scanmode-list", OptionList).focus()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        self.dismiss(event.option.id)

    def action_cursor_down(self) -> None:
        self.query_one("#scanmode-list", OptionList).action_cursor_down()

    def action_cursor_up(self) -> None:
        self.query_one("#scanmode-list", OptionList).action_cursor_up()

    def action_select(self) -> None:
        ol = self.query_one("#scanmode-list", OptionList)
        if ol.highlighted is not None:
            option = ol.get_option_at_index(ol.highlighted)
            self.dismiss(option.id)

    def action_back(self) -> None:
        self.dismiss(None)
