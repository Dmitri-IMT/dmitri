# ruff: noqa: E501, E701
"""Bounded web adapters and the versioned web-result policy.

The web adapter deliberately treats ffuf as a candidate producer.  A path name is
never evidence by itself: candidates are fetched once, compared with a synthetic
nonexistent-path response, and accepted only when the rule's content signature is
present.  The module contains no login, credential, recursion, or brute-force path.
"""

from __future__ import annotations

import csv
import hashlib
import re
import ssl
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from time import perf_counter
from typing import Any, Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urljoin, urlsplit
from urllib.request import HTTPRedirectHandler, HTTPSHandler, Request, build_opener

from agent.config import (
    TARGETED_MAX_ISSUES_PER_UNIT,
    TARGETED_UNIT_TIMEOUT_S,
    TARGETED_WEB_MAX_VALIDATIONS_PER_UNIT,
    TARGETED_WORDLIST_MAX_BYTES,
    TARGETED_WORDLIST_MAX_ENTRIES,
)
from agent.targeted.executor import TargetedExecutor, ToolCommand, ToolExecution
from agent.targeted.models import (
    TargetedGapReason,
    TargetedIssue,
    TargetedObservation,
    TargetedOutcome,
    TargetedTool,
    TargetedUnit,
    TargetedUnitResult,
)
from agent.targeted.report import parse_json_payload, sanitize_evidence

WEB_RESULT_POLICY_VERSION = "2026-09-15.1"
WEB_MAX_BODY_BYTES = 65_536
WEB_MAX_REDIRECTS = 2
NIKTO_DB_TESTS_PATH = Path("/opt/dmitri/tools/nikto-2.6.0/program/databases/db_tests")
NIKTO_DB_TESTS_SHA256 = (
    "e221b0ab6db1b3dec26a11674a68216fc6ee690b8b20f07056d4e4ae33ed30a2"
)
_CONFIG_STEMS = {
    ".env",
    "config.php",
    "web.config",
    "httpd.conf",
    "nginx.conf",
    "application.properties",
    "application.yml",
    "application.yaml",
    "config.json",
}
_BACKUP_SUFFIXES = (
    ".bak",
    ".backup",
    ".old",
    ".orig",
    ".save",
    "~",
    ".zip",
    ".tar",
    ".tar.gz",
    ".tgz",
    ".gz",
)


class _WebDeadlineExceeded(TimeoutError):
    pass


def _config_stem(base: str) -> str:
    stem = base
    while stem.endswith((".bak", ".backup", ".old", ".orig", ".save", "~")):
        stem = stem[:-1] if stem.endswith("~") else stem.rsplit(".", 1)[0]
    return stem


@dataclass(frozen=True, slots=True)
class WebRule:
    rule_id: str
    family: str
    severity: str | None
    title: str
    remediation: str
    observation: str | None = None
    matches_path: Callable[[str, str], bool] = field(kw_only=True)
    proof: str = field(kw_only=True)
    matches_body: Callable[[str, str, bytes], bool] = field(kw_only=True)
    seeds: tuple[str, ...] = field(default=(), kw_only=True)


