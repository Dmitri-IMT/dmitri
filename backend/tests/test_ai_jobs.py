from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import api.services.worker as worker_module
import pytest
from api.models.persistence import AIScanAnalysisRecord, EnrichmentJobRecord, KevRecord
from api.schemas.ai import (
    AIProviderFindingExplanation,
    AIProviderRecommendedAction,
    ProviderScanAIAnalysis,
)
from api.schemas.read import (
    FindingEvidenceConfidenceCounts,
    FindingEvidenceMethodCounts,
    FindingEvidenceSummary,
    SeverityBreakdown,
)
from api.services.ai.context import AIFindingContext, ScanAIContext
from api.services.ai.groq import AIProviderError
from api.services.ai.jobs import (
    _validate_analysis_with_repair,
    process_ready_ai_analyses,
)
from api.services.worker import run_ai_worker_once
from pydantic import ValidationError
from read_factories import (
    make_finding,
    make_host,
    make_org,
    make_scan,
    make_scan_host,
)
from sqlmodel import select


def _analysis() -> ProviderScanAIAnalysis:
    return ProviderScanAIAnalysis(
        executive_summary="Nenhum risco prioritário foi identificado.",
        overall_assessment="O scan não apresentou findings para priorização.",
        plain_language_summary="Nada urgente apareceu neste resultado.",
        priority_actions=[],
        important_findings=[],
        uncertainties=["A ausência de findings não comprova ausência de risco."],
    )


def _grounded_analysis(finding_ref: str = "finding_1") -> ProviderScanAIAnalysis:
    return ProviderScanAIAnalysis(
        executive_summary="One vulnerability needs attention.",
        overall_assessment="The observed risk is high but limited in scope.",
        plain_language_summary="One exposed service should be reviewed soon.",
        priority_actions=[
            AIProviderRecommendedAction(
                priority="high",
                title="Review the affected service",
                description="Ask a qualified professional to validate the service.",
                related_finding_refs=[finding_ref],
            )
        ],
        important_findings=[
            AIProviderFindingExplanation(
                finding_ref=finding_ref,
                why_it_matters="The service is exposed and has a high risk score.",
                plain_language_explanation="An exposed service may need an update.",
                recommendation="Have a professional validate and update it.",
                evidence_used=["NVD validated the supplied CVE."],
                uncertainty=None,
            )
        ],
        uncertainties=[],
    )


def _scan_with_finding(session):
    org = make_org(session, "Grounding Org")
    scan = make_scan(session, org.id)
    host = make_host(session, org.id, "192.168.1.10")
    scan_host = make_scan_host(session, scan.scan_id, host.id, "192.168.1.10")
    finding = make_finding(session, scan.scan_id, scan_host.id, "grounding")
    return scan, finding


def _run(session, provider, *, now, max_attempts=2, retry_delay_seconds=0):
    return process_ready_ai_analyses(
        session,
        provider=provider,
        batch_size=10,
        max_findings=10,
        max_attempts=max_attempts,
        retry_delay_seconds=retry_delay_seconds,
        stale_after_seconds=60,
        now=now,
    )


def _pending_analysis(session, scan, *, language="en"):
    record = AIScanAnalysisRecord(
        scan_id=scan.scan_id,
        provider="groq",
        model="openai/gpt-oss-120b",
        context_version="1",
        prompt_version="1",
        language=language,
    )
    session.add(record)
    session.commit()
    return record


def test_completed_scan_without_request_does_not_create_job(administrative_session):
    org = make_org(administrative_session, "No Request Org")
    make_scan(administrative_session, org.id)

    class FakeProvider:
        def analyze_scan(self, context, language="en"):
            raise AssertionError("provider must not run without a request")

    assert (
        _run(
            administrative_session,
            FakeProvider(),
            now=datetime.now(timezone.utc),
        )
        == 0
    )
    assert administrative_session.exec(select(AIScanAnalysisRecord)).all() == []


def test_requested_ai_job_runs_once_after_enrichment_is_terminal(
    administrative_session,
):
    org = make_org(administrative_session, "AI Org")
    scan = make_scan(administrative_session, org.id)
    _pending_analysis(administrative_session, scan)
    received = []

    class FakeProvider:
        def analyze_scan(self, context, language="en"):
            received.append(context)
            return _analysis()

        def analyze_chunk(self, context, *, language="en"):
            raise AssertionError("scan analysis should use one provider request")

        def repair_chunk(self, context, violation_codes, *, language="en"):
            raise AssertionError("scan analysis should not repair finding chunks")

        def synthesize_scan(
            self, context, child_results, failed_refs, *, language="en"
        ):
            raise AssertionError("scan analysis should not synthesize child requests")

    now = datetime.now(timezone.utc)
    assert _run(administrative_session, FakeProvider(), now=now) == 1
    assert _run(administrative_session, FakeProvider(), now=now) == 0

    record = administrative_session.exec(select(AIScanAnalysisRecord)).one()
    assert record.scan_id == scan.scan_id
    assert record.status == "completed"
    assert record.analysis_json == {
        "executive_summary": _analysis().executive_summary,
        "overall_assessment": _analysis().overall_assessment,
        "plain_language_summary": _analysis().plain_language_summary,
        "priority_actions": [],
        "important_findings": [],
        "uncertainties": _analysis().uncertainties,
    }
    assert record.context_hash is not None and len(record.context_hash) == 64
    assert record.analyzed_findings == 0
    assert record.failed_findings == 0
    assert record.total_findings == 0
    assert record.attempts == 1
    assert len(received) == 1


