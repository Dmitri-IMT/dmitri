"""Full scan view screen (S7) — renders a scan result in readable format."""

from __future__ import annotations

import json
from pathlib import Path

from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.widgets import Static

from agent.normalize.contracts import ScanPayload
from agent.tui.screens.base import DmitriScreen

MODE_LABELS = {"quick": "Quick", "standard": "Standard", "full": "Full", "nspi": "NSPi"}

SEVERITY_COLORS = {
    "critical": "red bold",
    "high": "red",
    "medium": "yellow",
    "low": "dim",
}


def _has_iolink_banner(device) -> bool:
    for p in device.ports:
        if p.version and any(kw in p.version.lower() for kw in ("balluf", "io-link")):
            return True
    return False


class ScanViewScreen(DmitriScreen):
    """S7: full scan results display."""

    BINDINGS = [
        Binding("escape", "go_back", "Back", priority=True),
    ]

    def __init__(
        self,
        scan_path: Path | None = None,
        payload: ScanPayload | None = None,
    ) -> None:
        super().__init__()
        self._scan_path = scan_path
        self._payload = payload

    def compose_body(self):
        with VerticalScroll(id="scan-view-scroll"):
            yield Static("", id="scan-view-content")

    def on_mount(self) -> None:
        payload = self._load_payload()
        if payload is None:
            self.query_one("#scan-view-content", Static).update(
                "[red]Failed to load scan results.[/red]"
            )
            return
        rendered = self._render_payload(payload)
        self.query_one("#scan-view-content", Static).update(rendered)

    def _load_payload(self) -> ScanPayload | None:
        if self._payload:
            return self._payload
        if self._scan_path and self._scan_path.is_file():
            try:
                data = json.loads(self._scan_path.read_text(encoding="utf-8"))
                return ScanPayload.model_validate(data)
            except (json.JSONDecodeError, ValueError, OSError):
                return None
        return None

    def _render_payload(self, payload: ScanPayload) -> str:
        lines: list[str] = []

        lines.append("[bold]── Scan Results ──────────────────────────────[/bold]")
        lines.append(f"Target:   {payload.subnet}")
        lines.append(f"Date:     {payload.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        mode_label = MODE_LABELS.get(
            payload.scan_mode, payload.scan_mode.capitalize()
        )
        lines.append(f"Mode:     {mode_label}")
        if payload.metadata and "elapsed_seconds" in payload.metadata:
            elapsed = payload.metadata["elapsed_seconds"]
            lines.append(f"Duration: {elapsed}s")
        lines.append("")

        device_count = len(payload.devices)
        lines.append(
            f"[bold]── Devices ({device_count}) ──────────────────────────────[/bold]"
        )
        lines.append("")

        findings_by_ip: dict[str, list] = {}
        for f in payload.findings:
            ip_key = str(f.ip) if f.ip else "_global"
            findings_by_ip.setdefault(ip_key, []).append(f)

        for device in payload.devices:
            ip_str = str(device.ip)
            vendor_str = f" — {device.vendor}" if device.vendor else ""
            lines.append(f"[bold]▶ {ip_str}[/bold] ({device.hostname}){vendor_str}")

            if device.ports:
                lines.append("  Ports:")
                for p in device.ports:
                    version_str = f"  {p.version}" if p.version else ""
                    line = (
                        f"    {p.port}/{p.protocol:<4} "
                        f"{p.state:<8} {p.service:<10}"
                        f"{version_str}"
                    )
                    lines.append(line)

            if _has_iolink_banner(device):
                lines.append("  [bold]⚙ IO-Link Master detected[/bold]")

            device_findings = findings_by_ip.get(ip_str, [])
            if device_findings:
                lines.append("  Vulnerabilities:")
                for f in device_findings:
                    sev = f.severity.upper()
                    color = SEVERITY_COLORS.get(f.severity, "")
                    cve = f.cve_id or "N/A"
                    cvss = f"(CVSS {f.cvss_score})" if f.cvss_score is not None else ""
                    lines.append(
                        f"    [{color}][{sev}][/{color}] {cve} — {f.title} {cvss}"
                    )

            lines.append("")

        lines.append("[bold]── Summary ──────────────────────────────────[/bold]")
        total_ports = sum(len(d.ports) for d in payload.devices)
        lines.append(f"Total devices:          {device_count}")
        lines.append(f"Total open ports:       {total_ports}")
        lines.append(f"Vulnerabilities found:  {len(payload.findings)}")

        return "\n".join(lines)

    def action_go_back(self) -> None:
        self.dismiss(None)
