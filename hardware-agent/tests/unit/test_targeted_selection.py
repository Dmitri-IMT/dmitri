from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from dataclasses import asdict, fields
from itertools import permutations

import pytest
from agent.config import (
    TARGETED_COVERAGE_LIMIT_CHARS,
    TARGETED_DIAGNOSTIC_LIMIT_CHARS,
    TARGETED_EVIDENCE_LIMIT_CHARS,
    TARGETED_MAX_ISSUES_PER_UNIT,
    TARGETED_MAX_UNITS,
    TARGETED_MODES,
    TARGETED_REPORT_LIMIT_BYTES,
    TARGETED_STAGE_TIMEOUT_S,
    TARGETED_STDIO_LIMIT_BYTES,
    TARGETED_UNIT_TIMEOUT_S,
    TARGETED_WEB_MAX_VALIDATIONS_PER_UNIT,
    TARGETED_WORDLIST_MAX_BYTES,
    TARGETED_WORDLIST_MAX_ENTRIES,
)
from agent.discovery.port_discovery import merge_ports
from agent.scanner.models import HostInfo, PortInfo, ScriptResult, ServiceInfo
from agent.targeted.models import (
    TargetedGapReason,
    TargetedIssue,
    TargetedObservation,
    TargetedOutcome,
    TargetedStageSummary,
    TargetedTool,
    TargetedUnit,
    TargetedUnitResult,
)
from agent.targeted.selection import select_targeted_units
from agent.utils.nmap_xml import parse_ports


def _port(
    port: int,
    service: str = "",
    *,
    state: str = "open",
    protocol: str = "tcp",
    tunnel: str | None = None,
) -> PortInfo:
    return PortInfo(
        port=port,
        protocol=protocol,
        state=state,
        service=ServiceInfo(name=service, tunnel=tunnel),
    )


def _host(ip: str, *ports: PortInfo) -> HostInfo:
    return HostInfo(ip=ip, hostname="", ports=list(ports))


def _tools(host: HostInfo, mode: str = "extensive") -> list[TargetedTool]:
    return [
        unit.tool for unit in select_targeted_units([host], scan_mode=mode)
    ]


def test_mode_gate_has_no_quick_or_standard_plan() -> None:
    host = _host("192.168.1.1", _port(443))

    assert TARGETED_MODES == ("extensive", "max", "nspi")
    assert select_targeted_units([host], scan_mode="quick") == []
    assert select_targeted_units([host], scan_mode="standard") == []
    assert len(select_targeted_units([host], scan_mode="extensive")) == 3
    assert len(select_targeted_units([host], scan_mode="max")) == 3
    assert len(select_targeted_units([host], scan_mode="nspi")) == 3


@pytest.mark.parametrize(
    ("port", "service", "tunnel", "expected"),
    [
        (80, "", None, [TargetedTool.FFUF, TargetedTool.NIKTO]),
        (
            443,
            "",
            None,
            [TargetedTool.FFUF, TargetedTool.NIKTO, TargetedTool.TESTSSL],
        ),
        (8080, "http", None, [TargetedTool.FFUF, TargetedTool.NIKTO]),
        (3000, "http-alt", None, [TargetedTool.FFUF, TargetedTool.NIKTO]),
        (
            3000,
            "http",
            "ssl",
            [TargetedTool.FFUF, TargetedTool.NIKTO, TargetedTool.TESTSSL],
        ),
        (465, "", None, [TargetedTool.TESTSSL]),
        (2525, "smtps", None, [TargetedTool.TESTSSL]),
        (2222, "ssh", None, [TargetedTool.SSH_AUDIT]),
        (2121, "ftp", None, [TargetedTool.FTP_CHECK]),
        (2323, "telnet", None, [TargetedTool.TELNET_CHECK]),
    ],
)
def test_supported_port_and_service_selection(
    port: int,
    service: str,
    tunnel: str | None,
    expected: list[TargetedTool],
) -> None:
    assert _tools(_host("192.168.1.1", _port(port, service, tunnel=tunnel))) == expected


@pytest.mark.parametrize(
    ("port", "transport", "has_tls"),
    [
        (80, "http", False),
        (443, "https", True),
        (8080, "http", False),
        (8443, "https", True),
    ],
)
def test_every_web_known_port_fallback(
    port: int, transport: str, has_tls: bool
) -> None:
    units = select_targeted_units(
        [_host("192.168.1.1", _port(port))], scan_mode="extensive"
    )

    assert [(unit.tool, unit.transport) for unit in units] == [
        (TargetedTool.FFUF, transport),
        (TargetedTool.NIKTO, transport),
        *([(TargetedTool.TESTSSL, "tls")] if has_tls else []),
    ]


