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
from agent.normalize.findings import assess_local_evidence
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

EVIDENCE_METHOD_LABELS = {
    "version_correlation": "Version association",
    "configuration_observation": "Observed configuration",
    "specific_check": "Specific check",
    "textual_reference": "Text reference only",
    "unknown": "Unknown",
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
            yield Static(
                self._render_standalone_observations(),
                id="device-finding-observations",
            )
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
        observations = self.query_one("#device-finding-observations", Static)
        observations.display = (
            any(item.ip == self._host.ip for item in self._payload.finding_observations)
            or self._payload.finding_observations_truncated
        )

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
        manufacturer = safe(profile.manufacturer) if profile.manufacturer else "Unknown"
        lines.append(f"Manufacturer: {manufacturer}")
        if profile.product_family and profile.model:
            product = f"{safe(profile.product_family)} · {safe(profile.model)}"
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
            lines.append(f"[yellow]⚠ Conflicting evidence:[/yellow] {safe(conflict)}")
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
                evidence = "; ".join(safe(item.value) for item in exposure.evidence)
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
                "No vulnerability finding records in accepted evidence."
                if partial
                else "No vulnerability finding records for this device."
            )
            return "\n".join(lines)
        version = self._payload.finding_evidence_policy_version
        if version == "1":
            lines.append(
                "Evidence interpretation is local to this agent (policy v1); "
                "it is not backend enrichment. Finding records are not all "
                "proven failures."
            )
        elif version is None:
            lines.append(
                "Evidence interpretation is unavailable for this legacy scan. "
                "Finding records are not proof of failure."
            )
        else:
            lines.append(
                f"Local evidence policy {safe(version)} is not supported by this "
                "agent; finding records are not proof of failure."
            )
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
            if version == "1":
                assessment = assess_local_evidence(finding)
                method = EVIDENCE_METHOD_LABELS.get(assessment.method, "Unknown")
                lines.append(
                    f"  Local evidence: {method} · {assessment.status} · "
                    f"{assessment.confidence} (category, not a percentage)"
                )
                if assessment.method == "version_correlation":
                    limit = (
                        "The version association does not validate this "
                        "vulnerability's presence on the device."
                    )
                elif assessment.method == "configuration_observation":
                    limit = (
                        "This configuration was observed; this does not show "
                        "exploitation of a known vulnerability."
                    )
                elif assessment.status == "conflicting":
                    limit = (
                        "Evidence conflicts; no single positive or negative "
                        "conclusion is established."
                    )
                elif (
                    assessment.method == "specific_check"
                    and assessment.status == "supported"
                    and finding.port is not None
                    and finding.protocol is not None
                ):
                    limit = (
                        "The check supports only its recorded condition on "
                        f"{finding.port}/{finding.protocol}; it does not describe "
                        "the whole device."
                    )
                elif assessment.method == "textual_reference":
                    limit = (
                        "A vulnerability reference appeared in text, but no "
                        "verifiable positive result was recorded."
                    )
                else:
                    limit = (
                        "The check is inconclusive; this neither confirms nor "
                        "rules out the condition."
                    )
                lines.append(f"  Limit: {limit}")
                if finding.evidence_truncated:
                    lines.append(
                        "  Evidence note: only a sample of this finding's evidence "
                        "observations is available."
                    )
                for observation in finding.evidence_observations:
                    endpoint = (
                        f"{observation.port}/{observation.protocol}"
                        if observation.port is not None
                        else "not recorded"
                    )
                    if observation.unit_id is not None:
                        endpoint += f" · unit {observation.unit_id}"
                    source = observation.source
                    if observation.source_script:
                        source += f" · {observation.source_script}"
                    lines.extend(
                        (
                            "  Evidence observation: "
                            f"{observation.result} · {observation.method}",
                            "    Condition: "
                            f"{safe(observation.condition_key, LIMIT_HOST_TEXT)}",
                            f"    Endpoint: {endpoint}",
                            f"    Source: {safe(source, LIMIT_HOST_TEXT)} · Rule: "
                            f"{safe(observation.rule_id, LIMIT_HOST_TEXT)} "
                            f"v{safe(observation.rule_version)}",
                            f"    Evidence excerpt: {safe(observation.evidence, 160)}",
                        )
                    )
                    if observation.facts:
                        facts = "; ".join(
                            f"{safe(key, LIMIT_HOST_TEXT)}={safe(value)}"
                            for key, value in sorted(observation.facts.items())
                        )
                        lines.append(f"    Facts: {facts}")
            elif version is None:
                lines.append(
                    "  Local evidence: unavailable (legacy record); the recorded "
                    "finding cannot be verified from this payload."
                )
            else:
                lines.append(
                    "  Local evidence: unknown; this agent does not interpret the "
                    "recorded policy version."
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

    def _render_standalone_observations(self) -> str:
        lines = [
            "[bold]Standalone check observations (not vulnerability findings)[/bold]"
        ]
        observations = [
            item
            for item in self._payload.finding_observations
            if item.ip == self._host.ip
        ]
        negative = sum(item.result == "negative" for item in observations)
        inconclusive = sum(item.result == "inconclusive" for item in observations)
        noun = "observation" if len(observations) == 1 else "observations"
        count_label = (
            f"Sample shown: {len(observations)} {noun}"
            if self._payload.finding_observations_truncated
            else f"{len(observations)} {noun}"
        )
        lines.append(
            f"{count_label} · {negative} negative · "
            f"{inconclusive} inconclusive. A negative result applies only to its "
            "recorded check."
        )
        for item in observations:
            endpoint = (
                f"{item.port}/{item.protocol}"
                if item.port is not None
                else "not recorded"
            )
            if item.unit_id is not None:
                endpoint += f" · unit {item.unit_id}"
            source = item.source
            if item.source_script:
                source += f" · {item.source_script}"
            lines.extend(
                (
                    f"Condition: {safe(item.condition_key, LIMIT_HOST_TEXT)} · "
                    f"Result: {item.result} · Method: {item.method}",
                    f"Endpoint: {endpoint}",
                    f"Source: {safe(source, LIMIT_HOST_TEXT)} · Rule: "
                    f"{safe(item.rule_id, LIMIT_HOST_TEXT)} "
                    f"v{safe(item.rule_version)}",
                    f"Evidence excerpt: {safe(item.evidence, 160)}",
                )
            )
            if item.facts:
                facts = "; ".join(
                    f"{safe(key, LIMIT_HOST_TEXT)}={safe(value)}"
                    for key, value in sorted(item.facts.items())
                )
                lines.append(f"Facts: {facts}")
        if self._payload.finding_observations_truncated:
            lines.append(
                "Only a sample of scan-level standalone observations is available."
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
            if service.protocol == "opcua_tcp":
                lines.append(
                    f"OPC UA TCP {service.port} - {service.confidence.upper()}"
                )
                lines.append(
                    f"  Inventory: {service.observation.inventory_phase.status}"
                )
                if service.observation.mapping is not None:
                    lines.append(
                        f"  Mapping: {service.observation.mapping.phase.status}"
                    )
                continue
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
