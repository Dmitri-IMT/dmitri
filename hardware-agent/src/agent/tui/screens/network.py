"""Network selection screen (S2) — pick interface/subnet to scan."""

from __future__ import annotations

import ipaddress

import psutil
from textual.binding import Binding
from textual.containers import Vertical
from textual.widgets import OptionList, Static
from textual.widgets.option_list import Option

from agent.tui.screens.base import DmitriScreen


def _detect_interfaces() -> list[tuple[str, str]]:
    """Return (interface_name, subnet_cidr) for all valid IPv4 interfaces."""
    results: list[tuple[str, str]] = []
    for name, addrs in psutil.net_if_addrs().items():
        for addr in addrs:
            if getattr(addr.family, "name", "") != "AF_INET":
                continue
            if not addr.netmask:
                continue
            ip = addr.address
            if ip.startswith("127.") or ip.startswith("169.254."):
                continue
            try:
                subnet = ipaddress.IPv4Network(f"{ip}/{addr.netmask}", strict=False)
            except ValueError:
                continue
            results.append((name, str(subnet)))
    return results


class NetworkScreen(DmitriScreen):
    """Wizard step 1: user picks which network to scan."""

    BINDINGS = [
        Binding("escape", "back", "Back"),
        Binding("j", "cursor_down", show=False, priority=True),
        Binding("k", "cursor_up", show=False, priority=True),
        Binding("up", "cursor_up", "↑↓ Navigate", show=True, priority=True),
        Binding("down", "cursor_down", show=False, priority=True),
        Binding("enter", "select", "Enter Select", show=True, priority=True),
        Binding("ctrl+r", "refresh", "Refresh"),
    ]

    def compose_body(self):
        with Vertical(id="network-container"):
            yield Static("Select network", id="network-title")
            yield OptionList(id="network-list")
            yield Static("", id="network-empty")

    def on_mount(self) -> None:
        self._populate()

    def _populate(self) -> None:
        option_list = self.query_one("#network-list", OptionList)
        option_list.clear_options()
        interfaces = _detect_interfaces()
        empty_msg = self.query_one("#network-empty", Static)
        if not interfaces:
            empty_msg.update("[yellow]No network interfaces found.[/yellow]")
            return
        empty_msg.update("")
        for idx, (name, subnet) in enumerate(interfaces):
            option_list.add_option(Option(f"{name}  —  {subnet}", id=f"{idx}:{subnet}"))
        option_list.focus()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        subnet = self._subnet_from_id(event.option.id)
        if subnet:
            self._push_scan_mode(subnet)

    def action_cursor_down(self) -> None:
        self.query_one("#network-list", OptionList).action_cursor_down()

    def action_cursor_up(self) -> None:
        self.query_one("#network-list", OptionList).action_cursor_up()

    def action_select(self) -> None:
        ol = self.query_one("#network-list", OptionList)
        if ol.highlighted is not None:
            option = ol.get_option_at_index(ol.highlighted)
            subnet = self._subnet_from_id(option.id)
            if subnet:
                self._push_scan_mode(subnet)

    def _push_scan_mode(self, subnet: str) -> None:
        from agent.tui.screens.scan_category import ScanCategoryScreen

        self.app.push_screen(
            ScanCategoryScreen(subnet),
            callback=self._on_mode_result,
        )

    def _on_mode_result(self, result: tuple[str, str, str | None] | None) -> None:
        if result is None:
            return
        self.dismiss(result)

    @staticmethod
    def _subnet_from_id(option_id: str | None) -> str | None:
        if option_id is None:
            return None
        return option_id.split(":", 1)[1] if ":" in option_id else option_id

    def action_back(self) -> None:
        self.dismiss(None)

    def action_refresh(self) -> None:
        self._populate()
        self.notify("Network list refreshed.", severity="information")
