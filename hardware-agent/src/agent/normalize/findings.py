"""Normalization of NSE output into shared finding payloads."""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

from agent.normalize.contracts import (
    FindingEvidenceObservationPayload,
    FindingPayload,
)
from agent.scanner.models import HostInfo, PortInfo, ScriptResult
from agent.targeted.models import TargetedIssue, TargetedUnitResult

CVE_PATTERN = re.compile(r"\bCVE-\d{4}-\d{4,}\b", re.IGNORECASE)
URL_PATTERN = re.compile(r"https?://\S+")


@dataclass(frozen=True, slots=True)
class LocalFindingEvidenceAssessment:
    method: str
    status: str
    confidence: str


def assess_local_evidence(finding: FindingPayload) -> LocalFindingEvidenceAssessment:
    """Apply the backend's closed evidence predicates to retained local witnesses."""
    supported = [
        item
        for item in finding.evidence_observations
        if _supported_local_observation(item, finding)
    ]
    direct = [item for item in supported if item.method != "version_correlation"]
    positive_direct = [item for item in direct if item.result == "positive"]
    negative_direct = [item for item in direct if item.result == "negative"]
    correlations = [item for item in supported if item.method == "version_correlation"]

    def endpoint(item: FindingEvidenceObservationPayload) -> tuple[object, ...]:
        return (item.ip, item.protocol, item.port, item.unit_id, item.condition_key)

    conflicting = any(
        endpoint(negative) == endpoint(positive) and negative.method == positive.method
        for negative in negative_direct
        for positive in positive_direct
    ) or any(
        endpoint(negative) == endpoint(correlation)
        and negative.condition_key == correlation.condition_key
        for negative in negative_direct
        for correlation in correlations
    )
    if positive_direct:
        best = min(
            positive_direct,
            key=lambda item: (item.method, item.rule_id, item.condition_key),
        )
        if conflicting:
            return LocalFindingEvidenceAssessment(
                best.method, "conflicting", "tentative"
            )
        if finding.evidence_truncated:
            return LocalFindingEvidenceAssessment(
                best.method, "inconclusive", "tentative"
            )
        return LocalFindingEvidenceAssessment(best.method, "supported", "confirmed")
    if correlations:
        best = min(
            correlations,
            key=lambda item: (item.method, item.rule_id, item.condition_key),
        )
        if conflicting:
            return LocalFindingEvidenceAssessment(
                best.method, "conflicting", "tentative"
            )
        if finding.evidence_truncated:
            return LocalFindingEvidenceAssessment(
                best.method, "inconclusive", "tentative"
            )
        return LocalFindingEvidenceAssessment(best.method, "supported", "probable")
    if negative_direct:
        best = min(
            negative_direct,
            key=lambda item: (item.method, item.rule_id, item.condition_key),
        )
        return LocalFindingEvidenceAssessment(best.method, "inconclusive", "tentative")
    if any(
        item.method == "textual_reference" for item in finding.evidence_observations
    ):
        return LocalFindingEvidenceAssessment(
            "textual_reference", "inconclusive", "tentative"
        )
    return LocalFindingEvidenceAssessment("unknown", "inconclusive", "tentative")


def _condition_matches_finding(
    item: FindingEvidenceObservationPayload, finding: FindingPayload
) -> bool:
    """Mirror backend condition selection before applying local predicates."""
    cve_condition = item.method == "version_correlation" or (
        item.method == "specific_check"
        and (item.rule_id.endswith("ms17-010") or finding.issue_key == finding.cve_id)
    )
    expected = finding.cve_id if cve_condition else finding.issue_key
    return expected is not None and item.condition_key == expected


def _tls_primitive(evidence: str) -> str | None:
    normalized = evidence.casefold()
    return next(
        (
            value
            for value in ("rc4", "3des", "des", "null", "export")
            if value in normalized
        ),
        None,
    )


def _tls_condition(item: FindingEvidenceObservationPayload) -> str:
    normalized = item.evidence.casefold().strip()
    primitive = _tls_primitive(item.evidence)
    if item.rule_id == "nse:ssl-enum-ciphers-warning":
        return (
            f"tls.cipher:{primitive}"
            if primitive
            else f"title:weak tls cipher configuration:{normalized}"
        )
    if item.rule_id == "nse:ssl-enum-ciphers-grade":
        if primitive:
            return f"tls.cipher:{primitive}"
        grade = str(item.facts.get("weakest_grade", "")).casefold()
        title = f"weak tls cipher strength (grade {grade})"
        return f"title:{title}:{normalized}"
    return ""


