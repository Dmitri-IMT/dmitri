from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from pydantic import TypeAdapter

from api.schemas.read import TargetedCoverageGap, TargetedToolCoverage
from api.schemas.scan import (
    CoverageUnitPayload,
    EvidenceCompleteness,
    FindingEvidenceObservationPayload,
)

_CVE_CORRELATION_ALIASES = frozenset({"nmap_vulners", "nvd", "nvd_enrichment"})
_COVERAGE = TypeAdapter(list[CoverageUnitPayload])
_OBSERVATION = TypeAdapter(FindingEvidenceObservationPayload)
_MAX_OBSERVATIONS = 16
_UNSET = object()


@dataclass(frozen=True)
class FindingEvidenceAssessment:
    detection_method: str
    evidence_status: str
    confidence: str
    observations: tuple[FindingEvidenceObservationPayload, ...]
    evidence_truncated: bool


_CONFIGURATION_RULES: dict[str, tuple[str, str, Any]] = {
    "nse:smb2-security-mode": (
        "configuration_observation", "signing_required", False
    ),
    "nse:smb-protocols": (
        "configuration_observation", "dialect", frozenset({"SMBv1", "SMBv2", "SMBv3"})
    ),
    "nse:http-methods": (
        "configuration_observation", "risky_method",
        frozenset({"PUT", "DELETE", "TRACE", "CONNECT"}),
    ),
    "nse:ssh-auth-methods": (
        "configuration_observation", "password_authentication", True
    ),
    "nse:ssl-cert-expired": (
        "configuration_observation", "certificate_expired", True
    ),
    "nse:ssl-cert-self-signed": (
        "configuration_observation", "subject_matches_issuer", True
    ),
    "nse:ssl-cert-weak-signature": (
        "configuration_observation", "signature_algorithm", frozenset({"sha1", "md5"})
    ),
    "nse:ssl-cert-weak-key": (
        "configuration_observation", "public_key_bits", 2048
    ),
    "nse:ssl-enum-ciphers-protocol": (
        "configuration_observation", "protocol", frozenset({"SSLv3", "TLSv1.0"})
    ),
    "nse:ssl-enum-ciphers-warning": (
        "configuration_observation", "weak_cipher",
        frozenset({"RC4", "3DES", "DES", "NULL", "EXPORT", "aNULL", "anonymous"}),
    ),
    "nse:ssl-enum-ciphers-grade": (
        "configuration_observation", "weakest_grade", frozenset({"C", "D", "E", "F"})
    ),
}
_SPECIFIC_RULES: dict[str, tuple[str, frozenset[str]]] = {
    "nse:ftp-anon": ("anonymous_login", frozenset({"ftp-anon"})),
    "targeted:ftp-check-anonymous": (
        "anonymous_login_accepted", frozenset({"ftp-check"})
    ),
    "targeted:enum4linux-ng-session": (
        "session_type", frozenset({"enum4linux-ng"})
    ),
    "nse:smb-vuln-ms17-010": (
        "vulnerability_state", frozenset({"smb-vuln-ms17-010"})
    ),
    "modbus:read-only": (
        "read_result", frozenset({"modbus-read-only-assessment"})
    ),
}
_NSE_RULE_SCRIPTS = {
    "nse:ssl-cert-expired": "ssl-cert",
    "nse:ssl-cert-self-signed": "ssl-cert",
    "nse:ssl-cert-weak-signature": "ssl-cert",
    "nse:ssl-cert-weak-key": "ssl-cert",
    "nse:ssl-enum-ciphers-protocol": "ssl-enum-ciphers",
    "nse:ssl-enum-ciphers-warning": "ssl-enum-ciphers",
    "nse:ssl-enum-ciphers-grade": "ssl-enum-ciphers",
}


def is_cve_correlation(cve_id: str | None, source: str | None) -> bool:
    return bool(cve_id) and source in _CVE_CORRELATION_ALIASES


