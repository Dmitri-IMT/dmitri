"""Full scan view screen (S7) — renders a scan result in readable format."""

from __future__ import annotations

import json
from pathlib import Path

from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.widgets import Static

from agent.normalize.contracts import (
    ModbusAddressRangePayload,
    ModbusDeviceIdentificationPayload,
    ModbusUnitPayload,
    ScanPayload,
)
from agent.tui.markup import (
    LIMIT_HOST_TEXT,
    LIMIT_IDENTIFICATION,
    LIMIT_MAPPING_SOURCE,
    LIMIT_OBJECT_KEY,
    LIMIT_OBJECT_VALUE,
    LIMIT_PORT_TEXT,
    LIMIT_RANGE_LABEL,
    LIMIT_UNIT_ERROR,
    MAX_CPES_SHOWN,
    MAX_OBJECTS_SHOWN,
    ShortenTracker,
    safe,
)
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

NOTICE_ONE = (
    "⚠ Device-supplied text is shown literally. "
    "1 value was shortened to fit its display limit."
)
NOTICE_MANY = (
    "⚠ Device-supplied text is shown literally. "
    "{count} values were shortened to fit their display limits."
)
PROCESS_NOTE = (
    "Process values are never shown. "
    "Address ranges report status and a keyed change digest only."
)


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


def _payload_has_address_ranges(payload: ScanPayload) -> bool:
    for device in payload.hosts:
        for service in device.industrial_services:
            for unit in service.units:
                if unit.address_ranges:
                    return True
    return False


def _digest_prefix(value_digest: str) -> str:
    return value_digest.removeprefix("hmac-sha256:")[:8].lower()


def _format_range_line(
    address_range: ModbusAddressRangePayload,
    tracker: ShortenTracker,
) -> str:
    end = address_range.start_address + address_range.count - 1
    line = (
        f"        {address_range.address_space} "
        f"{address_range.start_address}-{end}: {address_range.status}"
    )
    if address_range.label:
        label = safe(address_range.label, LIMIT_RANGE_LABEL, tracker=tracker)
        line = f"{line} ({label})"
    suffix_parts: list[str] = []
    if address_range.exception_code is not None:
        suffix_parts.append(f"exception {address_range.exception_code}")
    if address_range.status == "readable":
        if address_range.value_digest:
            suffix_parts.append(f"digest {_digest_prefix(address_range.value_digest)}")
        else:
            suffix_parts.append("digest not recorded")
    elif address_range.value_digest:
        suffix_parts.append(f"digest {_digest_prefix(address_range.value_digest)}")
    if suffix_parts:
        line = f"{line} · {' · '.join(suffix_parts)}"
    return line


def _format_identification_fields(
    detail: ModbusDeviceIdentificationPayload,
    tracker: ShortenTracker,
) -> list[str]:
    fields: list[str] = []
    mapping = (
        ("vendor_name", "vendor", LIMIT_IDENTIFICATION),
        ("product_code", "product", LIMIT_IDENTIFICATION),
        ("product_name", "product name", LIMIT_IDENTIFICATION),
        ("major_minor_revision", "firmware", LIMIT_IDENTIFICATION),
        ("model_name", "model", LIMIT_IDENTIFICATION),
        ("user_application_name", "application", LIMIT_IDENTIFICATION),
    )
    for attr, label, limit in mapping:
        value = getattr(detail, attr)
        if value:
            fields.append(f"{label} {safe(value, limit, tracker=tracker)}")
    return fields


def _format_identification_objects(
    detail: ModbusDeviceIdentificationPayload,
    tracker: ShortenTracker,
) -> list[str]:
    if not detail.objects:
        return []
    lines = ["         Identification extras:"]
    sorted_items = sorted(detail.objects.items(), key=lambda item: item[0])
    shown = sorted_items[:MAX_OBJECTS_SHOWN]
    for key, value in shown:
        safe_key = safe(key, LIMIT_OBJECT_KEY, tracker=tracker)
        safe_value = safe(value, LIMIT_OBJECT_VALUE, tracker=tracker)
        lines.append(f"           {safe_key} = {safe_value}")
    overflow = len(sorted_items) - len(shown)
    if overflow > 0:
        lines.append(
            f"           … {overflow} more identification objects not shown"
        )
    return lines


