"""Local scan summary and device navigation."""

from __future__ import annotations

import json
from pathlib import Path

from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.widgets import OptionList, Static
from textual.widgets.option_list import Option

from agent.normalize.contracts import HostPayload, ScanPayload
from agent.normalize.findings import assess_local_evidence
from agent.tui.markup import LIMIT_HOST_TEXT, safe
from agent.tui.screens.base import DmitriScreen

MODE_LABELS = {
    "quick": "Quick",
    "standard": "Standard",
    "extensive": "Extensive",
    "nspi": "NSPi",
    "max": "MAX",
}
MACHINE_TYPE_LABELS = {
    "router": "Router",
    "computer": "Computer",
    "camera": "Camera",
    "storage": "Storage",
    "tv": "TV",
    "phone": "Phone",
    "printer": "Printer",
    "sensor": "Sensor",
    "unknown": "Unknown",
}
STAGE_LABELS = {
    "discovery": "Host discovery",
    "ports": "Port scanning",
    "deep_inspection": "Deep inspection",
    "ot_inspection": "Industrial inspection",
    "targeted_assessment": "Targeted service assessment",
    "normalize": "Results generation",
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


def _count(noun: str, value: int) -> str:
    return f"{value} {noun}{'' if value == 1 else 's'}"


def count_unique_open_endpoints(payload: ScanPayload) -> int:
    """Count canonical open endpoints, not repeated raw port observations."""
    return len(
        {
            (str(host.ip), port.protocol, port.port)
            for host in payload.hosts
            for port in host.ports
            if port.state == "open"
        }
    )


def _finding_evidence_summary(payload: ScanPayload) -> str:
    version = payload.finding_evidence_policy_version
    if version is None:
        return (
            "Evidence interpretation: unavailable for this legacy scan. Finding "
            "counts are records, not proven failures."
        )
    if version != "1":
        return (
            "Evidence interpretation: local policy "
            f"{safe(version, 32)} is not supported by "
            "this agent. Finding counts are records, not proven failures."
        )

    assessments = [assess_local_evidence(finding) for finding in payload.findings]
    statuses = {
        status: sum(item.status == status for item in assessments)
        for status in ("supported", "conflicting", "inconclusive")
    }
    observations = payload.finding_observations
    negative = sum(item.result == "negative" for item in observations)
    inconclusive = sum(item.result == "inconclusive" for item in observations)
    observation_label = "Standalone observations"
    if payload.finding_observations_truncated:
        observation_label = "Standalone observation sample"
    return (
        "Evidence interpretation: local policy v1; this is not backend enrichment. "
        f"Finding records by evidence status: supported {statuses['supported']}, "
        f"conflicting {statuses['conflicting']}, "
        f"inconclusive {statuses['inconclusive']}. "
        f"{observation_label}: {negative} negative, {inconclusive} inconclusive; "
        "these are not finding records. Counts do not mean proven failures."
    )


def _render_observations(payload: ScanPayload) -> str:
    lines = ["[bold]Standalone check observations (not vulnerability findings)[/bold]"]
    if not payload.finding_observations:
        lines.append("No standalone check observations recorded.")
    for item in payload.finding_observations:
        endpoint = (
            f"{item.port}/{item.protocol}" if item.port is not None else "not recorded"
        )
        if item.unit_id is not None:
            endpoint += f" · unit {item.unit_id}"
        if item.ip is not None:
            endpoint = f"{item.ip} · {endpoint}"
        source = item.source
        if item.source_script:
            source += f" · {item.source_script}"
        lines.extend(
            (
                f"Condition: {safe(item.condition_key, LIMIT_HOST_TEXT)} · "
                f"Result: {item.result} · Method: {item.method}",
                f"Endpoint: {endpoint}",
                f"Source: {safe(source, LIMIT_HOST_TEXT)} · Rule: "
                f"{safe(item.rule_id, LIMIT_HOST_TEXT)} v{safe(item.rule_version)}",
                f"Evidence excerpt: {safe(item.evidence, 160)}",
            )
        )
        if item.facts:
            facts = "; ".join(
                f"{safe(key, LIMIT_HOST_TEXT)}={safe(value)}"
                for key, value in sorted(item.facts.items())
            )
            lines.append(f"Facts: {facts}")
    if payload.finding_observations_truncated:
        lines.append("Only a sample of standalone observations is available.")
    return "\n".join(lines)


def _partial_banner(payload: ScanPayload) -> tuple[str, str] | None:
    metadata = payload.metadata or {}
    if metadata.get("partial_result") is not True:
        return None
    if metadata.get("terminated_by") == "completed":
        return (
            "incomplete",
            "⚠ INCOMPLETE EVIDENCE — The scan finished, but some checks did not "
            "complete. Counts use accepted evidence only.",
        )
    stage = STAGE_LABELS.get(str(metadata.get("interrupted_stage", "")))
    unfinished = f"{stage} did not finish." if stage else "The scan did not finish."
    return (
        "stopped",
        f"■ STOPPED SCAN — {unfinished} Counts use accepted evidence only.",
    )


class ScanViewScreen(DmitriScreen):
    """Summary for an in-memory or locally saved scan payload."""

    BINDINGS = [
        Binding("up", "cursor_up", "↑↓ Navigate", priority=True),
        Binding("down", "cursor_down", show=False, priority=True),
        Binding("j", "cursor_down", show=False, priority=True),
        Binding("k", "cursor_up", show=False, priority=True),
        Binding("enter", "open_device", "Device details", priority=True),
        Binding("escape", "go_back", "Back", priority=True),
    ]

    def __init__(
        self, scan_path: Path | None = None, payload: ScanPayload | None = None
    ) -> None:
        super().__init__()
        self._scan_path = scan_path
        self._payload = payload

    def compose_body(self):
        with VerticalScroll(id="scan-view-scroll"):
            with Vertical(id="scan-view-container"):
                yield Static("", id="scan-result-header")
                yield Static("", id="scan-partial-banner")
                yield Static("", id="scan-category-summary")
                yield Static("", id="scan-finding-observations")
                yield Static("", id="scan-enrichment-note")
                yield Static("", id="scan-devices-title")
                yield OptionList(id="scan-device-list")
                yield Static("No devices were discovered.", id="scan-devices-empty")

    def on_mount(self) -> None:
        payload = self._load_payload()
        if payload is None:
            self.query_one("#scan-result-header", Static).update(
                "[red]Failed to load scan results.[/red]"
            )
            for widget_id in (
                "#scan-partial-banner",
                "#scan-category-summary",
                "#scan-finding-observations",
                "#scan-enrichment-note",
                "#scan-devices-title",
                "#scan-device-list",
                "#scan-devices-empty",
            ):
                self.query_one(widget_id).display = False
            return
        self._payload = payload
        self.query_one("#scan-result-header", Static).update(
            self._render_header(payload)
        )
        self.query_one("#scan-category-summary", Static).update(
            self._render_category_summary(payload)
        )
        observation_panel = self.query_one("#scan-finding-observations", Static)
        observation_panel.display = bool(
            payload.finding_observations or payload.finding_observations_truncated
        )
        if observation_panel.display:
            observation_panel.update(_render_observations(payload))
        banner = self.query_one("#scan-partial-banner", Static)
        partial = _partial_banner(payload)
        banner.display = partial is not None
        if partial is not None:
            state, copy = partial
            banner.update(copy)
            banner.set_classes(state)
        legacy_note = self.query_one("#scan-enrichment-note", Static)
        legacy_note.display = payload.assessment_policy_version is None
        if legacy_note.display:
            legacy_note.update(
                "Unavailable — this scan predates attack-surface analysis and device "
                "profiling. Re-run the scan to produce this data."
            )
        self.query_one("#scan-devices-title", Static).update(
            f"Devices ({len(payload.hosts)})"
        )
        devices = self.query_one("#scan-device-list", OptionList)
        empty = self.query_one("#scan-devices-empty", Static)
        devices.display = bool(payload.hosts)
        empty.display = not payload.hosts
        if payload.hosts:
            devices.add_options(
                Option(self._device_prompt(payload, host), id=str(index))
                for index, host in enumerate(payload.hosts)
            )
            devices.highlighted = 0
            devices.focus()

    def _load_payload(self) -> ScanPayload | None:
        if self._payload is not None:
            return self._payload
        if self._scan_path and self._scan_path.is_file():
            try:
                return ScanPayload.model_validate(
                    json.loads(self._scan_path.read_text(encoding="utf-8"))
                )
            except (json.JSONDecodeError, ValueError, OSError):
                return None
        return None

    def _render_header(self, payload: ScanPayload) -> str:
        mode = MODE_LABELS.get(payload.scan_mode, payload.scan_mode.capitalize())
        metadata = payload.metadata or {}
        if payload.scan_mode == "nspi":
            submode = {
                "inventory": "Inventory",
                "read_only_mapping": "Read-only mapping",
                "active_validation": "Active validation",
            }.get(str(metadata.get("nspi_submode")))
            if submode:
                mode = f"{mode} · {submode}"
        lines = [
            "[bold]Scan results[/bold]",
            f"Target: {payload.subnet} · "
            f"{payload.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')} · {mode}",
        ]
        if "elapsed_seconds" in metadata:
            lines.append(f"Duration: {format_duration(metadata['elapsed_seconds'])}")
        if metadata.get("modbus_stage_deadline_reached"):
            seconds = metadata.get("modbus_stage_deadline_seconds", 0)
            lines.append(
                f"Limits: Time limit reached during Modbus inventory ({seconds}s)"
            )
        return "\n".join(lines)

    def _render_category_summary(self, payload: ScanPayload) -> str:
        devices = len(payload.hosts)
        endpoints = count_unique_open_endpoints(payload)
        lines = [
            f"[bold]Inventory:[/bold] {_count('device', devices)} · "
            f"{_count('open endpoint', endpoints)}"
        ]
        if payload.assessment_policy_version is None:
            lines.append("[bold]Attack surface:[/bold] Unavailable")
        else:
            attention = sum(
                exposure.attention in {"review", "priority"}
                for exposure in payload.exposures
            )
            attention_copy = (
                "1 needs attention" if attention == 1 else f"{attention} need attention"
            )
            lines.append(
                f"[bold]Attack surface:[/bold] "
                f"{_count('exposure', len(payload.exposures))} · {attention_copy}"
            )
        lines.append(
            f"[bold]Vulnerability findings:[/bold] "
            f"{_count('finding record', len(payload.findings))}"
        )
        lines.append(_finding_evidence_summary(payload))
        return "\n".join(lines)

    def _device_prompt(self, payload: ScanPayload, host: HostPayload) -> str:
        findings = sum(finding.ip == host.ip for finding in payload.findings)
        if payload.assessment_policy_version is None:
            return (
                f"{host.ip} · Profile unavailable · exposures unavailable · "
                f"{_count('finding', findings)}"
            )
        exposures = sum(exposure.ip == host.ip for exposure in payload.exposures)
        machine_type = MACHINE_TYPE_LABELS.get(
            host.machine_type or "unknown", "Unknown"
        )
        confidence = host.device_profile.confidence if host.device_profile else "low"
        return (
            f"{host.ip} · {machine_type} · confidence {confidence} · "
            f"{_count('exposure', exposures)} · {_count('finding', findings)}"
        )

    def _render_payload(self, payload: ScanPayload, **_: object) -> str:
        """Return summary text for non-interactive diagnostics."""
        lines = [self._render_header(payload)]
        partial = _partial_banner(payload)
        if partial is not None:
            lines.append(partial[1])
        lines.append(self._render_category_summary(payload))
        if payload.finding_observations or payload.finding_observations_truncated:
            lines.append(_render_observations(payload))
        if payload.assessment_policy_version is None:
            lines.append(
                "Unavailable — this scan predates attack-surface analysis and device "
                "profiling. Re-run the scan to produce this data."
            )
        lines.append(f"Devices ({len(payload.hosts)})")
        lines.extend(self._device_prompt(payload, host) for host in payload.hosts)
        if not payload.hosts:
            lines.append("No devices were discovered.")
        return "\n".join(lines)

    def action_cursor_down(self) -> None:
        devices = self.query_one("#scan-device-list", OptionList)
        if devices.display:
            devices.action_cursor_down()

    def action_cursor_up(self) -> None:
        devices = self.query_one("#scan-device-list", OptionList)
        if devices.display:
            devices.action_cursor_up()

    def action_open_device(self) -> None:
        devices = self.query_one("#scan-device-list", OptionList)
        if devices.display and devices.highlighted is not None:
            self._open_device(devices.highlighted)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option.id is not None:
            self._open_device(int(event.option.id))

    def _open_device(self, index: int) -> None:
        if self._payload is None or not 0 <= index < len(self._payload.hosts):
            return
        from agent.tui.screens.device_detail import DeviceDetailScreen

        self.app.push_screen(
            DeviceDetailScreen(self._payload, self._payload.hosts[index])
        )

    def action_go_back(self) -> None:
        self.dismiss(None)
