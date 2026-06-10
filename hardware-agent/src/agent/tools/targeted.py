"""Targeted service-specific tools driven by prior Nmap discovery."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol

from agent.scanner.models import HostInfo, PortInfo, ScriptResult
from agent.tools.runner import ExternalToolRunner, ToolRunResult, ToolRunStatus
from agent.tools.web import WebToolSummary, run_web_security_tools

if TYPE_CHECKING:
    from agent.config import AgentSettings

ANSI_ESCAPE_PATTERN = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
WEAK_TLS_KEY_PATTERN = re.compile(r"(?P<bits>\d{3,5})\s*bit", re.IGNORECASE)
TESTSSL_GRADE_PATTERN = re.compile(r"\bgrade\b.*\b(?P<grade>[A-F])\b", re.IGNORECASE)

TLS_PORTS = {
    443,
    465,
    636,
    853,
    989,
    990,
    992,
    993,
    995,
    1443,
    2376,
    3389,
    4433,
    5061,
    5986,
    6443,
    8443,
    9443,
}
TLS_SERVICE_MARKERS = (
    "https",
    "ssl",
    "tls",
    "imaps",
    "pop3s",
    "smtps",
    "ftps",
    "ldaps",
)
SMB_PORTS = {139, 445}
SMB_SERVICE_MARKERS = (
    "microsoft-ds",
    "netbios-ssn",
    "smb",
    "samba",
)
TESTSSL_VULNERABILITY_LABELS = {
    "heartbleed": "Heartbleed vulnerability exposed",
    "robot": "ROBOT vulnerability exposed",
    "poodle": "POODLE vulnerability exposed",
    "beast": "BEAST vulnerability exposure",
    "drown": "DROWN vulnerability exposed",
    "lucky13": "Lucky13 vulnerability exposure",
}


@dataclass(frozen=True, slots=True)
class TLSTarget:
    """TLS-capable endpoint inferred from Nmap results."""

    host: HostInfo
    port: PortInfo

    @property
    def endpoint(self) -> str:
        return f"{self.host.ip}:{self.port.port}"


@dataclass(frozen=True, slots=True)
class SMBTarget:
    """SMB endpoint inferred from Nmap results."""

    host: HostInfo
    port: PortInfo


@dataclass(frozen=True, slots=True)
class TestsslIssue:
    """Conservative TLS issue parsed from testssl.sh output."""

    target: TLSTarget
    title: str
    message: str
    severity: str
    evidence: str


@dataclass(frozen=True, slots=True)
class Enum4linuxIssue:
    """Conservative SMB issue parsed from enum4linux-ng output."""

    target: SMBTarget
    title: str
    message: str
    severity: str
    evidence: str


@dataclass(slots=True)
class TargetedToolSummary:
    """Counters for optional targeted tools driven by service detection."""

    targets_discovered: int = 0
    web_targets_discovered: int = 0
    tls_targets_discovered: int = 0
    smb_targets_discovered: int = 0
    web_tools_attempted: int = 0
    web_tools_skipped: int = 0
    web_tools_timed_out: int = 0
    tools_attempted: int = 0
    tools_skipped: int = 0
    tools_timed_out: int = 0
    finding_candidates: int = 0
    web_finding_candidates: int = 0
    tls_finding_candidates: int = 0
    smb_finding_candidates: int = 0

    def merge_web(self, summary: WebToolSummary) -> None:
        self.web_targets_discovered = summary.targets_discovered
        self.web_tools_attempted = summary.tools_attempted
        self.web_tools_skipped = summary.tools_skipped
        self.web_tools_timed_out = summary.tools_timed_out
        self.targets_discovered += summary.targets_discovered
        self.tools_attempted += summary.tools_attempted
        self.tools_skipped += summary.tools_skipped
        self.tools_timed_out += summary.tools_timed_out
        self.finding_candidates += summary.finding_candidates
        self.web_finding_candidates += summary.finding_candidates


class TargetedToolRunner(Protocol):
    """Minimal runner interface shared by targeted tool adapters."""

    def run(self, executable: str, arguments: list[str]) -> ToolRunResult:
        ...


def select_tls_targets(hosts: list[HostInfo]) -> list[TLSTarget]:
    """Return open ports that are explicitly TLS-wrapped services."""

    targets: list[TLSTarget] = []
    for host in hosts:
        for port in host.open_ports:
            if _is_tls_port(port):
                targets.append(TLSTarget(host=host, port=port))
    return targets


def select_smb_targets(hosts: list[HostInfo]) -> list[SMBTarget]:
    """Return open SMB endpoints from discovered port/service data."""

    targets: list[SMBTarget] = []
    for host in hosts:
        for port in host.open_ports:
            if _is_smb_port(port):
                targets.append(SMBTarget(host=host, port=port))
    return targets


def run_targeted_security_tools(
    hosts: list[HostInfo],
    settings: AgentSettings,
    *,
    tool_runner: TargetedToolRunner | None = None,
) -> TargetedToolSummary:
    """Run all enabled targeted tools against Nmap-derived targets."""

    summary = TargetedToolSummary()

    web_summary = run_web_security_tools(
        hosts,
        settings,
        tool_runner=tool_runner,
    )
    summary.merge_web(web_summary)

    tls_targets = select_tls_targets(hosts)
    summary.tls_targets_discovered = len(tls_targets)
    summary.targets_discovered += len(tls_targets)
    if tls_targets and _targeted_tools_enabled(settings) and settings.testssl_enabled:
        tls_runner = tool_runner or ExternalToolRunner(
            timeout_seconds=settings.testssl_timeout_seconds
        )
        executable = settings.testssl_path or "testssl.sh"
        for target in tls_targets:
            _run_testssl(target, executable, tls_runner, summary)

    smb_targets = select_smb_targets(hosts)
    summary.smb_targets_discovered = len(smb_targets)
    summary.targets_discovered += len(smb_targets)
    if (
        smb_targets
        and _targeted_tools_enabled(settings)
        and settings.enum4linux_enabled
    ):
        smb_runner = tool_runner or ExternalToolRunner(
            timeout_seconds=settings.enum4linux_timeout_seconds
        )
        executable = settings.enum4linux_path or "enum4linux-ng"
        for target in smb_targets:
            _run_enum4linux(
                target,
                executable,
                smb_runner,
                summary,
                rpc_timeout_seconds=settings.enum4linux_timeout_seconds,
            )

    return summary


def parse_testssl_output(target: TLSTarget, output: str) -> list[TestsslIssue]:
    """Extract conservative TLS issues from testssl.sh text output."""

    issues: list[TestsslIssue] = []
    seen: set[str] = set()
    for raw_line in _normalized_lines(output):
        lowered = raw_line.lower()
        if not lowered:
            continue

        if "self-signed" in lowered or "self signed" in lowered:
            if "not self-signed" not in lowered and "not self signed" not in lowered:
                _append_issue(
                    issues,
                    seen,
                    TestsslIssue(
                        target=target,
                        title="Self-signed TLS certificate",
                        message=(
                            f"testssl.sh reported a self-signed certificate on "
                            f"{target.endpoint}."
                        ),
                        severity="medium",
                        evidence=raw_line,
                    ),
                )

        if "certificate" in lowered and (
            "expired" in lowered or "not valid anymore" in lowered
        ):
            _append_issue(
                issues,
                seen,
                TestsslIssue(
                    target=target,
                    title="TLS certificate expired",
                    message=(
                        f"testssl.sh reported an expired certificate on "
                        f"{target.endpoint}."
                    ),
                    severity="high",
                    evidence=raw_line,
                ),
            )

        if (
            "signature algorithm" in lowered
            and ("sha1" in lowered or "md5" in lowered)
            and "not ok" not in lowered
        ):
            _append_issue(
                issues,
                seen,
                TestsslIssue(
                    target=target,
                    title="Weak TLS certificate signature",
                    message=(
                        f"testssl.sh reported a weak certificate signature "
                        f"algorithm on {target.endpoint}."
                    ),
                    severity="medium",
                    evidence=raw_line,
                ),
            )

        if "public key" in lowered or "server key size" in lowered:
            key_match = WEAK_TLS_KEY_PATTERN.search(lowered)
            if key_match is not None and int(key_match.group("bits")) < 2048:
                _append_issue(
                    issues,
                    seen,
                    TestsslIssue(
                        target=target,
                        title="Weak TLS public key",
                        message=(
                            f"testssl.sh reported a TLS public key smaller than "
                            f"2048 bits on {target.endpoint}."
                        ),
                        severity="medium",
                        evidence=raw_line,
                    ),
                )

        protocol = _deprecated_protocol_from_line(lowered)
        if protocol is not None:
            _append_issue(
                issues,
                seen,
                TestsslIssue(
                    target=target,
                    title=f"Deprecated TLS/SSL protocol offered: {protocol}",
                    message=(
                        f"testssl.sh reported support for deprecated protocol "
                        f"{protocol} on {target.endpoint}."
                    ),
                    severity="medium",
                    evidence=raw_line,
                ),
            )

        grade_match = TESTSSL_GRADE_PATTERN.search(raw_line)
        if grade_match is not None and grade_match.group("grade").upper() in {
            "C",
            "D",
            "E",
            "F",
        }:
            grade = grade_match.group("grade").upper()
            _append_issue(
                issues,
                seen,
                TestsslIssue(
                    target=target,
                    title=f"Weak TLS cipher strength (grade {grade})",
                    message=(
                        f"testssl.sh reported a weak overall TLS grade for "
                        f"{target.endpoint}."
                    ),
                    severity="medium",
                    evidence=raw_line,
                ),
            )

        if any(marker in lowered for marker in ("rc4", "3des", "des-cbc3")) and any(
            marker in lowered for marker in ("offered", "supported", "accepted", "available")
        ):
            _append_issue(
                issues,
                seen,
                TestsslIssue(
                    target=target,
                    title="Weak TLS cipher configuration",
                    message=(
                        f"testssl.sh reported weak cipher support on "
                        f"{target.endpoint}."
                    ),
                    severity="medium",
                    evidence=raw_line,
                ),
            )

        for marker, title in TESTSSL_VULNERABILITY_LABELS.items():
            if marker not in lowered:
                continue
            if any(
                safe_text in lowered
                for safe_text in ("not vulnerable", "no vulnerability", "not affected")
            ):
                continue
            if not any(
                risk_text in lowered
                for risk_text in ("vulnerable", "potentially vulnerable", "yes", "vulnerability")
            ):
                continue
            _append_issue(
                issues,
                seen,
                TestsslIssue(
                    target=target,
                    title=title,
                    message=(
                        f"testssl.sh reported {marker.upper()} exposure on "
                        f"{target.endpoint}."
                    ),
                    severity="high",
                    evidence=raw_line,
                ),
            )

    return issues


def parse_enum4linux_output(target: SMBTarget, output: str) -> list[Enum4linuxIssue]:
    """Extract conservative SMB issues from enum4linux-ng text output."""

    issues: list[Enum4linuxIssue] = []
    seen: set[str] = set()
    for raw_line in _normalized_lines(output):
        lowered = raw_line.lower()
        if not lowered:
            continue

        if "allows authentication via username '' and password ''" in lowered:
            _append_issue(
                issues,
                seen,
                Enum4linuxIssue(
                    target=target,
                    title="Anonymous SMB session allowed",
                    message=(
                        f"enum4linux-ng reported a successful null SMB session on "
                        f"{target.host.ip}."
                    ),
                    severity="high",
                    evidence=raw_line,
                ),
            )

        if "password complexity" in lowered and "false" in lowered:
            _append_issue(
                issues,
                seen,
                Enum4linuxIssue(
                    target=target,
                    title="Weak SMB password policy",
                    message=(
                        "enum4linux-ng reported that password complexity is not "
                        f"required on {target.host.ip}."
                    ),
                    severity="medium",
                    evidence=raw_line,
                ),
            )

        if "minimum password length" in lowered:
            minimum = _first_int(lowered)
            if minimum is not None and minimum < 8:
                _append_issue(
                    issues,
                    seen,
                    Enum4linuxIssue(
                        target=target,
                        title="Weak SMB password policy",
                        message=(
                            "enum4linux-ng reported a minimum SMB password length "
                            f"below 8 characters on {target.host.ip}."
                        ),
                        severity="medium",
                        evidence=raw_line,
                    ),
                )

        if "share:" in lowered and any(
            marker in lowered
            for marker in ("anonymous", "guest", "read access", "write access")
        ):
            _append_issue(
                issues,
                seen,
                Enum4linuxIssue(
                    target=target,
                    title="SMB share exposed to unauthenticated users",
                    message=(
                        "enum4linux-ng reported an SMB share that appears "
                        f"reachable without authentication on {target.host.ip}."
                    ),
                    severity="medium",
                    evidence=raw_line,
                ),
            )

    return issues


def _targeted_tools_enabled(settings: AgentSettings) -> bool:
    if settings.web_tools_enabled is not None:
        return settings.web_tools_enabled
    return settings.scan_mode in {"extensive", "max"}


def _run_testssl(
    target: TLSTarget,
    executable: str,
    runner: TargetedToolRunner,
    summary: TargetedToolSummary,
) -> None:
    result = runner.run(
        executable,
        [
            "--warnings",
            "batch",
            "--color",
            "0",
            target.endpoint,
        ],
    )
    _record_run(summary, result)
    if result.status != ToolRunStatus.COMPLETED:
        return

    issues = parse_testssl_output(target, result.stdout)
    if not issues:
        return
    summary.finding_candidates += len(issues)
    summary.tls_finding_candidates += len(issues)
    target.port.scripts.append(
        ScriptResult(
            script_id="testssl",
            output=f"{len(issues)} TLS issue(s) reported by testssl.sh.",
            data={"issues": [_testssl_issue_payload(issue) for issue in issues]},
        )
    )


def _run_enum4linux(
    target: SMBTarget,
    executable: str,
    runner: TargetedToolRunner,
    summary: TargetedToolSummary,
    *,
    rpc_timeout_seconds: int,
) -> None:
    result = runner.run(
        executable,
        [
            "-As",
            "-t",
            str(rpc_timeout_seconds),
            target.host.ip,
        ],
    )
    _record_run(summary, result)
    if result.status != ToolRunStatus.COMPLETED:
        return

    issues = parse_enum4linux_output(target, result.stdout)
    if not issues:
        return
    summary.finding_candidates += len(issues)
    summary.smb_finding_candidates += len(issues)
    target.port.scripts.append(
        ScriptResult(
            script_id="enum4linux-ng",
            output=f"{len(issues)} SMB issue(s) reported by enum4linux-ng.",
            data={"issues": [_enum4linux_issue_payload(issue) for issue in issues]},
        )
    )


def _record_run(summary: TargetedToolSummary, result: ToolRunResult) -> None:
    if result.status == ToolRunStatus.SKIPPED:
        summary.tools_skipped += 1
        return
    summary.tools_attempted += 1
    if result.status == ToolRunStatus.TIMED_OUT:
        summary.tools_timed_out += 1


def _testssl_issue_payload(issue: TestsslIssue) -> dict[str, str]:
    return {
        "title": issue.title,
        "message": issue.message,
        "severity": issue.severity,
        "evidence": issue.evidence,
    }


def _enum4linux_issue_payload(issue: Enum4linuxIssue) -> dict[str, str]:
    return {
        "title": issue.title,
        "message": issue.message,
        "severity": issue.severity,
        "evidence": issue.evidence,
    }


def _is_tls_port(port: PortInfo) -> bool:
    service_name = port.service.name.lower()
    if port.port in TLS_PORTS:
        return True
    return any(marker in service_name for marker in TLS_SERVICE_MARKERS)


def _is_smb_port(port: PortInfo) -> bool:
    service_name = port.service.name.lower()
    if port.port in SMB_PORTS:
        return True
    return any(marker in service_name for marker in SMB_SERVICE_MARKERS)


def _normalized_lines(output: str) -> list[str]:
    sanitized = ANSI_ESCAPE_PATTERN.sub("", output)
    return [line.strip() for line in sanitized.splitlines()]


def _deprecated_protocol_from_line(line: str) -> str | None:
    if not any(
        marker in line for marker in ("offered", "supported", "accepted", "available")
    ):
        return None
    if any(
        marker in line
        for marker in ("not offered", "not supported", "not available", "disabled")
    ):
        return None
    if "sslv3" in line:
        return "SSLv3"
    if "sslv2" in line:
        return "SSLv2"
    if "tls 1.1" in line or "tlsv1.1" in line:
        return "TLSv1.1"
    if "tls 1.0" in line or "tlsv1.0" in line or re.search(r"\btls 1\b", line):
        return "TLSv1.0"
    return None


def _first_int(text: str) -> int | None:
    match = re.search(r"\b(\d+)\b", text)
    if match is None:
        return None
    return int(match.group(1))


def _append_issue(issues: list[Any], seen: set[str], issue: Any) -> None:
    title = getattr(issue, "title")
    evidence = getattr(issue, "evidence")
    key = f"{title}|{evidence}"
    if key in seen:
        return
    seen.add(key)
    issues.append(issue)
