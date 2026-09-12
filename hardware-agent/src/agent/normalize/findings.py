"""Normalization of NSE output into shared finding payloads."""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Mapping, Sequence
from datetime import datetime
from typing import Any

from agent.normalize.contracts import FindingPayload
from agent.scanner.models import HostInfo, PortInfo, ScriptResult

CVE_PATTERN = re.compile(r"\bCVE-\d{4}-\d{4,}\b", re.IGNORECASE)
URL_PATTERN = re.compile(r"https?://\S+")


def extract_findings(hosts: list[HostInfo]) -> list[FindingPayload]:
    """Convert parsed NSE results into the shared `findings` payload."""

    findings: list[FindingPayload] = []
    seen: set[tuple[str, int | None, int | None, str, str]] = set()

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
    seen: set[tuple[str, int | None, int | None, str, str]],
    finding: FindingPayload,
) -> None:
    key = (
        str(finding.ip) if finding.ip is not None else "global",
        finding.port,
        finding.unit_id,
        finding.source_script or "unknown-script",
        finding.cve_id or finding.title,
    )
    if key in seen:
        return
    seen.add(key)
    findings.append(finding)


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
    generic = _extract_generic_vuln_table_findings(host, port, script)
    if generic:
        return generic

    cves = sorted(set(CVE_PATTERN.findall(script.output)))
    if not cves:
        return []

    return [
        _base_finding(
            host,
            port,
            severity="high",
            title=f"{cve.upper()} reported by {script.script_id}",
            description=(
                f"The NSE script {script.script_id} reported {cve.upper()} for "
                f"{_service_label(port)} on {host.ip}."
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
) -> list[FindingPayload]:
    findings: list[FindingPayload] = []
    for candidate in _walk_mappings(script.data):
        title = _lookup(candidate, "title")
        description = _lookup(candidate, "description")
        state = (_lookup(candidate, "state") or "").lower()
        if not title or not description:
            continue
        if "vuln" not in state and "exploit" not in state and "dos" not in state:
            continue

        ids = candidate.get("IDS") or candidate.get("ids")
        cve_id = None
        if isinstance(ids, Mapping):
            raw_cve = ids.get("CVE") or ids.get("cve")
            if isinstance(raw_cve, str) and CVE_PATTERN.fullmatch(raw_cve):
                cve_id = raw_cve.upper()

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
    return findings


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