WEB_RESULT_RULES: dict[str, WebRule] = {
    "WEB-DIRLIST-001": WebRule(
        "WEB-DIRLIST-001",
        "directory-listing",
        "medium",
        "Directory listing enabled",
        "Disable directory indexing on the web server.",
        matches_path=lambda path, base: path.endswith("/"),
        proof="directory-index-structure",
        matches_body=lambda base, text, body: (
            re.search(r"(?i)<title>\s*index of|parent directory", text) is not None
            and len(re.findall(r"href\s*=", text.casefold())) >= 1
        ),
    ),
    "WEB-VCS-GIT-001": WebRule(
        "WEB-VCS-GIT-001",
        "git",
        "high",
        "Exposed Git repository metadata",
        "Remove repository metadata from the web root.",
        matches_path=lambda path, base: (
            path in {"/.git/head", "/.git/config"} or path.startswith("/.git/")
        ),
        proof="git-ref-or-config",
        matches_body=lambda base, text, body: (
            (
                base == "head"
                and re.search(r"(?:ref:\s+refs/|\b[0-9a-f]{40}\b)", text, re.I)
            )
            or (base == "config" and re.search(r"(?m)^\s*\[[^\]]+\]", text))
        ),
        seeds=(".git/HEAD", ".git/config"),
    ),
    "WEB-VCS-SVN-001": WebRule(
        "WEB-VCS-SVN-001",
        "svn",
        "high",
        "Exposed Subversion repository metadata",
        "Remove Subversion metadata from the web root.",
        matches_path=lambda path, base: (
            path in {"/.svn/entries", "/.svn/wc.db"} or path.startswith("/.svn/")
        ),
        proof="svn-entries-or-sqlite",
        matches_body=lambda base, text, body: (
            (
                base == "entries"
                and (
                    "dircvs-log" in text.casefold()
                    or "<?xml" in text.casefold()
                    or "svn" in text.casefold()
                )
            )
            or (base == "wc.db" and body.startswith(b"SQLite format 3"))
        ),
        seeds=(".svn/entries", ".svn/wc.db"),
    ),
    "WEB-SECRET-ENV-001": WebRule(
        "WEB-SECRET-ENV-001",
        "env",
        "high",
        "Exposed environment configuration",
        "Remove environment configuration from public web paths.",
        matches_path=lambda path, base: base == ".env" or base.startswith(".env."),
        proof="environment-assignments",
        matches_body=lambda base, text, body: (
            len(re.findall(r"(?m)^\s*[A-Za-z_][A-Za-z0-9_]*\s*=\s*[^\s#]+", text)) >= 2
        ),
        seeds=(".env", ".env.bak", ".env.old"),
    ),
    "WEB-SECRET-KEY-001": WebRule(
        "WEB-SECRET-KEY-001",
        "key",
        "critical",
        "Exposed private key material",
        "Remove the private key and rotate any affected credentials.",
        matches_path=lambda path, base: (
            base == "id_rsa" or base.endswith((".key", ".pem"))
        ),
        proof="private-key-header",
        matches_body=lambda base, text, body: (
            re.search(
                r"-----BEGIN (?:[A-Z0-9 ]+ )?PRIVATE KEY-----|-----BEGIN OPENSSH PRIVATE KEY-----",
                text,
            )
            is not None
        ),
        seeds=("id_rsa", "private.key", "server.key"),
    ),
    "WEB-CONFIG-001": WebRule(
        "WEB-CONFIG-001",
        "config",
        "high",
        "Exposed application or server configuration",
        "Remove configuration files from the public web root.",
        matches_path=lambda path, base: _config_stem(base) in _CONFIG_STEMS,
        proof="reviewed-config-setting",
        matches_body=lambda base, text, body: (
            re.search(
                r"(?i)(database|secret|password|listen|server_name|connection|string|api[_-]?key)",
                text,
            )
            is not None
            and ("{" in text or "=" in text or ":" in text or "[" in text)
        ),
        seeds=(
            "application.properties",
            "application.yml",
            "config.json",
            "config.php.bak",
            "web.config.bak",
        ),
    ),
    "WEB-BACKUP-001": WebRule(
        "WEB-BACKUP-001",
        "backup",
        "high",
        "Exposed backup or source artifact",
        "Remove backups and source artifacts from the web root.",
        matches_path=lambda path, base: base.endswith(_BACKUP_SUFFIXES),
        proof="archive-or-source-signature",
        matches_body=lambda base, text, body: (
            body.startswith((b"PK\x03\x04", b"\x1f\x8b", b"ustar"))
            or re.search(r"(?i)(?:<\?php|#!/|function\s+\w+\s*\(|source\s+code)", text)
            is not None
        ),
        seeds=("backup.tar.gz", "backup.zip"),
    ),
    "WEB-DUMP-001": WebRule(
        "WEB-DUMP-001",
        "dump",
        "high",
        "Exposed database artifact",
        "Remove database dumps from the web root and rotate exposed secrets.",
        matches_path=lambda path, base: (
            base.endswith((".sql", ".db", ".sqlite")) or base in {"database", "dump"}
        ),
        proof="database-dump-signature",
        matches_body=lambda base, text, body: (
            body.startswith(b"SQLite format 3")
            or re.search(
                r"(?i)(?:CREATE\s+TABLE|INSERT\s+INTO|--\s*(?:mysql|postgres|sql))",
                text,
            )
            is not None
        ),
        seeds=("database.sql", "database.sqlite"),
    ),
    "WEB-LOG-001": WebRule(
        "WEB-LOG-001",
        "log",
        "medium",
        "Exposed application or server log",
        "Remove logs from public paths and review disclosed information.",
        matches_path=lambda path, base: (
            base.endswith(".log") or base in {"debug.log", "error.log"}
        ),
        proof="log-structure",
        matches_body=lambda base, text, body: (
            len(re.findall(r"(?:\d{4}-\d\d-\d\d|\b\d\d?:\d\d:\d\d\b)", text)) >= 2
            or re.search(r"(?i)(GET|POST)\s+\S+\s+HTTP/\d|traceback|exception", text)
            is not None
        ),
        seeds=("debug.log", "error.log"),
    ),
    "WEB-DIAG-PHP-001": WebRule(
        "WEB-DIAG-PHP-001",
        "phpinfo",
        "medium",
        "Exposed PHP diagnostic page",
        "Remove or restrict PHP diagnostic pages.",
        matches_path=lambda path, base: base == "phpinfo.php" or "phpinfo" in base,
        proof="phpinfo-structure",
        matches_body=lambda base, text, body: (
            "php version" in text.casefold()
            and ("phpinfo" in text.casefold() or "configuration" in text.casefold())
        ),
        seeds=("phpinfo.php",),
    ),
    "WEB-DIAG-SERVER-001": WebRule(
        "WEB-DIAG-SERVER-001",
        "server-diagnostic",
        "medium",
        "Exposed web-server diagnostic endpoint",
        "Disable or restrict web-server diagnostic endpoints.",
        matches_path=lambda path, base: (
            path in {"/server-status", "/server-info", "/nginx_status"}
        ),
        proof="server-diagnostic-structure",
        matches_body=lambda base, text, body: (
            "server status" in text.casefold()
            or "server-info" in text.casefold()
            or "stub_status" in text.casefold()
        ),
        seeds=("nginx_status", "server-info", "server-status"),
    ),
    "WEB-DIAG-ACTUATOR-001": WebRule(
        "WEB-DIAG-ACTUATOR-001",
        "actuator",
        "high",
        "Exposed sensitive application diagnostic endpoint",
        "Restrict application diagnostic endpoints and sensitive actuator data.",
        matches_path=lambda path, base: path.startswith("/actuator/"),
        proof="actuator-sensitive-data",
        matches_body=lambda base, text, body: (
            (
                base == "heapdump"
                and (body.startswith(b"PK") or body.startswith(b"\x1f\x8b"))
            )
            or (
                base != "heapdump"
                and (
                    "environment" in text.casefold()
                    or "propertysources" in text.casefold()
                    or "activeprofiles" in text.casefold()
                )
            )
        ),
        seeds=("actuator/configprops", "actuator/env", "actuator/heapdump"),
    ),
    "WEB-METRICS-001": WebRule(
        "WEB-METRICS-001",
        "metrics",
        "medium",
        "Operational metrics exposed",
        "Restrict operational metrics endpoints to authorized users.",
        matches_path=lambda path, base: path in {"/metrics", "/prometheus"},
        proof="prometheus-exposition",
        matches_body=lambda base, text, body: (
            ("# help " in text.casefold() and "# type " in text.casefold())
            or re.search(
                r"(?m)^[a-z_:][a-z0-9_:]*(?:\{[^}]*\})?\s+-?\d", text.casefold()
            )
            is not None
        ),
        seeds=("metrics", "prometheus"),
    ),
    "WEB-ADMIN-001": WebRule(
        "WEB-ADMIN-001",
        "admin",
        None,
        "Administrative interface reachable",
        "Restrict administrative interfaces to authorized operators.",
        "administration",
        matches_path=lambda path, base: (
            path
            in {
                "/admin",
                "/administrator",
                "/manager/html",
                "/host-manager/html",
                "/phpmyadmin",
                "/adminer.php",
                "/wp-admin",
            }
        ),
        proof="administrative-login-surface",
        matches_body=lambda base, text, body: (
            re.search(
                r"(?i)\b(?:admin(?:istration)?|management\s+console|control\s+panel|dashboard)\b",
                text,
            )
            is not None
            or re.search(
                r"(?is)<form\b[^>]*(?:action|id|class)=[\"'][^\"']*(?:admin|manage|login)[^\"']*[\"']",
                text,
            )
            is not None
            or (
                re.search(r"(?i)<form\b", text)
                and re.search(
                    r"(?i)(?:type=[\"']?password|name=[\"']?(?:password|username|user))",
                    text,
                )
                and re.search(r"(?i)\b(?:login|sign\s*in|authenticate)\b", text)
            )
        ),
        seeds=(
            "admin",
            "administrator",
            "adminer.php",
            "host-manager/html",
            "manager/html",
            "phpmyadmin",
            "wp-admin",
        ),
    ),
    "WEB-API-DOCS-001": WebRule(
        "WEB-API-DOCS-001",
        "api-docs",
        None,
        "API documentation reachable",
        "Restrict API documentation and review its disclosed surface.",
        "api_surface",
        matches_path=lambda path, base: (
            path
            in {
                "/swagger",
                "/swagger-ui",
                "/api-docs",
                "/openapi.json",
                "/openapi.yaml",
            }
        ),
        proof="api-documentation-structure",
        matches_body=lambda base, text, body: (
            (
                re.search(r'(?i)["\']openapi["\']\s*:', text) is not None
                and "paths" in text.casefold()
            )
            or re.search(r"(?i)(swagger ui|swagger-ui|openapi documentation)", text)
            is not None
        ),
        seeds=("api-docs", "openapi.json", "openapi.yaml", "swagger", "swagger-ui"),
    ),
}

