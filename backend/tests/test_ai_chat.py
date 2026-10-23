from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from api.schemas.read import (
    FindingEvidenceConfidenceCounts,
    FindingEvidenceMethodCounts,
    FindingEvidenceSummary,
    FindingRead,
    HostDetailResponse,
    ScanDetailResponse,
    ScanRiskSummaryResponse,
    SeverityBreakdown,
)
from api.services.ai.chat import (
    build_finding_chat_bundle,
    build_host_chat_bundle,
    build_scan_chat_bundle,
    materialize_chat_response,
    scrub_secrets,
)
from api.services.ai.openai_responses import (
    AIProviderError,
    ChatTextPart,
    ProviderChatAnswer,
    UrlCitation,
)


def _answer(text: str) -> ProviderChatAnswer:
    return ProviderChatAnswer(
        parts=(ChatTextPart(text=text, citations=()),), sources=frozenset()
    )


def _finding(
    title: str,
    service: str | None = None,
    *,
    host_id: UUID | None = None,
    severity: str = "medium",
    risk_score: float | None = None,
    detection_method: str = "unknown",
    evidence_status: str = "unknown",
    evidence_truncated: bool = False,
    confidence: str | None = None,
) -> FindingRead:
    return FindingRead(
        finding_id=uuid4(),
        scan_id=uuid4(),
        host_id=host_id,
        host_ip="192.168.1.10" if host_id is not None else None,
        host_hostname="plc-01" if host_id is not None else None,
        service=service,
        severity=severity,
        title=title,
        description="description",
        recommendation="recommendation",
        evidence="evidence",
        detected_at=datetime.now(UTC),
        risk_score=risk_score,
        detection_method=detection_method,
        evidence_status=evidence_status,
        evidence_truncated=evidence_truncated,
        confidence=confidence,
    )


def _evidence_summary(scope: str, total: int) -> FindingEvidenceSummary:
    return FindingEvidenceSummary(
        scope=scope,
        total_records=total,
        by_method=FindingEvidenceMethodCounts(
            version_correlation=1,
            configuration_observation=0,
            specific_check=0,
            textual_reference=0,
            unknown=total - 1,
        ),
        by_confidence=FindingEvidenceConfidenceCounts(
            tentative=0, probable=1, confirmed=0, unknown=total - 1
        ),
        conflicting_records=1,
        demonstrated_records=0,
    )


def _scan_detail(findings: list[FindingRead], host_count: int) -> ScanDetailResponse:
    return ScanDetailResponse(
        scan_id=uuid4(),
        timestamp=datetime.now(UTC),
        subnet="192.168.1.0/24",
        scan_mode="quick",
        hosts=[],
        findings=findings,
        assessment_status="unavailable",
        assessment_policy_version=None,
        exposures=[],
        status="completed",
        evidence_completeness="complete",
        host_count=host_count,
        finding_count=len(findings),
    )


def _risk(
    findings: list[FindingRead], severity: SeverityBreakdown
) -> ScanRiskSummaryResponse:
    return ScanRiskSummaryResponse(
        scan_id=uuid4(),
        total_findings=len(findings),
        scored_findings=len(findings),
        confirmed_findings=0,
        kev_findings=0,
        average_risk_score=50,
        max_risk_score=90,
        severity=severity,
        top_findings=findings,
    )


def test_question_relevance_survives_the_bounded_cut() -> None:
    """The matching finding must reach the provider even past the five-row limit."""
    filler = [_finding(f"Atualizar OpenSSH {index}") for index in range(6)]
    relevant = _finding("Senha fraca", "modbus")
    detail = _scan_detail([*filler, relevant], host_count=1)

    bundle = build_scan_chat_bundle(
        detail, _risk(detail.findings, SeverityBreakdown(medium=7)),
        "o que devo corrigir no modbus?",
    )

    assert bundle.display_values_by_ref["finding_1"] == "Senha fraca"
    assert bundle.finding_ids_by_ref["finding_1"] == relevant.finding_id


def test_scan_chat_keeps_full_summary_and_limited_findings_sample() -> None:
    findings = [
        _finding(f"Finding {index}", detection_method="version_correlation",
                 evidence_status="inconclusive", confidence="probable")
        for index in range(7)
    ]
    detail = _scan_detail(findings, host_count=1).model_copy(
        update={"evidence_summary": _evidence_summary("scan", 37)}
    )

    bundle = build_scan_chat_bundle(
        detail, _risk(findings, SeverityBreakdown(medium=7))
    )

    context = bundle.provider_context
    assert len(context.top_findings) == 5
    assert context.evidence_summary.total_records == 37
    assert context.evidence_summary.by_method.version_correlation == 1
    assert context.top_findings[0].detection_method == "version_correlation"
    assert context.top_findings[0].evidence_status == "inconclusive"
    assert context.top_findings[0].confidence == "probable"


