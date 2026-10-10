"""Normalization of NSE output into shared finding payloads."""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Mapping, Sequence
from datetime import datetime
from typing import Any

from agent.normalize.contracts import FindingPayload
from agent.scanner.models import HostInfo, PortInfo, ScriptResult
from agent.targeted.models import TargetedIssue, TargetedUnitResult

CVE_PATTERN = re.compile(r"\bCVE-\d{4}-\d{4,}\b", re.IGNORECASE)
URL_PATTERN = re.compile(r"https?://\S+")


def extract_findings(hosts: list[HostInfo]) -> list[FindingPayload]:
    """Convert general and targeted evidence into the shared findings payload."""

    findings: list[FindingPayload] = []
    seen: dict[tuple[object, ...], int] = {}

    for host in hosts:
        for script in host.host_scripts:
            for finding in _extract_script_findings(host, None, script):
                _append_unique(findings, seen, finding)

        for port in host.ports:
            for script in port.scripts:
                for finding in _extract_script_findings(host, port, script):
                    _append_unique(findings, seen, finding)

        for finding in _extract_modbus_read_findings(host):
            _append_unique(findings, seen, finding)

        for result in host.targeted_results:
            port = next(
                (
                    candidate
                    for candidate in host.ports
                    if candidate.port == result.unit.port
                    and candidate.protocol == result.unit.protocol
                ),
                None,
            )
            for issue in result.issues:
                _append_unique(
                    findings,
                    seen,
                    _targeted_finding(host, port, result, issue),
                )

    return findings


def _extract_modbus_read_findings(host: HostInfo) -> list[FindingPayload]:
    port_index = {port.port: port for port in host.ports}
    findings: list[FindingPayload] = []
    for service in host.industrial_services:
        for unit in service.units:
            readable = [
                item for item in unit.address_ranges if item.status == "readable"
            ]
            if not readable:
                continue
            evidence = "; ".join(
                f"Unit {unit.unit_id} FC{_function_code(item.address_space):02d} "
                f"addresses {item.start_address}-{item.start_address + item.count - 1}"
                for item in readable
            )
            evidence += ". No Modbus write function was sent."
            findings.append(
                _base_finding(
                    host,
                    port_index.get(service.port),
                    severity="medium",
                    title="Unauthenticated Modbus data read is reachable",
                    description=(
                        "An authorised read-only probe received Modbus process data "
                        "without application-layer authentication."
                    ),
                    recommendation=(
                        "Restrict Modbus TCP to required peers and maintenance "
                        "paths, monitor read requests, and use an authenticated "
                        "security layer where supported."
                    ),
                    evidence=evidence,
                    source="modbus-read-only-assessment",
                    source_script=None,
                    unit_id=unit.unit_id,
                )
            )
    return findings


def _function_code(address_space: str) -> int:
    return {
        "coil": 1,
        "discrete_input": 2,
        "holding_register": 3,
        "input_register": 4,
    }[address_space]


def _append_unique(
    findings: list[FindingPayload],
    seen: dict[tuple[object, ...], int],
    finding: FindingPayload,
) -> None:
    key = finding_dedupe_key(finding)
    existing_index = seen.get(key)
    if existing_index is None:
        seen[key] = len(findings)
        findings.append(finding)
        return
    existing = findings[existing_index]
    preferred, other = _preferred_finding(existing, finding)
    richer = _richer_source_finding(existing, finding)
    content = {
        "references": sorted(set(existing.references + finding.references)),
        "evidence": _merge_evidence(
            preferred.evidence,
            other.evidence,
            preferred.source,
            other.source,
        ),
    }
    for field in _MERGE_FIELDS_FROM_HIGHER_RANK:
        content[field] = getattr(richer, field)
    if preferred is existing:
        merged = existing.model_copy(update=content)
    else:
        merged = preferred.model_copy(update=content)
    findings[existing_index] = merged