def _as_observation(
    value: FindingEvidenceObservationPayload | dict[str, Any],
) -> FindingEvidenceObservationPayload:
    if isinstance(value, FindingEvidenceObservationPayload):
        return value
    return _OBSERVATION.validate_python(value)


def _endpoint_key(item: FindingEvidenceObservationPayload) -> tuple[Any, ...]:
    return (
        str(item.ip) if item.ip is not None else None,
        item.protocol,
        item.port,
        item.unit_id,
        item.condition_key,
    )


def _configuration_condition_matches(
    rule_id: str, value: Any, evidence: str, condition_key: str
) -> bool:
    fixed = {
        "nse:smb2-security-mode": "smb:signing",
        "nse:smb-protocols": "smb:protocol:smbv1",
        "nse:http-methods": "title:potentially risky http methods enabled",
        "nse:ssh-auth-methods": "title:ssh password authentication exposed",
        "nse:ssl-cert-expired": "tls.certificate:expired",
        "nse:ssl-cert-self-signed": "tls.certificate:self-signed",
        "nse:ssl-cert-weak-signature": "tls.certificate:weak-signature",
        "nse:ssl-cert-weak-key": "tls.certificate:weak-key",
    }
    if rule_id in fixed:
        return condition_key == fixed[rule_id]
    if rule_id == "nse:ssl-enum-ciphers-protocol":
        return condition_key == f"tls.protocol:{str(value).casefold()}"
    if rule_id == "nse:ssl-enum-ciphers-warning":
        normalized = evidence.casefold()
        for primitive in ("rc4", "3des", "des", "null", "export"):
            if primitive in normalized:
                return condition_key == f"tls.cipher:{primitive}" and str(
                    value
                ).casefold() == primitive
        return condition_key == (
            f"title:weak tls cipher configuration:{normalized.strip()}"
        )
    if rule_id == "nse:ssl-enum-ciphers-grade":
        normalized = evidence.casefold()
        for primitive in ("rc4", "3des", "des", "null", "export"):
            if primitive in normalized:
                return condition_key == f"tls.cipher:{primitive}"
        title = f"weak tls cipher strength (grade {str(value).casefold()})"
        return condition_key == f"title:{title}:{normalized.strip()}"
    return False


def _specific_condition_matches(rule_id: str, condition_key: str) -> bool:
    expected = {
        "nse:ftp-anon": "ftp:anonymous-login",
        "targeted:ftp-check-anonymous": "ftp:anonymous-login",
        "targeted:enum4linux-ng-session": "smb:anonymous-session",
        "modbus:read-only": "title:unauthenticated modbus data read is reachable",
    }
    if rule_id.endswith("ms17-010"):
        return condition_key == "CVE-2017-0143"
    return condition_key == expected.get(rule_id)