@pytest.mark.parametrize(
    "port",
    [443, 465, 636, 853, 989, 990, 993, 995, 5061, 5986, 8443, 9443],
)
def test_every_tls_known_port_fallback(port: int) -> None:
    tools = _tools(_host("192.168.1.1", _port(port)))

    assert TargetedTool.TESTSSL in tools


@pytest.mark.parametrize("service", ["http", "http-alt", "https", "ssl/http"])
def test_every_normalized_http_name_selects_both_web_tools(service: str) -> None:
    units = select_targeted_units(
        [_host("192.168.1.1", _port(32123, service))], scan_mode="extensive"
    )

    assert [unit.tool for unit in units[:2]] == [
        TargetedTool.FFUF,
        TargetedTool.NIKTO,
    ]
    assert all(unit.transport == "https" for unit in units[:2]) is (
        service in {"https", "ssl/http"}
    )


@pytest.mark.parametrize(
    "service", ["tls", "https", "imaps", "pop3s", "smtps", "ftps", "ldaps", "ssl/imap"]
)
def test_every_tls_service_fingerprint_selects_testssl(service: str) -> None:
    assert TargetedTool.TESTSSL in _tools(
        _host("192.168.1.1", _port(32123, service))
    )


@pytest.mark.parametrize("service", ["netbios-ssn", "microsoft-ds", "smb", "samba"])
def test_every_smb_service_fingerprint_selects_enum4linux(service: str) -> None:
    assert _tools(_host("192.168.1.1", _port(32123, service))) == [
        TargetedTool.ENUM4LINUX
    ]


@pytest.mark.parametrize("service", ["", "unknown", "tcpwrapped", " TCPWRAPPED "])
@pytest.mark.parametrize(
    ("port", "expected"),
    [
        (22, [TargetedTool.SSH_AUDIT]),
        (21, [TargetedTool.FTP_CHECK]),
        (23, [TargetedTool.TELNET_CHECK]),
        (139, [TargetedTool.ENUM4LINUX]),
        (445, [TargetedTool.ENUM4LINUX]),
    ],
)
def test_blank_and_inconclusive_names_use_known_port_fallback(
    service: str, port: int, expected: list[TargetedTool]
) -> None:
    assert _tools(_host("192.168.1.1", _port(port, service))) == expected


@pytest.mark.parametrize(
    ("port", "service", "expected"),
    [
        (443, "ssh", [TargetedTool.SSH_AUDIT]),
        (445, "https", [TargetedTool.FFUF, TargetedTool.NIKTO, TargetedTool.TESTSSL]),
        (22, "telnet", [TargetedTool.TELNET_CHECK]),
        (21, "http", [TargetedTool.FFUF, TargetedTool.NIKTO]),
        (23, "ftp", [TargetedTool.FTP_CHECK]),
    ],
)
def test_positive_service_wins_for_each_conflicting_fallback_family(
    port: int, service: str, expected: list[TargetedTool]
) -> None:
    assert _tools(_host("192.168.1.1", _port(port, service))) == expected


def test_positive_service_overrides_conflicting_known_port() -> None:
    units = select_targeted_units(
        [_host("192.168.1.1", _port(8080, "ssh"))],
        scan_mode="extensive",
    )

    assert [(unit.tool, unit.transport) for unit in units] == [
        (TargetedTool.SSH_AUDIT, None)
    ]


def test_cleartext_and_secure_selectors_are_mutually_exclusive() -> None:
    host = _host(
        "192.168.1.1",
        _port(21, "ftps"),
        _port(23, "telnet", tunnel="ssl"),
    )

    units = select_targeted_units([host], scan_mode="extensive")

    assert [(unit.port, unit.tool) for unit in units] == [
        (21, TargetedTool.TESTSSL),
        (23, TargetedTool.TESTSSL),
    ]


@pytest.mark.parametrize("service", ["ftps", "ssl/ftp"])
def test_secure_ftp_names_never_select_cleartext_ftp(service: str) -> None:
    units = select_targeted_units(
        [_host("192.168.1.1", _port(2121, service))], scan_mode="extensive"
    )

    assert [(unit.tool, unit.transport) for unit in units] == [
        (TargetedTool.TESTSSL, "tls")
    ]


