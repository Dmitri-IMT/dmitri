from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import agent.tui.app as _agent_app
import pytest
from agent.assessment.analyzer import assess_hosts
from agent.assessment.policy import LOCAL_ASSESSMENT_POLICY_VERSION
from agent.config import AgentSettings
from agent.normalize.contracts import ScanPayload
from agent.normalize.findings import extract_findings
from agent.scanner.models import HostInfo, MacIdentity
from agent.scanner.stages import (
    build_host_payload,
    run_deep_inspection_stage,
    run_port_stage,
)
from agent.tui.screens.scan_view import ScanViewScreen
from agent.utils.nmap_xml import parse_ports
from textual.app import App
from textual.widgets import Static


class _ScanViewHarness(App[None]):
    CSS_PATH = Path(_agent_app.__file__).parent / "app.tcss"

    def __init__(self, screen: ScanViewScreen) -> None:
        super().__init__()
        self._target_screen = screen

    def on_mount(self) -> None:
        self.push_screen(self._target_screen)


def _weak_target_host() -> HostInfo:
    host_element = ET.fromstring("""
        <host>
          <ports>
            <port protocol="tcp" portid="443">
              <state state="open" />
              <service name="https" />
              <script id="ssl-cert" output="Certificate details">
                <table key="subject"><elem key="commonName">lab.local</elem></table>
                <table key="issuer"><elem key="commonName">Public CA</elem></table>
                <table key="pubkey"><elem key="bits">2048</elem></table>
                <table key="validity">
                  <elem key="notBefore">2019-01-01T00:00:00</elem>
                  <elem key="notAfter">2021-01-01T00:00:00</elem>
                </table>
                <elem key="sig_algo">sha256WithRSAEncryption</elem>
              </script>
            </port>
            <port protocol="tcp" portid="21">
              <state state="open" />
              <service name="ftp" />
              <script
                id="ftp-anon"
                output="Anonymous FTP login allowed (FTP code 230)"
              />
            </port>
          </ports>
        </host>
        """)
    return HostInfo(
        ip="192.168.1.20",
        hostname="weak-host",
        ports=parse_ports(host_element),
    )


@pytest.mark.asyncio
async def test_extensive_scan_surfaces_tls_and_ftp_findings_in_view() -> None:
    host = _weak_target_host()
    findings = extract_findings([host])
    assessment = assess_hosts([host])
    payload = ScanPayload(
        scan_id=uuid4(),
        timestamp=datetime.now(timezone.utc),
        subnet="192.168.1.0/24",
        scan_mode="extensive",
        hosts=[
            build_host_payload(
                host,
                machine_type=assessment.machine_types[host.ip],
                device_profile=assessment.device_profiles[host.ip],
            )
        ],
        findings=findings,
        assessment_policy_version=LOCAL_ASSESSMENT_POLICY_VERSION,
        exposures=assessment.exposures,
        metadata={"elapsed_seconds": 1500},
    )

    summary = ScanViewScreen(payload=payload)
    async with _ScanViewHarness(summary).run_test() as pilot:
        await pilot.pause()
        assert "Extensive" in str(
            summary.query_one("#scan-result-header", Static).render()
        )

        await pilot.press("enter")
        await pilot.pause()

        detail = pilot.app.screen
        assert detail.__class__.__name__ == "DeviceDetailScreen"
        rendered_findings = str(
            detail.query_one("#device-findings", Static).render()
        )
        assert "TLS certificate expired" in rendered_findings
        assert "Anonymous FTP login allowed" in rendered_findings