def _rule_result(
    item: FindingEvidenceObservationPayload,
    cve_id: str | None,
) -> tuple[str, str]:
    facts = item.facts
    if item.method == "version_correlation":
        allowed = {"cpe", "product", "version", "cve_id"}
        identity = facts.get("cpe") or (facts.get("product") and facts.get("version"))
        valid = (
            item.result == "positive"
            and item.rule_id in {"catalog:nvd-cpe", "catalog:nmap-vulners"}
            and item.rule_version == "1"
            and set(facts) <= allowed
            and bool(identity)
            and bool(cve_id)
            and facts.get("cve_id", cve_id) == cve_id
            and item.source in _CVE_CORRELATION_ALIASES
            and item.ip is not None
            and item.port is not None
            and item.protocol is not None
        )
        return (
            ("probable", "supported")
            if valid
            else ("tentative", "inconclusive")
        )
    configuration = _CONFIGURATION_RULES.get(item.rule_id)
    if configuration:
        method, fact, expected = configuration
        value = facts.get(fact)
        if isinstance(expected, frozenset):
            matches = type(value) is str and value in expected
            if item.rule_id == "nse:smb-protocols":
                matches = (
                    value == "SMBv1"
                    if item.result == "positive"
                    else value in {"SMBv2", "SMBv3"}
                )
            elif item.rule_id == "nse:http-methods":
                matches = (
                    value in expected
                    if item.result == "positive"
                    else value in {"GET", "HEAD", "POST", "OPTIONS", "PATCH"}
                )
            elif item.rule_id == "nse:ssl-cert-weak-signature":
                matches = (
                    value in expected
                    if item.result == "positive"
                    else value in {"sha256", "sha384", "sha512"}
                )
            elif item.rule_id == "nse:ssl-enum-ciphers-protocol":
                matches = (
                    value in expected
                    if item.result == "positive"
                    else value in {"TLSv1.2", "TLSv1.3"}
                )
            elif item.rule_id == "nse:ssl-enum-ciphers-grade":
                matches = (
                    value in expected
                    if item.result == "positive"
                    else value in {"A", "B"}
                )
        else:
            matches = (
                type(value) is bool and value is expected
                if type(expected) is bool
                else value == expected
            )
            if isinstance(expected, bool) and item.result == "negative":
                matches = type(value) is bool and value is not expected
        if item.rule_id == "nse:ssl-cert-weak-key":
            matches = type(value) is int and (
                value < expected if item.result == "positive" else value >= expected
            )
        valid = (
            item.method == method
            and item.result in {"positive", "negative"}
            and item.rule_version == "1"
            and item.source_script
            == _NSE_RULE_SCRIPTS.get(
                item.rule_id, item.rule_id.removeprefix("nse:")
            )
            and item.source == "nmap_nse"
            and _configuration_condition_matches(
                item.rule_id, value, item.evidence, item.condition_key
            )
            and set(facts) == {fact}
            and matches
            and item.ip is not None
            and item.port is not None
            and item.protocol == "tcp"
        )
        return ("confirmed", "supported") if valid else ("tentative", "inconclusive")
    specific = _SPECIFIC_RULES.get(item.rule_id)
    if specific:
        fact, sources = specific
        expected_cve = item.rule_id.endswith("ms17-010")
        fact_value = facts.get(fact)
        value_valid = (
            type(fact_value) is bool
            and fact_value is (item.result == "positive")
        )
        if item.rule_id.endswith("ms17-010"):
            value_valid = (
                fact_value
                == ("VULNERABLE" if item.result == "positive" else "NOT VULNERABLE")
                and facts.get("table") == "smb-vuln-ms17-010"
                and set(facts) == {fact, "table"}
                and _specific_condition_matches(item.rule_id, item.condition_key)
                and item.port == 445
                and item.unit_id is None
            )
        elif item.rule_id == "targeted:enum4linux-ng-session":
            value_valid = (
                fact_value in {"null", "guest"}
                and type(facts.get("accepted")) is bool
                and facts.get("accepted") is (item.result == "positive")
                and set(facts) == {fact, "accepted"}
            )
        valid = (
            item.method == "specific_check"
            and item.result in {"positive", "negative"}
            and item.rule_version == "1"
            and item.source_script in sources
            and (
                item.source == "nmap_nse"
                if item.rule_id.startswith("nse:")
                else item.source == "targeted_service_assessment"
                if item.rule_id.startswith("targeted:")
                else item.source == "modbus-read-only-assessment"
            )
            and (
                set(facts) == {fact}
                or item.rule_id.endswith("ms17-010")
                or item.rule_id == "targeted:enum4linux-ng-session"
            )
            and value_valid
            and _specific_condition_matches(item.rule_id, item.condition_key)
            and (not expected_cve or cve_id == "CVE-2017-0143")
            and item.ip is not None
            and item.port is not None
            and item.protocol == "tcp"
            and (not item.rule_id.startswith("modbus:") or item.unit_id is not None)
        )
        return ("confirmed", "supported") if valid else ("tentative", "inconclusive")
    return "tentative", "inconclusive"


def finding_observation_is_supported(
    observation: FindingEvidenceObservationPayload | dict[str, Any],
    *,
    cve_id: str | None = None,
) -> bool:
    item = _as_observation(observation)
    return _rule_result(item, cve_id)[1] == "supported"