def test_grounded_analysis_completes(administrative_session):
    scan, finding = _scan_with_finding(administrative_session)
    _pending_analysis(administrative_session, scan)
    expected = _grounded_analysis()
    received = []

    class FakeProvider:
        def analyze_scan(self, context, language="en"):
            received.append(context)
            return expected

    now = datetime.now(timezone.utc)
    assert _run(administrative_session, FakeProvider(), now=now) == 1

    record = administrative_session.exec(select(AIScanAnalysisRecord)).one()
    assert record.status == "completed"
    assert record.analysis_json["important_findings"][0]["finding_id"] == str(
        finding.finding_id
    )
    assert received[0].top_findings[0].finding_ref == "finding_1"


def test_unknown_provider_reference_is_repaired_before_materialization(
    administrative_session,
):
    scan, _ = _scan_with_finding(administrative_session)
    _pending_analysis(administrative_session, scan)
    rejected = _grounded_analysis("finding_99")
    repaired = _grounded_analysis()
    received_codes = []

    class RepairingProvider:
        def analyze_scan(self, context, language="en"):
            return rejected

        def repair_analysis(self, context, violation_codes, language="en"):
            received_codes.extend(violation_codes)
            return repaired

    assert (
        _run(
            administrative_session,
            RepairingProvider(),
            now=datetime.now(timezone.utc),
        )
        == 1
    )
    record = administrative_session.exec(select(AIScanAnalysisRecord)).one()
    assert record.status == "completed"
    assert "analysis contains an unknown reference" in received_codes


@pytest.mark.parametrize(
    "defect", ["invented_explanation", "invented_action", "duplicate_explanation"]
)
def test_ungrounded_analysis_fails(administrative_session, defect):
    scan, finding = _scan_with_finding(administrative_session)
    _pending_analysis(administrative_session, scan)
    analysis = _grounded_analysis()
    if defect == "invented_explanation":
        analysis.important_findings[0].finding_ref = "finding_99"
    elif defect == "invented_action":
        analysis.priority_actions[0].related_finding_refs = ["finding_99"]
    else:
        analysis.important_findings.append(analysis.important_findings[0])

    class FakeProvider:
        def analyze_scan(self, context, language="en"):
            return analysis

        def repair_analysis(self, context, violation_codes, language="en"):
            return analysis

    now = datetime.now(timezone.utc)
    assert _run(administrative_session, FakeProvider(), now=now) == 1

    record = administrative_session.exec(select(AIScanAnalysisRecord)).one()
    assert record.status == "failed"
    assert record.last_error == "invalid_analysis"
    assert record.analysis_json is None


@pytest.mark.parametrize(
    ("defect", "error"),
    [("missing_org", "scan_unavailable"), ("context_crash", "internal_error")],
)
def test_unbuildable_context_fails(
    administrative_session, monkeypatch, defect, error
):
    scan, finding = _scan_with_finding(administrative_session)
    _pending_analysis(administrative_session, scan)
    if defect == "missing_org":
        scan.org_id = None
        administrative_session.add(scan)
        administrative_session.commit()
    else:

        def crash(*args, **kwargs):
            raise RuntimeError("boom")

        monkeypatch.setattr("api.services.ai.jobs.build_scan_ai_context", crash)

    class FakeProvider:
        def analyze_scan(self, context, language="en"):
            return _grounded_analysis()

    now = datetime.now(timezone.utc)
    assert _run(administrative_session, FakeProvider(), now=now) == 1

    record = administrative_session.exec(select(AIScanAnalysisRecord)).one()
    assert record.status == "failed"
    assert record.last_error == error
    assert record.analysis_json is None


def test_analysis_schema_forbids_unknown_fields():
    payload = _grounded_analysis().model_dump()
    payload["invented_score"] = 100

    with pytest.raises(ValidationError):
        ProviderScanAIAnalysis.model_validate(payload)