def _format_unit_lines(unit: ModbusUnitPayload, tracker: ShortenTracker) -> list[str]:
    lines: list[str] = []
    prefix = f"      Unit ID {unit.unit_id}: {unit.status}"
    if unit.error:
        prefix = f"{prefix}; {safe(unit.error, LIMIT_UNIT_ERROR, tracker=tracker)}"
    detail = unit.device_identification
    if detail is not None:
        fields = _format_identification_fields(detail, tracker)
        if fields:
            prefix = f"{prefix}; {', '.join(fields)}"
    lines.append(prefix)
    if detail is not None:
        lines.extend(_format_identification_objects(detail, tracker))
    for address_range in unit.address_ranges:
        lines.append(_format_range_line(address_range, tracker))
    return lines


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
            yield Static("", id="scan-view-notice")
            yield Static(PROCESS_NOTE, id="scan-view-process-note")
            yield Static("", id="scan-view-content")

    def on_mount(self) -> None:
        notice = self.query_one("#scan-view-notice", Static)
        process_note = self.query_one("#scan-view-process-note", Static)
        notice.display = False
        process_note.display = False
        payload = self._load_payload()
        if payload is None:
            self.query_one("#scan-view-content", Static).update(
                "[red]Failed to load scan results.[/red]"
            )
            return
        tracker = ShortenTracker()
        rendered = self._render_payload(payload, tracker=tracker)
        self.query_one("#scan-view-content", Static).update(rendered)
        if tracker.count == 1:
            notice.update(NOTICE_ONE)
            notice.display = True
        elif tracker.count > 1:
            notice.update(NOTICE_MANY.format(count=tracker.count))
            notice.display = True
        process_note.display = _payload_has_address_ranges(payload)

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

    def _render_payload(
        self,
        payload: ScanPayload,
        *,
        tracker: ShortenTracker | None = None,
    ) -> str:
        shorten = tracker or ShortenTracker()
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
        if payload.metadata and payload.metadata.get("modbus_stage_deadline_reached"):
            seconds = payload.metadata.get("modbus_stage_deadline_seconds", 0)
            lines.append(
                f"Limits:   Time limit reached during Modbus inventory ({seconds}s)"
            )
        lines.append("")

        device_count = len(payload.hosts)
        lines.append(
            f"[bold]── Devices ({device_count}) ──────────────────────────────[/bold]"
        )
        lines.append("")

        findings_by_ip: dict[str, list] = {}
        for finding in payload.findings:
            ip_key = str(finding.ip) if finding.ip else "_global"
            findings_by_ip.setdefault(ip_key, []).append(finding)

        for device in payload.hosts:
            ip_str = str(device.ip)
            hostname = safe(device.hostname, LIMIT_HOST_TEXT, tracker=shorten)
            vendor_suffix = ""
            if device.vendor:
                vendor_suffix = (
                    f" — {safe(device.vendor, LIMIT_HOST_TEXT, tracker=shorten)}"
                )
            lines.append(f"[bold]▶ {ip_str}[/bold] ({hostname}){vendor_suffix}")

            operating_system = device.operating_system
            if operating_system is None:
                lines.append("  Operating system: Not detected")
            else:
                lines.append("  Operating system:")
                os_name = safe(
                    operating_system.name, LIMIT_HOST_TEXT, tracker=shorten
                )
                lines.append(
                    f"    Detected: {os_name} "
                    f"({operating_system.accuracy}% confidence)"
                )
                if operating_system.vendor is not None:
                    vendor = safe(
                        operating_system.vendor, LIMIT_HOST_TEXT, tracker=shorten
                    )
                    lines.append(f"    Vendor: {vendor}")
                if operating_system.family is not None:
                    family = safe(
                        operating_system.family, LIMIT_HOST_TEXT, tracker=shorten
                    )
                    lines.append(f"    Family: {family}")
                if operating_system.generation is not None:
                    generation = safe(
                        operating_system.generation, LIMIT_HOST_TEXT, tracker=shorten
                    )
                    lines.append(f"    Generation: {generation}")
                if operating_system.device_type is not None:
                    device_type = safe(
                        operating_system.device_type, LIMIT_HOST_TEXT, tracker=shorten
                    )
                    lines.append(f"    Device type: {device_type}")
                if operating_system.cpes:
                    lines.append("    Platform IDs:")
                    shown_cpes = operating_system.cpes[:MAX_CPES_SHOWN]
                    for platform_id in shown_cpes:
                        lines.append(
                            "      - "
                            f"{safe(platform_id, LIMIT_HOST_TEXT, tracker=shorten)}"
                        )
                    cpe_overflow = len(operating_system.cpes) - len(shown_cpes)
                    if cpe_overflow > 0:
                        lines.append(
                            f"      … {cpe_overflow} more platform IDs not shown"
                        )

            if device.ports:
                lines.append("  Ports:")
                for port in device.ports:
                    service = safe(port.service, LIMIT_PORT_TEXT, tracker=shorten)
                    version_str = ""
                    if port.version:
                        version_str = (
                            f"  {safe(port.version, LIMIT_PORT_TEXT, tracker=shorten)}"
                        )
                    line = (
                        f"    {port.port}/{port.protocol:<4} "
                        f"{port.state:<8} {service:<10}"
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
                        mapping_source = safe(
                            service.mapping_source,
                            LIMIT_MAPPING_SOURCE,
                            tracker=shorten,
                        )
                        lines.append(f"      Mapping plan: {mapping_source}")
                    for unit in service.units:
                        lines.extend(_format_unit_lines(unit, shorten))

            device_findings = findings_by_ip.get(ip_str, [])
            if device_findings:
                lines.append("  Vulnerabilities:")
                for finding in device_findings:
                    sev = finding.severity.upper()
                    color = SEVERITY_COLORS.get(finding.severity, "")
                    cve = finding.cve_id or "N/A"
                    cvss = (
                        f"(CVSS {finding.cvss_score})"
                        if finding.cvss_score is not None
                        else ""
                    )
                    lines.append(
                        f"    [{color}][{sev}][/{color}] {cve} — {finding.title} {cvss}"
                    )

            lines.append("")

        lines.append("[bold]── Summary ──────────────────────────────────[/bold]")
        total_ports = sum(len(host.ports) for host in payload.hosts)
        lines.append(f"Total devices:          {device_count}")
        lines.append(f"Total open ports:       {total_ports}")
        lines.append(f"Vulnerabilities found:  {len(payload.findings)}")
        modbus_services = sum(
            len(host.industrial_services) for host in payload.hosts
        )
        if modbus_services:
            modbus_units = sum(
                len(service.units)
                for host in payload.hosts
                for service in host.industrial_services
            )
            lines.append(f"Modbus services:        {modbus_services}")
            lines.append(f"Modbus Unit IDs:        {modbus_units}")
            mapped_ranges = sum(
                len(unit.address_ranges)
                for host in payload.hosts
                for service in host.industrial_services
                for unit in service.units
            )
            if mapped_ranges:
                lines.append(f"Modbus mapped ranges:   {mapped_ranges}")

        return "\n".join(lines)

    def action_go_back(self) -> None:
        self.dismiss(None)