def test_tls_tunnel_on_non_web_service_selects_only_tls() -> None:
    units = select_targeted_units(
        [_host("192.168.1.1", _port(32123, "smtp", tunnel="ssl"))],
        scan_mode="extensive",
    )

    assert [(unit.tool, unit.transport) for unit in units] == [
        (TargetedTool.TESTSSL, "tls")
    ]


def test_explicit_cleartext_http_on_tls_fallback_port_stays_http() -> None:
    units = select_targeted_units(
        [_host("192.168.1.1", _port(443, "http"))],
        scan_mode="extensive",
    )

    assert [(unit.tool, unit.transport) for unit in units] == [
        (TargetedTool.FFUF, "http"),
        (TargetedTool.NIKTO, "http"),
    ]


def test_smb_collapses_to_445_then_139_once_per_host() -> None:
    units = select_targeted_units(
        [_host("192.168.1.1", _port(139, "netbios-ssn"), _port(445, "smb"))],
        scan_mode="extensive",
    )

    assert [(unit.port, unit.tool) for unit in units] == [
        (445, TargetedTool.ENUM4LINUX)
    ]


def test_smb_uses_139_when_445_is_not_an_smb_endpoint() -> None:
    units = select_targeted_units(
        [_host("192.168.1.1", _port(139, "smb"), _port(445, "ssh"))],
        scan_mode="extensive",
    )

    assert [(unit.port, unit.tool) for unit in units] == [
        (139, TargetedTool.ENUM4LINUX),
        (445, TargetedTool.SSH_AUDIT),
    ]


def test_smb_uses_lowest_service_identified_nonstandard_port() -> None:
    units = select_targeted_units(
        [
            _host(
                "192.168.1.1",
                _port(139, "ssh"),
                _port(445, "https"),
                _port(2445, "samba"),
                _port(1445, "microsoft-ds"),
            )
        ],
        scan_mode="extensive",
    )

    assert [
        (unit.port, unit.tool)
        for unit in units
        if unit.tool is TargetedTool.ENUM4LINUX
    ] == [(1445, TargetedTool.ENUM4LINUX)]


def test_closed_udp_and_unrelated_endpoints_are_excluded() -> None:
    host = _host(
        "192.168.1.1",
        _port(22, state="filtered"),
        _port(80, protocol="udp"),
        _port(9999, "echo"),
    )

    assert select_targeted_units([host], scan_mode="extensive") == []


def test_plan_is_numeric_ip_port_tool_ordered_and_deduplicated() -> None:
    duplicate = _host("192.168.1.2", _port(443))
    hosts = [
        duplicate,
        _host("192.168.1.10", _port(22, "ssh")),
        _host("192.168.1.2", _port(80, "http")),
        duplicate,
    ]

    units = select_targeted_units(hosts, scan_mode="extensive")

    assert [unit.identity for unit in units] == [
        ("192.168.1.2", 80, "tcp", TargetedTool.FFUF),
        ("192.168.1.2", 80, "tcp", TargetedTool.NIKTO),
        ("192.168.1.2", 443, "tcp", TargetedTool.FFUF),
        ("192.168.1.2", 443, "tcp", TargetedTool.NIKTO),
        ("192.168.1.2", 443, "tcp", TargetedTool.TESTSSL),
        ("192.168.1.10", 22, "tcp", TargetedTool.SSH_AUDIT),
    ]


def test_plan_is_capped_at_96_units() -> None:
    hosts = [
        _host(f"10.0.0.{index}", _port(80, "http"))
        for index in range(1, 60)
    ]

    summary = TargetedStageSummary()
    units = select_targeted_units(
        hosts,
        scan_mode="extensive",
        summary=summary,
    )

    assert len(units) == TARGETED_MAX_UNITS
    assert units[-1].identity == (
        "10.0.0.48",
        80,
        "tcp",
        TargetedTool.NIKTO,
    )
    assert summary.eligible == 118
    assert summary.planned == 96
    assert summary.omitted == 22
    assert summary.skipped == 22
    assert summary.per_tool[TargetedTool.FFUF][TargetedOutcome.SKIPPED] == 11
    assert summary.per_tool[TargetedTool.NIKTO][TargetedOutcome.SKIPPED] == 11
    assert summary.plan_limit_by_tool[TargetedTool.FFUF] == 11
    assert summary.plan_limit_by_tool[TargetedTool.NIKTO] == 11