def _supported_local_observation(
    item: FindingEvidenceObservationPayload, finding: FindingPayload
) -> bool:
    if not _condition_matches_finding(item, finding):
        return False
    endpoint_matches = (
        item.ip == finding.ip
        and item.port == finding.port
        and item.protocol == finding.protocol
        and item.unit_id == finding.unit_id
    )
    endpoint = (
        endpoint_matches
        and item.ip is not None
        and item.port is not None
        and item.protocol == "tcp"
    )
    if item.rule_id == "catalog:nmap-vulners":
        return (
            item.method == "version_correlation"
            and item.result == "positive"
            and item.rule_version == "1"
            and item.source == "nmap_vulners"
            and endpoint
            and finding.cve_id is not None
            and item.condition_key == finding.cve_id
            and set(item.facts) == {"cpe", "cve_id"}
            and isinstance(item.facts.get("cpe"), str)
            and bool(item.facts.get("cpe"))
            and item.facts.get("cve_id") == finding.cve_id
            and endpoint_matches
        )
    grade_condition = (
        "title:weak tls cipher strength (grade "
        + str(item.facts.get("weakest_grade", "")).casefold()
        + "):"
        + item.evidence.casefold().strip()
    )
    configuration: dict[str, tuple[str, str, object, str]] = {
        "nse:smb2-security-mode": (
            "smb:signing",
            "signing_required",
            False,
            "smb2-security-mode",
        ),
        "nse:smb-protocols": (
            "smb:protocol:smbv1",
            "dialect",
            "SMBv1",
            "smb-protocols",
        ),
        "nse:http-methods": (
            "title:potentially risky http methods enabled",
            "risky_method",
            None,
            "http-methods",
        ),
        "nse:ssh-auth-methods": (
            "title:ssh password authentication exposed",
            "password_authentication",
            True,
            "ssh-auth-methods",
        ),
        "nse:ssl-cert-expired": (
            "tls.certificate:expired",
            "certificate_expired",
            True,
            "ssl-cert",
        ),
        "nse:ssl-cert-self-signed": (
            "tls.certificate:self-signed",
            "subject_matches_issuer",
            True,
            "ssl-cert",
        ),
        "nse:ssl-cert-weak-signature": (
            "tls.certificate:weak-signature",
            "signature_algorithm",
            None,
            "ssl-cert",
        ),
        "nse:ssl-cert-weak-key": (
            "tls.certificate:weak-key",
            "public_key_bits",
            None,
            "ssl-cert",
        ),
        "nse:ssl-enum-ciphers-protocol": (
            f"tls.protocol:{str(item.facts.get('protocol', '')).casefold()}",
            "protocol",
            None,
            "ssl-enum-ciphers",
        ),
        "nse:ssl-enum-ciphers-warning": (
            "",
            "weak_cipher",
            None,
            "ssl-enum-ciphers",
        ),
        "nse:ssl-enum-ciphers-grade": (
            grade_condition,
            "weakest_grade",
            None,
            "ssl-enum-ciphers",
        ),
    }
    expected = configuration.get(item.rule_id)
    if expected is not None:
        condition, fact, value, script = expected
        observed = item.facts.get(fact)
        positive_value = type(observed) is type(value) and observed == value
        if item.rule_id == "nse:http-methods":
            positive_value = type(observed) is str and observed in {
                "PUT",
                "DELETE",
                "TRACE",
                "CONNECT",
            }
        elif item.rule_id == "nse:ssl-cert-weak-signature":
            positive_value = type(observed) is str and observed in {"sha1", "md5"}
        elif item.rule_id == "nse:ssl-cert-weak-key":
            positive_value = type(observed) is int and observed < 2048
        elif item.rule_id == "nse:ssl-enum-ciphers-protocol":
            positive_value = type(observed) is str and observed in {"SSLv3", "TLSv1.0"}
        elif item.rule_id == "nse:ssl-enum-ciphers-warning":
            allowed_ciphers = {
                "RC4",
                "3DES",
                "DES",
                "NULL",
                "EXPORT",
                "aNULL",
                "anonymous",
            }
            primitive = _tls_primitive(item.evidence)
            positive_value = (
                type(observed) is str
                and observed in allowed_ciphers
                and (primitive is None or observed.casefold() == primitive)
            )
        elif item.rule_id == "nse:ssl-enum-ciphers-grade":
            positive_value = type(observed) is str and observed in {"C", "D", "E", "F"}
        negative_value = (
            type(observed) is str
            and observed in {"GET", "HEAD", "POST", "OPTIONS", "PATCH"}
            if item.rule_id == "nse:http-methods"
            else type(observed) is bool and observed is not value
            if type(value) is bool
            else type(observed) is str and observed in {"SMBv2", "SMBv3"}
        )
        if (
            item.rule_id == "nse:ssl-cert-expired"
            or item.rule_id == "nse:ssl-cert-self-signed"
        ):
            negative_value = type(observed) is bool and observed is False
        elif item.rule_id == "nse:ssl-cert-weak-signature":
            negative_value = type(observed) is str and observed in {
                "sha256",
                "sha384",
                "sha512",
            }
        elif item.rule_id == "nse:ssl-cert-weak-key":
            negative_value = type(observed) is int and observed >= 2048
        elif item.rule_id == "nse:ssl-enum-ciphers-protocol":
            negative_value = type(observed) is str and observed in {
                "TLSv1.2",
                "TLSv1.3",
            }
        elif item.rule_id == "nse:ssl-enum-ciphers-grade":
            negative_value = type(observed) is str and observed in {"A", "B"}
        elif item.rule_id == "nse:ssl-enum-ciphers-warning":
            # Backend accepts the closed cipher fact for either declared result.
            negative_value = positive_value
        if item.rule_id in {
            "nse:ssl-enum-ciphers-warning",
            "nse:ssl-enum-ciphers-grade",
        }:
            condition = _tls_condition(item)
        return (
            item.method == "configuration_observation"
            and item.result in {"positive", "negative"}
            and item.rule_version == "1"
            and item.source == "nmap_nse"
            and item.source_script == script
            and item.condition_key == condition
            and set(item.facts) == {fact}
            and (positive_value if item.result == "positive" else negative_value)
            and endpoint
        )
    specific: dict[str, tuple[str, str, object, str]] = {
        "nse:ftp-anon": ("ftp:anonymous-login", "anonymous_login", True, "ftp-anon"),
        "targeted:ftp-check-anonymous": (
            "ftp:anonymous-login",
            "anonymous_login_accepted",
            True,
            "ftp-check",
        ),
        "targeted:enum4linux-ng-session": (
            "smb:anonymous-session",
            "session_type",
            "null",
            "enum4linux-ng",
        ),
        "modbus:read-only": (
            "title:unauthenticated modbus data read is reachable",
            "read_result",
            True,
            "modbus-read-only-assessment",
        ),
    }
    expected_specific = specific.get(item.rule_id)
    if item.rule_id == "nse:smb-vuln-ms17-010":
        return (
            item.method == "specific_check"
            and item.result in {"positive", "negative"}
            and item.rule_version == "1"
            and item.source == "nmap_nse"
            and item.source_script == "smb-vuln-ms17-010"
            and item.condition_key == "CVE-2017-0143"
            and finding.cve_id == "CVE-2017-0143"
            and item.port == 445
            and item.unit_id is None
            and endpoint
            and type(item.facts.get("vulnerability_state")) is str
            and item.facts.get("vulnerability_state")
            == ("VULNERABLE" if item.result == "positive" else "NOT VULNERABLE")
            and item.facts.get("table") == "smb-vuln-ms17-010"
            and set(item.facts) == {"vulnerability_state", "table"}
        )
    if expected_specific is None:
        return False
    condition, fact, value, script = expected_specific
    fact_matches = (
        type(item.facts.get(fact)) is str
        and item.facts.get(fact) in {"null", "guest"}
        and type(item.facts.get("accepted")) is bool
        and item.facts.get("accepted") is (item.result == "positive")
        and set(item.facts) == {fact, "accepted"}
        if item.rule_id == "targeted:enum4linux-ng-session"
        else type(item.facts.get(fact)) is type(value)
        and item.facts.get(fact)
        == (
            value
            if item.result == "positive"
            else False
            if type(value) is bool
            else "none"
        )
        and set(item.facts) == {fact}
    )
    return (
        item.method == "specific_check"
        and item.result in {"positive", "negative"}
        and item.rule_version == "1"
        and item.source_script == script
        and item.source
        == (
            "targeted_service_assessment"
            if item.rule_id.startswith("targeted:")
            else "modbus-read-only-assessment"
            if item.rule_id.startswith("modbus:")
            else "nmap_nse"
        )
        and item.condition_key == condition
        and fact_matches
        and endpoint
        and (item.rule_id != "modbus:read-only" or item.unit_id is not None)
    )


