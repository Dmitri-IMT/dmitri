"""Home screen (H) — central hub with navigation menu."""

from __future__ import annotations

from pathlib import Path

from textual.binding import Binding
from textual.containers import Vertical
from textual.widgets import Button, OptionList, Static
from textual.widgets.option_list import Option

from agent.paths import load_config
from agent.scanner.workspace import write_scan_result
from agent.tui.screens.base import DmitriScreen
from agent.tui.screens.network import NetworkScreen
from agent.tui.screens.past_scans import PastScansScreen
from agent.tui.screens.scan_progress import ScanProgressScreen
from agent.tui.screens.scan_view import ScanViewScreen, count_unique_open_endpoints

MENU_START_SCAN = "start_scan"
MENU_VIEW_SCAN = "view_scan"
MENU_PAST_SCANS = "past_scans"


class HomeScreen(DmitriScreen):
    """Home hub: menu dispatches to scan wizard, view, or past scans."""

    BINDINGS = [
        Binding("j", "cursor_down", show=False, priority=True),
        Binding("k", "cursor_up", show=False, priority=True),
        Binding("up", "cursor_up", "↑↓ Navigate", show=True, priority=True),
        Binding("down", "cursor_down", show=False, priority=True),
        Binding("enter", "select", "Enter Select", show=True, priority=True),
    ]

    def compose_body(self):
        with Vertical(id="home-menu-container"):
            yield OptionList(
                Option("Start scan", id=MENU_START_SCAN),
                Option("View scan", id=MENU_VIEW_SCAN),
                Option("Past scans", id=MENU_PAST_SCANS),
                id="home-menu",
            )
        with Vertical(id="summary-section"):
            yield Static("", id="summary-band")
            yield Button("View full scan", id="btn-view-full-scan", variant="default")

    def on_mount(self) -> None:
        self.query_one("#summary-section").display = False
        self.query_one("#home-menu", OptionList).focus()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        self._activate_item(event.option.id)

    def action_cursor_down(self) -> None:
        menu = self.query_one("#home-menu", OptionList)
        menu.action_cursor_down()

    def action_cursor_up(self) -> None:
        menu = self.query_one("#home-menu", OptionList)
        menu.action_cursor_up()

    def action_select(self) -> None:
        menu = self.query_one("#home-menu", OptionList)
        if menu.highlighted is not None:
            option = menu.get_option_at_index(menu.highlighted)
            self._activate_item(option.id)

    def _on_network_result(self, result: tuple[str, str, str | None] | None) -> None:
        if result is None:
            return
        subnet, mode, nspi_submode = result
        self.app.push_screen(
            ScanProgressScreen(
                subnet=subnet,
                scan_mode=mode,
                nspi_submode=nspi_submode,
            ),
            callback=self._on_scan_complete,
        )

    def _on_scan_complete(self, result) -> None:
        if result is None:
            return

        if isinstance(result, tuple):
            payload, navigate_to_view = result
        else:
            payload, navigate_to_view = result, False

        if payload is None:
            return

        self._last_payload = payload
        self._last_scan_path: Path | None = None

        config = load_config()
        if config:
            try:
                self._last_scan_path = write_scan_result(payload, config.results_dir)
            except OSError as exc:
                self.notify(f"Failed to save scan: {exc}", severity="error")

        devices = len(payload.hosts)
        ports = count_unique_open_endpoints(payload)
        findings = len(payload.findings)
        summary_lines = [
            f"Last scan: {payload.subnet}\n"
            f"  Devices: {devices} | Ports open: {ports} | "
            f"Vulnerabilities: {findings}"
        ]
        if payload.assessment_policy_version is None:
            summary_lines.append("  Attack surface: Unavailable")
        else:
            exposures = len(payload.exposures)
            attention = sum(
                exposure.attention in {"review", "priority"}
                for exposure in payload.exposures
            )
            attention_copy = (
                "1 needs attention" if attention == 1 else f"{attention} need attention"
            )
            summary_lines.append(
                f"  Attack surface: {exposures} "
                f"{'exposure' if exposures == 1 else 'exposures'} · {attention_copy}"
            )
        self.query_one("#summary-band", Static).update("\n".join(summary_lines))
        self.query_one("#summary-section").display = True

        if navigate_to_view:
            self.app.push_screen(
                ScanViewScreen(scan_path=self._last_scan_path, payload=payload)
            )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-view-full-scan":
            self._view_last_scan()

    def _view_last_scan(self) -> None:
        if hasattr(self, "_last_payload") and self._last_payload:
            scan_path = getattr(self, "_last_scan_path", None)
            self.app.push_screen(
                ScanViewScreen(scan_path=scan_path, payload=self._last_payload)
            )
        else:
            self.notify("No recent scan.", severity="warning")

    def _activate_item(self, item_id: str | None) -> None:
        if item_id == MENU_START_SCAN:
            self.app.push_screen(NetworkScreen(), callback=self._on_network_result)
        elif item_id == MENU_VIEW_SCAN:
            self._view_last_scan()
        elif item_id == MENU_PAST_SCANS:
            self.app.push_screen(PastScansScreen())
