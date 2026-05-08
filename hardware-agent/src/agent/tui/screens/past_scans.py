"""Past scans picker screen (S6) — list saved scan files for viewing."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from textual.binding import Binding
from textual.containers import Vertical
from textual.widgets import OptionList, Static
from textual.widgets.option_list import Option

from agent.tui.config import load_config
from agent.tui.screens.base import DmitriScreen
from agent.tui.screens.scan_view import ScanViewScreen


@dataclass(slots=True)
class ScanEntry:
    """Parsed metadata from a scan JSON file."""

    path: Path
    subnet: str
    timestamp: datetime


class PastScansScreen(DmitriScreen):
    """S6: browse and select past scan results."""

    BINDINGS = [
        Binding("escape", "go_back", "Back", priority=True),
        Binding("ctrl+r", "refresh", "Refresh", priority=True),
        Binding("j", "cursor_down", show=False, priority=True),
        Binding("k", "cursor_up", show=False, priority=True),
        Binding("up", "cursor_up", "↑↓ Navigate", show=True, priority=True),
        Binding("down", "cursor_down", show=False, priority=True),
        Binding("enter", "select_scan", "Enter Select", show=True, priority=True),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._entries: list[ScanEntry] = []

    def compose_body(self):
        with Vertical(id="past-scans-container"):
            yield Static("Past Scans", id="past-scans-title")
            yield OptionList(id="past-scans-list")
            yield Static("No scans found.", id="past-scans-empty")

    def on_mount(self) -> None:
        self._load_entries()

    def _load_entries(self) -> None:
        config = load_config()
        self._entries = []

        if config:
            results_dir = Path(config.results_dir) / "results"
            if results_dir.is_dir():
                for file_path in results_dir.glob("*.json"):
                    entry = self._parse_entry(file_path)
                    if entry:
                        self._entries.append(entry)

        self._entries.sort(key=lambda e: e.timestamp, reverse=True)
        self._render_list()

    def _parse_entry(self, file_path: Path) -> ScanEntry | None:
        try:
            text = file_path.read_text(encoding="utf-8")
            data = json.loads(text)
        except (OSError, json.JSONDecodeError):
            return None

        subnet = data.get("subnet")
        if not subnet or not isinstance(subnet, str):
            return None

        ts_raw = data.get("timestamp")
        if ts_raw:
            try:
                ts = datetime.fromisoformat(ts_raw)
            except (ValueError, TypeError):
                ts = datetime.fromtimestamp(file_path.stat().st_mtime, tz=timezone.utc)
        else:
            ts = datetime.fromtimestamp(file_path.stat().st_mtime, tz=timezone.utc)

        return ScanEntry(path=file_path, subnet=subnet, timestamp=ts)

    def _render_list(self) -> None:
        option_list = self.query_one("#past-scans-list", OptionList)
        empty_label = self.query_one("#past-scans-empty", Static)

        option_list.clear_options()

        if not self._entries:
            option_list.display = False
            empty_label.display = True
            return

        empty_label.display = False
        option_list.display = True

        for i, entry in enumerate(self._entries):
            when = entry.timestamp.strftime("%Y-%m-%d %H:%M")
            label = f"{entry.subnet:<20} {when}"
            option_list.add_option(Option(label, id=str(i)))

        option_list.focus()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        self._open_entry(event.option.id)

    def action_select_scan(self) -> None:
        option_list = self.query_one("#past-scans-list", OptionList)
        if option_list.highlighted is not None:
            option = option_list.get_option_at_index(option_list.highlighted)
            self._open_entry(option.id)

    def _open_entry(self, entry_id: str | None) -> None:
        if entry_id is None:
            return
        idx = int(entry_id)
        if 0 <= idx < len(self._entries):
            entry = self._entries[idx]
            self.app.push_screen(ScanViewScreen(scan_path=entry.path))

    def action_cursor_down(self) -> None:
        self.query_one("#past-scans-list", OptionList).action_cursor_down()

    def action_cursor_up(self) -> None:
        self.query_one("#past-scans-list", OptionList).action_cursor_up()

    def action_refresh(self) -> None:
        self._load_entries()
        self.notify("Refreshed.", severity="information")

    def action_go_back(self) -> None:
        self.dismiss(None)