def finding_dedupe_key(finding: FindingPayload) -> tuple[object, ...]:
    """Return the source-independent identity used for finding reconciliation."""

    identity = finding.cve_id.upper() if finding.cve_id else _finding_identity(finding)
    return (
        str(finding.ip) if finding.ip is not None else "global",
        finding.port,
        finding.unit_id,
        finding.protocol,
        identity,
    )


def _finding_identity(finding: FindingPayload) -> str:
    if finding.issue_key:
        return finding.issue_key
    text = f"{finding.title} {finding.source_script or ''}".casefold()
    if "ftp" in text and "anonymous" in text:
        return "ftp:anonymous-login"
    if "ftp" in text and "cleartext" in text:
        return "ftp:cleartext"
    if "telnet" in text or ("cleartext" in text and "remote" in text):
        return "telnet:cleartext"
    if "smb" in text and "anonymous" in text:
        return "smb:anonymous-session"
    if "smb" in text and "signing" in text:
        return "smb:signing"
    if "smbv1" in text or "smb v1" in text:
        return "smb:protocol:smbv1"
    if "tls" in text or "ssl" in text:
        if "expired" in text:
            return "tls.certificate:expired"
        if "self-signed" in text:
            return "tls.certificate:self-signed"
        if "signature" in text:
            return "tls.certificate:weak-signature"
        if "public key" in text:
            return "tls.certificate:weak-key"
        for protocol in ("sslv3", "tlsv1.0", "tls1.0", "tlsv1.1", "tls1.1"):
            if protocol in text:
                return f"tls.protocol:{protocol}"
        if "cipher" in text:
            evidence = finding.evidence.casefold()
            for primitive in ("rc4", "3des", "des", "null", "export"):
                if primitive in evidence:
                    return f"tls.cipher:{primitive}"
            return f"title:{finding.title.casefold().strip()}:{evidence}"
    return f"title:{finding.title.casefold().strip()}"


def _severity_rank(value: str) -> int:
    return {"low": 1, "medium": 2, "high": 3, "critical": 4}.get(value, 0)


SOURCE_RANK: dict[str, int] = {
    "targeted_service_assessment": 1,
}

_MERGE_FIELDS_FROM_HIGHER_RANK = ("description", "recommendation")


def _source_rank(source: str) -> int:
    return SOURCE_RANK.get(source, 0)


def _richer_source_finding(
    first: FindingPayload, second: FindingPayload
) -> FindingPayload:
    if _source_rank(second.source) > _source_rank(first.source):
        return second
    return first


def _preferred_finding(
    first: FindingPayload, second: FindingPayload
) -> tuple[FindingPayload, FindingPayload]:
    if _severity_rank(second.severity) > _severity_rank(first.severity):
        return second, first
    if _severity_rank(first.severity) > _severity_rank(second.severity):
        return first, second
    if _source_rank(second.source) > _source_rank(first.source):
        return second, first
    return first, second


def _merge_evidence(
    preferred: str,
    other: str,
    preferred_source: str | None,
    other_source: str | None,
) -> str:
    if not other or other == preferred:
        return preferred
    label = f"corroborated by {other_source or preferred_source or 'another source'}"
    if label.casefold() in preferred.casefold():
        return preferred
    return f"{preferred}; {label}"


def _targeted_finding(
    host: HostInfo,
    port: PortInfo | None,
    result: TargetedUnitResult,
    issue: TargetedIssue,
) -> FindingPayload:
    return _base_finding(
        host,
        port,
        severity=issue.severity,
        title=issue.title,
        description=issue.description,
        recommendation=issue.recommendation,
        evidence=issue.evidence,
        source="targeted_service_assessment",
        source_script=result.unit.tool.value,
        issue_key=issue.issue_key,
        cve_id=issue.cve_id,
        cvss_score=issue.cvss_score,
        references=issue.references,
    )


