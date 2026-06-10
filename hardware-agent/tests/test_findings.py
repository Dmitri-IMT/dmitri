from __future__ import annotations

import xml.etree.ElementTree as ET

from agent.normalize.findings import extract_findings
from agent.scanner.models import HostInfo, PortInfo, ScriptResult, ServiceInfo
from agent.utils.nmap_xml import parse_ports


def test_vulners_script_is_normalized_into_cve_findings() -> None:
    host_element = ET.fromstring("""
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
        """)
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
    host_element = ET.fromstring("""
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
        """)
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


def test_smb_protocols_detects_smbv1_support() -> None:
    host_element = ET.fromstring("""
        <host>
          <ports>
            <port protocol="tcp" portid="445">
              <state state="open" />
              <service name="microsoft-ds" />
              <script
                id="smb-protocols"
                output="Supported dialects:&#10;  NT LM 0.12 (SMBv1)&#10;  2.02"
              >
                <elem key="dialects">NT LM 0.12 (SMBv1), 2.02</elem>
              </script>
            </port>
          </ports>
        </host>
        """)
    host = HostInfo(
        ip="192.168.0.50",
        hostname="fileserver",
        ports=parse_ports(host_element),
    )

    findings = extract_findings([host])

    assert len(findings) == 1
    finding = findings[0]
    assert finding.title == "SMBv1 protocol enabled"
    assert finding.severity == "high"
    assert finding.source_script == "smb-protocols"


def test_http_methods_detects_risky_verbs() -> None:
    host_element = ET.fromstring("""
        <host>
          <ports>
            <port protocol="tcp" portid="8080">
              <state state="open" />
              <service name="http" />
              <script
                id="http-methods"
                output="Supported Methods: GET HEAD POST OPTIONS PUT DELETE TRACE"
              />
            </port>
          </ports>
        </host>
        """)
    host = HostInfo(ip="192.168.0.60", hostname="web", ports=parse_ports(host_element))

    findings = extract_findings([host])

    assert len(findings) == 1
    finding = findings[0]
    assert finding.title == "Potentially risky HTTP methods enabled"
    assert finding.severity == "medium"
    assert finding.source_script == "http-methods"


def test_ssh_auth_methods_detects_password_authentication() -> None:
    host_element = ET.fromstring("""
        <host>
          <ports>
            <port protocol="tcp" portid="22">
              <state state="open" />
              <service name="ssh" />
              <script
                id="ssh-auth-methods"
                output="Supported authentication methods: publickey,password"
              />
            </port>
          </ports>
        </host>
        """)
    host = HostInfo(
        ip="192.168.0.70",
        hostname="ssh-host",
        ports=parse_ports(host_element),
    )

    findings = extract_findings([host])

    assert len(findings) == 1
    finding = findings[0]
    assert finding.title == "SSH password authentication exposed"
    assert finding.severity == "low"
    assert finding.source_script == "ssh-auth-methods"


def test_unmapped_script_with_cve_uses_generic_fallback() -> None:
    host_element = ET.fromstring("""
        <host>
          <ports>
            <port protocol="tcp" portid="443">
              <state state="open" />
              <service name="https" />
              <script
                id="some-unmapped-script"
                output="Advisory notes CVE-2021-1234 is present"
              />
            </port>
          </ports>
        </host>
        """)
    host = HostInfo(
        ip="192.168.0.80",
        hostname="host",
        ports=parse_ports(host_element),
    )

    findings = extract_findings([host])

    assert len(findings) == 1
    finding = findings[0]
    assert finding.cve_id == "CVE-2021-1234"
    assert finding.source_script == "some-unmapped-script"
    assert finding.severity == "high"


def _ssl_cert_host(
    *,
    not_after: str,
    subject_cn: str,
    issuer_cn: str,
    sig_algo: str,
    bits: str,
) -> HostInfo:
    host_element = ET.fromstring(f"""
        <host>
          <ports>
            <port protocol="tcp" portid="443">
              <state state="open" />
              <service name="https" />
              <script id="ssl-cert" output="Certificate details">
                <table key="subject"><elem key="commonName">{subject_cn}</elem></table>
                <table key="issuer"><elem key="commonName">{issuer_cn}</elem></table>
                <table key="pubkey">
                  <elem key="type">rsa</elem>
                  <elem key="bits">{bits}</elem>
                </table>
                <table key="validity">
                  <elem key="notBefore">2019-01-01T00:00:00</elem>
                  <elem key="notAfter">{not_after}</elem>
                </table>
                <elem key="sig_algo">{sig_algo}</elem>
                <elem key="md5">abc123</elem>
                <elem key="sha1">def456</elem>
              </script>
            </port>
          </ports>
        </host>
        """)
    return HostInfo(
        ip="192.168.1.10",
        hostname="tls-host",
        ports=parse_ports(host_element),
    )


