from __future__ import annotations

import pytest

from api.schemas.scan import CoverageUnitPayload
from api.services.scan_evidence import (
    evidence_completeness,
    incomplete_check_count,
    is_cve_correlation,
    parse_coverage,
    reduce_finding_evidence,
    summarize_finding_evidence,
    validate_finding_evidence,
)


def _unit(outcome: str) -> CoverageUnitPayload:
    return CoverageUnitPayload(
        ip="10.0.0.5",
        stage="ports",
        outcome=outcome,
        evidence_source="nmap_ports",
    )


@pytest.mark.parametrize(
    ("metadata", "coverage", "expected"),
    [
        ({"partial_result": False}, [], "complete"),
        ({"partial_result": False}, [_unit("completed")], "complete"),
        ({"partial_result": True}, [_unit("completed")], "partial"),
        ({"partial_result": False}, [_unit("timed_out")], "partial"),
        (None, [_unit("skipped")], "partial"),
        (None, [], "unknown"),
        ({"partial_result": "yes"}, [_unit("completed")], "unknown"),
    ],
)
def test_evidence_completeness(metadata, coverage, expected) -> None:
    assert evidence_completeness(metadata, coverage) == expected


def test_incomplete_check_count_counts_every_unfinished_outcome() -> None:
    coverage = [_unit(outcome) for outcome in ("completed", "partial", "skipped")]
    assert incomplete_check_count(coverage) == 2


def test_parse_coverage_reads_stored_json() -> None:
    stored = [_unit("failed").model_dump(mode="json")]
    assert parse_coverage(stored) == [_unit("failed")]
    assert parse_coverage(None) == []


@pytest.mark.parametrize(
    ("cve_id", "source", "expected"),
    [
        ("CVE-2026-0001", "nmap_vulners", True),
        ("CVE-2026-0001", "nvd", True),
        ("CVE-2026-0001", "nvd_enrichment", True),
        ("CVE-2026-0001", "targeted", False),
        (None, "nmap_vulners", False),
    ],
)
def test_is_cve_correlation(cve_id, source, expected) -> None:
    assert is_cve_correlation(cve_id, source) is expected


def _observation(**overrides):
    value = {
        "ip": "10.0.0.5",
        "port": 445,
        "protocol": "tcp",
        "condition_key": "smb:signing",
        "method": "configuration_observation",
        "result": "positive",
        "source": "nmap_nse",
        "source_script": "smb2-security-mode",
        "rule_id": "nse:smb2-security-mode",
        "rule_version": "1",
        "evidence": "Message signing enabled but not required",
        "facts": {"signing_required": False},
    }
    value.update(overrides)
    return value


def test_closed_configuration_rule_requires_scope_and_exact_facts() -> None:
    obs = _observation()
    assert (
        validate_finding_evidence([obs], issue_key="smb:signing").confidence
        == "confirmed"
    )
    assert validate_finding_evidence([obs]).confidence == "tentative"
    malformed = _observation(
        facts={"signing_required": False, "extra": True}
    )
    assert (
        validate_finding_evidence([malformed], issue_key="smb:signing").confidence
        == "tentative"
    )
    wrong_script = _observation(source_script="random")
    assert (
        validate_finding_evidence(
            [wrong_script], issue_key="smb:signing"
        ).confidence
        == "tentative"
    )
    for value in (0, "false", "unknown"):
        malformed_value = _observation(facts={"signing_required": value})
        assert validate_finding_evidence(
            [malformed_value], issue_key="smb:signing"
        ).confidence == "tentative"


def test_unknown_rule_positive_and_future_rule_version_do_not_confirm() -> None:
    arbitrary = _observation(
        rule_id="nse:unreviewed-script",
        source_script="unreviewed-script",
        facts={"vulnerable": True},
    )
    future = _observation(rule_version="2")
    assert validate_finding_evidence(
        [arbitrary], issue_key="smb:signing"
    ).evidence_status == "inconclusive"
    assert validate_finding_evidence(
        [future], issue_key="smb:signing"
    ).evidence_status == "unknown"


def test_supported_rule_requires_matching_endpoint_and_unit_scope() -> None:
    observation = _observation(unit_id=7)
    assert validate_finding_evidence(
        [observation],
        issue_key="smb:signing",
        ip="10.0.0.6",
        port=445,
        protocol="tcp",
        unit_id=7,
    ).evidence_status == "unknown"
    assert validate_finding_evidence(
        [observation],
        issue_key="smb:signing",
        ip="10.0.0.5",
        port=445,
        protocol="tcp",
        unit_id=8,
    ).evidence_status == "unknown"


