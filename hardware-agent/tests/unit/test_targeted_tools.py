from __future__ import annotations

from agent.config import AgentSettings
from agent.scanner.models import HostInfo, PortInfo, ServiceInfo
from agent.tools.runner import ToolRunResult, ToolRunStatus
from agent.tools.targeted import (
    parse_enum4linux_output,
    parse_testssl_output,
    run_targeted_security_tools,
    select_smb_targets,
    select_tls_targets,
)


class _TargetedFakeRunner:
    def run(self, executable: str, arguments: list[str]) -> ToolRunResult:
        if executable == "testssl.sh":
            return ToolRunResult(
                tool=executable,
                argv=[executable, *arguments],
                status=ToolRunStatus.COMPLETED,
                exit_code=0,
                stdout="""
                Testing protocols via sockets
                TLS 1.0 offered
                Signature algorithm: SHA1withRSA
                Server key size: 1024 bit
                Grade capped to C
                """,
            )
        if executable == "enum4linux-ng":
            return ToolRunResult(
                tool=executable,
                argv=[executable, *arguments],
                status=ToolRunStatus.COMPLETED,
                exit_code=0,
                stdout="""
                [+] Server allows authentication via username '' and password ''
                Minimum password length: 6
                """,
            )
        raise AssertionError(f"Unexpected tool: {executable}")


class _MissingToolRunner:
    def run(self, executable: str, arguments: list[str]) -> ToolRunResult:
        return ToolRunResult(
            tool=executable,
            argv=[executable, *arguments],
            status=ToolRunStatus.SKIPPED,
            error=f"{executable} not found in PATH.",
        )


def test_select_tls_targets_uses_known_tls_ports_and_service_names() -> None:
    host = HostInfo(
        ip="192.168.1.70",
        hostname="tls.local",
        ports=[
            PortInfo(port=443, service=ServiceInfo(name="https")),
            PortInfo(port=993, service=ServiceInfo(name="imap")),
            PortInfo(port=7443, service=ServiceInfo(name="ssl/http")),
            PortInfo(port=8443, state="filtered", service=ServiceInfo(name="https")),
            PortInfo(port=80, service=ServiceInfo(name="http")),
        ],
    )

    targets = select_tls_targets([host])

    assert [target.port.port for target in targets] == [443, 993, 7443]


def test_select_smb_targets_uses_open_smb_ports_only() -> None:
    host = HostInfo(
        ip="192.168.1.71",
        hostname="smb.local",
        ports=[
            PortInfo(port=139, service=ServiceInfo(name="netbios-ssn")),
            PortInfo(port=445, service=ServiceInfo(name="microsoft-ds")),
            PortInfo(
                port=445,
                state="filtered",
                service=ServiceInfo(name="microsoft-ds"),
            ),
            PortInfo(port=8445, service=ServiceInfo(name="smb-alt")),
        ],
    )

    targets = select_smb_targets([host])

    assert [target.port.port for target in targets] == [139, 445, 8445]


def test_parse_testssl_output_extracts_conservative_tls_findings() -> None:
    host = HostInfo(
        ip="192.168.1.72",
        hostname="tls.local",
        ports=[PortInfo(port=443, service=ServiceInfo(name="https"))],
    )
    target = select_tls_targets([host])[0]

    issues = parse_testssl_output(
        target,
        """
        TLS 1.0 offered
        Server key size: 1024 bit
        Grade capped to C
        Heartbleed vulnerable
        """,
    )

    assert [issue.title for issue in issues] == [
        "Deprecated TLS/SSL protocol offered: TLSv1.0",
        "Weak TLS public key",
        "Weak TLS cipher strength (grade C)",
        "Heartbleed vulnerability exposed",
    ]


def test_parse_enum4linux_output_extracts_anonymous_and_policy_findings() -> None:
    host = HostInfo(
        ip="192.168.1.73",
        hostname="smb.local",
        ports=[PortInfo(port=445, service=ServiceInfo(name="microsoft-ds"))],
    )
    target = select_smb_targets([host])[0]

    issues = parse_enum4linux_output(
        target,
        """
        [+] Server allows authentication via username '' and password ''
        Password complexity: false
        Minimum password length: 5
        """,
    )

    assert [issue.title for issue in issues] == [
        "Anonymous SMB session allowed",
        "Weak SMB password policy",
        "Weak SMB password policy",
    ]


def test_run_targeted_security_tools_attaches_testssl_and_enum4linux_scripts() -> None:
    host = HostInfo(
        ip="192.168.1.74",
        hostname="mixed.local",
        ports=[
            PortInfo(port=443, service=ServiceInfo(name="https")),
            PortInfo(port=445, service=ServiceInfo(name="microsoft-ds")),
        ],
    )
    settings = AgentSettings(
        scan_mode="extensive",
        web_directory_enum_enabled=False,
        nikto_enabled=False,
    )

    summary = run_targeted_security_tools(
        [host],
        settings,
        tool_runner=_TargetedFakeRunner(),
    )

    assert summary.web_targets_discovered == 1
    assert summary.tls_targets_discovered == 1
    assert summary.smb_targets_discovered == 1
    assert summary.tools_attempted == 2
    assert summary.finding_candidates == 6
    assert [script.script_id for script in host.ports[0].scripts] == ["testssl"]
    assert [script.script_id for script in host.ports[1].scripts] == ["enum4linux-ng"]


def test_run_targeted_security_tools_skips_missing_binaries_non_fatally() -> None:
    host = HostInfo(
        ip="192.168.1.75",
        hostname="mixed.local",
        ports=[
            PortInfo(port=443, service=ServiceInfo(name="https")),
            PortInfo(port=445, service=ServiceInfo(name="microsoft-ds")),
        ],
    )

    summary = run_targeted_security_tools(
        [host],
        AgentSettings(
            scan_mode="extensive",
            web_directory_enum_enabled=False,
            nikto_enabled=False,
        ),
        tool_runner=_MissingToolRunner(),
    )

    assert summary.tools_attempted == 0
    assert summary.tools_skipped == 2
    assert summary.finding_candidates == 0
    assert host.ports[0].scripts == []
    assert host.ports[1].scripts == []