WEB_RESULT_SEEDS = tuple(
    seed for rule in WEB_RESULT_RULES.values() for seed in rule.seeds
)

# A provisioned Nikto tree supplies the authoritative rows at runtime.  An ID
# not resolved from that pinned database cannot become a finding.  Tests and
# callers may provide a parsed mapping; a file is accepted only after the
# pinned database digest has been checked.


@dataclass(frozen=True, slots=True)
class WebCandidate:
    url: str
    path: str
    status: int
    length: int | None = None
    words: int | None = None
    lines: int | None = None
    redirectlocation: str | None = None


@dataclass(frozen=True, slots=True)
class WebBaseline:
    status: int
    content_type: str
    length: int
    words: int
    lines: int
    body_digest: str


@dataclass(frozen=True, slots=True)
class WebResponse:
    status: int
    content_type: str
    body: bytes
    url: str = ""
    truncated: bool = False

    @property
    def length(self) -> int:
        return len(self.body)

    @property
    def words(self) -> int:
        return len(self.body.decode("utf-8", "replace").split())

    @property
    def lines(self) -> int:
        return self.body.count(b"\n") + (1 if self.body else 0)


def _normal_path(path: str) -> str:
    raw = (
        urlsplit(path).path if "://" in path else path.split("?", 1)[0].split("#", 1)[0]
    )
    decoded = unquote(unquote(raw or "/"))
    trailing_slash = decoded.endswith("/")
    parts: list[str] = []
    for part in decoded.split("/"):
        if part in ("", "."):
            continue
        if part == "..":
            if parts:
                parts.pop()
            continue
        parts.append(part)
    normalized = "/" + "/".join(parts)
    if trailing_slash and normalized != "/":
        normalized += "/"
    return normalized


def _basename(path: str) -> str:
    return _normal_path(path).rstrip("/").rsplit("/", 1)[-1].casefold()


def _rule_for_path(path: str) -> WebRule | None:
    path = _normal_path(path).casefold()
    base = _basename(path)
    for rule in WEB_RESULT_RULES.values():
        if rule.matches_path(path, base):
            return rule
    return None


def _signature(rule: WebRule, path: str, body: bytes) -> str | None:
    text = body.decode("utf-8", "replace")
    if rule.matches_body(_basename(path), text, body):
        return rule.proof
    return None


