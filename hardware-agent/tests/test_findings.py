from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

from agent.normalize.contracts import FindingEvidenceObservationPayload, FindingPayload
from agent.normalize.findings import (
    _merge_finding_group,
    _merge_observations,
    assess_local_evidence,
    extract_findings,
)
from agent.ot.modbus.models import ModbusAddressRange, ModbusService, ModbusUnit
from agent.scanner.models import HostInfo, PortInfo, ScriptResult, ServiceInfo
from agent.targeted.models import (
    TargetedGapReason,
    TargetedIssue,
    TargetedObservation,
    TargetedOutcome,
    TargetedTool,
    TargetedUnit,
    TargetedUnitResult,
)
from agent.utils.nmap_xml import parse_host_scripts, parse_ports

_BACKEND_SRC = Path(__file__).resolve().parents[2] / "backend" / "src"
if str(_BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(_BACKEND_SRC))
from api.services.scan_evidence import reduce_finding_evidence  # noqa: E402


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


def test_host_scoped_smb_signing_output_becomes_misconfiguration_finding() -> None:
    host_element = ET.fromstring("""
        <host>
          <hostscript>
            <script
              id="smb2-security-mode"
              output="&#xa;  311: &#xa;    Message signing enabled but not required"
            >
              <table key="311">
                <elem>Message signing enabled but not required</elem>
              </table>
            </script>
          </hostscript>
        </host>
        """)
    host = HostInfo(
        ip="192.168.0.40",
        hostname="nas",
        host_scripts=parse_host_scripts(host_element),
    )

    findings = extract_findings([host])

    assert len(findings) == 1
    finding = findings[0]
    assert finding.title == "SMB signing disabled"
    assert finding.source_script == "smb2-security-mode"
    assert finding.severity == "medium"
    assert finding.port is None


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
    assert finding.port == 445


def test_host_scoped_smb_protocols_detects_smbv1_support() -> None:
    host_element = ET.fromstring("""
        <host>
          <hostscript>
            <script
              id="smb-protocols"
              output="&#xa;  dialects: &#xa;    NT LM 0.12 (SMBv1) [dangerous]
                &#xa;    202"
            >
              <table key="dialects">
                <elem>NT LM 0.12 (SMBv1) [dangerous]</elem>
                <elem>202</elem>
              </table>
            </script>
          </hostscript>
        </host>
        """)
    host = HostInfo(
        ip="192.168.0.50",
        hostname="fileserver",
        host_scripts=parse_host_scripts(host_element),
    )

    findings = extract_findings([host])

    assert len(findings) == 1
    finding = findings[0]
    assert finding.title == "SMBv1 protocol enabled"
    assert finding.source_script == "smb-protocols"
    assert finding.port is None


def test_host_scoped_smb2_only_protocols_yields_no_finding() -> None:
    host_element = ET.fromstring("""
        <host>
          <hostscript>
            <script
              id="smb-protocols"
              output="&#xa;  dialects: &#xa;    202&#xa;    210&#xa;    300
                &#xa;    302&#xa;    311"
            >
              <table key="dialects">
                <elem>202</elem>
                <elem>210</elem>
                <elem>300</elem>
                <elem>302</elem>
                <elem>311</elem>
              </table>
            </script>
          </hostscript>
        </host>
        """)
    host = HostInfo(
        ip="192.168.0.50",
        hostname="fileserver",
        host_scripts=parse_host_scripts(host_element),
    )

    assert extract_findings([host]) == []


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
    assert finding.issue_key == "title:potentially risky http methods enabled"
    evidence_finding = extract_findings([host], include_evidence_metadata=True)[0]
    assert assess_local_evidence(evidence_finding).confidence == "confirmed"
    _assert_backend_assessment_matches(evidence_finding)


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
    assert finding.issue_key == "title:ssh password authentication exposed"
    evidence_finding = extract_findings([host], include_evidence_metadata=True)[0]
    assert assess_local_evidence(evidence_finding).confidence == "confirmed"
    _assert_backend_assessment_matches(evidence_finding)


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
    assert finding.severity == "low"
    assert "no structured positive result" in finding.description
    assert finding.title == "CVE-2021-1234 reported by some-unmapped-script"
    assert finding.references == []
    assert finding.evidence_observations == []
    internal_finding = extract_findings([host], include_evidence_metadata=True)[0]
    assert internal_finding.evidence_observations[0].method == "textual_reference"
    assert internal_finding.evidence_observations[0].result == "inconclusive"
    assessment = assess_local_evidence(internal_finding)
    assert (assessment.method, assessment.status, assessment.confidence) == (
        "textual_reference",
        "inconclusive",
        "tentative",
    )