def validate_finding_evidence(
    observations: Sequence[FindingEvidenceObservationPayload | dict[str, Any]],
    *,
    cve_id: str | None = None,
    issue_key: str | None = None,
    ip: str | None | object = _UNSET,
    port: int | None | object = _UNSET,
    protocol: str | None | object = _UNSET,
    unit_id: int | None | object = _UNSET,
    policy_version: str = "1",
    issue_key_ambiguous: bool = False,
    allowed_conditions: Sequence[str] | None = None,
) -> FindingEvidenceAssessment:
    parsed = _matching_observations(
        observations,
        cve_id,
        issue_key,
        ip,
        port,
        protocol,
        unit_id,
        policy_version,
        issue_key_ambiguous,
        allowed_conditions,
    )
    validated = [(item, *_rule_result(item, cve_id)) for item in parsed]
    return _assessment(validated, False)


def _matching_observations(
    observations: Sequence[FindingEvidenceObservationPayload | dict[str, Any]],
    cve_id: str | None,
    issue_key: str | None,
    ip: str | None | object,
    port: int | None | object,
    protocol: str | None | object,
    unit_id: int | None | object,
    policy_version: str,
    issue_key_ambiguous: bool = False,
    allowed_conditions: Sequence[str] | None = None,
) -> list[FindingEvidenceObservationPayload]:
    matched = []
    for value in observations:
        item = _as_observation(value)
        if item.rule_version != policy_version:
            continue
        is_cve_condition = item.method == "version_correlation" or (
            item.method == "specific_check"
            and (item.rule_id.endswith("ms17-010") or issue_key == cve_id)
        )
        condition = cve_id if is_cve_condition else issue_key
        if issue_key_ambiguous:
            if allowed_conditions is not None and item.condition_key not in set(
                allowed_conditions
            ):
                continue
        elif condition is None or item.condition_key != condition:
            continue
        if ip is not _UNSET and (str(item.ip) if item.ip is not None else None) != (
            str(ip) if ip is not None else None
        ):
            continue
        if port is not _UNSET and item.port != port:
            continue
        if protocol is not _UNSET and item.protocol != protocol:
            continue
        if unit_id is not _UNSET and item.unit_id != unit_id:
            continue
        matched.append(item)
    return matched


def _assessment(
    validated: Sequence[tuple[FindingEvidenceObservationPayload, str, str]],
    truncated: bool,
) -> FindingEvidenceAssessment:
    positive = [
        (item, conf, status)
        for item, conf, status in validated
        if item.result == "positive" and status == "supported"
    ]
    direct = [
        row
        for row in positive
        if row[0].method in {"configuration_observation", "specific_check"}
    ]
    if direct:
        best = min(
            direct,
            key=lambda row: (row[0].method, row[0].rule_id, row[0].condition_key),
        )
    elif positive:
        best = min(
            positive,
            key=lambda row: (row[0].method, row[0].rule_id, row[0].condition_key),
        )
    elif validated:
        best = min(
            validated,
            key=lambda row: (row[0].method, row[0].rule_id, row[0].condition_key),
        )
    else:
        return FindingEvidenceAssessment(
            "unknown", "unknown", "tentative", (), truncated
        )
    confidence, status = best[1], best[2]
    conflicts: set[str] = set()
    for item, _, item_status in validated:
        if item_status != "supported" or item.result != "negative":
            continue
        for candidate, _, candidate_status in positive:
            correlation_refuted = (
                candidate.method == "version_correlation"
                and item.condition_key == candidate.condition_key
                and _endpoint_key(item) == _endpoint_key(candidate)
                and item.ip is not None
                and item.port is not None
                and item.protocol is not None
                and candidate.ip is not None
                and candidate.port is not None
                and candidate.protocol is not None
            )
            direct_conflict = (
                candidate.method in {"configuration_observation", "specific_check"}
                and item.method == candidate.method
                and _endpoint_key(item) == _endpoint_key(candidate)
            )
            if correlation_refuted or direct_conflict:
                conflicts.update((_observation_key(item), _observation_key(candidate)))
    if conflicts:
        status, confidence = "conflicting", "tentative"
    elif not positive:
        status = (
            "inconclusive"
            if any(row[0].method != "unknown" for row in validated)
            else "unknown"
        )
        confidence = "tentative"
    if truncated:
        if status != "conflicting":
            status = "inconclusive"
        confidence = "tentative"
    return FindingEvidenceAssessment(
        best[0].method, status, confidence, (), truncated
    )