def extract_findings(
    hosts: list[HostInfo], *, include_evidence_metadata: bool = False
) -> list[FindingPayload]:
    """Convert general and targeted evidence into the shared findings payload."""

    findings, _, _ = extract_findings_and_observations(hosts)
    if include_evidence_metadata:
        return findings
    # Task 9 retains evidence at the internal extractor boundary. Task 10 opts in
    # only after it sets the scan-level policy version.
    return [
        item.model_copy(
            update={"evidence_observations": [], "evidence_truncated": False}
        )
        for item in findings
    ]


def extract_findings_and_observations(
    hosts: list[HostInfo],
) -> tuple[list[FindingPayload], list[FindingEvidenceObservationPayload], bool]:
    """Extract findings and bounded standalone negative/inconclusive evidence."""

    candidates: list[FindingPayload] = []
    standalone: list[FindingEvidenceObservationPayload] = []

    for host in hosts:
        for script in host.host_scripts:
            for finding in _extract_script_findings(host, None, script):
                candidates.append(finding)
            standalone.extend(
                _extract_standalone_nse_observations(host, None, script)
            )

        for port in host.ports:
            for script in port.scripts:
                for finding in _extract_script_findings(host, port, script):
                    candidates.append(finding)
                standalone.extend(
                    _extract_standalone_nse_observations(host, port, script)
                )

        for finding in _extract_modbus_read_findings(host):
            candidates.append(finding)

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
                candidates.append(_targeted_finding(host, port, result, issue))

    # A supported standalone negative for the same condition is a conflict
    # witness, so bind it to that finding before reducing duplicates. Unsupported
    # negatives and failures remain standalone and cannot downgrade a finding.
    remaining_standalone: list[FindingEvidenceObservationPayload] = []
    for observation in standalone:
        matching = [
            candidate
            for candidate in candidates
            if _supported_local_observation(observation, candidate)
        ]
        if matching and observation.result == "negative":
            for candidate in matching:
                candidate.evidence_observations.append(observation)
        else:
            remaining_standalone.append(observation)

    findings = _reduce_findings(candidates)
    unique: dict[str, FindingEvidenceObservationPayload] = {}
    for item in remaining_standalone:
        identity_key = _standalone_observation_key(item)
        unique[identity_key] = item
    ordered = [unique[key] for key in sorted(unique, key=str)]
    truncated = len(ordered) > 512
    return findings, ordered[:512], truncated