def _generic_nse_host(data: object, output: str = "") -> HostInfo:
    return HostInfo(
        ip="192.168.0.81",
        hostname="host",
        ports=[
            PortInfo(
                port=445,
                service=ServiceInfo(name="microsoft-ds"),
                scripts=[ScriptResult("unmapped-nse", output, data)],
            )
        ],
    )


def test_structured_negative_without_description_blocks_text_fallback() -> None:
    findings = extract_findings(
        [_generic_nse_host({"state": " NOT   VULNERABLE "}, "CVE-2020-1234")]
    )

    assert findings == []


def test_structured_ids_maps_and_lists_are_accepted_only_for_positive_state() -> None:
    data = [
        {
            "state": "VULNERABLE",
            "title": "First issue",
            "IDS": {"CVE": "CVE-2020-1234"},
        },
        {
            "state": "vulnerable (DoS)",
            "ids": [{"CVE": "CVE-2021-2345"}],
            "title": "Second issue",
        },
        {"state": "LIKELY VULNERABLE", "title": "Candidate", "ids": ["CVE-2022-3456"]},
        {
            "state": "NOT VULNERABLE",
            "IDS": {"CVE": "CVE-2023-4567"},
        },
    ]

    findings = extract_findings([_generic_nse_host(data, "CVE-2023-4567")])

    assert [(finding.title, finding.cve_id) for finding in findings] == [
        ("First issue", "CVE-2020-1234"),
        ("Second issue", "CVE-2021-2345"),
    ]


def test_malformed_structured_result_blocks_text_fallback() -> None:
    findings = extract_findings(
        [_generic_nse_host({"state": ["VULNERABLE"]}, "CVE-2020-1234")]
    )

    assert findings == []


def test_malformed_nested_record_does_not_change_mixed_sibling_results() -> None:
    data = [
        {
            "state": "NOT VULNERABLE",
            "ids": {"CVE": "CVE-2020-1234"},
            "details": {"state": ["VULNERABLE"]},
        },
        {
            "state": "VULNERABLE",
            "title": "Independent positive record",
            "ids": {"CVE": "CVE-2021-2345"},
        },
    ]

    findings = extract_findings([_generic_nse_host(data, "Advisory CVE-2022-3456")])

    assert [(finding.title, finding.cve_id) for finding in findings] == [
        ("Independent positive record", "CVE-2021-2345")
    ]


def test_null_structured_fields_block_text_fallback() -> None:
    for data in (
        {"state": None},
        {"IDS": None},
        {"state": None, "ids": None},
    ):
        assert (
            extract_findings([_generic_nse_host(data, "Advisory CVE-2020-1234")]) == []
        )


def test_unknown_structured_result_blocks_text_fallback() -> None:
    data = {
        "state": "UNKNOWN (unable to test)",
        "IDS": {"CVE": "CVE-2020-1234"},
    }

    assert extract_findings([_generic_nse_host(data, "CVE-2022-3456")]) == []


def test_cve_in_reference_or_child_record_does_not_inherit_positive_state() -> None:
    data = {
        "state": "VULNERABLE",
        "title": "Positive parent record",
        "references": ["https://example.test/CVE-2020-1234"],
        "details": {"ids": {"CVE": "CVE-2021-2345"}},
    }

    findings = extract_findings([_generic_nse_host(data)])

    assert len(findings) == 1
    assert findings[0].title == "Positive parent record"
    assert findings[0].cve_id is None
    assert findings[0].references == ["https://example.test/CVE-2020-1234"]


def test_native_ms17_positive_state_does_not_require_check_results() -> None:
    data = {
        "state": "VULNERABLE",
        "title": "Remote Code Execution vulnerability in Microsoft SMBv1 servers",
        "IDS": ["CVE:CVE-2017-0143"],
    }

    host = _generic_nse_host(data)
    host.ports[0].scripts[0].script_id = "smb-vuln-ms17-010"
    findings = extract_findings([host], include_evidence_metadata=True)

    assert len(findings) == 1
    assert findings[0].cve_id == "CVE-2017-0143"
    observation = findings[0].evidence_observations[0]
    assert observation.method == "specific_check"
    assert observation.result == "positive"
    assert observation.rule_id == "nse:smb-vuln-ms17-010"
    assert observation.facts == {
        "vulnerability_state": "VULNERABLE",
        "table": "smb-vuln-ms17-010",
    }