def test_single_host_plan_is_capped_and_omissions_are_counted_by_tool() -> None:
    host = _host(
        "10.0.0.1",
        *[_port(port, "http") for port in range(10_000, 10_049)],
    )
    summary = TargetedStageSummary()

    units = select_targeted_units([host], scan_mode="max", summary=summary)

    assert len(units) == 96
    assert units[-1].identity == (
        "10.0.0.1",
        10_047,
        "tcp",
        TargetedTool.NIKTO,
    )
    assert (summary.eligible, summary.planned, summary.omitted, summary.skipped) == (
        98,
        96,
        2,
        2,
    )
    assert summary.per_tool[TargetedTool.FFUF][TargetedOutcome.SKIPPED] == 1
    assert summary.per_tool[TargetedTool.NIKTO][TargetedOutcome.SKIPPED] == 1
    assert summary.plan_limit_by_tool[TargetedTool.FFUF] == 1
    assert summary.plan_limit_by_tool[TargetedTool.NIKTO] == 1


def test_duplicate_units_do_not_consume_plan_or_omission_counts() -> None:
    host = _host("10.0.0.1", _port(80, "http"))
    summary = TargetedStageSummary()

    units = select_targeted_units([host, host, host], scan_mode="nspi", summary=summary)

    assert len(units) == 2
    assert (summary.eligible, summary.planned, summary.omitted) == (2, 2, 0)


def test_duplicate_ports_inside_one_host_create_each_unit_once() -> None:
    host = _host(
        "10.0.0.1",
        _port(443, ""),
        _port(443, "https", tunnel="ssl"),
        _port(443, "https", tunnel="ssl"),
    )

    units = select_targeted_units([host], scan_mode="extensive")

    assert [unit.identity for unit in units] == [
        ("10.0.0.1", 443, "tcp", TargetedTool.FFUF),
        ("10.0.0.1", 443, "tcp", TargetedTool.NIKTO),
        ("10.0.0.1", 443, "tcp", TargetedTool.TESTSSL),
    ]
    assert {(unit.service, unit.transport) for unit in units} == {
        ("https", "https"),
        ("https", "tls"),
    }


def test_reversed_duplicate_hosts_keep_identical_canonical_units() -> None:
    blank = _host("10.0.0.1", _port(443, ""))
    identified = _host("10.0.0.1", _port(443, "https", tunnel="ssl"))

    forward = select_targeted_units([blank, identified], scan_mode="extensive")
    reverse = select_targeted_units([identified, blank], scan_mode="extensive")

    assert forward == reverse
    assert [(unit.service, unit.transport) for unit in forward] == [
        ("https", "https"),
        ("https", "https"),
        ("https", "tls"),
    ]


def test_duplicate_evidence_does_not_change_cap_counts() -> None:
    unique_hosts = [
        _host(f"10.0.0.{index}", _port(80, "http"))
        for index in range(1, 60)
    ]
    duplicated_hosts = [
        host
        for original in unique_hosts
        for host in (original, _host(original.ip, _port(80, "http")))
    ]
    unique_summary = TargetedStageSummary()
    duplicate_summary = TargetedStageSummary()

    unique_units = select_targeted_units(
        unique_hosts, scan_mode="extensive", summary=unique_summary
    )
    duplicate_units = select_targeted_units(
        reversed(duplicated_hosts),
        scan_mode="extensive",
        summary=duplicate_summary,
    )

    assert duplicate_units == unique_units
    assert duplicate_summary.eligible == unique_summary.eligible == 118
    assert duplicate_summary.planned == unique_summary.planned == 96
    assert duplicate_summary.omitted == unique_summary.omitted == 22
    assert duplicate_summary.skipped == unique_summary.skipped == 22
    assert duplicate_summary.plan_limit_by_tool == unique_summary.plan_limit_by_tool


def _serialized_plan_and_summary(hosts: list[HostInfo]) -> str:
    summary = TargetedStageSummary()
    units = select_targeted_units(hosts, scan_mode="extensive", summary=summary)
    return json.dumps(
        {"units": [asdict(unit) for unit in units], "summary": asdict(summary)},
        sort_keys=True,
        separators=(",", ":"),
    )