def test_inconclusive_observation_does_not_erase_independent_positive() -> None:
    positive = _observation()
    inconclusive = _observation(
        rule_id="nse:unreviewed-script",
        source_script="unreviewed-script",
        result="inconclusive",
        facts={},
    )
    result = reduce_finding_evidence(
        [positive, inconclusive], issue_key="smb:signing"
    )
    assert result.evidence_status == "supported"
    assert result.confidence == "confirmed"
    assert len(result.observations) == 2


def test_truncation_limit_one_cannot_claim_a_conflict_was_retained() -> None:
    positive = _observation()
    negative = _observation(
        result="negative",
        evidence="Signing required",
        facts={"signing_required": True},
    )
    result = reduce_finding_evidence(
        [positive, negative], issue_key="smb:signing", limit=1
    )
    assert result.evidence_truncated is True
    assert result.evidence_status == "inconclusive"
    assert result.confidence == "tentative"
    assert len(result.observations) == 1


@pytest.mark.parametrize(
    ("rule_id", "source_script", "fact", "condition_key"),
    [
        (
            "nse:http-methods",
            "http-methods",
            {"risky_method": "PUT"},
            "title:potentially risky http methods enabled",
        ),
        (
            "nse:ssh-auth-methods",
            "ssh-auth-methods",
            {"password_authentication": True},
            "title:ssh password authentication exposed",
        ),
        (
            "nse:ssl-cert-expired",
            "ssl-cert",
            {"certificate_expired": True},
            "tls.certificate:expired",
        ),
        (
            "nse:ssl-enum-ciphers-warning",
            "ssl-enum-ciphers",
            {"weak_cipher": "RC4"},
            "tls.cipher:rc4",
        ),
        (
            "nse:ssl-enum-ciphers-protocol",
            "ssl-enum-ciphers",
            {"protocol": "TLSv1.0"},
            "tls.protocol:tlsv1.0",
        ),
    ],
)
def test_supported_configuration_rules_use_closed_facts(
    rule_id, source_script, fact, condition_key
) -> None:
    observation = _observation(
        condition_key=condition_key,
        source_script=source_script,
        rule_id=rule_id,
        facts=fact,
        evidence="RC4 weak cipher"
        if rule_id == "nse:ssl-enum-ciphers-warning"
        else "A supported configuration observation",
    )
    assessment = validate_finding_evidence(
        [observation],
        issue_key=condition_key,
        ip="10.0.0.5",
        port=445,
        protocol="tcp",
    )
    assert assessment.evidence_status == "supported"
    assert assessment.confidence == "confirmed"


@pytest.mark.parametrize(
    ("rule_id", "source", "source_script", "fact", "unit_id", "condition_key"),
    [
        (
            "nse:ftp-anon",
            "nmap_nse",
            "ftp-anon",
            {"anonymous_login": True},
            None,
            "ftp:anonymous-login",
        ),
        (
            "targeted:enum4linux-ng-session",
            "targeted_service_assessment",
            "enum4linux-ng",
            {"session_type": "null", "accepted": True},
            None,
            "smb:anonymous-session",
        ),
        (
            "modbus:read-only",
            "modbus-read-only-assessment",
            "modbus-read-only-assessment",
            {"read_result": True},
            1,
            "title:unauthenticated modbus data read is reachable",
        ),
    ],
)
def test_supported_specific_checks_require_response_facts(
    rule_id, source, source_script, fact, unit_id, condition_key
) -> None:
    port = (
        21
        if "ftp" in rule_id
        else 445
        if "enum4linux" in rule_id
        else 502
    )
    observation = _observation(
        condition_key=condition_key,
        port=port,
        method="specific_check",
        source=source,
        source_script=source_script,
        rule_id=rule_id,
        facts=fact,
        unit_id=unit_id,
    )
    assessment = validate_finding_evidence(
        [observation],
        issue_key=condition_key,
        ip="10.0.0.5",
        port=port,
        protocol="tcp",
        unit_id=unit_id,
    )
    assert assessment.evidence_status == "supported"
    assert assessment.confidence == "confirmed"