def test_native_nmap_ids_list_prefix_is_parsed_strictly() -> None:
    data = {
        "state": "VULNERABLE",
        "title": "Native vulnerability record",
        "IDS": ["CVE:CVE-2020-1234", "BID:1234"],
    }

    findings = extract_findings([_generic_nse_host(data)])

    assert len(findings) == 1
    assert findings[0].cve_id == "CVE-2020-1234"


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

    findings = extract_findings([host], include_evidence_metadata=True)

    assert len(findings) == 3
    assert all(f.severity == "medium" for f in findings)
    titles = {f.title for f in findings}
    assert "Deprecated TLS/SSL protocol offered: TLSv1.0" in titles
    assert "Weak TLS cipher configuration" in titles
    assert "Weak TLS cipher strength (grade C)" in titles
    grade = next(
        finding
        for finding in findings
        if finding.title == "Weak TLS cipher strength (grade C)"
    )
    observation = grade.evidence_observations[0]
    assert (
        observation.condition_key
        == "title:weak tls cipher strength (grade c):cipher report"
    )
    assessment = assess_local_evidence(grade)
    assert (assessment.status, assessment.confidence) == ("supported", "confirmed")


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


def test_modbus_read_findings_emit_one_finding_per_readable_unit() -> None:
    observed_at = datetime(2026, 9, 12, tzinfo=timezone.utc)
    host = HostInfo(
        ip="192.168.10.30",
        hostname="plc",
        ports=[PortInfo(port=502, service=ServiceInfo(name="modbus"))],
        industrial_services=[
            ModbusService(
                port=502,
                confidence="confirmed",
                units=[
                    ModbusUnit(
                        unit_id=0,
                        status="responding",
                        address_ranges=[
                            ModbusAddressRange(
                                address_space="input_register",
                                start_address=0,
                                count=1,
                                status="readable",
                                observed_at=observed_at,
                            )
                        ],
                    ),
                    ModbusUnit(
                        unit_id=1,
                        status="responding",
                        address_ranges=[
                            ModbusAddressRange(
                                address_space="holding_register",
                                start_address=0,
                                count=1,
                                status="readable",
                                observed_at=observed_at,
                            )
                        ],
                    ),
                    ModbusUnit(
                        unit_id=2,
                        status="responding",
                        address_ranges=[
                            ModbusAddressRange(
                                address_space="coil",
                                start_address=0,
                                count=1,
                                status="readable",
                                observed_at=observed_at,
                            )
                        ],
                    ),
                ],
            )
        ],
    )

    findings = extract_findings([host], include_evidence_metadata=True)
    modbus_findings = [
        finding
        for finding in findings
        if finding.source == "modbus-read-only-assessment"
    ]

    assert len(modbus_findings) == 3
    assert sorted(finding.unit_id for finding in modbus_findings) == [0, 1, 2]
    for finding in modbus_findings:
        observation = finding.evidence_observations[0]
        assert observation.unit_id == finding.unit_id
        assert observation.source_script == "modbus-read-only-assessment"
        assert observation.facts == {"read_result": True}
        assert assess_local_evidence(finding).confidence == "confirmed"


def test_modbus_read_rule_does_not_confirm_a_forged_write_condition() -> None:
    observed_at = datetime(2026, 9, 12, tzinfo=timezone.utc)
    host = HostInfo(
        ip="192.168.10.30",
        hostname="plc",
        ports=[PortInfo(port=502, service=ServiceInfo(name="modbus"))],
        industrial_services=[
            ModbusService(
                port=502,
                confidence="confirmed",
                units=[
                    ModbusUnit(
                        unit_id=0,
                        status="responding",
                        address_ranges=[
                            ModbusAddressRange(
                                address_space="input_register",
                                start_address=0,
                                count=1,
                                status="readable",
                                observed_at=observed_at,
                            )
                        ],
                    )
                ],
            )
        ],
    )
    finding = next(
        item
        for item in extract_findings([host], include_evidence_metadata=True)
        if item.source == "modbus-read-only-assessment"
    )
    arbitrary_condition = "title:modbus write permitted"
    forged = finding.model_copy(
        update={
            "title": "Modbus write permitted",
            "issue_key": arbitrary_condition,
            "evidence_observations": [
                finding.evidence_observations[0].model_copy(
                    update={"condition_key": arbitrary_condition}
                )
            ],
        }
    )

    assessment = assess_local_evidence(forged)

    assert assessment.status == "inconclusive"
    assert assessment.confidence == "tentative"


def _targeted_result(
    *,
    issue: TargetedIssue | None = None,
    outcome: TargetedOutcome = TargetedOutcome.COMPLETED,
    reason_code: TargetedGapReason | None = None,
) -> TargetedUnitResult:
    unit = TargetedUnit(
        ip="192.168.10.40",
        port=443,
        protocol="tcp",
        service="https",
        tool=TargetedTool.TESTSSL,
    )
    return TargetedUnitResult(
        unit,
        outcome,
        issues=[issue] if issue is not None else [],
        reason_code=reason_code,
    )


