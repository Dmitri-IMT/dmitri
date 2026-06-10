"""Web target selection for Nmap-driven targeted tools."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import TYPE_CHECKING, Any, Protocol
from urllib.parse import urlparse

from agent.scanner.models import HostInfo, PortInfo, ScriptResult
from agent.tools.runner import ExternalToolRunner, ToolRunResult, ToolRunStatus

if TYPE_CHECKING:
    from agent.config import AgentSettings

WEB_PORT_SCHEMES = {
    80: "http",
    443: "https",
    8000: "http",
    8008: "http",
    8080: "http",
    8443: "https",
    9000: "http",
    9443: "https",
}

SENSITIVE_PATH_MARKERS = (
    "/.git",
    "/.env",
    "/.svn",
    "/admin",
    "/administrator",
    "/backup",
    "/backups",
    "/console",
    "/config",
    "/database",
    "/dashboard",
    "/db",
    "/debug",
    "/login",
    "/manager",
    "/phpinfo",
    "/server-status",
    "/swagger",
    "/wp-config",
    "/wp-admin",
)

SENSITIVE_FILE_SUFFIXES = (
    ".bak",
    ".backup",
    ".conf",
    ".config",
    ".db",
    ".dump",
    ".old",
    ".orig",
    ".sql",
    ".sqlite",
    ".tar",
    ".tar.gz",
    ".tgz",
    ".zip",
)

NIKTO_ADVISORY_PATTERN = re.compile(
    r"^(?:(?P<advisory>[A-Z]+-\d+|CVE-\d{4}-\d{4,}):\s*)?"
    r"(?P<path>/\S*)?:?\s*(?P<message>.+)$",
    re.IGNORECASE,
)

NIKTO_INFORMATION_PREFIXES = (
    "Target IP:",
    "Target Hostname:",
    "Target Port:",
    "Start Time:",
    "End Time:",
    "Server:",
    "No web server",
    "[FAIL]",
)


@dataclass(frozen=True, slots=True)
class WebTarget:
    """HTTP(S) target derived from existing Nmap host/port data."""

    host: HostInfo
    port: PortInfo
    scheme: str

    @property
    def url(self) -> str:
        return f"{self.scheme}://{self.host.ip}:{self.port.port}"


@dataclass(frozen=True, slots=True)
class WebDirectoryHit:
    """Directory/content enumeration hit with a risk classification."""

    target: WebTarget
    url: str
    path: str
    status: int
    dangerous: bool
    risk: str
    reason: str
    length: int | None = None


@dataclass(frozen=True, slots=True)
class NiktoIssue:
    """Security-relevant issue parsed from Nikto output."""

    target: WebTarget
    title: str
    message: str
    path: str | None = None
    advisory: str | None = None
    severity: str = "medium"


@dataclass(slots=True)
class WebToolSummary:
    """Counters from the optional web targeted tools stage."""

    targets_discovered: int = 0
    tools_attempted: int = 0
    tools_skipped: int = 0
    tools_timed_out: int = 0
    finding_candidates: int = 0


class WebToolRunner(Protocol):
    """Minimal runner interface used by web tool adapters."""

    def run(self, executable: str, arguments: list[str]) -> ToolRunResult:
        ...


def select_web_targets(hosts: list[HostInfo]) -> list[WebTarget]:
    """Return open HTTP(S) targets from already-discovered host data."""

    targets: list[WebTarget] = []
    for host in hosts:
        for port in host.open_ports:
            scheme = _web_scheme(port)
            if scheme is None:
                continue
            targets.append(WebTarget(host=host, port=port, scheme=scheme))
    return targets


def run_web_security_tools(
    hosts: list[HostInfo],
    settings: AgentSettings,
    *,
    tool_runner: WebToolRunner | None = None,
) -> WebToolSummary:
    """Run enabled web tools against Nmap-derived web targets."""

    targets = select_web_targets(hosts)
    summary = WebToolSummary(targets_discovered=len(targets))
    if not targets or not _web_tools_enabled(settings):
        return summary

    runner = tool_runner or ExternalToolRunner(
        timeout_seconds=settings.web_tool_timeout_seconds
    )
    wordlist_path = _resolve_wordlist(settings.web_wordlist_path)

    for target in targets:
        if settings.web_directory_enum_enabled:
            if wordlist_path is None:
                summary.tools_skipped += 1
            else:
                _run_ffuf(target, wordlist_path, runner, summary)
        if settings.nikto_enabled:
            _run_nikto(target, runner, summary)

    return summary


def parse_ffuf_results(target: WebTarget, raw_json: str) -> list[WebDirectoryHit]:
    """Parse ffuf JSON output into classified directory/content hits."""

    try:
        payload = json.loads(raw_json)
    except json.JSONDecodeError:
        return []

    results = payload.get("results")
    if not isinstance(results, list):
        return []

    hits: list[WebDirectoryHit] = []
    for result in results:
        if not isinstance(result, dict):
            continue
        hit = _parse_ffuf_hit(target, result)
        if hit is not None:
            hits.append(hit)
    return hits


def parse_nikto_output(target: WebTarget, output: str) -> list[NiktoIssue]:
    """Parse conservative Nikto findings from text output."""

    issues: list[NiktoIssue] = []
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line.startswith("+"):
            continue
        candidate = line[1:].strip()
        if not candidate or _is_nikto_information(candidate):
            continue
        issue = _parse_nikto_issue(target, candidate)
        if issue is not None:
            issues.append(issue)
    return issues


def _web_tools_enabled(settings: AgentSettings) -> bool:
    if settings.web_tools_enabled is not None:
        return settings.web_tools_enabled
    return settings.scan_mode in {"extensive", "max"}


def _resolve_wordlist(configured_path: str | None) -> Path | None:
    candidates = []
    if configured_path:
        candidates.append(Path(configured_path))
    candidates.extend(
        [
            Path("/usr/share/seclists/Discovery/Web-Content/common.txt"),
            Path("/usr/share/wordlists/dirb/common.txt"),
            Path("/usr/share/dirb/wordlists/common.txt"),
            Path("/usr/share/wordlists/dirbuster/directory-list-2.3-small.txt"),
        ]
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def _run_ffuf(
    target: WebTarget,
    wordlist_path: Path,
    runner: WebToolRunner,
    summary: WebToolSummary,
) -> None:
    target_url = f"{target.url.rstrip('/')}/FUZZ"
    output_path = _temporary_ffuf_output_path()
    try:
        result = runner.run(
            "ffuf",
            [
                "-u",
                target_url,
                "-w",
                str(wordlist_path),
                "-of",
                "json",
                "-o",
                str(output_path),
                "-ac",
                "-noninteractive",
                "-s",
            ],
        )
        _record_run(summary, result)
        if result.status != ToolRunStatus.COMPLETED:
            return

        hits = parse_ffuf_results(
            target,
            _read_ffuf_output(output_path=output_path, fallback_stdout=result.stdout),
        )
        if not hits:
            return
        summary.finding_candidates += len(hits)
        target.port.scripts.append(
            ScriptResult(
                script_id="ffuf",
                output=f"{len(hits)} web path(s) discovered and classified.",
                data={"hits": [_directory_hit_payload(hit) for hit in hits]},
            )
        )
    finally:
        output_path.unlink(missing_ok=True)


def _run_nikto(
    target: WebTarget,
    runner: WebToolRunner,
    summary: WebToolSummary,
) -> None:
    result = runner.run(
        "nikto",
        [
            "-h",
            target.url,
            "-nointeractive",
        ],
    )
    _record_run(summary, result)
    if result.status != ToolRunStatus.COMPLETED:
        return

    issues = parse_nikto_output(target, result.stdout)
    if not issues:
        return
    summary.finding_candidates += len(issues)
    target.port.scripts.append(
        ScriptResult(
            script_id="nikto",
            output=f"{len(issues)} Nikto issue(s) reported.",
            data={"issues": [_nikto_issue_payload(issue) for issue in issues]},
        )
    )


def _record_run(summary: WebToolSummary, result: ToolRunResult) -> None:
    if result.status == ToolRunStatus.SKIPPED:
        summary.tools_skipped += 1
        return
    summary.tools_attempted += 1
    if result.status == ToolRunStatus.TIMED_OUT:
        summary.tools_timed_out += 1


def _temporary_ffuf_output_path() -> Path:
    handle = NamedTemporaryFile(
        prefix="dmitri-ffuf-",
        suffix=".json",
        delete=False,
    )
    handle.close()
    return Path(handle.name)


def _read_ffuf_output(*, output_path: Path, fallback_stdout: str) -> str:
    try:
        file_output = output_path.read_text(encoding="utf-8")
    except OSError:
        file_output = ""
    return file_output or fallback_stdout


def _directory_hit_payload(hit: WebDirectoryHit) -> dict[str, str | int | bool]:
    payload: dict[str, str | int | bool] = {
        "url": hit.url,
        "path": hit.path,
        "status": hit.status,
        "dangerous": hit.dangerous,
        "risk": hit.risk,
        "reason": hit.reason,
    }
    if hit.length is not None:
        payload["length"] = hit.length
    return payload


def _nikto_issue_payload(issue: NiktoIssue) -> dict[str, str]:
    payload = {
        "title": issue.title,
        "message": issue.message,
        "severity": issue.severity,
    }
    if issue.path:
        payload["path"] = issue.path
    if issue.advisory:
        payload["advisory"] = issue.advisory
    return payload


def _web_scheme(port: PortInfo) -> str | None:
    service_name = port.service.name.lower()
    if port.port in WEB_PORT_SCHEMES:
        return WEB_PORT_SCHEMES[port.port]
    if "https" in service_name or service_name == "ssl/http":
        return "https"
    if "http" in service_name:
        return "http"
    return None


def _parse_ffuf_hit(
    target: WebTarget,
    result: dict[str, Any],
) -> WebDirectoryHit | None:
    raw_url = result.get("url")
    if not isinstance(raw_url, str) or not raw_url:
        return None

    parsed = urlparse(raw_url)
    path = parsed.path or "/"
    if parsed.query:
        path = f"{path}?{parsed.query}"
    status = _coerce_int(result.get("status"))
    if status is None:
        return None
    if status < 200 or status >= 500:
        return None

    classification = _classify_ffuf_path(path)

    return WebDirectoryHit(
        target=target,
        url=raw_url,
        path=path,
        status=status,
        dangerous=classification["dangerous"],
        risk=classification["risk"],
        reason=classification["reason"],
        length=_coerce_int(result.get("length")),
    )


def _classify_ffuf_path(path: str) -> dict[str, str | bool]:
    normalized = path.lower()
    if any(normalized.startswith(marker) for marker in SENSITIVE_PATH_MARKERS):
        return {
            "dangerous": True,
            "risk": "dangerous",
            "reason": "sensitive-path",
        }
    if any(normalized.endswith(suffix) for suffix in SENSITIVE_FILE_SUFFIXES):
        return {
            "dangerous": True,
            "risk": "dangerous",
            "reason": "sensitive-file-extension",
        }
    return {
        "dangerous": False,
        "risk": "informational",
        "reason": "common-web-path",
    }


def _coerce_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _is_nikto_information(candidate: str) -> bool:
    if any(candidate.startswith(prefix) for prefix in NIKTO_INFORMATION_PREFIXES):
        return True
    return "host(s) tested" in candidate.lower()


def _parse_nikto_issue(target: WebTarget, candidate: str) -> NiktoIssue | None:
    match = NIKTO_ADVISORY_PATTERN.match(candidate)
    if match is None:
        return None

    advisory = match.group("advisory")
    path = match.group("path")
    if path is not None:
        path = path.rstrip(":")
    message = match.group("message").strip()
    if not message:
        return None

    if advisory:
        normalized_advisory = advisory.upper()
        title = f"Nikto reported {normalized_advisory}"
    elif path:
        normalized_advisory = None
        title = f"Nikto reported {path}"
    else:
        normalized_advisory = None
        title = f"Nikto reported {_compact_title(message)}"

    return NiktoIssue(
        target=target,
        title=title,
        message=message,
        path=path,
        advisory=normalized_advisory,
        severity="high" if normalized_advisory else "medium",
    )


def _compact_title(message: str) -> str:
    sentence = message.split(".", 1)[0].strip()
    if len(sentence) <= 100:
        return sentence
    return f"{sentence[:97]}..."
