from __future__ import annotations

from datetime import datetime, timedelta, timezone

import api.services.ai.worker as ai_worker_module
from api.models.persistence import AIScanAnalysisRecord, EnrichmentJobRecord
from api.services.ai.jobs import process_ready_ai_analyses
from api.services.ai.provider import AIProviderError
from api.services.ai.schemas import ScanAIAnalysis
from api.services.ai.worker import run_ai_worker_once
from read_factories import make_org, make_scan
from sqlmodel import select


def _analysis() -> ScanAIAnalysis:
    return ScanAIAnalysis(
        executive_summary="Nenhum risco prioritário foi identificado.",
        overall_assessment="O scan não apresentou findings para priorização.",
        plain_language_summary="Nada urgente apareceu neste resultado.",
        priority_actions=[],
        important_findings=[],
        uncertainties=["A ausência de findings não comprova ausência de risco."],
    )


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


def _pending_analysis(session, scan):
    record = AIScanAnalysisRecord(
        scan_id=scan.scan_id,
        provider="groq",
        model="openai/gpt-oss-120b",
        context_version="1",
        prompt_version="1",
    )
    session.add(record)
    session.commit()
    return record


def test_completed_scan_without_request_does_not_create_job(administrative_session):
    org = make_org(administrative_session, "No Request Org")
    make_scan(administrative_session, org.id)

    class FakeProvider:
        def analyze_scan(self, context):
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
        def analyze_scan(self, context):
            received.append(context)
            return _analysis()

    now = datetime.now(timezone.utc)
    assert _run(administrative_session, FakeProvider(), now=now) == 1
    assert _run(administrative_session, FakeProvider(), now=now) == 0

    record = administrative_session.exec(select(AIScanAnalysisRecord)).one()
    assert record.scan_id == scan.scan_id
    assert record.status == "completed"
    assert record.analysis_json == _analysis().model_dump(mode="json")
    assert record.context_hash is not None and len(record.context_hash) == 64
    assert record.attempts == 1
    assert len(received) == 1


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
        def analyze_scan(self, context):
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
        def analyze_scan(self, context):
            raise AIProviderError("provider_timeout", retryable=True)

    now = datetime.now(timezone.utc)
    assert _run(administrative_session, TimeoutProvider(), now=now) == 1
    record = administrative_session.exec(select(AIScanAnalysisRecord)).one()
    assert record.status == "pending"
    assert record.attempts == 1
    assert record.last_error_code == "provider_timeout"

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
    assert record.last_error_code == "provider_timeout"
    assert record.completed_at is not None


def test_retry_waits_for_configured_delay(administrative_session):
    org = make_org(administrative_session, "Backoff Org")
    scan = make_scan(administrative_session, org.id)
    _pending_analysis(administrative_session, scan)

    class TimeoutProvider:
        def analyze_scan(self, context):
            raise AIProviderError("provider_timeout", retryable=True)

    now = datetime.now(timezone.utc)
    assert _run(administrative_session, TimeoutProvider(), now=now) == 1
    assert (
        _run(
            administrative_session,
            TimeoutProvider(),
            now=now + timedelta(seconds=5),
            retry_delay_seconds=30,
        )
        == 0
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
        def analyze_scan(self, context):
            raise AssertionError("exhausted job must not run")

    assert _run(administrative_session, FakeProvider(), now=now) == 0
    administrative_session.refresh(record)
    assert record.status == "failed"
    assert record.last_error_code == "processing_timeout"


def test_run_ai_worker_once_processes_one_requested_row(
    monkeypatch, administrative_session
):
    monkeypatch.setattr(
        ai_worker_module,
        "get_session",
        lambda: iter([administrative_session]),
    )
    org = make_org(administrative_session, "Worker Org")
    scan = make_scan(administrative_session, org.id)
    _pending_analysis(administrative_session, scan)
    received = []

    class FakeProvider:
        def analyze_scan(self, context):
            received.append(context)
            return _analysis()

    assert run_ai_worker_once(provider=FakeProvider()) == 1
    assert len(received) == 1

    record = administrative_session.exec(select(AIScanAnalysisRecord)).one()
    assert record.status == "completed"


def test_run_ai_worker_loop_skips_provider_when_ai_unavailable(monkeypatch):
    provider_calls: list[object] = []

    def _track_provider(settings):
        provider_calls.append(settings)
        raise AssertionError("provider must not be built when AI is unavailable")

    monkeypatch.setattr(ai_worker_module, "ai_is_available", lambda settings: False)
    monkeypatch.setattr(ai_worker_module, "build_ai_provider", _track_provider)

    ai_worker_module.run_ai_worker_loop()
    assert provider_calls == []