@pytest.mark.parametrize(
    ("method", "status", "confidence", "truncated"),
    [
        ("unknown", "unknown", None, False),
        ("specific_check", "unknown", "tentative", False),
        ("specific_check", "inconclusive", "tentative", False),
        ("configuration_observation", "conflicting", "tentative", True),
        ("version_correlation", "supported", "probable", False),
    ],
)
def test_finding_chat_retains_semantic_limits(method, status, confidence, truncated):
    finding = _finding(
        "RAW_TITLE_SENTINEL", "RAW_SERVICE_SENTINEL", host_id=uuid4(),
        detection_method=method, evidence_status=status,
        confidence=confidence, evidence_truncated=truncated,
    )
    bundle = build_finding_chat_bundle(finding)

    context = bundle.provider_context
    row = context.finding
    assert row.detection_method == method
    assert row.evidence_status == status
    assert row.confidence == confidence
    assert row.evidence_truncated is truncated
    assert row.evidence_basis == "unknown"
    payload = context.model_dump_json()
    for raw in ("RAW_TITLE_SENTINEL", "RAW_SERVICE_SENTINEL", "192.168.1.10", "plc-01"):
        assert raw not in payload
    assert context.evidence_summary.total_records == 1


def test_question_without_terms_keeps_the_original_order() -> None:
    findings = [_finding("Primeiro"), _finding("Segundo")]
    detail = _scan_detail(findings, host_count=1)

    bundle = build_scan_chat_bundle(
        detail, _risk(findings, SeverityBreakdown(medium=2)), "e de um"
    )

    assert bundle.display_values_by_ref["finding_1"] == "Primeiro"


def test_machine_summary_counts_findings_by_machine_ref() -> None:
    host_id = uuid4()
    findings = [
        _finding("First", "http", host_id=host_id, severity="high"),
        _finding("Second", "ssh", host_id=host_id, severity="critical"),
        _finding("Third", "http", host_id=uuid4(), severity="low"),
    ]
    detail = _scan_detail(findings, host_count=2)

    bundle = build_scan_chat_bundle(
        detail, _risk(findings, SeverityBreakdown(critical=1, high=1, low=1))
    )

    summary = bundle.provider_context.machine_vulnerability_summary
    assert summary[0].machine_ref == "machine_1"
    assert summary[0].finding_count == 2


def test_finding_chat_bundle_uses_placeholders_only() -> None:
    finding = _finding("OpenSSH vulnerability", "ssh", host_id=uuid4(), severity="high")

    bundle = build_finding_chat_bundle(finding)

    payload = bundle.provider_context.model_dump_json()
    assert str(finding.finding_id) not in payload
    assert finding.title not in payload
    assert "192.168.1.10" not in payload
    assert bundle.provider_context.finding.finding_ref == "finding_1"


def test_host_chat_bundle_sends_no_service_map() -> None:
    host_id = uuid4()
    host = HostDetailResponse(
        host_id=host_id,
        ip="192.168.1.10",
        mac=None,
        hostname="plc-01",
        vendor="Acme",
        first_seen_at=datetime.now(UTC),
        last_seen_at=datetime.now(UTC),
        open_ports_count=2,
        machine_type="sensor",
        device_profile=None,
        vulnerability_count=2,
        highest_severity="critical",
        assessment_status="unavailable",
        assessment_policy_version=None,
        exposures=[],
        ports=[],
        scan_history=[],
    )
    finding = _finding("Modbus exposed", "modbus", host_id=host_id, severity="critical")

    bundle = build_host_chat_bundle(host, [finding])

    payload = bundle.provider_context.model_dump_json()
    assert "192.168.1.10" not in payload
    assert "plc-01" not in payload
    assert "modbus" not in payload
    assert str(host_id) not in payload
    assert bundle.provider_context.machine_ref == "machine_1"


