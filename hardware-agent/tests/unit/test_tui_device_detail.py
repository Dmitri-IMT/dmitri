"""Unit tests for local device assessment details."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import agent.tui.app as _agent_app
import pytest
from agent.normalize.contracts import (
    AssessmentEvidencePayload,
    DeviceProfilePayload,
    ExposurePayload,
    FindingEvidenceObservationPayload,
    FindingPayload,
    HostPayload,
    ModbusDeviceIdentificationPayload,
    ModbusTcpServicePayload,
    ModbusUnitPayload,
    OperatingSystemDetection,
    PortPayload,
    ScanPayload,
)
from agent.tui.screens.device_detail import DeviceDetailScreen
from rich.text import Text
from textual.app import App
from textual.widgets import Static


class _Harness(App[None]):
    CSS_PATH = Path(_agent_app.__file__).parent / "app.tcss"

    def __init__(self, screen: DeviceDetailScreen) -> None:
        super().__init__()
        self._target_screen = screen

    def on_mount(self) -> None:
        self.push_screen(self._target_screen)


@pytest.fixture(autouse=True)
def _no_animations(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TEXTUAL_ANIMATIONS", "none")


def _payload(*, findings: bool = True) -> ScanPayload:
    profile = DeviceProfilePayload(
        manufacturer="Tuya Smart",
        confidence="low",
        evidence=[
            AssessmentEvidencePayload(
                kind="hostname", source="hostname", value="living-room-sensor"
            ),
            AssessmentEvidencePayload(
                kind="manufacturer", source="mac_vendor", value="Tuya Smart"
            ),
            AssessmentEvidencePayload(kind="service", source="nmap", value="irc"),
        ],
        conflicts=[
            "6668/tcp has registry label irc, while protocol evidence indicates "
            "device control."
        ],
        limitations=["No reliable operating system or certificate evidence."],
    )
    host = HostPayload(
        ip="192.168.1.6",
        mac="02:00:00:00:00:06",
        hostname="living-room-sensor",
        vendor="Tuya Smart",
        operating_system=OperatingSystemDetection(name="Embedded Linux", accuracy=82),
        machine_type="unknown",
        device_profile=profile,
        ports=[
            PortPayload(
                port=6668,
                protocol="tcp",
                state="open",
                service="irc",
                version="registry label",
            )
        ],
        industrial_services=[
            ModbusTcpServicePayload(
                port=502,
                confidence="confirmed",
                mapping_source="generic_baseline",
                units=[
                    ModbusUnitPayload(
                        unit_id=7,
                        status="responding",
                        device_identification=ModbusDeviceIdentificationPayload(
                            vendor_name="Schneider Electric",
                            product_code="BMX P34",
                        ),
                    )
                ],
            )
        ],
    )
    finding_list = (
        [
            FindingPayload(
                ip=host.ip,
                port=6668,
                protocol="tcp",
                service="irc",
                severity="high",
                cve_id="CVE-2024-12345",
                cvss_score=8.1,
                title="Exposed control weakness",
                description="A control weakness was confirmed",
                recommendation="Restrict the affected endpoint",
                evidence="Confirmed by the inspection script",
                issue_key="title:potentially risky http methods enabled",
                evidence_observations=[
                    FindingEvidenceObservationPayload(
                        ip=host.ip,
                        port=6668,
                        protocol="tcp",
                        condition_key="title:potentially risky http methods enabled",
                        method="configuration_observation",
                        result="positive",
                        source="nmap_nse",
                        source_script="http-methods",
                        rule_id="nse:http-methods",
                        rule_version="1",
                        evidence="PUT",
                        facts={"risky_method": "PUT"},
                    )
                ],
            )
        ]
        if findings
        else []
    )
    return ScanPayload(
        scan_id=uuid4(),
        timestamp=datetime(2026, 5, 3, tzinfo=timezone.utc),
        subnet="192.168.1.0/24",
        scan_mode="nspi",
        hosts=[host],
        findings=finding_list,
        finding_evidence_policy_version="1",
        finding_observations=[
            FindingEvidenceObservationPayload(
                ip=host.ip,
                port=6668,
                protocol="tcp",
                condition_key="CVE-2020-1234",
                method="unknown",
                result="negative",
                source="nmap_nse",
                rule_id="nse:unknown-check",
                rule_version="1",
                evidence="The check returned not vulnerable.",
            )
        ],
        assessment_policy_version="2026-09-15.1",
        exposures=[
            ExposurePayload(
                ip=host.ip,
                port=6668,
                protocol="tcp",
                observed_service="irc",
                observed_version="registry label",
                role="device_control",
                attention="review",
                confidence="low",
                reason="An unidentified control-like listener is reachable.",
                evidence=[
                    AssessmentEvidencePayload(
                        kind="port", source="open_endpoint", value="6668/tcp"
                    ),
                    AssessmentEvidencePayload(
                        kind="protocol", source="nmap_script", value="device control"
                    ),
                ],
            )
        ],
    )


def _legacy(payload: ScanPayload) -> ScanPayload:
    data = payload.model_dump(mode="json")
    data["assessment_policy_version"] = None
    data["exposures"] = []
    data["hosts"][0]["machine_type"] = None
    data["hosts"][0]["device_profile"] = None
    return ScanPayload.model_validate(data)


def test_detail_preserves_profile_evidence_and_raw_inventory() -> None:
    payload = _payload(findings=False)
    screen = DeviceDetailScreen(payload, payload.hosts[0])

    profile = screen._render_profile()
    inventory = screen._render_inventory()

    assert "Machine type: Unknown" in profile
    assert "Manufacturer: Tuya Smart" in profile
    assert "Product/model: Unknown" in profile
    assert "Profile confidence: Low" in profile
    evidence = profile.split("Based on: ", maxsplit=1)[1].splitlines()[0]
    assert evidence.index("living-room-sensor") < evidence.index("Tuya Smart")
    assert evidence.index("Tuya Smart") < evidence.index("irc")
    assert "⚠ Conflicting evidence:" in profile
    assert "Limitation: No reliable operating system" in profile
    assert "6668/tcp open · observed label: irc · registry label" in inventory
    assert "Operating system: Embedded Linux (82% confidence)" in inventory
    assert "IoT" not in profile


def test_detail_preserves_randomized_mac_uncertainty() -> None:
    payload = _payload(findings=False)
    host = payload.hosts[0]
    host.mac = "02:00:00:00:00:06"
    host.vendor = "Tuya Smart"
    host.machine_type = "unknown"
    host.device_profile = DeviceProfilePayload(
        manufacturer=None,
        product_family=None,
        model=None,
        confidence="low",
        limitations=["Locally administered MAC address; OUI manufacturer unavailable."],
    )

    profile = DeviceDetailScreen(payload, host)._render_profile()

    assert "Machine type: Unknown" in profile
    assert "Manufacturer: Unknown" in profile
    assert "Product/model: Unknown" in profile
    assert (
        "Limitation: Locally administered MAC address; OUI manufacturer unavailable."
        in profile
    )
    assert "Tuya Smart" not in profile
    assert "IoT" not in profile


def test_exposure_and_finding_are_separate_with_reciprocal_relationship() -> None:
    payload = _payload()
    screen = DeviceDetailScreen(payload, payload.hosts[0])

    exposures = Text.from_markup(screen._render_exposures()).plain
    findings = Text.from_markup(screen._render_findings()).plain

    assert "◇ [ATTENTION: REVIEW] 6668/tcp · Device control" in exposures
    assert "Related finding: CVE-2024-12345 (see Vulnerability findings)" in exposures
    assert "[HIGH] CVE-2024-12345" in findings
    assert "Endpoint: 6668/tcp · also listed in Attack surface" in findings
    assert "Evidence interpretation is local to this agent (policy v1)" in findings
    assert "Finding records are not all proven failures." in findings
    assert "Local evidence: Observed configuration · supported · confirmed" in findings
    assert (
        "This configuration was observed; this does not show exploitation" in findings
    )
    assert "Standalone check observations" not in findings
    assert "Evidence observation: positive · configuration_observation" in findings
    assert "Condition: title:potentially risky http methods enabled" in findings
    assert "Source: nmap_nse · http-methods · Rule: nse:http-methods v1" in findings
    assert "Evidence excerpt: PUT" in findings
    assert "Facts: risky_method=PUT" in findings
    standalone = Text.from_markup(screen._render_standalone_observations()).plain
    assert "1 observation · 1 negative · 0 inconclusive" in standalone
    assert "Condition: CVE-2020-1234 · Result: negative · Method: unknown" in standalone
    assert "Source: nmap_nse · Rule: nse:unknown-check v1" in standalone
    assert "Evidence excerpt: The check returned not vulnerable." in standalone
    assert exposures.count("CVE-2024-12345") == 1
    assert findings.count("CVE-2024-12345") == 1


def test_current_empty_and_legacy_unavailable_are_distinct() -> None:
    current = _payload(findings=False)
    current.hosts[0].ports = []
    current.exposures = []
    current_screen = DeviceDetailScreen(current, current.hosts[0])
    legacy = _legacy(_payload(findings=False))
    legacy_screen = DeviceDetailScreen(legacy, legacy.hosts[0])

    assert (
        "No confirmed open endpoints for this device."
        in current_screen._render_exposures()
    )
    assert (
        "No vulnerability finding records for this device."
        in current_screen._render_findings()
    )
    assert (
        "Unavailable — this scan predates device profiling."
        in legacy_screen._render_profile()
    )
    assert (
        "Unavailable — this scan predates attack-surface analysis."
        in legacy_screen._render_exposures()
    )
    assert "6668/tcp open · observed label: irc" in legacy_screen._render_inventory()


def test_unknown_evidence_policy_is_not_interpreted_as_version_one() -> None:
    payload = _payload()
    payload.finding_evidence_policy_version = "2"

    findings = DeviceDetailScreen(payload, payload.hosts[0])._render_findings()

    assert "this agent does not interpret the recorded policy version" in findings
    assert "Local evidence: Observed configuration" not in findings
    assert "finding records are not proof of failure" in findings


def test_finding_evidence_truncation_is_shown_as_sample_limit() -> None:
    payload = _payload()
    payload.findings[0].evidence_truncated = True
    payload.finding_observations_truncated = True
    screen = DeviceDetailScreen(payload, payload.hosts[0])

    findings = Text.from_markup(screen._render_findings()).plain
    standalone = Text.from_markup(screen._render_standalone_observations()).plain

    assert "only a sample of this finding's evidence observations is available" in (
        findings
    )
    assert "Only a sample of scan-level standalone observations is available." in (
        standalone
    )
    assert "Sample shown: 1 observation" in standalone


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("metadata", "expected", "unexpected"),
    [
        (
            {"partial_result": True, "terminated_by": "completed"},
            "⚠ INCOMPLETE EVIDENCE — The scan finished",
            "STOPPED SCAN",
        ),
        (
            {
                "partial_result": True,
                "terminated_by": "user_cancel",
                "interrupted_stage": "ports",
            },
            "■ STOPPED SCAN — Port scanning did not finish.",
            "INCOMPLETE EVIDENCE",
        ),
    ],
)
async def test_detail_partial_banner_and_accepted_evidence_copy(
    metadata: dict[str, str | bool], expected: str, unexpected: str
) -> None:
    payload = _payload(findings=False)
    payload.metadata = metadata
    screen = DeviceDetailScreen(payload, payload.hosts[0])

    async with _Harness(screen).run_test() as pilot:
        await pilot.pause()
        banner = str(screen.query_one("#device-partial-banner", Static).render())
        findings = str(screen.query_one("#device-findings", Static).render())
        assert expected in banner
        assert unexpected not in banner
        assert "This device shows accepted evidence only." in banner
        assert "No vulnerability finding records in accepted evidence." in findings
        assert "found for this device" not in findings


@pytest.mark.asyncio
async def test_detail_mount_has_all_stable_ids_and_industrial_inventory() -> None:
    payload = _payload()
    screen = DeviceDetailScreen(payload, payload.hosts[0])

    async with _Harness(screen).run_test() as pilot:
        await pilot.pause()
        for widget_id in (
            "#device-detail-scroll",
            "#device-detail-header",
            "#device-partial-banner",
            "#device-profile",
            "#device-inventory",
            "#device-exposures",
            "#device-findings",
            "#device-finding-observations",
            "#device-industrial",
        ):
            assert screen.query_one(widget_id) is not None
        industrial = str(screen.query_one("#device-industrial", Static).render())
        assert "Modbus TCP 502 - CONFIRMED" in industrial
        observations = str(
            screen.query_one("#device-finding-observations", Static).render()
        )
        assert "Condition: CVE-2020-1234" in observations
        assert "Mapping plan: generic_baseline" in industrial
        assert "Unit ID 7: responding" in industrial
        assert "vendor Schneider Electric" in industrial
        assert "product BMX P34" in industrial
