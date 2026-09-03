"""Scan category screen — General vs NSPi."""

from __future__ import annotations

from textual.binding import Binding
from textual.containers import Vertical
from textual.widgets import OptionList, Static
from textual.widgets.option_list import Option

from agent.tui.screens.base import DmitriScreen


class ScanCategoryScreen(DmitriScreen):
    """Wizard step between network and mode: pick scan category."""

    BINDINGS = [
        Binding("escape", "back", "Back"),
        Binding("j", "cursor_down", show=False, priority=True),
        Binding("k", "cursor_up", show=False, priority=True),
        Binding("up", "cursor_up", "↑↓ Navigate", show=True, priority=True),
        Binding("down", "cursor_down", show=False, priority=True),
        Binding("enter", "select", "Enter Select", show=True, priority=True),
    ]

    def __init__(self, subnet: str) -> None:
        super().__init__()
        self._subnet = subnet
        self._category: str | None = None

    def compose_body(self):
        with Vertical(id="scancategory-container"):
            yield Static("Select scan category", id="scancategory-title")
            yield OptionList(
                Option(
                    "General  —  Standard network scanning modes",
                    id="general",
                ),
                Option(
                    "NSPi     —  Industrial lab · OT/ICS devices",
                    id="nspi",
                ),
                id="scancategory-list",
            )

    def on_mount(self) -> None:
        self.query_one("#scancategory-list", OptionList).focus()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        self._push_mode_screen(event.option.id)

    def action_cursor_down(self) -> None:
        self.query_one("#scancategory-list", OptionList).action_cursor_down()

    def action_cursor_up(self) -> None:
        self.query_one("#scancategory-list", OptionList).action_cursor_up()

    def action_select(self) -> None:
        ol = self.query_one("#scancategory-list", OptionList)
        if ol.highlighted is not None:
            option = ol.get_option_at_index(ol.highlighted)
            self._push_mode_screen(option.id)

    def _push_mode_screen(self, category: str) -> None:
        from agent.tui.screens.scan_mode import ScanModeScreen

        self._category = category
        self.app.push_screen(
            ScanModeScreen(category=category),
            callback=self._on_mode_result,
        )

    def _on_mode_result(self, mode: str | None) -> None:
        if mode is None:
            return
        if self._category == "nspi":
            self.dismiss((self._subnet, "nspi", mode))
        else:
            self.dismiss((self._subnet, mode, None))

    def action_back(self) -> None:
        self.dismiss(None)