def _observation_scope_key(
    item: FindingEvidenceObservationPayload,
) -> tuple[object, ...]:
    return (
        str(item.ip) if item.ip is not None else None,
        item.protocol,
        item.port,
        item.unit_id,
        item.condition_key,
    )


def _standalone_observation_key(
    item: FindingEvidenceObservationPayload,
) -> str:
    """Retain distinct evidence/facts while deduplicating exact observations."""
    payload = item.model_dump(mode="json")
    payload["facts"] = dict(sorted(item.facts.items()))
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _extract_standalone_nse_observations(
    host: HostInfo,
    port: PortInfo | None,
    script: ScriptResult,
) -> list[FindingEvidenceObservationPayload]:
    """Keep explicit non-positive NSE states separate from positive findings."""

    observations: list[FindingEvidenceObservationPayload] = []
    for candidate in _walk_mappings(script.data):
        if not any(str(key).casefold() in {"state", "ids"} for key in candidate):
            continue
        state_value = _lookup(candidate, "state")
        state = (
            " ".join(state_value.split()).casefold()
            if isinstance(state_value, str)
            else ""
        )
        if state == "not vulnerable":
            result: Literal["negative", "inconclusive"] = "negative"
            state_fact = "NOT VULNERABLE"
        elif state in {
            "vulnerable",
            "vulnerable (dos)",
            "vulnerable (exploitable)",
        }:
            # Positive states are carried by their finding observation.
            continue
        else:
            # Missing/null state, errors, and unrecognized states identify an
            # attempted check at most; they never become negative evidence.
            result = "inconclusive"
            has_state_field = any(
                str(key).casefold() == "state" for key in candidate
            )
            if state:
                state_fact = state.upper()[:160]
            elif not has_state_field:
                state_fact = "MISSING"
            elif state_value is None:
                state_fact = "NULL"
            else:
                state_fact = (
                    f"UNSUPPORTED TYPE: {type(state_value).__name__.upper()}"
                )[:160]

        condition_keys = _structured_cves(_lookup(candidate, "ids"))
        if not condition_keys:
            continue
        evidence = json.dumps(
            {"output": script.output.strip(), "table": candidate},
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
        for condition_key in condition_keys:
            supported_ms17_negative = (
                result == "negative"
                and script.script_id == "smb-vuln-ms17-010"
                and condition_key == "CVE-2017-0143"
                and port is not None
                and port.port == 445
                and port.protocol == "tcp"
            )
            observations.append(
                FindingEvidenceObservationPayload(
                    ip=host.ip,
                    port=port.port if port is not None else None,
                    protocol=port.protocol if port is not None else None,
                    condition_key=condition_key,
                    method="specific_check" if supported_ms17_negative else "unknown",
                    result=result,
                    source="nmap_nse",
                    source_script=script.script_id,
                    rule_id=(
                        "nse:smb-vuln-ms17-010"
                        if supported_ms17_negative
                        else "nse:unsupported"
                    ),
                    rule_version="1",
                    evidence=evidence[:512],
                    facts=(
                        {
                            "vulnerability_state": state_fact,
                            "table": "smb-vuln-ms17-010",
                        }
                        if supported_ms17_negative
                        else {"vulnerability_state": state_fact}
                    ),
                )
            )
    return observations


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
                    issue_key="title:unauthenticated modbus data read is reachable",
                    evidence_method="specific_check",
                    evidence_result="positive",
                    evidence_rule_id="modbus:read-only",
                    evidence_facts={"read_result": True},
                    evidence_observations=[
                        FindingEvidenceObservationPayload(
                            ip=host.ip,
                            port=service.port,
                            protocol="tcp",
                            unit_id=unit.unit_id,
                            condition_key=(
                                "title:unauthenticated modbus data read is reachable"
                            ),
                            method="specific_check",
                            result="positive",
                            source="modbus-read-only-assessment",
                            source_script="modbus-read-only-assessment",
                            rule_id="modbus:read-only",
                            rule_version="1",
                            evidence=evidence[:512],
                            facts={"read_result": True},
                        )
                    ],
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


def _reduce_findings(candidates: list[FindingPayload]) -> list[FindingPayload]:
    groups: dict[tuple[object, ...], list[FindingPayload]] = {}
    for finding in candidates:
        identity = finding_dedupe_key(finding)
        # The backend's persistent identity still collides on CVE + endpoint,
        # where its approved merge records issue_key ambiguity. Keep distinct
        # declared conditions as separate wire findings so each observation is
        # attached to a compatible issue_key and remains valid under the schema.
        key = (*identity, finding.issue_key) if finding.cve_id else identity
        groups.setdefault(key, []).append(finding)
    return [
        _merge_finding_group(groups[key])
        for key in sorted(groups, key=lambda value: tuple(str(item) for item in value))
    ]


def _merge_finding_group(candidates: list[FindingPayload]) -> FindingPayload:
    preferred = min(candidates, key=_finding_preference_key)
    observations, truncated = _merge_observations(
        [],
        [item for candidate in candidates for item in candidate.evidence_observations],
        preferred,
    )
    merged = preferred.model_copy(
        update={
            "references": sorted(
                {ref for candidate in candidates for ref in candidate.references}
            ),
            "evidence_observations": observations,
            "evidence_truncated": truncated
            or any(candidate.evidence_truncated for candidate in candidates),
        }
    )
    return merged


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


def _richer_source_finding(
    first: FindingPayload, second: FindingPayload
) -> FindingPayload:
    return min((first, second), key=_finding_preference_key)


def _preferred_finding(
    first: FindingPayload, second: FindingPayload
) -> tuple[FindingPayload, FindingPayload]:
    return tuple(sorted((first, second), key=_finding_preference_key))  # type: ignore[return-value]


def _finding_evidence_quality(finding: FindingPayload) -> int:
    assessment = assess_local_evidence(finding)
    if assessment.status == "supported" and assessment.method in {
        "configuration_observation",
        "specific_check",
    }:
        return 3
    if assessment.status == "supported" and assessment.method == "version_correlation":
        return 2
    if assessment.status == "conflicting":
        return 1
    return 0


def _finding_preference_key(finding: FindingPayload) -> tuple[object, ...]:
    """Rank evidence, severity, then canonical full-payload JSON lexically."""
    return (
        -_finding_evidence_quality(finding),
        -_severity_rank(finding.severity),
        _canonical_finding_key(finding),
    )


def _canonical_finding_key(finding: FindingPayload) -> str:
    payload = finding.model_dump(mode="json")
    # These fields are merged independently and cannot choose the primary row.
    payload.pop("evidence_observations", None)
    payload.pop("evidence_truncated", None)
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _merge_observations(
    first: list[FindingEvidenceObservationPayload],
    second: list[FindingEvidenceObservationPayload],
    finding: FindingPayload,
) -> tuple[list[FindingEvidenceObservationPayload], bool]:
    """Union evidence witnesses deterministically before applying the wire bound."""
    by_key: dict[str, FindingEvidenceObservationPayload] = {}
    for item in [*first, *second]:
        payload = item.model_dump(mode="json")
        payload["facts"] = dict(sorted(item.facts.items()))
        key = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        by_key[key] = item
    ordered = [by_key[key] for key in sorted(by_key)]

    def key(item: FindingEvidenceObservationPayload) -> str:
        payload = item.model_dump(mode="json")
        return json.dumps(payload, sort_keys=True, separators=(",", ":"))

    valid = {
        key(item): item
        for item in ordered
        if _supported_local_observation(item, finding)
    }

    def quality(item: FindingEvidenceObservationPayload) -> tuple[int, str, str]:
        return (
            0 if item.method in {"configuration_observation", "specific_check"} else 1,
            item.rule_id,
            key(item),
        )

    positives = sorted(
        (item for item in valid.values() if item.result == "positive"), key=quality
    )
    negatives = sorted(
        (item for item in valid.values() if item.result == "negative"), key=quality
    )
    selected: list[FindingEvidenceObservationPayload] = []
    selected_keys: set[str] = set()

    def retain(item: FindingEvidenceObservationPayload) -> None:
        item_key = key(item)
        if item_key not in selected_keys:
            selected.append(item)
            selected_keys.add(item_key)

    # Preserve a strongest positive and directly comparable conflict witnesses
    # before lexical remainder can consume the fixed bound.
    if positives:
        retain(positives[0])
    elif negatives:
        retain(negatives[0])

    conflict_pairs: list[tuple[str, str]] = []
    for negative in negatives:
        for positive in positives:
            same_scope = (
                negative.ip,
                negative.protocol,
                negative.port,
                negative.unit_id,
                negative.condition_key,
            ) == (
                positive.ip,
                positive.protocol,
                positive.port,
                positive.unit_id,
                positive.condition_key,
            )
            comparable = positive.method == "version_correlation" or (
                positive.method in {"specific_check", "configuration_observation"}
                and positive.method == negative.method
            )
            if same_scope and comparable:
                conflict_pairs.append((key(positive), key(negative)))
    conflict_pairs = sorted(set(conflict_pairs))
    for positive_key, negative_key in conflict_pairs:
        retain(valid[positive_key])
        retain(valid[negative_key])

    essential_missing = len(selected) > 16
    selected = selected[:16]
    selected_keys = {key(item) for item in selected}
    remainder = [item for item in ordered if key(item) not in selected_keys]
    selected.extend(remainder[: max(0, 16 - len(selected))])
    return selected, len(ordered) > 16 or essential_missing


def _targeted_observation(
    host: HostInfo,
    port: PortInfo | None,
    result: TargetedUnitResult,
    issue: TargetedIssue,
) -> FindingEvidenceObservationPayload:
    facts, _truncated = _bounded_facts(issue.facts)
    # Configuration findings keep their own condition even when the tool cites
    # an advisory; only an explicit version-correlation method keys by CVE.
    condition_key = (
        issue.cve_id
        if issue.method == "version_correlation" and issue.cve_id
        else "CVE-2017-0143"
        if issue.method == "specific_check" and issue.rule_id.endswith("ms17-010")
        else issue.issue_key
    )
    return FindingEvidenceObservationPayload(
        ip=host.ip,
        port=port.port if port is not None else result.unit.port,
        protocol=result.unit.protocol
        if result.unit.protocol in {"tcp", "udp"}
        else None,
        condition_key=condition_key[:256],
        method=issue.method,
        result=issue.result,
        source="targeted_service_assessment",
        source_script=result.unit.tool.value,
        rule_id=issue.rule_id[:128],
        rule_version=issue.rule_version[:64],
        evidence=(issue.evidence.strip() or "Targeted result recorded.")[:512],
        facts=facts,
    )


def _targeted_finding(
    host: HostInfo,
    port: PortInfo | None,
    result: TargetedUnitResult,
    issue: TargetedIssue,
) -> FindingPayload:
    observation = _targeted_observation(host, port, result, issue)
    _facts, facts_truncated = _bounded_facts(issue.facts)
    truncated = (
        facts_truncated
        or len(issue.evidence.strip()) > 512
        or len(issue.issue_key) > 256
    )
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
        evidence_observations=[observation],
        evidence_truncated=truncated,
    )