def _class_of(rule: WebRule) -> int:
    return {"critical": 0, "high": 1, "medium": 2, None: 3}.get(rule.severity, 3)


def parse_ffuf_json(
    report: bytes | str | Mapping[str, Any],
    unit: TargetedUnit | None = None,
) -> list[WebCandidate]:
    """Parse only bounded native ffuf JSON result records."""
    payload = parse_json_payload(report)
    if not isinstance(payload, dict) or not isinstance(payload.get("results"), list):
        return []
    output: dict[tuple[str, int], WebCandidate] = {}
    for raw in payload["results"][: TARGETED_MAX_ISSUES_PER_UNIT * 4]:
        if not isinstance(raw, dict) or not isinstance(raw.get("url"), str):
            continue
        url = raw["url"]
        parsed = urlsplit(url)
        status = _int(raw.get("status"))
        if status is None or not parsed.scheme or not parsed.netloc:
            continue
        if unit is not None and (
            (parsed.hostname or "") != unit.ip
            or (parsed.port or unit.port) != unit.port
        ):
            continue
        path = _normal_path(parsed.path)
        candidate = WebCandidate(
            url,
            path,
            status,
            _int(raw.get("length")),
            _int(raw.get("words")),
            _int(raw.get("lines")),
            (
                raw.get("redirectlocation")
                if isinstance(raw.get("redirectlocation"), str)
                else None
            ),
        )
        output[(path.casefold(), status)] = candidate
    return list(output.values())


def classify_ffuf_candidate(candidate: WebCandidate | str) -> WebRule | None:
    path = candidate.path if isinstance(candidate, WebCandidate) else candidate
    return _rule_for_path(path)


def _int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _body_digest(body: bytes) -> str:
    return hashlib.sha256(re.sub(rb"\s+", b" ", body[:WEB_MAX_BODY_BYTES])).hexdigest()


def _baseline(response: WebResponse) -> WebBaseline:
    return WebBaseline(
        response.status,
        response.content_type,
        response.length,
        response.words,
        response.lines,
        _body_digest(response.body),
    )


def _same_as_baseline(response: WebResponse, baseline: WebBaseline) -> bool:
    return (
        response.status,
        response.content_type,
        response.length,
        response.words,
        response.lines,
        _body_digest(response.body),
    ) == (
        baseline.status,
        baseline.content_type,
        baseline.length,
        baseline.words,
        baseline.lines,
        baseline.body_digest,
    )


def _origin(url: str) -> tuple[str, str, int | None]:
    parsed = urlsplit(url)
    port = parsed.port
    if port is None:
        port = {"http": 80, "https": 443}.get(parsed.scheme.casefold())
    return parsed.scheme.casefold(), (parsed.hostname or "").casefold(), port


class _NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, *_args: Any, **_kwargs: Any) -> None:
        return None


def _fetch(
    url: str,
    *,
    timeout: float = 5.0,
    opener: Callable[..., Any] | None = None,
    deadline: float | None = None,
) -> WebResponse:
    current = url
    original_origin = _origin(url)
    if opener is not None:
        open_url = opener
    elif original_origin[0] == "https":
        # Certificate quality is assessed by testssl; still enumerate and
        # validate paths on HTTPS services that use private/self-signed certs.
        context = ssl._create_unverified_context()
        open_url = build_opener(
            _NoRedirectHandler(), HTTPSHandler(context=context)
        ).open
    else:
        open_url = build_opener(_NoRedirectHandler()).open
    for redirect_count in range(WEB_MAX_REDIRECTS + 1):
        request = Request(
            current, method="GET", headers={"User-Agent": "Dmitri-targeted/1"}
        )
        try:
            request_timeout = timeout
            if deadline is not None:
                request_timeout = min(timeout, deadline - perf_counter())
                if request_timeout <= 0:
                    raise _WebDeadlineExceeded("web validation deadline reached")
            response = open_url(request, timeout=request_timeout)
        except HTTPError as error:
            response = error
        try:
            status = int(getattr(response, "status", response.getcode()))
            if 300 <= status <= 399:
                location = response.headers.get("Location")
                if not isinstance(location, str) or redirect_count >= WEB_MAX_REDIRECTS:
                    raise URLError("redirect limit exceeded")
                destination = urljoin(current, location)
                if _origin(destination) != original_origin:
                    raise URLError("external redirect rejected")
                current = destination
                continue
            content_type = (
                str(response.headers.get("Content-Type", ""))
                .split(";", 1)[0]
                .strip()
                .casefold()
            )
            body = response.read(WEB_MAX_BODY_BYTES + 1)
            truncated = len(body) > WEB_MAX_BODY_BYTES
            return WebResponse(
                status, content_type, body[:WEB_MAX_BODY_BYTES], current, truncated
            )
        finally:
            close = getattr(response, "close", None)
            if callable(close):
                close()
    raise URLError("redirect limit exceeded")