def _extract_script_findings(
    host: HostInfo,
    port: PortInfo | None,
    script: ScriptResult,
) -> list[FindingPayload]:
    extractor = _EXTRACTORS.get(script.script_id)
    if extractor is not None:
        return extractor(host, port, script)
    return _extract_generic_findings(host, port, script)


def _extract_generic_findings(
    host: HostInfo,
    port: PortInfo | None,
    script: ScriptResult,
) -> list[FindingPayload]:
    recognized, generic = _extract_generic_vuln_table_findings(host, port, script)
    if recognized:
        return generic

    cves = sorted(set(CVE_PATTERN.findall(script.output)))
    lowered_output = script.output.casefold()
    if not cves or any(
        marker in lowered_output
        for marker in ("not vulnerable", "unable to test", "could not test", "error")
    ):
        return []

    return [
        _base_finding(
            host,
            port,
            severity="low",
            title=f"{cve.upper()} reported by {script.script_id}",
            description=(
                f"The NSE script {script.script_id} mentioned {cve.upper()} for "
                f"{_service_label(port)} on {host.ip}; no structured positive result "
                "was recorded."
            ),
            recommendation=(
                "Review the affected service and apply the vendor patch or mitigation "
                "referenced by the NSE script output."
            ),
            evidence=(
                script.output
                or f"NSE script {script.script_id} reported {cve.upper()}."
            ),
            source="nmap_nse",
            source_script=script.script_id,
            cve_id=cve.upper(),
            references=_extract_urls(script.output),
        )
        for cve in cves
    ]


def _extract_vulners_findings(
    host: HostInfo,
    port: PortInfo | None,
    script: ScriptResult,
) -> list[FindingPayload]:
    if port is None or not isinstance(script.data, Mapping):
        return []

    findings: list[FindingPayload] = []
    for lookup_key, advisories in script.data.items():
        advisory_items = (
            advisories
            if isinstance(advisories, Sequence)
            and not isinstance(advisories, (str, bytes))
            else [advisories]
        )
        for advisory in advisory_items:
            if not isinstance(advisory, Mapping):
                continue

            advisory_id = str(advisory.get("id", "")).upper()
            if not advisory_id or not CVE_PATTERN.fullmatch(advisory_id):
                continue

            score = _coerce_float(advisory.get("cvss"))
            evidence = (
                f"vulners matched {_service_label(port)} on {host.ip}:{port.port} "
                f"to {advisory_id} via {lookup_key}."
            )
            findings.append(
                _base_finding(
                    host,
                    port,
                    severity=_severity_from_cvss(score),
                    title=f"Known CVE detected via vulners: {advisory_id}",
                    description=(
                        f"The service {_service_label(port)} exposed by "
                        f"{host.ip}:{port.port} "
                        f"was correlated by the vulners NSE script with the known "
                        f"vulnerability {advisory_id}."
                    ),
                    recommendation=(
                        "Validate the affected product/version, apply the vendor fix, "
                        "and restrict exposure of the service until remediation "
                        "is complete."
                    ),
                    evidence=evidence,
                    source="nmap_vulners",
                    source_script="vulners",
                    cve_id=advisory_id,
                    cvss_score=score,
                    references=[f"https://vulners.com/cve/{advisory_id}"],
                )
            )
    return findings


def _extract_smb_signing_finding(
    host: HostInfo,
    port: PortInfo | None,
    script: ScriptResult,
) -> FindingPayload | None:
    haystack = f"{script.output}\n{_stringify(script.data)}".lower()
    if "message_signing" not in haystack and "signing" not in haystack:
        return None
    if (
        "disabled" not in haystack
        and "not required" not in haystack
        and "dangerous" not in haystack
    ):
        return None

    evidence = (
        script.output
        or "smb2-security-mode reported SMB signing disabled or not required."
    )
    location = f" on TCP/{port.port}" if port is not None else ""
    return _base_finding(
        host,
        port,
        severity="medium",
        title="SMB signing disabled",
        description=(
            f"The host {host.ip} exposes SMB{location} with message signing "
            "disabled or not required, which can enable tampering or relay attacks."
        ),
        recommendation=(
            "Require SMB signing on the server and restrict SMB exposure to trusted "
            "segments and approved clients."
        ),
        evidence=evidence,
        source="nmap_nse",
        source_script=script.script_id,
    )