def test_ssl_cert_expired_is_high() -> None:
    host = _ssl_cert_host(
        not_after="2021-01-01T00:00:00",
        subject_cn="a.local",
        issuer_cn="DigiCert CA",
        sig_algo="sha256WithRSAEncryption",
        bits="2048",
    )

    findings = extract_findings([host])

    assert len(findings) == 1
    assert findings[0].title == "TLS certificate expired"
    assert findings[0].severity == "high"
    assert findings[0].source_script == "ssl-cert"


def test_ssl_cert_self_signed_is_medium() -> None:
    host = _ssl_cert_host(
        not_after="2035-01-01T00:00:00",
        subject_cn="a.local",
        issuer_cn="a.local",
        sig_algo="sha256WithRSAEncryption",
        bits="2048",
    )

    findings = extract_findings([host])

    assert len(findings) == 1
    assert findings[0].title == "Self-signed TLS certificate"
    assert findings[0].severity == "medium"


def test_ssl_cert_weak_signature_is_medium_not_fooled_by_fingerprint() -> None:
    host = _ssl_cert_host(
        not_after="2035-01-01T00:00:00",
        subject_cn="a.local",
        issuer_cn="DigiCert CA",
        sig_algo="sha1WithRSAEncryption",
        bits="2048",
    )

    findings = extract_findings([host])

    assert len(findings) == 1
    assert findings[0].title == "Weak TLS certificate signature"
    assert findings[0].severity == "medium"


def test_ssl_cert_weak_key_is_medium() -> None:
    host = _ssl_cert_host(
        not_after="2035-01-01T00:00:00",
        subject_cn="a.local",
        issuer_cn="DigiCert CA",
        sig_algo="sha256WithRSAEncryption",
        bits="1024",
    )

    findings = extract_findings([host])

    assert len(findings) == 1
    assert findings[0].title == "Weak TLS public key"
    assert findings[0].severity == "medium"


def test_ssl_cert_valid_modern_yields_no_finding() -> None:
    host = _ssl_cert_host(
        not_after="2035-01-01T00:00:00",
        subject_cn="a.local",
        issuer_cn="DigiCert CA",
        sig_algo="sha256WithRSAEncryption",
        bits="4096",
    )

    assert extract_findings([host]) == []


def test_ssl_enum_ciphers_weak_config_yields_medium_findings() -> None:
    host_element = ET.fromstring("""
        <host>
          <ports>
            <port protocol="tcp" portid="443">
              <state state="open" />
              <service name="https" />
              <script id="ssl-enum-ciphers" output="cipher report">
                <table key="TLSv1.0">
                  <table key="warnings">
                    <elem>Broken cipher RC4 is deprecated by RFC 7465</elem>
                  </table>
                </table>
                <elem key="least strength">C</elem>
              </script>
            </port>
          </ports>
        </host>
        """)
    host = HostInfo(
        ip="192.168.1.11",
        hostname="tls-host",
        ports=parse_ports(host_element),
    )

    findings = extract_findings([host])

    assert len(findings) == 3
    assert all(f.severity == "medium" for f in findings)
    titles = {f.title for f in findings}
    assert "Deprecated TLS/SSL protocol offered: TLSv1.0" in titles
    assert "Weak TLS cipher configuration" in titles
    assert "Weak TLS cipher strength (grade C)" in titles


def test_ssl_enum_ciphers_clean_grade_yields_no_finding() -> None:
    host_element = ET.fromstring("""
        <host>
          <ports>
            <port protocol="tcp" portid="443">
              <state state="open" />
              <service name="https" />
              <script id="ssl-enum-ciphers" output="cipher report">
                <table key="TLSv1.2">
                  <table key="ciphers" />
                </table>
                <elem key="least strength">A</elem>
              </script>
            </port>
          </ports>
        </host>
        """)
    host = HostInfo(
        ip="192.168.1.12",
        hostname="tls-host",
        ports=parse_ports(host_element),
    )

    assert extract_findings([host]) == []


def _ftp_anon_host(output: str) -> HostInfo:
    host_element = ET.fromstring(f"""
        <host>
          <ports>
            <port protocol="tcp" portid="21">
              <state state="open" />
              <service name="ftp" />
              <script id="ftp-anon" output="{output}" />
            </port>
          </ports>
        </host>
        """)
    return HostInfo(
        ip="192.168.1.13",
        hostname="ftp-host",
        ports=parse_ports(host_element),
    )


def test_ftp_anon_allowed_is_high() -> None:
    host = _ftp_anon_host("Anonymous FTP login allowed (FTP code 230)")
    findings = extract_findings([host])

    assert len(findings) == 1
    assert findings[0].title == "Anonymous FTP login allowed"
    assert findings[0].severity == "high"