def validate_web_candidate(
    candidate: WebCandidate,
    baseline: WebBaseline | None = None,
    *,
    fetcher: Callable[[str], WebResponse] | None = None,
    response: WebResponse | None = None,
) -> TargetedIssue | TargetedObservation | None:
    """Validate one candidate without retaining its response body or secrets."""
    rule = classify_ffuf_candidate(candidate)
    if rule is None:
        return None
    try:
        result = response or (fetcher or _fetch)(candidate.url)
    except _WebDeadlineExceeded:
        raise
    except Exception:
        return None
    if result.url:
        if _origin(candidate.url) != _origin(result.url):
            return None
    if baseline is not None and _same_as_baseline(result, baseline):
        return None
    if result.status in {401, 403, 407}:
        if rule.observation:
            normal_path = _normal_path(candidate.path)
            return TargetedObservation(
                f"web:{rule.observation}:{normal_path}",
                rule.observation,
                rule.title,
                f"{WEB_RESULT_POLICY_VERSION}:{rule.rule_id}; path={normal_path}; status={result.status}; protected surface",
                path=normal_path,
                rule_id=rule.rule_id,
                policy_version=WEB_RESULT_POLICY_VERSION,
            )
        return None
    if not 200 <= result.status <= 299 or result.truncated:
        return None
    signature = _signature(rule, candidate.path, result.body)
    if signature is None:
        return None
    path = _normal_path(candidate.path)
    evidence = sanitize_evidence(
        f"{WEB_RESULT_POLICY_VERSION}:{rule.rule_id}; path={path}; status={result.status}; content_type={result.content_type or 'unknown'}; length={result.length}; signature={signature}"
    )
    if rule.observation:
        return TargetedObservation(
            f"web:{rule.observation}:{path}",
            rule.observation,
            rule.title,
            evidence,
            path=path,
            rule_id=rule.rule_id,
            policy_version=WEB_RESULT_POLICY_VERSION,
        )
    return TargetedIssue(
        f"web.sensitive-path:{path}",
        rule.title,
        f"The endpoint exposed content matching the {rule.rule_id} policy rule.",
        rule.severity or "medium",
        rule.remediation,
        evidence,
        references=[f"policy:{WEB_RESULT_POLICY_VERSION}:{rule.rule_id}"],
        method="specific_check",
        result="positive",
        rule_id=f"targeted:ffuf:{rule.rule_id}"[:128],
        facts={
            "path": path[:160],
            "status": result.status,
            "signature": sanitize_evidence(signature, 160),
        },
    )


def _result_from_execution(
    unit: TargetedUnit, execution: ToolExecution
) -> TargetedUnitResult:
    return TargetedUnitResult(
        unit,
        execution.outcome,
        exit_code=execution.exit_code,
        reason_code=execution.reason_code,
        diagnostic=execution.diagnostic,
    )


def _wordlist(path: str | Path | None) -> tuple[Path | None, TargetedGapReason | None]:
    candidates = (
        [Path(path)]
        if path
        else [
            Path("/usr/share/wordlists/dirb/common.txt"),
            Path("/usr/share/dirb/wordlists/common.txt"),
        ]
    )
    for candidate in candidates:
        try:
            if (
                not candidate.is_file()
                or candidate.stat().st_size > TARGETED_WORDLIST_MAX_BYTES
            ):
                continue
            entries = [
                line.strip()
                for line in candidate.read_text(encoding="utf-8").splitlines()
                if line.strip() and not line.lstrip().startswith("#")
            ]
            if 4_000 <= len(entries) <= TARGETED_WORDLIST_MAX_ENTRIES:
                return candidate, None
        except (OSError, UnicodeError):
            continue
    return None, TargetedGapReason.WORDLIST_UNAVAILABLE


def _effective_wordlist(base: Path) -> Path:
    handle = tempfile.NamedTemporaryFile(
        prefix="dmitri-web-", suffix=".txt", delete=False, mode="w", encoding="utf-8"
    )
    try:
        entries = {
            line.strip()
            for line in base.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        }
        entries.update(WEB_RESULT_SEEDS)
        for entry in sorted(entries):
            handle.write(entry + "\n")
        return Path(handle.name)
    finally:
        handle.close()