def test_duplicate_host_and_port_permutations_are_byte_identical() -> None:
    evidence = [
        _host(
            "10.0.0.2",
            _port(443, ""),
            _port(445, ""),
            _port(139, "netbios-ssn"),
        ),
        _host(
            "10.0.0.2",
            _port(445, "microsoft-ds"),
            _port(443, "https", tunnel="ssl"),
        ),
        _host("10.0.0.1", _port(21, "ftps"), _port(22, "ssh")),
        _host("10.0.0.1", _port(21, "", tunnel="ssl"), _port(22, "")),
    ]

    serialized = {
        _serialized_plan_and_summary(list(order)) for order in permutations(evidence)
    }

    assert len(serialized) == 1
    payload = json.loads(serialized.pop())
    identities = [
        (unit["ip"], unit["port"], unit["protocol"], unit["tool"])
        for unit in payload["units"]
    ]
    assert len(identities) == len(set(identities))
    assert [
        (unit["port"], unit["service"], unit["tool"], unit["transport"])
        for unit in payload["units"]
        if unit["port"] in {21, 443, 445}
    ] == [
        (21, "ftps", "testssl.sh", "tls"),
        (443, "https", "ffuf", "https"),
        (443, "https", "nikto", "https"),
        (443, "https", "testssl.sh", "tls"),
        (445, "microsoft-ds", "enum4linux-ng", None),
    ]


def test_duplicate_evidence_near_cap_has_unique_accounting() -> None:
    canonical = _host(
        "10.0.0.1",
        *[_port(port, "http") for port in range(10_000, 10_048)],
    )
    duplicate = _host(
        "10.0.0.1",
        *[
            duplicate_port
            for port in reversed(range(10_000, 10_048))
            for duplicate_port in (_port(port, ""), _port(port, "http"))
        ],
    )
    overflow = _host("10.0.0.2", _port(22, "ssh"))

    unique_summary = TargetedStageSummary()
    duplicate_summary = TargetedStageSummary()
    unique_units = select_targeted_units(
        [canonical, overflow], scan_mode="extensive", summary=unique_summary
    )
    duplicate_units = select_targeted_units(
        [overflow, duplicate, canonical],
        scan_mode="extensive",
        summary=duplicate_summary,
    )

    assert duplicate_units == unique_units
    assert len({unit.identity for unit in duplicate_units}) == TARGETED_MAX_UNITS
    assert asdict(duplicate_summary) == asdict(unique_summary)
    assert (
        duplicate_summary.eligible,
        duplicate_summary.planned,
        duplicate_summary.omitted,
        duplicate_summary.skipped,
    ) == (97, 96, 1, 1)
    assert duplicate_summary.plan_limit_by_tool[TargetedTool.SSH_AUDIT] == 1


def test_large_single_pass_input_does_not_retain_host_records() -> None:
    class Lifetime:
        alive = 0
        peak = 0

        def __init__(self) -> None:
            type(self).alive += 1
            type(self).peak = max(type(self).peak, type(self).alive)

        def __del__(self) -> None:
            type(self).alive -= 1

    class SinglePassHosts:
        consumed = False

        def __iter__(self):
            if self.consumed:
                raise AssertionError("host evidence was consumed more than once")
            self.consumed = True
            for index in range(1, 501):
                host = _host(f"10.1.{index // 255}.{index % 255}", _port(22, "ssh"))
                host.hostname = Lifetime()  # type: ignore[assignment]
                yield host

    summary = TargetedStageSummary()
    units = select_targeted_units(
        SinglePassHosts(), scan_mode="extensive", summary=summary
    )

    assert len(units) == TARGETED_MAX_UNITS
    assert (summary.eligible, summary.planned, summary.omitted) == (500, 96, 404)
    assert Lifetime.peak <= 2


def test_nmap_tunnel_is_parsed_and_preserved_by_merge() -> None:
    root = ET.fromstring(
        """
        <host><ports><port protocol="tcp" portid="9443">
          <state state="open"/><service name="http" tunnel="ssl"/>
        </port></ports></host>
        """
    )
    parsed = parse_ports(root)
    merged = merge_ports([_port(9443)], parsed)

    assert parsed[0].service.tunnel == "ssl"
    assert merged[0].service.tunnel == "ssl"
    assert [
        unit.tool
        for unit in select_targeted_units(
            [_host("192.168.1.1", *merged)], scan_mode="extensive"
        )
    ] == [TargetedTool.FFUF, TargetedTool.NIKTO, TargetedTool.TESTSSL]


def test_later_service_merge_does_not_drop_known_tunnel() -> None:
    merged = merge_ports(
        [_port(9443, "http", tunnel="ssl")],
        [_port(9443, "http", tunnel=None)],
    )

    assert merged[0].service.tunnel == "ssl"


def test_later_service_merge_uses_final_positive_tunnel_value() -> None:
    merged = merge_ports(
        [_port(9443, "http", tunnel="tls")],
        [_port(9443, "http", tunnel="ssl")],
    )

    assert merged[0].service.tunnel == "ssl"