def test_targeted_issue_maps_to_existing_finding_contract() -> None:
    issue = TargetedIssue(
        issue_key="tls:weak-cipher:rc4",
        title="RC4 cipher accepted",
        description="The endpoint accepts RC4.",
        severity="high",
        recommendation="Disable RC4.",
        evidence="TLS_RSA_WITH_RC4_128_SHA",
        cve_id="CVE-2013-2566",
        cvss_score=7.5,
        references=["https://example.test/advisory"],
    )
    host = HostInfo(
        ip="192.168.10.40",
        hostname="tls-host",
        ports=[
            PortInfo(
                port=443,
                service=ServiceInfo(name="https"),
            )
        ],
        targeted_results=[_targeted_result(issue=issue)],
    )

    findings = extract_findings([host])

    assert len(findings) == 1
    finding = findings[0]
    assert finding.source == "targeted_service_assessment"
    assert finding.source_script == "testssl.sh"
    assert str(finding.ip) == host.ip
    assert finding.port == 443
    assert finding.title == issue.title
    assert finding.description == issue.description
    assert finding.recommendation == issue.recommendation
    assert finding.evidence == issue.evidence
    assert finding.cve_id == issue.cve_id
    assert finding.cvss_score == issue.cvss_score
    assert finding.references == issue.references


def test_targeted_gaps_and_benign_inventory_do_not_become_findings() -> None:
    unit = TargetedUnit(
        ip="192.168.10.41",
        port=445,
        protocol="tcp",
        service="microsoft-ds",
        tool=TargetedTool.ENUM4LINUX,
    )
    host = HostInfo(
        ip="192.168.10.41",
        hostname="fileserver",
        ports=[PortInfo(port=445, service=ServiceInfo(name="microsoft-ds"))],
        targeted_results=[
            TargetedUnitResult(
                unit,
                TargetedOutcome.COMPLETED,
                observations=[
                    TargetedObservation(
                        "smb:inventory",
                        "service_identity",
                        "Samba file server",
                        "service=samba",
                    )
                ],
            ),
            TargetedUnitResult(
                unit,
                TargetedOutcome.SKIPPED,
                reason_code=TargetedGapReason.TOOL_UNAVAILABLE,
            ),
        ],
    )

    assert extract_findings([host]) == []


def test_targeted_finding_precedes_nse_duplicate_and_merges_corroboration() -> None:
    host_element = ET.fromstring(
        """
        <host>
          <ports>
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
        """
    )
    issue = TargetedIssue(
        issue_key="ftp:anonymous-login",
        title="Anonymous FTP login allowed",
        description="Targeted probe confirmed anonymous login.",
        severity="high",
        recommendation="Disable anonymous access.",
        evidence="220 FTP banner; anonymous login accepted",
        references=["https://example.test/ftp"],
        method="specific_check",
        result="positive",
        rule_id="targeted:ftp-check-anonymous",
        facts={"anonymous_login_accepted": True},
    )
    host = HostInfo(
        ip="192.168.10.42",
        hostname="ftp-host",
        ports=parse_ports(host_element),
        targeted_results=[
            TargetedUnitResult(
                TargetedUnit("192.168.10.42", 21, "tcp", "ftp", TargetedTool.FTP_CHECK),
                TargetedOutcome.COMPLETED,
                issues=[issue],
            )
        ],
    )

    legacy_findings = extract_findings([host])
    assert legacy_findings[0].evidence_observations == []
    findings = extract_findings([host], include_evidence_metadata=True)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.source == "targeted_service_assessment"
    assert finding.description == issue.description
    assert finding.recommendation == issue.recommendation
    assert finding.references == ["https://example.test/ftp"]
    assert "corroborated by" not in finding.evidence
    assert len(finding.evidence_observations) == 2
    targeted = next(
        item
        for item in finding.evidence_observations
        if item.source_script == "ftp-check"
    )
    assert targeted.method == "specific_check"
    assert targeted.result == "positive"
    assert targeted.condition_key == "ftp:anonymous-login"
    assert targeted.facts == {"anonymous_login_accepted": True}
    assessment = assess_local_evidence(finding)
    assert (assessment.method, assessment.status, assessment.confidence) == (
        "specific_check",
        "supported",
        "confirmed",
    )
    cve_reference_only = finding.model_copy(
        update={"cve_id": "CVE-2024-12345", "issue_key": None}
    )
    assert assess_local_evidence(cve_reference_only).confidence == "tentative"
    negative = targeted.model_copy(
        update={
            "result": "negative",
            "facts": {"anonymous_login_accepted": False},
            "evidence": "anonymous login was rejected",
        }
    )
    for witnesses in ([targeted, negative], [negative, targeted]):
        assessment = assess_local_evidence(
            finding.model_copy(update={"evidence_observations": witnesses})
        )
        assert (assessment.status, assessment.confidence) == (
            "conflicting",
            "tentative",
        )

    # Candidate facts must be typed and bound to the finding endpoint.
    zero_is_not_false = targeted.model_copy(
        update={"facts": {"anonymous_login_accepted": 0}}
    )
    wrong_endpoint = targeted.model_copy(update={"port": 22})
    for invalid in (zero_is_not_false, wrong_endpoint):
        result = assess_local_evidence(
            finding.model_copy(update={"evidence_observations": [invalid]})
        )
        assert (result.status, result.confidence) == ("inconclusive", "tentative")

    negative_only = assess_local_evidence(
        finding.model_copy(update={"evidence_observations": [negative]})
    )
    assert (negative_only.method, negative_only.status, negative_only.confidence) == (
        "specific_check",
        "inconclusive",
        "tentative",
    )