def run_ffuf(
    unit: TargetedUnit,
    executor: TargetedExecutor,
    wordlist: str | Path | None = None,
    scan_id: str = "",
    *,
    fetcher: Callable[[str], WebResponse] | None = None,
    **deadline: Any,
) -> TargetedUnitResult:
    start = perf_counter()
    unit_deadline = start + TARGETED_UNIT_TIMEOUT_S[TargetedTool.FFUF.value]
    deadline_values = [unit_deadline]
    scope = "unit"
    for key, candidate_scope in (
        ("stage_deadline", "stage"),
        ("overall_deadline", "overall"),
    ):
        value = deadline.get(key)
        if isinstance(value, (int, float)) and value < min(deadline_values):
            deadline_values = [float(value)]
            scope = candidate_scope
    end = min(deadline_values)
    cancel_event = deadline.get("cancel_event")

    def incomplete_result() -> TargetedUnitResult | None:
        cancelled = bool(getattr(executor, "_cancelled", False)) or bool(
            cancel_event is not None and cancel_event.is_set()
        )
        if cancelled:
            return TargetedUnitResult(
                unit,
                TargetedOutcome.SKIPPED,
                reason_code=TargetedGapReason.SCAN_CANCELLED,
            )
        if perf_counter() < end:
            return None
        if scope == "stage":
            return TargetedUnitResult(
                unit,
                TargetedOutcome.SKIPPED,
                reason_code=TargetedGapReason.STAGE_BUDGET,
            )
        return TargetedUnitResult(
            unit,
            TargetedOutcome.TIMED_OUT,
            reason_code=(TargetedGapReason.UNIT_TIMEOUT if scope == "unit" else None),
        )

    def bounded_fetch(url: str) -> WebResponse:
        status = incomplete_result()
        if status is not None:
            raise _WebDeadlineExceeded("web validation deadline reached")
        if fetcher is not None:
            return fetcher(url)
        return _fetch(url, deadline=end)

    base, reason = _wordlist(wordlist)
    if base is None:
        return TargetedUnitResult(unit, TargetedOutcome.SKIPPED, reason_code=reason)
    effective = _effective_wordlist(base)
    try:
        url = f"{unit.transport or 'http'}://{unit.ip}:{unit.port}/FUZZ"
        argv = [
            "ffuf",
            "-u",
            url,
            "-w",
            str(effective),
            "-of",
            "json",
            "-o",
            "REPORT",
            "-noninteractive",
            "-s",
            "-ac",
            "-t",
            "2",
            "-rate",
            "20",
            "-timeout",
            "5",
            "-maxtime",
            "300",
        ]
        if unit.transport == "https":
            # The target certificate is reported separately by testssl.
            argv.append("-k")
        command = ToolCommand(
            TargetedTool.FFUF,
            argv,
            "file",
            8,
        )
        execution = executor.execute(command, **deadline)
        if (
            execution.outcome != TargetedOutcome.COMPLETED
            and not execution.report_present
        ):
            return _result_from_execution(unit, execution)
        if execution.report_truncated:
            return TargetedUnitResult(
                unit,
                TargetedOutcome.FAILED,
                exit_code=execution.exit_code,
                reason_code=TargetedGapReason.OUTPUT_LIMIT,
            )
        if not execution.report_present:
            return TargetedUnitResult(
                unit,
                TargetedOutcome.FAILED,
                exit_code=execution.exit_code,
                reason_code=(
                    TargetedGapReason.EXECUTION_ERROR
                    if execution.exit_code not in (None, 0)
                    else TargetedGapReason.MALFORMED_REPORT
                ),
                diagnostic=sanitize_evidence(
                    execution.diagnostic or "ffuf did not create its JSON report.", 512
                ),
            )
        payload = parse_json_payload(execution.report)
        if not isinstance(payload, dict) or not isinstance(
            payload.get("results"), list
        ):
            if execution.outcome != TargetedOutcome.COMPLETED:
                return _result_from_execution(unit, execution)
            return TargetedUnitResult(
                unit,
                TargetedOutcome.FAILED,
                exit_code=execution.exit_code,
                reason_code=TargetedGapReason.MALFORMED_REPORT,
                diagnostic=sanitize_evidence(
                    execution.diagnostic
                    or "ffuf JSON report has an unsupported schema.",
                    512,
                ),
            )
        candidates = parse_ffuf_json(execution.report, unit)
        candidates = [c for c in candidates if classify_ffuf_candidate(c)]
        candidates.sort(
            key=lambda c: (
                _class_of(classify_ffuf_candidate(c)),
                classify_ffuf_candidate(c).rule_id,
                c.path.casefold(),
            )
        )
        execution_output = (
            (execution.diagnostic or "")
            + " "
            + execution.stdout.decode(errors="replace")
            + " "
            + execution.stderr.decode(errors="replace")
        ).casefold()
        internal_timeout = (
            execution.outcome == TargetedOutcome.COMPLETED
            and "maximum running time for entire process reached, exiting"
            in execution_output
        )
        if internal_timeout:
            status = incomplete_result()
            if status is not None:
                return status
        result = TargetedUnitResult(
            unit,
            TargetedOutcome.TIMED_OUT if internal_timeout else execution.outcome,
            exit_code=execution.exit_code,
            reason_code=(
                TargetedGapReason.UNIT_TIMEOUT
                if internal_timeout
                else execution.reason_code
            ),
            diagnostic=(
                execution.diagnostic
                or (
                    sanitize_evidence(
                        "Maximum running time for entire process reached, exiting.", 512
                    )
                    if internal_timeout
                    else None
                )
            ),
        )
        if candidates:
            synthetic = hashlib.sha256(
                f"{scan_id}|{unit.ip}|{unit.port}".encode()
            ).hexdigest()[:16]
            baseline_response = bounded_fetch(
                f"{unit.transport or 'http'}://{unit.ip}:{unit.port}/.dmitri-not-found-{synthetic}"
            )
            if baseline_response.truncated:
                return TargetedUnitResult(
                    unit,
                    TargetedOutcome.FAILED,
                    exit_code=execution.exit_code,
                    reason_code=TargetedGapReason.BASELINE_UNAVAILABLE,
                )
            baseline = _baseline(baseline_response)
            for candidate in candidates[:TARGETED_WEB_MAX_VALIDATIONS_PER_UNIT]:
                status = incomplete_result()
                if status is not None:
                    status.issues = result.issues
                    status.observations = result.observations
                    return status
                try:
                    validated = validate_web_candidate(
                        candidate, baseline, fetcher=bounded_fetch
                    )
                except _WebDeadlineExceeded:
                    status = incomplete_result()
                    if status is not None:
                        status.issues = result.issues
                        status.observations = result.observations
                        return status
                    raise
                if (
                    isinstance(validated, TargetedIssue)
                    and len(result.issues) < TARGETED_MAX_ISSUES_PER_UNIT
                ):
                    result.issues.append(validated)
                elif isinstance(validated, TargetedObservation):
                    result.observations.append(validated)
            if (
                len(candidates) > TARGETED_WEB_MAX_VALIDATIONS_PER_UNIT
                and not internal_timeout
            ):
                result.outcome, result.reason_code = (
                    TargetedOutcome.FAILED,
                    TargetedGapReason.VALIDATION_LIMIT,
                )
        return result
    except Exception as exc:
        status = incomplete_result()
        if status is not None:
            return status
        return TargetedUnitResult(
            unit,
            TargetedOutcome.FAILED,
            reason_code=TargetedGapReason.BASELINE_UNAVAILABLE,
            diagnostic=sanitize_evidence(exc, 512),
        )
    finally:
        effective.unlink(missing_ok=True)