@pytest.mark.parametrize(("raw", "expected"), [(" ssl ", "ssl"), ("", None)])
def test_nmap_tunnel_normalization(raw: str, expected: str | None) -> None:
    root = ET.fromstring(
        f"""
        <host><ports><port protocol="tcp" portid="9443">
          <state state="open"/><service name="http" tunnel="{raw}"/>
        </port></ports></host>
        """
    )

    assert parse_ports(root)[0].service.tunnel == expected


def test_target_models_have_stable_values_and_serialization() -> None:
    unit = TargetedUnit(
        ip="192.0.2.1",
        port=443,
        protocol="tcp",
        service="https",
        tool=TargetedTool.TESTSSL,
        transport="tls",
    )
    result = TargetedUnitResult(
        unit=unit,
        outcome=TargetedOutcome.FAILED,
        issues=[
            TargetedIssue(
                issue_key="tls:weak",
                title="Weak TLS",
                description="Supported evidence",
                severity="high",
                recommendation="Disable it",
                evidence="protocol offered",
            )
        ],
        observations=[
            TargetedObservation(
                observation_key="identity",
                kind="service_identity",
                summary="Service identified",
                evidence="structured field",
            )
        ],
        reason_code=TargetedGapReason.MALFORMED_REPORT,
    )

    assert json.loads(json.dumps(asdict(result))) == {
        "unit": {
            "ip": "192.0.2.1",
            "port": 443,
            "protocol": "tcp",
            "service": "https",
            "tool": "testssl.sh",
            "transport": "tls",
        },
        "outcome": "failed",
        "issues": [
            {
                "issue_key": "tls:weak",
                "title": "Weak TLS",
                "description": "Supported evidence",
                "severity": "high",
                "recommendation": "Disable it",
                "evidence": "protocol offered",
                "cve_id": None,
                "cvss_score": None,
                "references": [],
            }
        ],
        "observations": [
            {
                "observation_key": "identity",
                "kind": "service_identity",
                "summary": "Service identified",
                "evidence": "structured field",
            }
        ],
        "exit_code": None,
        "reason_code": "malformed_report",
        "diagnostic": None,
    }
    assert unit.identity == ("192.0.2.1", 443, "tcp", TargetedTool.TESTSSL)
    assert [member.value for member in TargetedTool] == [
        "ffuf",
        "nikto",
        "testssl.sh",
        "enum4linux-ng",
        "ssh-audit",
        "ftp-check",
        "telnet-check",
    ]
    assert [member.value for member in TargetedOutcome] == [
        "completed",
        "failed",
        "timed_out",
        "skipped",
    ]
    assert [member.value for member in TargetedGapReason] == [
        "tool_unavailable",
        "dependency_unavailable",
        "incompatible_tool",
        "wordlist_unavailable",
        "policy_unavailable",
        "plan_limit",
        "stage_budget",
        "output_limit",
        "issue_limit",
        "validation_limit",
        "baseline_unavailable",
        "malformed_report",
        "wrong_target",
        "spawn_error",
        "execution_error",
        "unit_timeout",
    ]
    assert "tunnel" not in {field.name for field in fields(ScriptResult)}


def test_all_targeted_resource_bounds_match_the_approved_spec() -> None:
    assert TARGETED_STAGE_TIMEOUT_S == {
        "extensive": 1800.0,
        "max": 3600.0,
        "nspi": 1800.0,
    }
    assert TARGETED_UNIT_TIMEOUT_S == {
        "ffuf": 480.0,
        "nikto": 180.0,
        "testssl.sh": 300.0,
        "enum4linux-ng": 180.0,
        "ssh-audit": 60.0,
        "ftp-check": 15.0,
        "telnet-check": 10.0,
    }
    assert TARGETED_MAX_UNITS == 96
    assert TARGETED_STDIO_LIMIT_BYTES == 131_072
    assert TARGETED_REPORT_LIMIT_BYTES == 2_097_152
    assert TARGETED_EVIDENCE_LIMIT_CHARS == 4_096
    assert TARGETED_DIAGNOSTIC_LIMIT_CHARS == 512
    assert TARGETED_MAX_ISSUES_PER_UNIT == 128
    assert TARGETED_WEB_MAX_VALIDATIONS_PER_UNIT == 32
    assert TARGETED_COVERAGE_LIMIT_CHARS == 2_048
    assert TARGETED_WORDLIST_MAX_BYTES == 1_048_576
    assert TARGETED_WORDLIST_MAX_ENTRIES == 10_000
