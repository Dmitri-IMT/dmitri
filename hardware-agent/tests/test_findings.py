from __future__ import annotations

import xml.etree.ElementTree as ET

from agent.normalize.findings import extract_findings
from agent.scanner.models import HostInfo
from agent.utils.nmap_xml import parse_ports


def test_vulners_script_is_normalized_into_cve_findings() -> None:
    host_element = ET.fromstring(
        """
        <host>
          <ports>
            <port protocol="tcp" portid="22">
              <state state="open" />
              <service name="ssh" product="OpenSSH" version="7.2p2">
                <cpe>cpe:/a:openbsd:openssh:7.2p2</cpe>
              </service>
              <script id="vulners" output="Known vulnerabilities found">
                <table key="cpe:/a:openbsd:openssh:7.2p2">
                  <table>
                    <elem key="is_exploit">false</elem>
                    <elem key="cvss">7.8</elem>
                    <elem key="id">CVE-2016-10012</elem>
                    <elem key="type">cve</elem>
                  </table>
                </table>
              </script>
            </port>
          </ports>
        </host>
        """
    )
    host = HostInfo(
        ip="192.168.0.10",
        hostname="camera",
        ports=parse_ports(host_element),
    )

    findings = extract_findings([host])

    assert len(findings) == 1
    finding = findings[0]
    assert finding.cve_id == "CVE-2016-10012"
    assert finding.cvss_score == 7.8
    assert finding.source == "nmap_vulners"
    assert finding.source_script == "vulners"
    assert finding.port == 22
    assert finding.references == ["https://vulners.com/cve/CVE-2016-10012"]


def test_smb_signing_output_becomes_misconfiguration_finding() -> None:
    host_element = ET.fromstring(
        """
        <host>
          <ports>
            <port protocol="tcp" portid="445">
              <state state="open" />
              <service name="microsoft-ds" product="Samba smbd" version="4.13.14" />
              <script
                id="smb2-security-mode"
                output="2.02:&#10;  Message signing enabled but not required"
              >
                <elem key="message_signing">disabled (dangerous, but default)</elem>
              </script>
            </port>
          </ports>
        </host>
        """
    )
    host = HostInfo(
        ip="192.168.0.40",
        hostname="nas",
        ports=parse_ports(host_element),
    )

    findings = extract_findings([host])

    assert len(findings) == 1
    finding = findings[0]
    assert finding.title == "SMB signing disabled"
    assert finding.source_script == "smb2-security-mode"
    assert finding.severity == "medium"
    assert finding.port == 445