def test_local_cve_text_stays_tentative() -> None:
    host = HostInfo(
        ip="192.0.2.94",
        hostname="server",
        ports=[
            PortInfo(
                port=445,
                service=ServiceInfo(name="microsoft-ds"),
                scripts=[
                    ScriptResult(
                        script_id="unknown-check",
                        output="See CVE-2024-12345 for details",
                    )
                ],
            )
        ],
    )
    finding = extract_findings([host], include_evidence_metadata=True)[0]
    assert finding.evidence_observations[0].method == "textual_reference"
    assert (
        assess_local_evidence(finding).method,
        assess_local_evidence(finding).confidence,
    ) == ("textual_reference", "tentative")


def test_local_observation_limit_keeps_supported_positive_witness() -> None:
    finding = FindingPayload(
        ip="192.0.2.95",
        port=21,
        protocol="tcp",
        issue_key="ftp:anonymous-login",
        severity="high",
        title="Anonymous FTP login allowed",
        description="Anonymous login was accepted.",
        recommendation="Disable anonymous login.",
        evidence="FTP code 230",
    )
    positive = FindingEvidenceObservationPayload(
        ip="192.0.2.95",
        port=21,
        protocol="tcp",
        condition_key="ftp:anonymous-login",
        method="specific_check",
        result="positive",
        source="nmap_nse",
        source_script="ftp-anon",
        rule_id="nse:ftp-anon",
        rule_version="1",
        evidence="Anonymous FTP login allowed",
        facts={"anonymous_login": True},
    )
    unsupported = [
        positive.model_copy(
            update={
                "method": "unknown",
                "result": "inconclusive",
                "rule_id": f"aaa-unsupported-{index}",
                "facts": {},
            }
        )
        for index in range(16)
    ]
    forward, truncated = _merge_observations(unsupported, [positive], finding)
    reverse, _ = _merge_observations([positive], unsupported, finding)
    assert truncated is True
    assert positive in forward
    assert [item.model_dump_json() for item in forward] == [
        item.model_dump_json() for item in reverse
    ]


def test_ms17_specific_negative_conflicts_with_same_cve_correlation() -> None:
    finding = FindingPayload(
        ip="192.0.2.96",
        port=445,
        protocol="tcp",
        cve_id="CVE-2017-0143",
        severity="high",
        title="CVE-2017-0143 detected",
        description="A catalog correlated this CVE.",
        recommendation="Review the server.",
        evidence="correlated product version",
        evidence_observations=[
            FindingEvidenceObservationPayload(
                ip="192.0.2.96",
                port=445,
                protocol="tcp",
                condition_key="CVE-2017-0143",
                method="version_correlation",
                result="positive",
                source="nmap_vulners",
                source_script="vulners",
                rule_id="catalog:nmap-vulners",
                rule_version="1",
                evidence="CPE matched catalog entry",
                facts={"cpe": "cpe:/o:microsoft:windows", "cve_id": "CVE-2017-0143"},
            ),
            FindingEvidenceObservationPayload(
                ip="192.0.2.96",
                port=445,
                protocol="tcp",
                condition_key="CVE-2017-0143",
                method="specific_check",
                result="negative",
                source="nmap_nse",
                source_script="smb-vuln-ms17-010",
                rule_id="nse:smb-vuln-ms17-010",
                rule_version="1",
                evidence="NOT VULNERABLE",
                facts={
                    "vulnerability_state": "NOT VULNERABLE",
                    "table": "smb-vuln-ms17-010",
                },
            ),
        ],
    )
    result = assess_local_evidence(finding)
    assert (result.status, result.confidence) == ("conflicting", "tentative")


