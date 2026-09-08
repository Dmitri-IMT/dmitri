"""Full scan view screen (S7) — renders a scan result in readable format."""

from __future__ import annotations

import json
from pathlib import Path

from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.widgets import Static

from agent.normalize.contracts import ScanPayload
from agent.tui.screens.base import DmitriScreen

MODE_LABELS = {
    "quick": "Quick",
    "standard": "Standard",
    "extensive": "Extensive",
    "nspi": "NSPi",
    "max": "MAX",
}

SEVERITY_COLORS = {
    "critical": "red bold",
    "high": "red",
    "medium": "yellow",
    "low": "dim",
}


def format_duration(seconds: float) -> str:
    total = round(seconds)
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if total >= 3600:
        return f"{hours}h {minutes:02d}m {secs:02d}s"
    if total >= 60:
        return f"{minutes}m {secs:02d}s"
    return f"{secs}s"


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
        mode_label = MODE_LABELS.get(payload.scan_mode, payload.scan_mode.capitalize())
        if payload.scan_mode == "nspi" and payload.metadata:
            submode = payload.metadata.get("nspi_submode")
            submode_label = {
                "inventory": "Inventory",
                "read_only_mapping": "Read-only mapping",
                "active_validation": "Active validation",
            }.get(str(submode))
            if submode_label:
                mode_label = f"{mode_label} · {submode_label}"
        lines.append(f"Mode:     {mode_label}")
        if payload.metadata and "elapsed_seconds" in payload.metadata:
            elapsed = payload.metadata["elapsed_seconds"]
            lines.append(f"Duration: {format_duration(elapsed)}")
        lines.append("")

        device_count = len(payload.hosts)
        lines.append(
            f"[bold]── Devices ({device_count}) ──────────────────────────────[/bold]"
        )
        lines.append("")

        findings_by_ip: dict[str, list] = {}
        for f in payload.findings:
            ip_key = str(f.ip) if f.ip else "_global"
            findings_by_ip.setdefault(ip_key, []).append(f)

        for device in payload.hosts:
            ip_str = str(device.ip)
            vendor_str = f" — {device.vendor}" if device.vendor else ""
            lines.append(f"[bold]▶ {ip_str}[/bold] ({device.hostname}){vendor_str}")

            operating_system = device.operating_system
            if operating_system is None:
                lines.append("  Operating system: Not detected")
            else:
                lines.append("  Operating system:")
                lines.append(
                    f"    Detected: {operating_system.name} "
                    f"({operating_system.accuracy}% confidence)"
                )
                if operating_system.vendor is not None:
                    lines.append(f"    Vendor: {operating_system.vendor}")
                if operating_system.family is not None:
                    lines.append(f"    Family: {operating_system.family}")
                if operating_system.generation is not None:
                    lines.append(f"    Generation: {operating_system.generation}")
                if operating_system.device_type is not None:
                    lines.append(f"    Device type: {operating_system.device_type}")
                if operating_system.cpes:
                    lines.append("    Platform IDs:")
                    for platform_id in operating_system.cpes:
                        lines.append(f"      - {platform_id}")

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

            if device.industrial_services:
                lines.append("  Industrial inventory:")
                for service in device.industrial_services:
                    confidence = service.confidence.upper()
                    lines.append(f"    Modbus TCP {service.port} - {confidence}")
                    if service.mapping_source:
                        lines.append(f"      Mapping plan: {service.mapping_source}")
                    for unit in service.units:
                        detail = unit.device_identification
                        fields = []
                        if detail is not None:
                            if detail.vendor_name:
                                fields.append(f"vendor {detail.vendor_name}")
                            if detail.product_code:
                                fields.append(f"product {detail.product_code}")
                            if detail.major_minor_revision:
                                fields.append(f"firmware {detail.major_minor_revision}")
                        suffix = f"; {', '.join(fields)}" if fields else ""
                        lines.append(
                            f"      Unit ID {unit.unit_id}: {unit.status}{suffix}"
                        )
                        for address_range in unit.address_ranges:
                            end = address_range.start_address + address_range.count - 1
                            summary_parts = []
                            if address_range.nonzero_count is not None:
                                summary_parts.append(
                                    f"nonzero {address_range.nonzero_count}"
                                )
                            if address_range.value_min is not None:
                                summary_parts.append(f"min {address_range.value_min}")
                            if address_range.value_max is not None:
                                summary_parts.append(f"max {address_range.value_max}")
                            summary = (
                                f" · {' · '.join(summary_parts)}"
                                if summary_parts
                                else ""
                            )
                            lines.append(
                                "        "
                                f"{address_range.address_space} "
                                f"{address_range.start_address}-{end}: "
                                f"{address_range.status}{summary}"
                            )

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
        total_ports = sum(len(d.ports) for d in payload.hosts)
        lines.append(f"Total devices:          {device_count}")
        lines.append(f"Total open ports:       {total_ports}")
        lines.append(f"Vulnerabilities found:  {len(payload.findings)}")
        modbus_services = sum(
            len(device.industrial_services) for device in payload.hosts
        )
        if modbus_services:
            modbus_units = sum(
                len(service.units)
                for device in payload.hosts
                for service in device.industrial_services
            )
            lines.append(f"Modbus services:        {modbus_services}")
            lines.append(f"Modbus Unit IDs:        {modbus_units}")
            mapped_ranges = sum(
                len(unit.address_ranges)
                for device in payload.hosts
                for service in device.industrial_services
                for unit in service.units
            )
            if mapped_ranges:
                lines.append(f"Modbus mapped ranges:   {mapped_ranges}")

        return "\n".join(lines)

    def action_go_back(self) -> None:
        self.dismiss(None)