def test_extensive_responsibility_split_preserves_deterministic_evidence() -> None:
    ip = "192.168.1.30"
    port_xml = ET.fromstring(f"""
        <nmaprun>
          <host>
            <address addr="{ip}" addrtype="ipv4" />
            <ports>
              <port protocol="tcp" portid="21"><state state="open" /></port>
              <port protocol="tcp" portid="443"><state state="open" /></port>
              <port protocol="udp" portid="161">
                <state state="filtered" />
              </port>
            </ports>
          </host>
        </nmaprun>
        """)
    deep_xml = ET.fromstring("""
        <nmaprun>
          <host>
            <ports>
              <port protocol="tcp" portid="21">
                <state state="open" />
                <service
                  name="ftp"
                  product="vsftpd"
                  version="3.0.3"
                  extrainfo="secure mode"
                >
                  <cpe>cpe:/a:vsftpd:vsftpd:3.0.3</cpe>
                </service>
                <script
                  id="ftp-anon"
                  output="Anonymous FTP login allowed (FTP code 230)"
                />
              </port>
              <port protocol="tcp" portid="443">
                <state state="open" />
                <service
                  name="https"
                  product="nginx"
                  version="1.24.0"
                  extrainfo="Ubuntu"
                >
                  <cpe>cpe:/a:nginx:nginx:1.24.0</cpe>
                </service>
                <script id="vulners" output="Known vulnerabilities found">
                  <table key="cpe:/a:nginx:nginx:1.24.0">
                    <table>
                      <elem key="cvss">8.8</elem>
                      <elem key="id">CVE-2024-23456</elem>
                    </table>
                  </table>
                </script>
              </port>
            </ports>
            <hostscript>
              <script
                id="smb2-security-mode"
                output="Message signing enabled but not required"
              />
            </hostscript>
          </host>
        </nmaprun>
        """)
    calls: list[list[str]] = []

    class DeterministicRunner:
        nmap_path = "nmap"

        def run_xml(
            self, arguments: list[str], timeout: float | None = None
        ) -> ET.Element:
            calls.append(list(arguments))
            return port_xml if len(calls) == 1 else deep_xml

    host = HostInfo(
        ip=ip,
        hostname="edge-gateway.lab",
        identity=MacIdentity(mac="02:00:00:00:01:30", vendor="Lab Hardware Ltd"),
    )
    settings = AgentSettings(
        scan_mode="extensive",
        min_cvss=3.0,
        max_workers=1,
        host_batch_size=1,
    )
    runner = DeterministicRunner()

    run_port_stage(runner, settings, [host])  # type: ignore[arg-type]
    run_deep_inspection_stage(runner, settings, [host])  # type: ignore[arg-type]
    findings = extract_findings([host])
    assessment = assess_hosts([host])
    payload = ScanPayload(
        scan_id=uuid4(),
        timestamp=datetime.now(timezone.utc),
        subnet="192.168.1.0/24",
        scan_mode="extensive",
        hosts=[
            build_host_payload(
                host,
                machine_type=assessment.machine_types[host.ip],
                device_profile=assessment.device_profiles[host.ip],
            )
        ],
        findings=findings,
        assessment_policy_version=LOCAL_ASSESSMENT_POLICY_VERSION,
        exposures=assessment.exposures,
        metadata={"elapsed_seconds": 42},
    )

    assert len(calls) == 2
    assert "-sV" not in calls[0]
    assert "--script" not in calls[0]
    assert calls[1].count("-sV") == 1
    assert calls[1][-3:] == ["-p", "21,443", ip]

    assert (host.hostname, host.identity.mac, host.identity.vendor) == (
        "edge-gateway.lab",
        "02:00:00:00:01:30",
        "Lab Hardware Ltd",
    )
    assert [(port.port, port.protocol, port.state) for port in host.ports] == [
        (21, "tcp", "open"),
        (161, "udp", "filtered"),
        (443, "tcp", "open"),
    ]
    ftp, _, https = host.ports
    assert (
        ftp.service.name,
        ftp.service.product,
        ftp.service.version,
        ftp.service.extra_info,
        ftp.service.banner,
        ftp.service.cpes,
    ) == (
        "ftp",
        "vsftpd",
        "3.0.3",
        "secure mode",
        "vsftpd 3.0.3 secure mode",
        ["cpe:/a:vsftpd:vsftpd:3.0.3"],
    )
    assert https.service.banner == "nginx 1.24.0 Ubuntu"
    assert https.service.cpes == ["cpe:/a:nginx:nginx:1.24.0"]
    assert [script.script_id for script in ftp.scripts] == ["ftp-anon"]
    assert [script.script_id for script in https.scripts] == ["vulners"]
    assert [script.script_id for script in host.host_scripts] == [
        "smb2-security-mode"
    ]

    serialized_host = payload.hosts[0]
    assert (
        str(serialized_host.ip),
        serialized_host.hostname,
        serialized_host.mac,
        serialized_host.vendor,
    ) == (
        ip,
        "edge-gateway.lab",
        "02:00:00:00:01:30",
        "Lab Hardware Ltd",
    )
    assert {
        (port.port, port.protocol, port.state, port.service, port.version)
        for port in serialized_host.ports
    } == {
        (21, "tcp", "open", "ftp", "vsftpd 3.0.3 secure mode"),
        (161, "udp", "filtered", "unknown", None),
        (443, "tcp", "open", "https", "nginx 1.24.0 Ubuntu"),
    }
    assert [(item.port, item.protocol) for item in payload.exposures] == [
        (21, "tcp"),
        (443, "tcp"),
    ]
    assert payload.hosts[0].device_profile is not None
    assert {
        (
            finding.port,
            finding.source_script,
            finding.cve_id,
            finding.severity,
            finding.evidence,
        )
        for finding in payload.findings
    } == {
        (
            21,
            "ftp-anon",
            None,
            "high",
            "Anonymous FTP login allowed (FTP code 230)",
        ),
        (
            443,
            "vulners",
            "CVE-2024-23456",
            "high",
            "vulners matched nginx 1.24.0 Ubuntu (TCP/443) on "
            "192.168.1.30:443 to CVE-2024-23456 via "
            "cpe:/a:nginx:nginx:1.24.0.",
        ),
        (
            None,
            "smb2-security-mode",
            None,
            "medium",
            "Message signing enabled but not required",
        ),
    }