def test_host_chat_uses_full_aggregate_summary_with_bounded_rows() -> None:
    host_id = uuid4()
    host = HostDetailResponse(
        host_id=host_id, ip="192.168.1.10", mac=None, hostname="plc-01",
        vendor="Acme", first_seen_at=datetime.now(UTC),
        last_seen_at=datetime.now(UTC), open_ports_count=2,
        machine_type="sensor", device_profile=None, vulnerability_count=19,
        highest_severity="critical", assessment_status="unavailable",
        assessment_policy_version=None, exposures=[], ports=[], scan_history=[],
    )
    findings = [
        _finding(f"Finding {index}", host_id=host_id) for index in range(12)
    ]
    summary = _evidence_summary("filtered_findings", 83)

    bundle = build_host_chat_bundle(host, findings, summary)

    context = bundle.provider_context
    assert len(context.findings) == 10
    assert context.evidence_summary == summary


def test_materialize_chat_response_substitutes_display_values() -> None:
    finding_id = uuid4()
    response = materialize_chat_response(
        _answer("Revise finding_1 on machine_1."),
        {"finding_1": finding_id},
        {
            "finding_1": "Weak SSH configuration",
            "machine_1": "edge-router",
        },
    )

    assert response.answer == "Revise Weak SSH configuration on edge-router."
    assert response.referenced_finding_ids == [finding_id]


def test_materialize_chat_response_rejects_an_unsent_placeholder() -> None:
    """An unknown token in the prose must fail as a provider error, not a KeyError."""
    with pytest.raises(AIProviderError) as caught:
        materialize_chat_response(
            _answer("Check machine_9 as well."),
            {"finding_1": uuid4()},
            {"finding_1": "Weak SSH configuration"},
        )

    assert caught.value.code == "invalid_provider_response"


def test_materialize_chat_response_keeps_only_cited_and_consulted_links() -> None:
    text = (
        "**Update** the camera ([vendor.example.com](https://vendor.example.com/a)).\n"
        "## Steps\n"
        "1. Read [the forum](https://forum.example.com/t) at https://x.example/y\n"
        "- Ask <b>IT</b> to check `config` (see [other](https://other.example.com))."
    )
    start = text.index("[vendor")
    end = text.index(")).") + 1
    forum_start = text.index("[the forum")
    answer = ProviderChatAnswer(
        parts=(
            ChatTextPart(
                text=text,
                citations=(
                    UrlCitation(
                        start=start,
                        end=end,
                        url="https://www.vendor.example.com/a?utm_source=openai",
                    ),
                    UrlCitation(
                        start=forum_start,
                        end=forum_start + len("[the forum](https://forum.example.com/t)"),
                        url="https://forum.example.com/t",
                    ),
                ),
            ),
        ),
        sources=frozenset({"https://www.vendor.example.com/a"}),
    )

    response = materialize_chat_response(answer, {}, {})

    assert response.answer == (
        "**Update** the camera ([vendor.example.com](https://www.vendor.example.com/a)).\n"
        "Steps\n"
        "1. Read at\n"
        "- Ask IT to check config (see other)."
    )
    assert response.uncertainties == []


def test_materialize_chat_response_neutralises_markup_in_display_values() -> None:
    finding_id = uuid4()

    response = materialize_chat_response(
        _answer("Fix finding_1 first."),
        {"finding_1": finding_id},
        {"finding_1": "[x](https://evil.example) **bad**"},
    )

    assert response.answer == "Fix (x)(https://evil.example) bad first."
    assert response.referenced_finding_ids == [finding_id]


@pytest.mark.parametrize(
    ("question", "expected"),
    [
        ("my password: hunter2 please", "my password: [removed] please"),
        ("api key=abc and token: xyz", "api key=[removed] and token: [removed]"),
        ("Bearer eyJabc.def.ghi", "[removed]"),
        ("key sk-abcdefghijklmnop1234", "key [removed]"),
        ("why is 192.168.1.10 open", "why is [removed] open"),
        ("mac aa:bb:cc:dd:ee:ff", "mac [removed]"),
        ("router fe80::1:2:3 at 10:30:15", "router [removed] at 10:30:15"),
        ("blob A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6", "blob [removed]"),
        ("how do I fix CVE-2026-1234 on OpenSSH 9.2p1", None),
    ],
)
def test_scrub_secrets(question, expected) -> None:
    assert scrub_secrets(question) == (question if expected is None else expected)


def test_answer_scrubbing_keeps_addresses_but_removes_tokens() -> None:
    assert (
        scrub_secrets(
            "Open 192.168.1.1 and use sk-abcdefghijklmnop1234", addresses=False
        )
        == "Open 192.168.1.1 and use [removed]"
    )