def _extract_smbv1_finding(
    host: HostInfo,
    port: PortInfo | None,
    script: ScriptResult,
) -> FindingPayload | None:
    haystack = f"{script.output}\n{_stringify(script.data)}".lower()
    if "smbv1" not in haystack and "nt lm 0.12" not in haystack:
        return None

    location = f" on TCP/{port.port}" if port is not None else ""
    return _base_finding(
        host,
        port,
        severity="high",
        title="SMBv1 protocol enabled",
        description=(
            f"The host {host.ip} appears to support SMBv1{location}, "
            "which is deprecated and associated with multiple legacy attack paths."
        ),
        recommendation=(
            "Disable SMBv1 on the affected host, restrict SMB exposure, and keep "
            "the operating system and file-sharing stack fully patched."
        ),
        evidence=(
            script.output
            or _stringify(script.data)
            or "smb-protocols reported SMBv1 support."
        ),
        source="nmap_nse",
        source_script=script.script_id,
    )


def _extract_http_methods_finding(
    host: HostInfo,
    port: PortInfo | None,
    script: ScriptResult,
) -> FindingPayload | None:
    if port is None:
        return None

    risky_methods = []
    haystack = f"{script.output}\n{_stringify(script.data)}".upper()
    for method in ("PUT", "DELETE", "TRACE", "CONNECT"):
        if re.search(rf"\b{method}\b", haystack):
            risky_methods.append(method)

    if not risky_methods:
        return None

    risky_methods.sort()
    return _base_finding(
        host,
        port,
        severity="medium",
        title="Potentially risky HTTP methods enabled",
        description=(
            f"The HTTP service on {host.ip}:{port.port} appears to allow the "
            f"following methods: {', '.join(risky_methods)}."
        ),
        recommendation=(
            "Restrict HTTP methods to those required by the application and "
            "disable unused verbs such as PUT, DELETE, TRACE, or CONNECT."
        ),
        evidence=script.output or _stringify(script.data),
        source="nmap_nse",
        source_script=script.script_id,
    )


def _extract_ssh_auth_methods_finding(
    host: HostInfo,
    port: PortInfo | None,
    script: ScriptResult,
) -> FindingPayload | None:
    if port is None:
        return None

    haystack = f"{script.output}\n{_stringify(script.data)}".lower()
    if "password" not in haystack:
        return None

    return _base_finding(
        host,
        port,
        severity="low",
        title="SSH password authentication exposed",
        description=(
            f"The SSH service on {host.ip}:{port.port} appears to allow password-based "
            "authentication, which increases brute-force and "
            "credential-stuffing exposure."
        ),
        recommendation=(
            "Prefer key-based SSH authentication, restrict network exposure, and "
            "rate-limit or monitor login attempts."
        ),
        evidence=script.output or _stringify(script.data),
        source="nmap_nse",
        source_script=script.script_id,
    )