def test_ftp_anon_writeable_is_critical() -> None:
    output = (
        "Anonymous FTP login allowed (FTP code 230) "
        "drwxrwxrwx incoming [NSE: writeable]"
    )
    findings = extract_findings([_ftp_anon_host(output)])

    assert len(findings) == 1
    assert findings[0].severity == "critical"


def test_ftp_anon_denied_yields_no_finding() -> None:
    assert extract_findings([_ftp_anon_host("")]) == []


def test_ffuf_classified_path_hits_become_web_findings() -> None:
    host = HostInfo(
        ip="192.168.1.90",
        hostname="web-host",
        ports=[
            PortInfo(
                port=80,
                service=ServiceInfo(name="http"),
                scripts=[
                    ScriptResult(
                        script_id="ffuf",
                        output="1 sensitive path discovered",
                        data={
                            "hits": [
                                {
                                    "path": "/.git/",
                                    "url": "http://192.168.1.90:80/.git/",
                                    "status": 403,
                                    "dangerous": True,
                                    "risk": "dangerous",
                                    "reason": "sensitive-path",
                                },
                                {
                                    "path": "/assets/",
                                    "url": "http://192.168.1.90:80/assets/",
                                    "status": 200,
                                    "dangerous": False,
                                    "risk": "informational",
                                    "reason": "common-web-path",
                                },
                            ]
                        },
                    )
                ],
            )
        ],
    )

    findings = extract_findings([host])

    assert len(findings) == 2
    assert [finding.source for finding in findings] == [
        "web_directory_enum",
        "web_directory_enum",
    ]
    assert [finding.source_script for finding in findings] == ["ffuf", "ffuf"]
    assert [finding.title for finding in findings] == [
        "Potentially dangerous web path exposed: /.git/",
        "Web path discovered: /assets/",
    ]
    assert [finding.severity for finding in findings] == ["medium", "low"]


def test_nikto_issue_becomes_web_vulnerability_finding() -> None:
    host = HostInfo(
        ip="192.168.1.91",
        hostname="web-host",
        ports=[
            PortInfo(
                port=80,
                service=ServiceInfo(name="http"),
                scripts=[
                    ScriptResult(
                        script_id="nikto",
                        output="Nikto reported /admin/",
                        data={
                            "issues": [
                                {
                                    "title": "Nikto reported /admin/",
                                    "message": "Admin login page/section found.",
                                    "path": "/admin/",
                                    "severity": "medium",
                                }
                            ]
                        },
                    )
                ],
            )
        ],
    )

    findings = extract_findings([host])

    assert len(findings) == 1
    assert findings[0].source == "web_vulnerability_scan"
    assert findings[0].source_script == "nikto"
    assert findings[0].title == "Nikto reported /admin/"
    assert findings[0].severity == "medium"


def test_testssl_issue_becomes_tls_finding() -> None:
    host = HostInfo(
        ip="192.168.1.92",
        hostname="tls-host",
        ports=[
            PortInfo(
                port=443,
                service=ServiceInfo(name="https"),
                scripts=[
                    ScriptResult(
                        script_id="testssl",
                        output="testssl issues",
                        data={
                            "issues": [
                                {
                                    "title": "Deprecated TLS/SSL protocol offered: TLSv1.0",
                                    "message": "testssl.sh reported support for TLSv1.0.",
                                    "severity": "medium",
                                    "evidence": "TLS 1.0 offered",
                                }
                            ]
                        },
                    )
                ],
            )
        ],
    )

    findings = extract_findings([host])

    assert len(findings) == 1
    assert findings[0].source == "tls_configuration_audit"
    assert findings[0].source_script == "testssl"
    assert findings[0].title == "Deprecated TLS/SSL protocol offered: TLSv1.0"
    assert findings[0].severity == "medium"


def test_enum4linux_issue_becomes_smb_finding() -> None:
    host = HostInfo(
        ip="192.168.1.93",
        hostname="smb-host",
        ports=[
            PortInfo(
                port=445,
                service=ServiceInfo(name="microsoft-ds"),
                scripts=[
                    ScriptResult(
                        script_id="enum4linux-ng",
                        output="enum4linux issues",
                        data={
                            "issues": [
                                {
                                    "title": "Anonymous SMB session allowed",
                                    "message": "enum4linux-ng reported a successful null SMB session.",
                                    "severity": "high",
                                    "evidence": "Server allows authentication via username '' and password ''",
                                }
                            ]
                        },
                    )
                ],
            )
        ],
    )

    findings = extract_findings([host])

    assert len(findings) == 1
    assert findings[0].source == "smb_enumeration"
    assert findings[0].source_script == "enum4linux-ng"
    assert findings[0].title == "Anonymous SMB session allowed"
    assert findings[0].severity == "high"