def test_supported_evidence_wins_before_severity_or_source() -> None:
    host = HostInfo(
        ip="192.168.10.43",
        hostname="ftp-host",
        ports=[
            PortInfo(
                port=21,
                service=ServiceInfo(name="ftp"),
                scripts=[
                    ScriptResult(
                        script_id="ftp-anon",
                        output="Anonymous FTP login allowed (FTP code 230)",
                    )
                ],
            )
        ],
        targeted_results=[
            TargetedUnitResult(
                TargetedUnit("192.168.10.43", 21, "tcp", "ftp", TargetedTool.FTP_CHECK),
                TargetedOutcome.COMPLETED,
                issues=[
                    TargetedIssue(
                        issue_key="ftp:anonymous-login",
                        title="Targeted anonymous FTP result",
                        description="Targeted probe confirmed anonymous login.",
                        severity="medium",
                        recommendation="Disable anonymous access immediately.",
                        evidence="anonymous login accepted",
                    )
                ],
            )
        ],
    )

    findings = extract_findings([host])

    assert len(findings) == 1
    assert findings[0].severity == "high"
    assert findings[0].description.startswith("The FTP service")
    assert findings[0].recommendation.startswith("Disable anonymous FTP")


def test_ftp_evidence_must_match_finding_condition_and_endpoint() -> None:
    finding = extract_findings(
        [_ftp_anon_host("Anonymous FTP login allowed (FTP code 230)")],
        include_evidence_metadata=True,
    )[0]
    assert (
        assess_local_evidence(
            finding.model_copy(update={"issue_key": "ftp:unrelated"})
        ).confidence
        == "tentative"
    )
    wrong_endpoint = finding.evidence_observations[0].model_copy(
        update={"ip": "198.51.100.8"}
    )
    mismatched = finding.model_copy(update={"evidence_observations": [wrong_endpoint]})
    assert assess_local_evidence(mismatched).confidence == "tentative"


def test_configuration_observation_cannot_confirm_referenced_cve() -> None:
    observation = FindingEvidenceObservationPayload(
        ip="192.0.2.30",
        port=443,
        protocol="tcp",
        condition_key="CVE-2024-12345",
        method="configuration_observation",
        result="positive",
        source="nmap_nse",
        source_script="ssl-cert",
        rule_id="nse:ssl-cert-expired",
        rule_version="1",
        evidence="certificate expired",
        facts={"certificate_expired": True},
    )
    finding = FindingPayload(
        ip="192.0.2.30",
        port=443,
        protocol="tcp",
        issue_key="tls.certificate:expired",
        cve_id="CVE-2024-12345",
        severity="medium",
        title="Expired certificate",
        description="Expired certificate observed.",
        recommendation="Replace the certificate.",
        evidence="certificate expired",
        evidence_observations=[observation],
    )
    assert assess_local_evidence(finding).status == "inconclusive"


def test_smb_signing_fact_uses_exact_boolean_type() -> None:
    finding = FindingPayload(
        ip="192.0.2.31",
        port=445,
        protocol="tcp",
        issue_key="smb:signing",
        severity="medium",
        title="SMB signing is not required",
        description="SMB signing value recorded.",
        recommendation="Require SMB signing.",
        evidence="signing_required=0",
        evidence_observations=[
            FindingEvidenceObservationPayload(
                ip="192.0.2.31",
                port=445,
                protocol="tcp",
                condition_key="smb:signing",
                method="configuration_observation",
                result="positive",
                source="nmap_nse",
                source_script="smb2-security-mode",
                rule_id="nse:smb2-security-mode",
                rule_version="1",
                evidence="signing_required=0",
                facts={"signing_required": 0},
            )
        ],
    )
    assert assess_local_evidence(finding).confidence == "tentative"


def _assert_backend_assessment_matches(finding: FindingPayload) -> None:
    backend = reduce_finding_evidence(
        [item.model_dump(mode="json") for item in finding.evidence_observations],
        cve_id=finding.cve_id,
        issue_key=finding.issue_key,
        ip=finding.ip,
        port=finding.port,
        protocol=finding.protocol,
        unit_id=finding.unit_id,
        evidence_truncated=finding.evidence_truncated,
    )
    local = assess_local_evidence(finding)
    assert (local.method, local.status, local.confidence) == (
        backend.detection_method,
        backend.evidence_status,
        backend.confidence,
    )


def _tls_cipher_findings(output: str, data: dict[str, object]) -> list[FindingPayload]:
    host = HostInfo(
        ip="192.0.2.44",
        hostname="tls",
        ports=[
            PortInfo(
                port=443,
                service=ServiceInfo(name="https"),
                scripts=[
                    ScriptResult(script_id="ssl-enum-ciphers", output=output, data=data)
                ],
            )
        ],
    )
    return extract_findings([host], include_evidence_metadata=True)