def _parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _extract_ssl_cert_findings(
    host: HostInfo,
    port: PortInfo | None,
    script: ScriptResult,
) -> list[FindingPayload]:
    data = script.data
    if port is None or not isinstance(data, Mapping):
        return []

    findings: list[FindingPayload] = []

    validity = _lookup(data, "validity")
    not_after = _lookup(validity, "notAfter") if isinstance(validity, Mapping) else None
    expiry = _parse_timestamp(not_after)
    if expiry is not None and expiry < datetime.now():
        findings.append(
            _base_finding(
                host,
                port,
                severity="high",
                title="TLS certificate expired",
                description=(
                    f"The TLS certificate on {host.ip}:{port.port} expired on "
                    f"{not_after}."
                ),
                recommendation=(
                    "Renew the certificate and automate rotation before expiry."
                ),
                evidence=script.output or f"notAfter={not_after}",
                source="nmap_nse",
                source_script=script.script_id,
            )
        )

    subject = _lookup(data, "subject")
    issuer = _lookup(data, "issuer")
    if subject and issuer and subject == issuer:
        findings.append(
            _base_finding(
                host,
                port,
                severity="medium",
                title="Self-signed TLS certificate",
                description=(
                    f"The TLS certificate on {host.ip}:{port.port} is self-signed "
                    "(subject matches issuer)."
                ),
                recommendation=(
                    "Replace with a certificate from a trusted CA for "
                    "externally-reachable services."
                ),
                evidence=script.output or _stringify(subject),
                source="nmap_nse",
                source_script=script.script_id,
            )
        )

    sig_algo = _stringify(_lookup(data, "sig_algo")).lower()
    if "sha1" in sig_algo or "md5" in sig_algo:
        findings.append(
            _base_finding(
                host,
                port,
                severity="medium",
                title="Weak TLS certificate signature",
                description=(
                    f"The TLS certificate on {host.ip}:{port.port} is signed with a "
                    f"weak algorithm ({sig_algo})."
                ),
                recommendation="Reissue the certificate using SHA-256 or stronger.",
                evidence=script.output or sig_algo,
                source="nmap_nse",
                source_script=script.script_id,
            )
        )

    pubkey = _lookup(data, "pubkey")
    bits = (
        _coerce_float(_lookup(pubkey, "bits")) if isinstance(pubkey, Mapping) else None
    )
    if bits is not None and bits < 2048:
        findings.append(
            _base_finding(
                host,
                port,
                severity="medium",
                title="Weak TLS public key",
                description=(
                    f"The TLS certificate on {host.ip}:{port.port} uses a "
                    f"{int(bits)}-bit key, below the 2048-bit minimum."
                ),
                recommendation=(
                    "Reissue the certificate with a 2048-bit or larger key."
                ),
                evidence=script.output or f"bits={int(bits)}",
                source="nmap_nse",
                source_script=script.script_id,
            )
        )

    return findings


def _extract_weak_cipher_findings(
    host: HostInfo,
    port: PortInfo | None,
    script: ScriptResult,
) -> list[FindingPayload]:
    data = script.data
    if port is None or not isinstance(data, Mapping):
        return []

    findings: list[FindingPayload] = []

    for protocol in ("SSLv3", "TLSv1.0"):
        if isinstance(_lookup(data, protocol), Mapping):
            findings.append(
                _base_finding(
                    host,
                    port,
                    severity="medium",
                    title=f"Deprecated TLS/SSL protocol offered: {protocol}",
                    description=(
                        f"{host.ip}:{port.port} offers the deprecated {protocol} "
                        "protocol."
                    ),
                    recommendation=f"Disable {protocol}; require TLS 1.2 or higher.",
                    evidence=script.output or protocol,
                    source="nmap_nse",
                    source_script=script.script_id,
                )
            )

    seen_warnings: set[str] = set()
    for value in data.values():
        if not isinstance(value, Mapping):
            continue
        warnings = value.get("warnings")
        if not isinstance(warnings, Sequence) or isinstance(warnings, (str, bytes)):
            continue
        for warning in warnings:
            text = _stringify(warning)
            if not text or text in seen_warnings:
                continue
            seen_warnings.add(text)
            findings.append(
                _base_finding(
                    host,
                    port,
                    severity="medium",
                    title="Weak TLS cipher configuration",
                    description=f"{host.ip}:{port.port}: {text}",
                    recommendation=(
                        "Disable the affected ciphers/protocols and prefer modern "
                        "AEAD suites."
                    ),
                    evidence=text,
                    source="nmap_nse",
                    source_script=script.script_id,
                )
            )

    least = _stringify(_lookup(data, "least strength")).upper()
    if least in {"C", "D", "E", "F"}:
        findings.append(
            _base_finding(
                host,
                port,
                severity="medium",
                title=f"Weak TLS cipher strength (grade {least})",
                description=(
                    f"The weakest cipher offered by {host.ip}:{port.port} graded "
                    f"{least}."
                ),
                recommendation="Remove low-grade ciphers; prefer A-grade suites.",
                evidence=script.output or f"least strength={least}",
                source="nmap_nse",
                source_script=script.script_id,
            )
        )

    return findings