def _observation_key(item: FindingEvidenceObservationPayload) -> str:
    return json.dumps(
        item.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
    )


def reduce_finding_evidence(
    observations: Sequence[FindingEvidenceObservationPayload | dict[str, Any]],
    *,
    cve_id: str | None = None,
    issue_key: str | None = None,
    ip: str | None | object = _UNSET,
    port: int | None | object = _UNSET,
    protocol: str | None | object = _UNSET,
    unit_id: int | None | object = _UNSET,
    policy_version: str = "1",
    evidence_truncated: bool = False,
    issue_key_ambiguous: bool = False,
    allowed_conditions: Sequence[str] | None = None,
    limit: int = _MAX_OBSERVATIONS,
) -> FindingEvidenceAssessment:
    if limit < 1:
        raise ValueError("limit must be positive")
    candidates = _matching_observations(
        observations,
        cve_id,
        issue_key,
        ip,
        port,
        protocol,
        unit_id,
        policy_version,
        issue_key_ambiguous,
        allowed_conditions,
    )
    full = sorted(
        {
            _observation_key(item): item
            for item in candidates
        }.values(),
        key=_observation_key,
    )
    validated = [(item, *_rule_result(item, cve_id)) for item in full]
    conflict_pairs = _conflict_pairs(validated)
    conflict_keys = {key for pair in conflict_pairs for key in pair}
    witness_keys = set(conflict_keys)
    positive_witnesses = [
        (item, confidence)
        for item, confidence, status in validated
        if status == "supported" and item.result == "positive"
    ]
    if positive_witnesses:
        confidence_rank = {"confirmed": 0, "probable": 1, "tentative": 2}
        witness, _ = min(
            positive_witnesses,
            key=lambda row: (
                confidence_rank[row[1]],
                row[0].method,
                _observation_key(row[0]),
            ),
        )
        witness_keys.add(_observation_key(witness))
    by_key = {_observation_key(item): item for item in full}
    selected = []
    selected_keys: set[str] = set()
    for negative_key, positive_key in conflict_pairs:
        for key in (positive_key, negative_key):
            if key not in selected_keys:
                selected.append(by_key[key])
                selected_keys.add(key)
    selected.extend(
        item
        for item in full
        if _observation_key(item) in witness_keys
        and _observation_key(item) not in conflict_keys
    )
    selected.extend(
        item for item in full if _observation_key(item) not in witness_keys
    )
    retained = selected[:limit]
    truncated = evidence_truncated or len(full) > len(retained)
    retained_keys = {_observation_key(item) for item in retained}
    missing_witness = not witness_keys <= retained_keys
    result = _assessment(
        [(item, *_rule_result(item, cve_id)) for item in retained], truncated
    )
    if issue_key_ambiguous and result.evidence_status != "conflicting":
        result = FindingEvidenceAssessment(
            result.detection_method,
            "inconclusive",
            "tentative",
            (),
            result.evidence_truncated,
        )
    if missing_witness and result.evidence_status != "conflicting":
        result = FindingEvidenceAssessment(
            result.detection_method, "inconclusive", "tentative", (), True
        )
    return FindingEvidenceAssessment(
        result.detection_method,
        result.evidence_status,
        result.confidence,
        tuple(retained),
        truncated,
    )