def test_tls_warning_and_grade_metadata_match_backend_oracle() -> None:
    warning = _tls_cipher_findings(
        "cipher RC4 report", {"TLSv1.2": {"warnings": ["RC4 cipher is weak"]}}
    )[0]
    grade_with_primitive = _tls_cipher_findings(
        "cipher RC4 report",
        {"TLSv1.2": {"ciphers": []}, "least strength": "C"},
    )[0]
    grade_without_primitive = _tls_cipher_findings(
        "cipher report",
        {"TLSv1.2": {"ciphers": []}, "least strength": "C"},
    )[0]
    assert warning.evidence_observations[0].facts == {"weak_cipher": "RC4"}
    assert (
        grade_with_primitive.evidence_observations[0].condition_key == "tls.cipher:rc4"
    )
    assert grade_without_primitive.evidence_observations[0].condition_key == (
        "title:weak tls cipher strength (grade c):cipher report"
    )
    for finding in (warning, grade_with_primitive, grade_without_primitive):
        _assert_backend_assessment_matches(finding)

    negative = FindingPayload(
        ip="192.0.2.44",
        port=443,
        protocol="tcp",
        issue_key="title:weak tls cipher strength (grade a):clean cipher report",
        severity="low",
        title="TLS grade A",
        description="TLS grade is A.",
        recommendation="No change required.",
        evidence="clean cipher report",
        evidence_observations=[
            FindingEvidenceObservationPayload(
                ip="192.0.2.44",
                port=443,
                protocol="tcp",
                condition_key=(
                    "title:weak tls cipher strength (grade a):clean cipher report"
                ),
                method="configuration_observation",
                result="negative",
                source="nmap_nse",
                source_script="ssl-enum-ciphers",
                rule_id="nse:ssl-enum-ciphers-grade",
                rule_version="1",
                evidence="clean cipher report",
                facts={"weakest_grade": "A"},
            )
        ],
    )
    _assert_backend_assessment_matches(negative)


def test_complete_union_reduces_independently_of_candidate_order() -> None:
    unit = TargetedUnit("192.0.2.45", 21, "tcp", "ftp", TargetedTool.FTP_CHECK)

    def issue(
        title: str, method: str, result: str, rule: str, facts: dict[str, object]
    ):
        return TargetedIssue(
            "ftp:anonymous-login",
            title,
            title,
            "medium",
            title,
            title,
            method=method,
            result=result,
            rule_id=rule,
            facts=facts,
        )

    candidates = [
        issue(
            "Direct positive",
            "specific_check",
            "positive",
            "targeted:ftp-check-anonymous",
            {"anonymous_login_accepted": True},
        ),
        issue(
            "Direct negative",
            "specific_check",
            "negative",
            "targeted:ftp-check-anonymous",
            {"anonymous_login_accepted": False},
        ),
    ] + [
        issue(
            f"Unknown {index:02}",
            "unknown",
            "inconclusive",
            f"unsupported:{index:02}",
            {},
        )
        for index in range(17)
    ]

    def extract(issues: list[TargetedIssue]) -> FindingPayload:
        host = HostInfo(
            ip=unit.ip,
            hostname="ftp",
            ports=[PortInfo(port=21, service=ServiceInfo(name="ftp"))],
            targeted_results=[
                TargetedUnitResult(unit, TargetedOutcome.COMPLETED, issues=[item])
                for item in issues
            ],
        )
        return extract_findings([host], include_evidence_metadata=True)[0]

    forward = extract(candidates)
    reverse = extract(list(reversed(candidates)))
    assert (
        forward.title,
        forward.description,
        forward.recommendation,
        forward.evidence,
        forward.source,
    ) == (
        reverse.title,
        reverse.description,
        reverse.recommendation,
        reverse.evidence,
        reverse.source,
    )
    assert [item.model_dump_json() for item in forward.evidence_observations] == [
        item.model_dump_json() for item in reverse.evidence_observations
    ]
    assert forward.evidence_truncated is True
    assert len(forward.evidence_observations) == 16
    assert {
        item.result
        for item in forward.evidence_observations
        if item.rule_id == "targeted:ftp-check-anonymous"
    } == {"positive", "negative"}
    assert (
        assess_local_evidence(forward).status,
        assess_local_evidence(forward).confidence,
    ) == ("conflicting", "tentative")