def _extract_ftp_anon_finding(
    host: HostInfo,
    port: PortInfo | None,
    script: ScriptResult,
) -> FindingPayload | None:
    if port is None:
        return None

    haystack = f"{script.output}\n{_stringify(script.data)}"
    if "anonymous ftp login allowed" not in haystack.lower():
        return None

    writeable = "[NSE: writeable]" in haystack
    severity = "critical" if writeable else "high"
    description = f"The FTP service on {host.ip}:{port.port} allows anonymous login" + (
        " and exposes a writeable directory."
        if writeable
        else ", which can disclose files to unauthenticated users."
    )
    return _base_finding(
        host,
        port,
        severity=severity,
        title="Anonymous FTP login allowed",
        description=description,
        recommendation=(
            "Disable anonymous FTP access, or restrict it to a controlled, "
            "read-only directory."
        ),
        evidence=script.output or "Anonymous FTP login allowed",
        source="nmap_nse",
        source_script=script.script_id,
    )


def _extract_generic_vuln_table_findings(
    host: HostInfo,
    port: PortInfo | None,
    script: ScriptResult,
) -> tuple[bool, list[FindingPayload]]:
    findings: list[FindingPayload] = []
    recognized = False
    for candidate in _walk_mappings(script.data):
        has_state_or_ids = any(
            str(key).casefold() in {"state", "ids"} for key in candidate
        )
        state_value = _lookup(candidate, "state")
        ids = _lookup(candidate, "ids")
        if not has_state_or_ids:
            continue
        recognized = True
        state = " ".join(str(state_value or "").split()).casefold()
        if state not in {
            "vulnerable",
            "vulnerable (dos)",
            "vulnerable (exploitable)",
        }:
            continue

        title = _lookup(candidate, "title")
        description = _lookup(candidate, "description")
        cves = _structured_cves(ids)
        cve_id = cves[0] if cves else None
        if not title:
            title = cve_id or f"NSE positive result from {script.script_id}"
        if not description:
            description = (
                f"The NSE script {script.script_id} declared a positive result; "
                "the available structured record has no description."
            )

        check_results = candidate.get("check_results") or candidate.get("check-results")
        evidence = _stringify(check_results) or script.output or str(title)
        findings.append(
            _base_finding(
                host,
                port,
                severity=_severity_from_risk_factor(_lookup(candidate, "risk_factor")),
                title=str(title),
                description=str(description),
                recommendation=(
                    "Review the upstream advisory referenced by the NSE script and "
                    "apply the vendor fix or mitigation."
                ),
                evidence=evidence,
                source="nmap_nse",
                source_script=script.script_id,
                cve_id=cve_id,
                cvss_score=_coerce_float(_lookup(candidate, "cvss")),
                references=_extract_urls(_stringify(candidate)),
            )
        )
    return recognized, findings


def _structured_cves(value: Any) -> list[str]:
    found: set[str] = set()
    if isinstance(value, Mapping):
        for key, nested in value.items():
            if str(key).casefold() == "cve":
                candidates = (
                    nested
                    if isinstance(nested, Sequence)
                    and not isinstance(nested, (str, bytes))
                    else [nested]
                )
                for candidate in candidates:
                    if isinstance(candidate, str):
                        normalized = _normalize_structured_cve(candidate)
                        if normalized:
                            found.add(normalized)
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        for nested in value:
            found.update(_structured_cves(nested))
    elif isinstance(value, str):
        normalized = _normalize_structured_cve(value)
        if normalized:
            found.add(normalized)
    return sorted(found)