def test_ai_job_waits_for_active_enrichment(administrative_session):
    org = make_org(administrative_session, "Waiting Org")
    scan = make_scan(administrative_session, org.id)
    record = _pending_analysis(administrative_session, scan)
    administrative_session.add(
        EnrichmentJobRecord(
            scan_id=scan.scan_id,
            job_type="nvd_cve",
            target_value="CVE-2026-0001",
            status="pending",
        )
    )
    administrative_session.commit()

    class FakeProvider:
        def analyze_scan(self, context, language="en"):
            raise AssertionError("provider must not run before enrichment")

    assert (
        _run(
            administrative_session,
            FakeProvider(),
            now=datetime.now(timezone.utc),
        )
        == 0
    )
    administrative_session.refresh(record)
    assert record.status == "pending"
    assert record.attempts == 0


def test_retryable_provider_failure_is_bounded(administrative_session):
    org = make_org(administrative_session, "Retry Org")
    scan = make_scan(administrative_session, org.id)
    _pending_analysis(administrative_session, scan)

    class TimeoutProvider:
        def analyze_scan(self, context, language="en"):
            raise AIProviderError("provider_timeout", retryable=True)

    now = datetime.now(timezone.utc)
    assert _run(administrative_session, TimeoutProvider(), now=now) == 1
    record = administrative_session.exec(select(AIScanAnalysisRecord)).one()
    assert record.status == "pending"
    assert record.attempts == 1
    assert record.last_error == "provider_timeout"

    assert (
        _run(
            administrative_session,
            TimeoutProvider(),
            now=now + timedelta(seconds=1),
        )
        == 1
    )
    administrative_session.refresh(record)
    assert record.status == "failed"
    assert record.attempts == 2
    assert record.last_error == "provider_timeout"
    assert record.completed_at is not None


def test_style_violation_is_repaired_once(administrative_session):
    scan, _ = _scan_with_finding(administrative_session)
    _pending_analysis(administrative_session, scan)
    rejected = _grounded_analysis()
    rejected.executive_summary = "Your network is safe."
    repaired = _grounded_analysis()
    received_codes = []

    class RepairingProvider:
        def analyze_scan(self, context, language="en"):
            return rejected

        def repair_analysis(self, context, violation_codes, language="en"):
            received_codes.extend(violation_codes)
            return repaired

    assert (
        _run(
            administrative_session,
            RepairingProvider(),
            now=datetime.now(timezone.utc),
        )
        == 1
    )
    record = administrative_session.exec(select(AIScanAnalysisRecord)).one()
    assert record.status == "completed"
    assert "executive_summary:safety_certification" in received_codes


def test_style_repair_gets_deterministic_kev_action_in_pt_br(
    administrative_session,
):
    scan, finding = _scan_with_finding(administrative_session)
    finding.cve_id = "CVE-2026-0001"
    administrative_session.add(finding)
    administrative_session.add(KevRecord(cve_id=finding.cve_id))
    administrative_session.commit()
    _pending_analysis(administrative_session, scan, language="pt-BR")

    rejected = _grounded_analysis()
    rejected.executive_summary = "Your network is safe."
    repaired = _grounded_analysis()
    repaired.priority_actions = []
    calls = []

    class RepairingProvider:
        def analyze_scan(self, context, language="en"):
            calls.append(("analysis", language))
            return rejected

        def repair_analysis(self, context, violation_codes, language="en"):
            calls.append(("repair", language))
            return repaired

    assert (
        _run(
            administrative_session,
            RepairingProvider(),
            now=datetime.now(timezone.utc),
        )
        == 1
    )
    record = administrative_session.exec(select(AIScanAnalysisRecord)).one()
    assert record.status == "completed"
    assert calls == [("analysis", "pt-BR"), ("repair", "pt-BR")]
    assert len(record.analysis_json["priority_actions"]) == 1
    assert record.analysis_json["priority_actions"][0]["title"] == (
        "Revisar vulnerabilidade no KEV"
    )


def test_second_style_violation_fails_the_job(administrative_session):
    scan, _ = _scan_with_finding(administrative_session)
    _pending_analysis(administrative_session, scan)
    rejected = _grounded_analysis()
    rejected.executive_summary = "Your network is safe."

    class InvalidRepairProvider:
        def analyze_scan(self, context, language="en"):
            return rejected

        def repair_analysis(self, context, violation_codes, language="en"):
            return rejected

    assert (
        _run(
            administrative_session,
            InvalidRepairProvider(),
            now=datetime.now(timezone.utc),
        )
        == 1
    )
    record = administrative_session.exec(select(AIScanAnalysisRecord)).one()
    assert record.status == "failed"
    assert record.last_error == "style_violation"