def test_valid_nse_content_wins_over_targeted_unknown_in_any_host_order() -> None:
    nse = _ftp_anon_host("Anonymous FTP login allowed (FTP code 230)")
    unit = TargetedUnit("192.168.1.13", 21, "tcp", "ftp", TargetedTool.FTP_CHECK)
    targeted = HostInfo(
        ip=unit.ip,
        hostname="ftp",
        ports=[PortInfo(port=21, service=ServiceInfo(name="ftp"))],
        targeted_results=[
            TargetedUnitResult(
                unit,
                TargetedOutcome.COMPLETED,
                issues=[
                    TargetedIssue(
                        "ftp:anonymous-login",
                        "Unclassified FTP result",
                        "Unclassified detail",
                        "critical",
                        "Unclassified remediation",
                        "Unclassified evidence",
                    )
                ],
            )
        ],
    )
    first = extract_findings([nse, targeted], include_evidence_metadata=True)[0]
    second = extract_findings([targeted, nse], include_evidence_metadata=True)[0]
    for field in (
        "source",
        "source_script",
        "title",
        "description",
        "recommendation",
        "evidence",
    ):
        assert getattr(first, field) == getattr(second, field)
    assert first.source == "nmap_nse"
    assert assess_local_evidence(first).confidence == "confirmed"


def test_full_finding_payload_tie_break_is_order_independent() -> None:
    base = FindingPayload(
        ip="192.0.2.46",
        port=443,
        protocol="tcp",
        service="https",
        issue_key="tls:shared-identity",
        severity="medium",
        title="Shared finding identity",
        description="Candidate description.",
        recommendation="Candidate recommendation.",
        evidence="Candidate evidence.",
    )
    lower_score = base.model_copy(update={"cvss_score": 4.0, "service": "z-service"})
    higher_score = base.model_copy(update={"cvss_score": 8.0, "service": "a-service"})
    forward = _merge_finding_group([lower_score, higher_score])
    reverse = _merge_finding_group([higher_score, lower_score])
    assert forward.model_dump(mode="json") == reverse.model_dump(mode="json")
    # Canonical serialized payload is the lexical tie-break after evidence and severity.
    assert (forward.cvss_score, forward.service) == (4.0, "z-service")

    service_a = base.model_copy(update={"cvss_score": 4.0, "service": "a-service"})
    service_z = base.model_copy(update={"cvss_score": 4.0, "service": "z-service"})
    service_forward = _merge_finding_group([service_z, service_a])
    service_reverse = _merge_finding_group([service_a, service_z])
    assert service_forward.model_dump(mode="json") == service_reverse.model_dump(
        mode="json"
    )
    assert service_forward.service == "a-service"


def test_targeted_issue_key_is_used_for_cross_source_identity() -> None:
    host = HostInfo(
        ip="192.168.10.44",
        hostname="ftp-host",
        ports=[
            PortInfo(
                port=21,
                service=ServiceInfo(name="ftp"),
                scripts=[
                    ScriptResult(
                        script_id="ftp-anon",
                        output="Anonymous FTP login allowed (FTP code 230)",
                    )
                ],
            )
        ],
        targeted_results=[
            TargetedUnitResult(
                TargetedUnit("192.168.10.44", 21, "tcp", "ftp", TargetedTool.FTP_CHECK),
                TargetedOutcome.COMPLETED,
                issues=[
                    TargetedIssue(
                        issue_key="ftp:anonymous-login",
                        title="Tool-specific title that must not affect identity",
                        description="Targeted probe confirmed anonymous login.",
                        severity="high",
                        recommendation="Disable anonymous access.",
                        evidence="anonymous login accepted",
                    )
                ],
            )
        ],
    )

    assert len(extract_findings([host])) == 1


def test_local_evidence_merge_is_deterministic_and_marks_truncation() -> None:
    unit = TargetedUnit("192.0.2.90", 443, "tcp", "https", TargetedTool.FFUF)

    def host_with_order(order: list[int]) -> HostInfo:
        return HostInfo(
            ip=unit.ip,
            hostname="web",
            ports=[PortInfo(port=443, service=ServiceInfo(name="https"))],
            targeted_results=[
                TargetedUnitResult(
                    unit,
                    TargetedOutcome.COMPLETED,
                    issues=[
                        TargetedIssue(
                            "web:test",
                            "Policy test candidate",
                            "A policy candidate needs review.",
                            "low",
                            "Review the response.",
                            f"candidate response {index}",
                        )
                    ],
                )
                for index in order
            ],
        )

    forward = extract_findings(
        [host_with_order(list(range(17)))], include_evidence_metadata=True
    )[0]
    reverse = extract_findings(
        [host_with_order(list(reversed(range(17))))],
        include_evidence_metadata=True,
    )[0]

    assert len(forward.evidence_observations) == 16
    assert forward.evidence_truncated is True
    assert [item.model_dump_json() for item in forward.evidence_observations] == [
        item.model_dump_json() for item in reverse.evidence_observations
    ]
    assert (forward.title, forward.description, forward.evidence) == (
        reverse.title,
        reverse.description,
        reverse.evidence,
    )
    assessment = assess_local_evidence(forward)
    assert (assessment.status, assessment.confidence) == ("inconclusive", "tentative")