def _bounded_facts(
    facts: dict[str, str | int | bool],
) -> tuple[dict[str, str | int | bool], bool]:
    bounded: dict[str, str | int | bool] = {}
    truncated = len(facts) > 8
    for key, value in sorted(facts.items())[:8]:
        normalized_key = key[:64]
        normalized_value = value[:160] if isinstance(value, str) else value
        truncated |= normalized_key != key or normalized_value != value
        bounded[normalized_key] = normalized_value
    return bounded, truncated


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
            evidence_method="textual_reference",
            evidence_result="inconclusive",
            evidence_rule_id="nse:textual-cve-reference",
            evidence_facts={"cve_id": cve.upper()},
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
                    evidence_method=(
                        "version_correlation"
                        if lookup_key in port.service.cpes
                        else "unknown"
                    ),
                    evidence_result=(
                        "positive"
                        if lookup_key in port.service.cpes
                        else "inconclusive"
                    ),
                    evidence_rule_id="catalog:nmap-vulners",
                    evidence_facts=(
                        {"cpe": lookup_key, "cve_id": advisory_id}
                        if lookup_key in port.service.cpes
                        else {}
                    ),
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
    if "disabled" not in haystack and "not required" not in haystack:
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
        issue_key="smb:signing",
        evidence_method="configuration_observation",
        evidence_result="positive",
        evidence_rule_id="nse:smb2-security-mode",
        evidence_facts={"signing_required": False},
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
        issue_key="smb:protocol:smbv1",
        evidence_method="configuration_observation",
        evidence_result="positive",
        evidence_rule_id="nse:smb-protocols",
        evidence_facts={"dialect": "SMBv1"},
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
        issue_key="title:potentially risky http methods enabled",
        evidence_method="configuration_observation",
        evidence_result="positive",
        evidence_rule_id="nse:http-methods",
        evidence_facts={"risky_method": risky_methods[0]},
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
        issue_key="title:ssh password authentication exposed",
        evidence_method="configuration_observation",
        evidence_result="positive",
        evidence_rule_id="nse:ssh-auth-methods",
        evidence_facts={"password_authentication": True},
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
                issue_key="tls.certificate:expired",
                evidence_method="configuration_observation",
                evidence_result="positive",
                evidence_rule_id="nse:ssl-cert-expired",
                evidence_facts={"certificate_expired": True},
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
                issue_key="tls.certificate:self-signed",
                evidence_method="configuration_observation",
                evidence_result="positive",
                evidence_rule_id="nse:ssl-cert-self-signed",
                evidence_facts={"subject_matches_issuer": True},
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
                issue_key="tls.certificate:weak-signature",
                evidence_method="configuration_observation",
                evidence_result="positive",
                evidence_rule_id="nse:ssl-cert-weak-signature",
                evidence_facts={
                    "signature_algorithm": "sha1" if "sha1" in sig_algo else "md5"
                },
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
                issue_key="tls.certificate:weak-key",
                evidence_method="configuration_observation",
                evidence_result="positive",
                evidence_rule_id="nse:ssl-cert-weak-key",
                evidence_facts={"public_key_bits": int(bits)},
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
                    issue_key=f"tls.protocol:{protocol.casefold()}",
                    evidence_method="configuration_observation",
                    evidence_result="positive",
                    evidence_rule_id="nse:ssl-enum-ciphers-protocol",
                    evidence_facts={"protocol": protocol},
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
            weak_cipher = _weak_cipher_from_text(text)
            primitive = _tls_primitive(text)
            issue_key = (
                f"tls.cipher:{primitive}"
                if primitive
                else f"title:weak tls cipher configuration:{text.casefold().strip()}"
            )
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
                    issue_key=issue_key,
                    evidence_method="configuration_observation",
                    evidence_result="positive",
                    evidence_rule_id="nse:ssl-enum-ciphers-warning",
                    evidence_facts={"weak_cipher": weak_cipher} if weak_cipher else {},
                )
            )

    least = _stringify(_lookup(data, "least strength")).upper()
    if least in {"C", "D", "E", "F"}:
        grade_evidence = script.output or f"least strength={least}"
        primitive = _tls_primitive(grade_evidence)
        grade_issue_key = (
            f"tls.cipher:{primitive}"
            if primitive
            else (
                "title:weak tls cipher strength (grade "
                f"{least.casefold()}):{grade_evidence.casefold().strip()}"
            )
        )
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
                issue_key=grade_issue_key,
                evidence_method="configuration_observation",
                evidence_result="positive",
                evidence_rule_id="nse:ssl-enum-ciphers-grade",
                evidence_facts={"weakest_grade": least},
            )
        )

    return findings