def _conflict_pairs(
    validated: Sequence[tuple[FindingEvidenceObservationPayload, str, str]],
) -> list[tuple[str, str]]:
    positives = [
        item
        for item, _, status in validated
        if status == "supported" and item.result == "positive"
    ]
    negatives = [
        item
        for item, _, status in validated
        if status == "supported" and item.result == "negative"
    ]
    pairs: set[tuple[str, str]] = set()
    for negative in negatives:
        for positive in positives:
            direct = (
                positive.method in {"configuration_observation", "specific_check"}
                and negative.method == positive.method
                and _endpoint_key(negative) == _endpoint_key(positive)
            )
            correlation = (
                positive.method == "version_correlation"
                and negative.condition_key == positive.condition_key
                and _endpoint_key(negative) == _endpoint_key(positive)
                and negative.ip is not None
                and negative.port is not None
                and negative.protocol is not None
                and positive.ip is not None
                and positive.port is not None
                and positive.protocol is not None
            )
            if direct or correlation:
                pairs.add((_observation_key(negative), _observation_key(positive)))
    return sorted(pairs)


def summarize_finding_evidence(
    records: Sequence[Any], *, scope: str
) -> dict[str, Any]:
    methods = {
        key: 0
        for key in (
            "version_correlation",
            "configuration_observation",
            "specific_check",
            "textual_reference",
            "unknown",
        )
    }
    confidence = {key: 0 for key in ("tentative", "probable", "confirmed", "unknown")}
    conflicts = demonstrated = 0
    for record in records:
        if isinstance(record, dict):
            get = record.get
        else:
            def get(key, default=None, current=record):
                return getattr(current, key, default)
        method = get("detection_method", "unknown")
        methods[method if method in methods else "unknown"] += 1
        value = get("confidence")
        confidence[value if value in confidence else "unknown"] += 1
        status = get("evidence_status", "unknown")
        conflicts += status == "conflicting"
        observations = get("evidence_observations", ()) or ()
        truncated = bool(get("evidence_truncated", False))
        if status == "supported" and not truncated and any(
            _rule_result(_as_observation(item), get("cve_id"))[1] == "supported"
            and _as_observation(item).method
            in {"configuration_observation", "specific_check"}
            and _as_observation(item).result == "positive"
            for item in observations
        ):
            demonstrated += 1
    return {
        "scope": scope,
        "total_records": len(records),
        "by_method": methods,
        "by_confidence": confidence,
        "conflicting_records": conflicts,
        "demonstrated_records": demonstrated,
    }


def parse_coverage(raw: list[dict[str, Any]] | None) -> list[CoverageUnitPayload]:
    return _COVERAGE.validate_python(raw or [])


def parse_targeted_coverage(
    metadata: dict[str, Any] | None,
) -> list[TargetedToolCoverage]:
    raw = (metadata or {}).get("targeted_coverage")
    if not isinstance(raw, str):
        return []
    tools: list[TargetedToolCoverage] = []
    for chunk in raw.split(";"):
        tool, _, detail = chunk.partition(":")
        counts_text, _, gaps_text = detail.partition(",gaps=")
        counts = dict(item.partition("=")[::2] for item in counts_text.split(","))
        if not tool or not all(counts.get(key, "").isdigit() for key in "cfts"):
            continue
        gaps = []
        for gap in gaps_text.split("|") if gaps_text else []:
            reason, _, count = gap.partition(":")
            if reason and count.isdigit():
                gaps.append(TargetedCoverageGap(reason=reason, count=int(count)))
        tools.append(
            TargetedToolCoverage(
                tool=tool,
                completed=int(counts["c"]),
                failed=int(counts["f"]),
                timed_out=int(counts["t"]),
                skipped=int(counts["s"]),
                gaps=gaps,
            )
        )
    return tools


def incomplete_check_count(coverage: Sequence[CoverageUnitPayload]) -> int:
    return sum(unit.outcome != "completed" for unit in coverage)


def evidence_completeness(
    metadata: dict[str, Any] | None,
    coverage: Sequence[CoverageUnitPayload],
) -> EvidenceCompleteness:
    flag = (metadata or {}).get("partial_result")
    if flag is True or incomplete_check_count(coverage) > 0:
        return "partial"
    if flag is False:
        return "complete"
    return "unknown"