@pytest.mark.parametrize(
    ("rule_id", "source", "source_script", "result", "facts", "port", "unit_id"),
    [
        (
            "nse:ftp-anon",
            "nmap_nse",
            "ftp-anon",
            "positive",
            {"anonymous_login": True},
            21,
            None,
        ),
        (
            "nse:ftp-anon",
            "nmap_nse",
            "ftp-anon",
            "negative",
            {"anonymous_login": False},
            21,
            None,
        ),
        (
            "targeted:enum4linux-ng-session",
            "targeted_service_assessment",
            "enum4linux-ng",
            "positive",
            {"session_type": "null", "accepted": True},
            445,
            None,
        ),
        (
            "targeted:enum4linux-ng-session",
            "targeted_service_assessment",
            "enum4linux-ng",
            "negative",
            {"session_type": "null", "accepted": False},
            445,
            None,
        ),
        (
            "modbus:read-only",
            "modbus-read-only-assessment",
            "modbus-read-only-assessment",
            "positive",
            {"read_result": True},
            502,
            1,
        ),
        (
            "modbus:read-only",
            "modbus-read-only-assessment",
            "modbus-read-only-assessment",
            "negative",
            {"read_result": False},
            502,
            1,
        ),
    ],
)
def test_specific_checks_do_not_confirm_unrelated_cve(
    rule_id, source, source_script, result, facts, port, unit_id
) -> None:
    observation = _observation(
        condition_key="CVE-2024-1234",
        port=port,
        unit_id=unit_id,
        method="specific_check",
        result=result,
        source=source,
        source_script=source_script,
        rule_id=rule_id,
        facts=facts,
    )
    result = validate_finding_evidence(
        [observation], cve_id="CVE-2024-1234", issue_key="CVE-2024-1234"
    )
    assert result.confidence == "tentative"
    assert result.evidence_status == "inconclusive"


def test_reducer_is_order_independent_deduplicates_and_keeps_conflict_pair() -> None:
    positive = _observation()
    negative = _observation(
        result="negative",
        evidence="Signing required",
        facts={"signing_required": True},
    )
    extra = _observation(evidence="Alternate structured evidence")
    left = reduce_finding_evidence(
        [positive, negative, extra], issue_key="smb:signing", limit=2
    )
    right = reduce_finding_evidence(
        [negative, positive, positive, extra],
        issue_key="smb:signing",
        limit=2,
    )
    assert left == right
    assert left.evidence_status == "conflicting"
    assert left.confidence == "tentative"
    assert left.evidence_truncated is True


def test_unrelated_endpoint_and_monotonic_truncation() -> None:
    positive = _observation()
    other_endpoint = _observation(
        result="negative", ip="10.0.0.6", evidence="Signing required"
    )
    result = reduce_finding_evidence(
        [positive, other_endpoint], issue_key="smb:signing"
    )
    assert result.evidence_status == "supported"
    merged = reduce_finding_evidence(
        [positive], issue_key="smb:signing", evidence_truncated=True
    )
    later = reduce_finding_evidence(
        [positive, other_endpoint],
        issue_key="smb:signing",
        evidence_truncated=merged.evidence_truncated,
    )
    assert later.evidence_truncated is True


def test_native_ms17_check_requires_expected_cve_and_table() -> None:
    observation = _observation(
        condition_key="CVE-2017-0143",
        method="specific_check",
        source_script="smb-vuln-ms17-010",
        rule_id="nse:smb-vuln-ms17-010",
        facts={
            "vulnerability_state": "VULNERABLE",
            "table": "smb-vuln-ms17-010",
        },
    )
    assessment = validate_finding_evidence(
        [observation],
        cve_id="CVE-2017-0143",
        issue_key="CVE-2017-0143",
    )
    assert assessment.confidence == "confirmed"
    wrong_cve = validate_finding_evidence(
        [observation],
        cve_id="CVE-2017-0144",
        issue_key="CVE-2017-0144",
    )
    assert wrong_cve.confidence == "tentative"


def test_config_cve_reference_stays_tentative() -> None:
    obs = _observation(condition_key="CVE-2024-1234")
    assert (
        validate_finding_evidence([obs], cve_id="CVE-2024-1234").confidence
        == "tentative"
    )
    correlation = _observation(
        condition_key="CVE-2024-1234",
        method="version_correlation",
        source="nvd_enrichment",
        source_script=None,
        rule_id="catalog:nvd-cpe",
        facts={
            "cpe": "cpe:2.3:a:vendor:product:1.0:*:*:*:*:*:*:*",
            "cve_id": "CVE-2024-1234",
        },
    )
    assert (
        validate_finding_evidence(
            [correlation], cve_id="CVE-2024-1234"
        ).confidence
        == "probable"
    )


def test_negative_specific_check_for_unrelated_cve_is_rejected() -> None:
    correlation = _observation(
        ip="10.0.0.5",
        port=21,
        condition_key="CVE-2024-1234",
        method="version_correlation",
        source="nvd_enrichment",
        source_script=None,
        rule_id="catalog:nvd-cpe",
        facts={
            "product": "vendor product",
            "version": "1.0",
            "cve_id": "CVE-2024-1234",
        },
    )
    negative = _observation(
        ip="10.0.0.5",
        port=21,
        condition_key="CVE-2024-1234",
        method="specific_check",
        source_script="ftp-anon",
        rule_id="nse:ftp-anon",
        result="negative",
        facts={"anonymous_login": False},
    )
    result = reduce_finding_evidence(
        [correlation, negative],
        cve_id="CVE-2024-1234",
        issue_key="CVE-2024-1234",
        ip="10.0.0.5",
        port=21,
        protocol="tcp",
    )
    assert result.evidence_status == "supported"
    assert result.confidence == "probable"


