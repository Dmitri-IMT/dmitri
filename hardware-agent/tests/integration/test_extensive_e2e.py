from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from uuid import uuid4

from agent.normalize.contracts import ScanPayload
from agent.normalize.findings import extract_findings
from agent.scanner.models import HostInfo
from agent.scanner.stages import build_device_payload
from agent.tui.screens.scan_view import ScanViewScreen
from agent.utils.nmap_xml import parse_ports


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


def test_extensive_scan_surfaces_tls_and_ftp_findings_in_view() -> None:
    host = _weak_target_host()
    findings = extract_findings([host])
    payload = ScanPayload(
        scan_id=uuid4(),
        timestamp=datetime.now(timezone.utc),
        subnet="192.168.1.0/24",
        scan_mode="extensive",
        devices=[build_device_payload(host)],
        findings=findings,
        metadata={"elapsed_seconds": 1500},
    )

    rendered = ScanViewScreen(payload=payload)._render_payload(payload)

    assert "Extensive" in rendered
    assert "TLS certificate expired" in rendered
    assert "Anonymous FTP login allowed" in rendered