def _load_nikto_policy(
    source: Mapping[str, str] | str | Path | None,
) -> Mapping[str, str]:
    if isinstance(source, Mapping):
        return {
            str(identifier).zfill(6): str(category).casefold()
            for identifier, category in source.items()
            if re.fullmatch(r"\d{1,6}", str(identifier)) and isinstance(category, str)
        }
    path = NIKTO_DB_TESTS_PATH if source is None else Path(source)
    try:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != NIKTO_DB_TESTS_SHA256:
            return {}
        with path.open(newline="", encoding="utf-8", errors="replace") as stream:
            rows = list(
                csv.reader(
                    line
                    for line in stream
                    if line.strip() and not line.lstrip().startswith("#")
                )
            )
        if not rows:
            return {}
        header = [value.strip().casefold() for value in rows[0]]
        id_index = next(
            (
                header.index(key)
                for key in ("id", "testid", "test_id", "osvdb")
                if key in header
            ),
            None,
        )
        category_index = next(
            (
                header.index(key)
                for key in ("tuning", "category", "categories")
                if key in header
            ),
            None,
        )
        if id_index is not None and category_index is not None:
            data_rows = rows[1:]
        else:
            # The pinned Nikto 2.6 database documents its nine-column format
            # in comments; its actual rows have ID and Tuning in columns 0/2.
            id_index, category_index = 0, 2
            data_rows = rows
        output: dict[str, str] = {}
        for row in data_rows:
            if len(row) <= max(id_index, category_index):
                continue
            identifier, category = row[id_index].strip(), row[category_index].strip()
            if re.fullmatch(r"\d{1,6}", identifier) and category:
                output[identifier.zfill(6)] = category.casefold()
        return output
    except (OSError, UnicodeError):
        return {}


def _nikto_policy_available(source: Mapping[str, str] | str | Path | None) -> bool:
    if isinstance(source, Mapping):
        return True
    return bool(_load_nikto_policy(source))


def _nikto_severity(categories: str) -> str | None:
    categories = categories.casefold()
    if any(c in categories for c in ("8", "c")):
        return "critical"
    if any(c in categories for c in ("4", "5", "7", "9", "a", "f")):
        return "high"
    if any(c in categories for c in ("2", "3")):
        return "medium"
    return None


def _safe_nikto_references(row: Mapping[str, Any]) -> tuple[list[str], str | None]:
    values: list[str] = []

    def collect(value: Any) -> None:
        if isinstance(value, str):
            values.append(value)
        elif isinstance(value, Mapping):
            for nested in value.values():
                collect(nested)
        elif isinstance(value, (list, tuple)):
            for nested in value:
                collect(nested)

    collect(row.get("references", row.get("reference", row.get("refs"))))
    safe: list[str] = []
    cve_id: str | None = None
    for value in values:
        cves = re.findall(r"(?i)\bCVE-\d{4}-\d{4,7}\b", value)
        if cve_id is None and cves:
            cve_id = cves[0].upper()
        for match in re.findall(r"(?i)https?://[^\s<>\"']+", value):
            safe.append(sanitize_evidence(match))
    return list(dict.fromkeys(safe))[:8], cve_id


def _parse_nikto_issues(
    payload: Mapping[str, Any],
    target_unit: TargetedUnit | None,
    policies: Mapping[str, str],
    limit: int | None,
) -> tuple[list[TargetedIssue], bool]:
    rows = payload["vulnerabilities"]
    issues: list[TargetedIssue] = []
    supported_count = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        identifier = row.get("id", row.get("testid", row.get("test_id")))
        if not re.fullmatch(r"\d{1,6}", str(identifier or "")):
            continue
        identifier = str(identifier).zfill(6)
        categories = policies.get(identifier)
        if categories is None:
            continue
        severity = _nikto_severity(str(categories))
        if severity is None:
            continue
        uri = row.get("uri", row.get("url", row.get("path", "/")))
        message = row.get("msg", row.get("message", row.get("description", "")))
        if not isinstance(uri, str) or not isinstance(message, str):
            continue
        if (
            target_unit is not None
            and isinstance(row.get("host"), str)
            and row["host"] not in {target_unit.ip, ""}
        ):
            continue
        if target_unit is not None and row.get("port") not in (
            None,
            "",
            target_unit.port,
            str(target_unit.port),
        ):
            continue
        supported_count += 1
        if limit is not None and len(issues) >= limit:
            continue
        path = _normal_path(uri)
        method = row.get("method", "")
        method_text = sanitize_evidence(method) if isinstance(method, str) else ""
        references, cve_id = _safe_nikto_references(row)
        evidence = sanitize_evidence(
            f"{WEB_RESULT_POLICY_VERSION}:nikto:{identifier}; method={method_text or 'unknown'}; path={path}; {sanitize_evidence(message)}"
        )
        issue_key = f"nikto:{identifier}:{path}"
        if len(issue_key) > 256:
            digest = hashlib.sha256(issue_key.encode("utf-8")).hexdigest()[:16]
            issue_key = f"{issue_key[:239]}:{digest}"
        issues.append(
            TargetedIssue(
                issue_key,
                f"Nikto web security issue {identifier}",
                sanitize_evidence(message),
                severity,
                "Apply the vendor or web-server remediation for this issue and restrict the affected endpoint.",
                evidence,
                cve_id=cve_id,
                references=references,
                method="unknown",
                result="inconclusive",
                rule_id="targeted:nikto-unsupported",
                facts={},
            )
        )
    return issues, supported_count > (limit or supported_count)