@pytest.mark.parametrize("scope", [{"ip": "10.0.0.6"}, {"port": 502}, {"unit_id": 2}])
def test_correlation_conflict_requires_same_endpoint_and_unit(scope) -> None:
    cve = "CVE-2017-0143"
    correlation = _observation(
        ip="10.0.0.5",
        port=445,
        unit_id=None,
        condition_key=cve,
        method="version_correlation",
        source="nvd_enrichment",
        source_script=None,
        rule_id="catalog:nvd-cpe",
        facts={
            "product": "vendor product",
            "version": "1.0",
            "cve_id": cve,
        },
    )
    negative = _observation(
        ip="10.0.0.5",
        port=445,
        unit_id=None,
        condition_key=cve,
        method="specific_check",
        source_script="smb-vuln-ms17-010",
        rule_id="nse:smb-vuln-ms17-010",
        result="negative",
        facts={"vulnerability_state": "NOT VULNERABLE", "table": "smb-vuln-ms17-010"},
    )
    negative.update(scope)
    result = reduce_finding_evidence(
        [correlation, negative], cve_id=cve, issue_key=cve
    )
    assert result.evidence_status == "supported"
    assert result.confidence == "probable"


def test_native_ms17_negative_is_supported_and_conflicts_at_same_scope() -> None:
    cve = "CVE-2017-0143"
    correlation = _observation(
        ip="10.0.0.5",
        port=445,
        condition_key=cve,
        method="version_correlation",
        source="nvd_enrichment",
        source_script=None,
        rule_id="catalog:nvd-cpe",
        facts={"product": "windows", "version": "7", "cve_id": cve},
    )
    negative = _observation(
        ip="10.0.0.5",
        port=445,
        condition_key=cve,
        method="specific_check",
        source_script="smb-vuln-ms17-010",
        rule_id="nse:smb-vuln-ms17-010",
        result="negative",
        facts={"vulnerability_state": "NOT VULNERABLE", "table": "smb-vuln-ms17-010"},
    )
    negative_assessment = validate_finding_evidence(
        [negative], cve_id=cve, issue_key=cve
    )
    assert negative_assessment.evidence_status == "inconclusive"
    conflict = reduce_finding_evidence(
        [correlation, negative], cve_id=cve, issue_key=cve
    )
    assert conflict.evidence_status == "conflicting"
    assert conflict.confidence == "tentative"


def test_reducer_keeps_configuration_and_referenced_cve_conditions_separate() -> None:
    cve = "CVE-2024-1234"
    config = _observation()
    correlation = _observation(
        condition_key=cve,
        method="version_correlation",
        source="nvd_enrichment",
        source_script=None,
        rule_id="catalog:nvd-cpe",
        facts={"cpe": "cpe:2.3:a:vendor:product:1.0", "cve_id": cve},
    )
    assessment = reduce_finding_evidence(
        [config, correlation],
        cve_id=cve,
        issue_key="smb:signing",
        ip="10.0.0.5",
        port=445,
        protocol="tcp",
    )
    assert assessment.confidence == "confirmed"
    assert assessment.evidence_status == "supported"
    assert {item.condition_key for item in assessment.observations} == {
        "smb:signing",
        cve,
    }


def test_ambiguous_issue_keys_never_promote_and_keep_valid_conflict() -> None:
    positive = _observation()
    negative = _observation(
        result="negative",
        evidence="Signing is required",
        facts={"signing_required": True},
    )
    result = reduce_finding_evidence(
        [positive, negative],
        ip="10.0.0.5",
        port=445,
        protocol="tcp",
        issue_key_ambiguous=True,
        allowed_conditions=("smb:signing", "smb:other-signing"),
    )
    assert result.evidence_status == "conflicting"
    assert result.confidence == "tentative"
    assert len(result.observations) == 2


def test_summary_does_not_count_legacy_confirmed_as_demonstrated() -> None:
    legacy = {
        "confidence": "confirmed",
        "detection_method": "unknown",
        "evidence_status": "unknown",
    }
    current = {
        "confidence": "confirmed",
        "detection_method": "configuration_observation",
        "evidence_status": "supported",
        "evidence_observations": [_observation()],
        "evidence_truncated": False,
    }
    summary = summarize_finding_evidence([legacy, current], scope="scan")
    assert summary["by_confidence"]["confirmed"] == 2
    assert summary["demonstrated_records"] == 1