def test_missing_kev_action_is_repaired_before_analysis_is_rejected():
    context = ScanAIContext(
        scan_mode="quick",
        duration_seconds=1,
        host_count=1,
        total_findings=1,
        scored_findings=1,
        confirmed_findings=1,
        kev_findings=1,
        average_risk_score=90,
        max_risk_score=90,
        severity=SeverityBreakdown(critical=1),
        evidence_summary=FindingEvidenceSummary(
            scope="scan",
            total_records=0,
            by_method=FindingEvidenceMethodCounts(
                version_correlation=0,
                configuration_observation=0,
                specific_check=0,
                textual_reference=0,
                unknown=0,
            ),
            by_confidence=FindingEvidenceConfidenceCounts(
                tentative=0, probable=0, confirmed=0, unknown=0
            ),
            conflicting_records=0,
            demonstrated_records=0,
        ),
        top_findings=[
            AIFindingContext(
                finding_ref="finding_1",
                machine_ref="machine_1",
                cve_id="CVE-2026-0001",
                cvss_score=9.8,
                severity="critical",
                confidence="confirmed",
                risk_score=90,
                exploitability=1,
                epss_score=0.9,
                epss_percentile=0.99,
                is_kev=True,
                known_ransomware=False,
            )
        ],
    )
    context._finding_ids_by_ref = {"finding_1": uuid4()}
    context._display_values_by_ref = {
        "finding_1": "CVE-2026-0001 vulnerability",
        "machine_1": "Test machine",
    }
    missing_action = _analysis()
    received_codes = []

    class RepairingProvider:
        def repair_analysis(self, context, violation_codes, *, language="en"):
            received_codes.extend(violation_codes)
            return _grounded_analysis()

    validated = _validate_analysis_with_repair(
        RepairingProvider(), context, missing_action, language="en"
    )

    assert validated.priority_actions[0].related_finding_refs == ["finding_1"]
    assert "analysis omits a KEV finding from actions" in received_codes


def test_retry_waits_for_configured_delay(administrative_session):
    org = make_org(administrative_session, "Backoff Org")
    scan = make_scan(administrative_session, org.id)
    _pending_analysis(administrative_session, scan)

    class TimeoutProvider:
        def analyze_scan(self, context, language="en"):
            raise AIProviderError("provider_timeout", retryable=True)

    now = datetime.now(timezone.utc)
    assert (
        _run(
            administrative_session,
            TimeoutProvider(),
            now=now,
            retry_delay_seconds=30,
        )
        == 1
    )
    record = administrative_session.exec(select(AIScanAnalysisRecord)).one()
    assert record.next_attempt_at == now + timedelta(seconds=30)
    assert (
        _run(
            administrative_session,
            TimeoutProvider(),
            now=now + timedelta(seconds=5),
            retry_delay_seconds=30,
        )
        == 0
    )
    assert (
        _run(
            administrative_session,
            TimeoutProvider(),
            now=now + timedelta(seconds=30),
            retry_delay_seconds=30,
        )
        == 1
    )


def test_stale_exhausted_job_becomes_failed(administrative_session):
    org = make_org(administrative_session, "Stale Org")
    scan = make_scan(administrative_session, org.id)
    now = datetime.now(timezone.utc)
    record = AIScanAnalysisRecord(
        scan_id=scan.scan_id,
        provider="groq",
        model="openai/gpt-oss-120b",
        status="processing",
        context_version="1",
        prompt_version="1",
        attempts=2,
        started_at=now - timedelta(minutes=2),
    )
    administrative_session.add(record)
    administrative_session.commit()

    class FakeProvider:
        def analyze_scan(self, context, language="en"):
            raise AssertionError("exhausted job must not run")

    assert _run(administrative_session, FakeProvider(), now=now) == 0
    administrative_session.refresh(record)
    assert record.status == "failed"
    assert record.last_error == "processing_timeout"


def test_run_ai_worker_once_processes_one_requested_row(
    monkeypatch, administrative_session
):
    monkeypatch.setattr(
        worker_module,
        "get_session",
        lambda: iter([administrative_session]),
    )
    org = make_org(administrative_session, "Worker Org")
    scan = make_scan(administrative_session, org.id)
    _pending_analysis(administrative_session, scan)
    received = []

    class FakeProvider:
        def analyze_scan(self, context, language="en"):
            received.append(context)
            return _analysis()

    assert run_ai_worker_once(provider=FakeProvider()) == 1
    assert len(received) == 1

    record = administrative_session.exec(select(AIScanAnalysisRecord)).one()
    assert record.status == "completed"


def test_run_ai_worker_loop_skips_provider_when_ai_unavailable(monkeypatch):
    poll_calls: list[object] = []

    monkeypatch.setattr(worker_module, "build_ai_provider", lambda settings: None)
    monkeypatch.setattr(
        worker_module, "_poll_forever", lambda *args: poll_calls.append(args)
    )

    worker_module.run_ai_worker_loop()
    assert poll_calls == []