def _normalize_structured_cve(value: str) -> str | None:
    normalized = value.strip()
    if normalized.casefold().startswith("cve:"):
        normalized = normalized[4:]
    return normalized.upper() if CVE_PATTERN.fullmatch(normalized) else None


def _base_finding(
    host: HostInfo,
    port: PortInfo | None,
    *,
    severity: str,
    title: str,
    description: str,
    recommendation: str,
    evidence: str,
    source: str,
    source_script: str | None,
    cve_id: str | None = None,
    cvss_score: float | None = None,
    references: list[str] | None = None,
    unit_id: int | None = None,
    issue_key: str | None = None,
) -> FindingPayload:
    protocol = (
        port.protocol if port is not None and port.protocol in {"tcp", "udp"} else None
    )
    service_name = port.service.name if port is not None and port.service.name else None
    return FindingPayload(
        ip=host.ip,
        port=port.port if port is not None else None,
        unit_id=unit_id,
        protocol=protocol,
        service=service_name,
        source=source,
        source_script=source_script,
        issue_key=issue_key,
        cve_id=cve_id,
        cvss_score=cvss_score,
        severity=severity,  # type: ignore[arg-type]
        title=title,
        description=description,
        recommendation=recommendation,
        evidence=evidence,
        references=references or [],
    )


def _lookup(mapping: Mapping[str, Any], key: str) -> Any:
    if key in mapping:
        return mapping[key]
    lowered = {str(k).lower(): value for k, value in mapping.items()}
    return lowered.get(key.lower())


def _walk_mappings(value: Any) -> Iterable[Mapping[str, Any]]:
    if isinstance(value, Mapping):
        yield value
        for nested in value.values():
            yield from _walk_mappings(nested)
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        for nested in value:
            yield from _walk_mappings(nested)


def _coerce_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _severity_from_cvss(score: float | None) -> str:
    if score is None:
        return "medium"
    if score >= 9.0:
        return "critical"
    if score >= 7.0:
        return "high"
    if score >= 4.0:
        return "medium"
    return "low"


def _severity_from_risk_factor(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in {"critical", "high", "medium", "low"}:
        return normalized
    return "medium"


def _extract_urls(text: str) -> list[str]:
    return sorted(set(URL_PATTERN.findall(text)))


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, Mapping):
        return " ".join(_stringify(item) for item in value.values() if _stringify(item))
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return " ".join(_stringify(item) for item in value if _stringify(item))
    return str(value)


def _service_label(port: PortInfo | None) -> str:
    if port is None:
        return "host-level observation"
    label = port.service.banner or port.service.name or "unknown service"
    if port.protocol == "tcp":
        return f"{label} (TCP/{port.port})"
    return f"{label} ({port.protocol}/{port.port})"


_SingleExtractor = Callable[
    [HostInfo, "PortInfo | None", ScriptResult], "FindingPayload | None"
]
_ListExtractor = Callable[
    [HostInfo, "PortInfo | None", ScriptResult], list[FindingPayload]
]


def _single(extractor: _SingleExtractor) -> _ListExtractor:
    def _wrapped(
        host: HostInfo,
        port: PortInfo | None,
        script: ScriptResult,
    ) -> list[FindingPayload]:
        finding = extractor(host, port, script)
        return [finding] if finding is not None else []

    return _wrapped


_EXTRACTORS: dict[str, _ListExtractor] = {
    "vulners": _extract_vulners_findings,
    "smb2-security-mode": _single(_extract_smb_signing_finding),
    "smb-protocols": _single(_extract_smbv1_finding),
    "http-methods": _single(_extract_http_methods_finding),
    "ssh-auth-methods": _single(_extract_ssh_auth_methods_finding),
    "ssl-cert": _extract_ssl_cert_findings,
    "ssl-enum-ciphers": _extract_weak_cipher_findings,
    "ftp-anon": _single(_extract_ftp_anon_finding),
}