def parse_nikto_json(
    report: bytes | str | Mapping[str, Any],
    unit: TargetedUnit | None = None,
    *,
    policy: Mapping[str, str] | str | Path | None = None,
) -> list[TargetedIssue]:
    payload = _nikto_payload(parse_json_payload(report))
    if payload is None:
        return []
    policies = _load_nikto_policy(policy)
    return _parse_nikto_issues(payload, unit, policies, TARGETED_MAX_ISSUES_PER_UNIT)[0]


def _nikto_payload(value: Any) -> dict[str, Any] | None:
    """Normalize Nikto's native host-array JSON and the legacy object form."""
    if isinstance(value, Mapping) and isinstance(value.get("vulnerabilities"), list):
        return {"vulnerabilities": value["vulnerabilities"]}
    if not isinstance(value, list) or not value:
        return None
    vulnerabilities: list[dict[str, Any]] = []
    for host in value:
        if (
            not isinstance(host, Mapping)
            or not isinstance(host.get("vulnerabilities"), list)
            or not isinstance(host.get("ip", host.get("host")), str)
        ):
            return None
        for item in host["vulnerabilities"]:
            if not isinstance(item, Mapping):
                return None
            normalized = dict(item)
            normalized.setdefault("host", host.get("ip", host.get("host")))
            normalized.setdefault("port", host.get("port"))
            vulnerabilities.append(normalized)
    return {"vulnerabilities": vulnerabilities}


def run_nikto(
    unit: TargetedUnit,
    executor: TargetedExecutor,
    policy: Mapping[str, str] | str | Path | None = None,
    **deadline: Any,
) -> TargetedUnitResult:
    url = f"{unit.transport or 'http'}://{unit.ip}:{unit.port}"
    argv = [
        "nikto",
        "-h",
        url,
        "-nointeractive",
        "-nolookup",
        "-nocheck",
        "-nocookies",
        "-Tuning",
        "2345789acf",
        "-timeout",
        "5",
        "-maxtime",
        "700s",
        "-Pause",
        "0.05",
        "-Format",
        "json",
        "-output",
        "REPORT",
    ]
    execution = executor.execute(
        ToolCommand(TargetedTool.NIKTO, argv, "file", 18, report_path_mode="base"),
        **deadline,
    )
    if execution.outcome != TargetedOutcome.COMPLETED and not execution.report_present:
        return _result_from_execution(unit, execution)
    if execution.report_truncated:
        return TargetedUnitResult(
            unit,
            TargetedOutcome.FAILED,
            exit_code=execution.exit_code,
            reason_code=TargetedGapReason.OUTPUT_LIMIT,
        )
    if not execution.report_present:
        return TargetedUnitResult(
            unit,
            TargetedOutcome.FAILED,
            exit_code=execution.exit_code,
            reason_code=TargetedGapReason.MALFORMED_REPORT,
            diagnostic=execution.diagnostic or "Nikto did not create its JSON report.",
        )
    payload = _nikto_payload(parse_json_payload(execution.report))
    if payload is None:
        if execution.outcome != TargetedOutcome.COMPLETED:
            return _result_from_execution(unit, execution)
        return TargetedUnitResult(
            unit,
            TargetedOutcome.FAILED,
            exit_code=execution.exit_code,
            reason_code=TargetedGapReason.MALFORMED_REPORT,
            diagnostic=execution.diagnostic
            or "Nikto JSON report has an unsupported schema.",
        )
    if not _nikto_policy_available(policy):
        return TargetedUnitResult(
            unit,
            TargetedOutcome.SKIPPED,
            exit_code=execution.exit_code,
            reason_code=TargetedGapReason.POLICY_UNAVAILABLE,
        )
    policies = _load_nikto_policy(policy)
    issues, exceeded = _parse_nikto_issues(
        payload, unit, policies, TARGETED_MAX_ISSUES_PER_UNIT
    )
    if exceeded:
        return TargetedUnitResult(
            unit,
            TargetedOutcome.FAILED,
            issues=issues,
            exit_code=execution.exit_code,
            reason_code=TargetedGapReason.ISSUE_LIMIT,
        )
    timeout_output = (
        (execution.diagnostic or "")
        + " "
        + execution.stdout.decode(errors="replace")
        + " "
        + execution.stderr.decode(errors="replace")
    ).casefold()
    internal_timeout = (
        execution.outcome == TargetedOutcome.COMPLETED
        and "host maximum execution time" in timeout_output
        and "reached" in timeout_output
    )
    error_limit = (
        re.search(
            r"\+\s*error:\s*\*{3}\s*error limit \(\d+\) reached for host, giving up\.",
            timeout_output,
        )
        if execution.outcome == TargetedOutcome.COMPLETED
        else None
    )
    return TargetedUnitResult(
        unit,
        (
            TargetedOutcome.TIMED_OUT
            if internal_timeout
            else TargetedOutcome.FAILED if error_limit else execution.outcome
        ),
        issues=issues,
        exit_code=execution.exit_code,
        reason_code=(
            TargetedGapReason.UNIT_TIMEOUT
            if internal_timeout
            else (
                TargetedGapReason.EXECUTION_ERROR
                if error_limit
                else execution.reason_code
            )
        ),
        diagnostic=(
            execution.diagnostic
            or (sanitize_evidence(error_limit.group(0), 512) if error_limit else None)
        ),
    )