def _weak_cipher_from_text(value: str) -> str:
    normalized = value.casefold()
    for cipher, fact in (
        ("rc4", "RC4"),
        ("3des", "3DES"),
        ("des", "DES"),
        ("null", "NULL"),
        ("export", "EXPORT"),
        ("anull", "aNULL"),
        ("anonymous", "anonymous"),
    ):
        if cipher in normalized:
            return fact
    return ""


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
        issue_key="ftp:anonymous-login",
        evidence_method="specific_check",
        evidence_result="positive",
        evidence_rule_id="nse:ftp-anon",
        evidence_facts={"anonymous_login": True},
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
                evidence_method=(
                    "specific_check"
                    if script.script_id == "smb-vuln-ms17-010"
                    and state == "vulnerable"
                    and cve_id == "CVE-2017-0143"
                    and port is not None
                    and port.port == 445
                    else "unknown"
                ),
                evidence_result=(
                    "positive"
                    if script.script_id == "smb-vuln-ms17-010"
                    and state == "vulnerable"
                    and cve_id == "CVE-2017-0143"
                    and port is not None
                    and port.port == 445
                    else "inconclusive"
                ),
                evidence_rule_id=(
                    "nse:smb-vuln-ms17-010"
                    if script.script_id == "smb-vuln-ms17-010"
                    else "nse:unsupported"
                ),
                evidence_facts=(
                    {"vulnerability_state": "VULNERABLE", "table": script.script_id}
                    if script.script_id == "smb-vuln-ms17-010"
                    and state == "vulnerable"
                    and cve_id == "CVE-2017-0143"
                    and port is not None
                    and port.port == 445
                    else {}
                ),
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
    evidence_observations: list[FindingEvidenceObservationPayload] | None = None,
    evidence_method: str = "unknown",
    evidence_result: str = "inconclusive",
    evidence_rule_id: str | None = None,
    evidence_facts: dict[str, str | int | bool] | None = None,
    evidence_truncated: bool = False,
) -> FindingPayload:
    protocol = (
        port.protocol if port is not None and port.protocol in {"tcp", "udp"} else None
    )
    service_name = port.service.name if port is not None and port.service.name else None
    facts, facts_truncated = _bounded_facts(evidence_facts or {})
    observation_evidence = (
        evidence.strip() or "Result recorded without a supported evidence rule."
    )[:512]
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
        evidence_truncated=(
            evidence_truncated
            or facts_truncated
            or len(evidence.strip()) > 512
            or len(cve_id or issue_key or f"title:{title.casefold()}") > 256
        ),
        evidence_observations=evidence_observations
        or [
            FindingEvidenceObservationPayload(
                ip=host.ip,
                port=port.port if port is not None else None,
                protocol=protocol,
                unit_id=unit_id,
                condition_key=(cve_id or issue_key or f"title:{title.casefold()}")[
                    :256
                ],
                method=evidence_method,
                result=evidence_result,
                source=source[:64],
                source_script=source_script[:64] if source_script else None,
                rule_id=evidence_rule_id
                or (
                    "nse:unsupported" if source == "nmap_nse" else "modbus:unsupported"
                ),
                rule_version="1",
                evidence=observation_evidence,
                facts=facts,
            )
        ],
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
