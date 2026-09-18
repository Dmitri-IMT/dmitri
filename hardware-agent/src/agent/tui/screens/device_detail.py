"""Read-only local detail for one device in a scan payload."""

from __future__ import annotations

from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.widgets import Static

from agent.normalize.contracts import (
    FindingPayload,
    HostPayload,
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
from agent.tui.screens.scan_view import MACHINE_TYPE_LABELS, STAGE_LABELS

ROLE_LABELS = {
    "administration": "Administration",
    "api": "API",
    "data_store": "Data store",
    "file_sharing": "File sharing",
    "remote_access": "Remote access",
    "proxy": "Proxy",
    "device_control": "Device control",
    "discovery": "Discovery",
    "media": "Media",
    "general_service": "General service",
    "unknown": "Unknown",
}
SEVERITY_COLORS = {
    "critical": "red bold",
    "high": "red",
    "medium": "yellow",
    "low": "dim",
}


class DeviceDetailScreen(DmitriScreen):
    """Show stored inventory, assessment, and findings for one host."""

    BINDINGS = [Binding("escape", "go_back", "Back", priority=True)]

    def __init__(self, payload: ScanPayload, host: HostPayload) -> None:
        super().__init__()
        self._payload = payload
        self._host = host

    def compose_body(self):
        with VerticalScroll(id="device-detail-scroll"):
            yield Static(self._render_header(), id="device-detail-header")
            yield Static("", id="device-partial-banner")
            yield Static(self._render_profile(), id="device-profile")
            yield Static(self._render_inventory(), id="device-inventory")
            yield Static(self._render_exposures(), id="device-exposures")
            yield Static(self._render_findings(), id="device-findings")
            yield Static(self._render_industrial(), id="device-industrial")

    def on_mount(self) -> None:
        banner = self.query_one("#device-partial-banner", Static)
        metadata = self._payload.metadata or {}
        partial = metadata.get("partial_result") is True
        banner.display = partial
        if partial:
            if metadata.get("terminated_by") == "completed":
                banner.update(
                    "⚠ INCOMPLETE EVIDENCE — The scan finished, but some checks did "
                    "not complete. This device shows accepted evidence only."
                )
                banner.set_classes("incomplete")
            else:
                stage = STAGE_LABELS.get(str(metadata.get("interrupted_stage", "")))
                unfinished = (
                    f"{stage} did not finish." if stage else "The scan did not finish."
                )
                banner.update(
                    f"■ STOPPED SCAN — {unfinished} This device shows accepted "
                    "evidence only."
                )
                banner.set_classes("stopped")
        industrial = self.query_one("#device-industrial", Static)
        industrial.display = bool(self._host.industrial_services)

    def _render_header(self) -> str:
        hostname = safe(self._host.hostname, LIMIT_HOST_TEXT)
        lines = [f"[bold]{self._host.ip} · {hostname}[/bold]"]
        if self._host.vendor:
            lines.append(
                f"Observed MAC vendor: {safe(self._host.vendor, LIMIT_HOST_TEXT)}"
            )
        return "\n".join(lines)

    def _render_profile(self) -> str:
        lines = ["[bold]Profile[/bold]"]
        if self._payload.assessment_policy_version is None:
            lines.append(
                "[dim]Unavailable — this scan predates device profiling. Re-run "
                "the scan to produce this data.[/dim]"
            )
            return "\n".join(lines)
        profile = self._host.device_profile
        if profile is None:
            lines.append("Unknown")
            return "\n".join(lines)
        machine = MACHINE_TYPE_LABELS.get(
            self._host.machine_type or "unknown", "Unknown"
        )
        lines.append(f"Machine type: {machine}")
        manufacturer = (
            safe(profile.manufacturer)
            if profile.manufacturer
            else "Unknown"
        )
        lines.append(f"Manufacturer: {manufacturer}")
        if profile.product_family and profile.model:
            product = (
                f"{safe(profile.product_family)} · {safe(profile.model)}"
            )
        elif profile.product_family:
            product = f"{safe(profile.product_family)}; exact model unknown"
        elif profile.model:
            product = safe(profile.model)
        else:
            product = "Unknown — available evidence does not support a model"
        lines.append(f"Product/model: {product}")
        lines.append(f"Profile confidence: {profile.confidence.capitalize()}")
        if profile.evidence:
            evidence = "; ".join(safe(item.value) for item in profile.evidence)
            lines.append(f"Based on: {evidence}")
        for conflict in profile.conflicts:
            lines.append(
                "[yellow]⚠ Conflicting evidence:[/yellow] "
                f"{safe(conflict)}"
            )
        for limitation in profile.limitations:
            lines.append(f"Limitation: {safe(limitation)}")
        return "\n".join(lines)

    def _render_inventory(self) -> str:
        lines = ["[bold]Inventory[/bold]"]
        ports = [port for port in self._host.ports if port.state == "open"]
        if ports:
            lines.append(
                "Open endpoints: "
                + ", ".join(f"{port.port}/{port.protocol}" for port in ports)
            )
            for port in ports:
                service = safe(port.service, LIMIT_PORT_TEXT)
                version = (
                    f" · {safe(port.version, LIMIT_PORT_TEXT)}" if port.version else ""
                )
                lines.append(
                    f"{port.port}/{port.protocol} open · observed label: "
                    f"{service}{version}"
                )
        else:
            lines.append("Open endpoints: None observed")
        operating_system = self._host.operating_system
        if operating_system is None:
            lines.append("Operating system: Not detected")
        else:
            lines.append(
                "Operating system: "
                f"{safe(operating_system.name, LIMIT_HOST_TEXT)} "
                f"({operating_system.accuracy}% confidence)"
            )
            for label, value in (
                ("Vendor", operating_system.vendor),
                ("Family", operating_system.family),
                ("Generation", operating_system.generation),
                ("Device type", operating_system.device_type),
            ):
                if value:
                    lines.append(f"{label}: {safe(value, LIMIT_HOST_TEXT)}")
            if operating_system.cpes:
                lines.append("Platform IDs:")
                lines.extend(
                    f"  - {safe(cpe, LIMIT_HOST_TEXT)}"
                    for cpe in operating_system.cpes[:MAX_CPES_SHOWN]
                )
                overflow = len(operating_system.cpes) - MAX_CPES_SHOWN
                if overflow > 0:
                    lines.append(f"  … {overflow} more platform IDs not shown")
        return "\n".join(lines)

    def _render_exposures(self) -> str:
        lines = ["[bold]Attack surface[/bold]"]
        if self._payload.assessment_policy_version is None:
            lines.append(
                "[dim]Unavailable — this scan predates attack-surface analysis.[/dim]"
            )
            return "\n".join(lines)
        exposures = [
            exposure
            for exposure in self._payload.exposures
            if exposure.ip == self._host.ip
        ]
        if not exposures:
            lines.append("No confirmed open endpoints for this device.")
            return "\n".join(lines)
        for exposure in exposures:
            role = ROLE_LABELS.get(exposure.role, "Unknown")
            lines.append(
                f"[cyan]◇ [ATTENTION: {exposure.attention.upper()}][/cyan] "
                f"{exposure.port}/{exposure.protocol} · {role}"
            )
            observed = safe(exposure.observed_service, LIMIT_PORT_TEXT)
            if exposure.observed_version:
                observed += f" · {safe(exposure.observed_version, LIMIT_PORT_TEXT)}"
            lines.append(f"  Observed service: {observed}")
            lines.append(f"  Why it matters: {safe(exposure.reason)}")
            if exposure.evidence:
                evidence = "; ".join(
                    safe(item.value) for item in exposure.evidence
                )
                lines.append(f"  Evidence: {evidence}")
            related = self._related_findings(exposure.port, exposure.protocol)
            for finding in related:
                label = finding.cve_id or safe(finding.title, LIMIT_HOST_TEXT)
                lines.append(f"  Related finding: {label} (see Vulnerability findings)")
        return "\n".join(lines)

    def _render_findings(self) -> str:
        lines = ["[bold]Vulnerability findings[/bold]"]
        findings = [
            finding for finding in self._payload.findings if finding.ip == self._host.ip
        ]
        if not findings:
            partial = (self._payload.metadata or {}).get("partial_result") is True
            lines.append(
                "No confirmed vulnerabilities in accepted evidence."
                if partial
                else "No confirmed vulnerabilities found for this device."
            )
            return "\n".join(lines)
        exposure_keys = {
            (exposure.protocol, exposure.port)
            for exposure in self._payload.exposures
            if exposure.ip == self._host.ip
        }
        for finding in findings:
            severity = finding.severity.upper()
            color = SEVERITY_COLORS[finding.severity]
            identifier = finding.cve_id or "N/A"
            cvss = (
                f" (CVSS {finding.cvss_score})"
                if finding.cvss_score is not None
                else ""
            )
            lines.append(
                f"[{color}][{severity}][/{color}] {identifier} — "
                f"{safe(finding.title, LIMIT_HOST_TEXT)}{cvss}"
            )
            if finding.port is not None and finding.protocol is not None:
                relationship = (
                    " · also listed in Attack surface"
                    if (finding.protocol, finding.port) in exposure_keys
                    else ""
                )
                lines.append(
                    f"  Endpoint: {finding.port}/{finding.protocol}{relationship}"
                )
        return "\n".join(lines)

    def _related_findings(self, port: int, protocol: str) -> list[FindingPayload]:
        return [
            finding
            for finding in self._payload.findings
            if finding.ip == self._host.ip
            and finding.port == port
            and finding.protocol == protocol
        ]

    def _render_industrial(self) -> str:
        lines = ["[bold]Industrial inventory[/bold]"]
        tracker = ShortenTracker()
        for service in self._host.industrial_services:
            lines.append(f"Modbus TCP {service.port} - {service.confidence.upper()}")
            if service.mapping_source:
                lines.append(
                    "  Mapping plan: "
                    + safe(
                        service.mapping_source,
                        LIMIT_MAPPING_SOURCE,
                        tracker=tracker,
                    )
                )
            for unit in service.units:
                lines.extend(_format_unit(unit, tracker))
        return "\n".join(lines)

    def action_go_back(self) -> None:
        self.dismiss(None)


def _format_unit(unit: ModbusUnitPayload, tracker: ShortenTracker) -> list[str]:
    line = f"  Unit ID {unit.unit_id}: {unit.status}"
    if unit.error:
        line += f"; {safe(unit.error, LIMIT_UNIT_ERROR, tracker=tracker)}"
    if unit.device_identification:
        fields = _identification_fields(unit.device_identification, tracker)
        if fields:
            line += f"; {', '.join(fields)}"
    lines = [line]
    if unit.device_identification:
        lines.extend(_identification_objects(unit.device_identification, tracker))
    for address_range in unit.address_ranges:
        end = address_range.start_address + address_range.count - 1
        range_line = (
            f"    {address_range.address_space} "
            f"{address_range.start_address}-{end}: {address_range.status}"
        )
        if address_range.label:
            range_line += (
                " ("
                + safe(address_range.label, LIMIT_RANGE_LABEL, tracker=tracker)
                + ")"
            )
        suffix: list[str] = []
        if address_range.exception_code is not None:
            suffix.append(f"exception {address_range.exception_code}")
        if address_range.status == "readable":
            digest = address_range.value_digest
            suffix.append(
                "digest "
                + (
                    digest.removeprefix("hmac-sha256:")[:8].lower()
                    if digest
                    else "not recorded"
                )
            )
        elif address_range.value_digest:
            suffix.append(
                "digest "
                + address_range.value_digest.removeprefix("hmac-sha256:")[:8].lower()
            )
        if suffix:
            range_line += f" · {' · '.join(suffix)}"
        lines.append(range_line)
    return lines


def _identification_fields(
    detail: ModbusDeviceIdentificationPayload, tracker: ShortenTracker
) -> list[str]:
    fields = []
    for attr, label in (
        ("vendor_name", "vendor"),
        ("product_code", "product"),
        ("product_name", "product name"),
        ("major_minor_revision", "firmware"),
        ("model_name", "model"),
        ("user_application_name", "application"),
    ):
        value = getattr(detail, attr)
        if value:
            fields.append(
                f"{label} {safe(value, LIMIT_IDENTIFICATION, tracker=tracker)}"
            )
    return fields


def _identification_objects(
    detail: ModbusDeviceIdentificationPayload, tracker: ShortenTracker
) -> list[str]:
    if not detail.objects:
        return []
    items = sorted(detail.objects.items())
    lines = ["   Identification extras:"]
    for key, value in items[:MAX_OBJECTS_SHOWN]:
        lines.append(
            "     "
            f"{safe(key, LIMIT_OBJECT_KEY, tracker=tracker)} = "
            f"{safe(value, LIMIT_OBJECT_VALUE, tracker=tracker)}"
        )
    overflow = len(items) - MAX_OBJECTS_SHOWN
    if overflow > 0:
        lines.append(f"     … {overflow} more identification objects not shown")
    return lines
