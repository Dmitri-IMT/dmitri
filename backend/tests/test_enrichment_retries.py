from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlmodel import Session, select

from api.core.config import get_settings
from api.dependencies.agent_auth import AgentIdentity
from api.models.command import Agent
from api.models.identity import Org
from api.models.persistence import (
    AIScanAnalysisRecord,
    EnrichmentJobRecord,
    FindingRecord,
    PortRecord,
    ScanRecord,
)
from api.schemas.scan import (
    FindingEvidenceObservationPayload,
    FindingPayload,
    HostPayload,
    PortPayload,
    ScanIngestRequest,
)
from api.services.enrichment import (
    claim_pending_enrichment_jobs,
    process_claimed_enrichment_job,
)
from api.services.nvd import NvdTemporaryError
from api.services.persistence import ingest_scan


def _one_nvd_job(
    session: Session,
    *,
    org: Org,
    agent: Agent,
) -> EnrichmentJobRecord:
    scan = ScanIngestRequest(
        scan_id=uuid4(),
        timestamp=datetime.now(timezone.utc),
        subnet="10.0.0.0/24",
        scan_mode="standard",
        hosts=[
            HostPayload(
                ip="10.0.0.10",
                mac=None,
                hostname="host",
                vendor="vendor",
                ports=[
                    PortPayload(
                        port=443,
                        protocol="tcp",
                        state="open",
                        service="https",
                        cpes=["cpe:2.3:a:vendor:product:1.0:*:*:*:*:*:*:*"],
                    )
                ],
            )
        ],
        findings=[],
    )
    ingest_scan(
        session,
        scan,
        identity=AgentIdentity(agent_id=agent.id, org_id=org.id),
        now=datetime.now(timezone.utc),
    )
    return session.exec(select(EnrichmentJobRecord)).one()


def test_nvd_rate_limit_requeues_job_for_later(
    monkeypatch: pytest.MonkeyPatch,
    runtime_session: Session,
    seeded_org: Org,
    provisioned_agent: Agent,
) -> None:
    monkeypatch.setenv("ENRICHMENT_RETRY_DELAY_SECONDS", "12")
    get_settings.cache_clear()
    job = _one_nvd_job(
        runtime_session,
        org=seeded_org,
        agent=provisioned_agent,
    )
    claimed = claim_pending_enrichment_jobs(runtime_session, batch_size=1)
    assert claimed == [job]

    class _RateLimitedClient:
        def query_by_cpe(self, session: Session, cpe: str) -> dict:
            raise NvdTemporaryError(
                "nvd_rate_limited",
                retry_after_seconds=45,
            )

    before = datetime.now(timezone.utc)
    process_claimed_enrichment_job(
        runtime_session,
        claimed[0],
        client=_RateLimitedClient(),  # type: ignore[arg-type]
    )

    runtime_session.refresh(job)
    assert job.status == "pending"
    assert job.attempts == 1
    assert job.last_error == "nvd_rate_limited"
    assert job.completed_at is None
    assert job.next_attempt_at is not None
    assert job.next_attempt_at >= before + timedelta(seconds=45)

    assert claim_pending_enrichment_jobs(runtime_session, batch_size=1) == []
    get_settings.cache_clear()


def test_nvd_cpe_job_adds_structured_correlation(
    runtime_session: Session,
    seeded_org: Org,
    provisioned_agent: Agent,
) -> None:
    job = _one_nvd_job(
        runtime_session,
        org=seeded_org,
        agent=provisioned_agent,
    )
    standalone_negative = FindingEvidenceObservationPayload(
        ip="10.0.0.10",
        port=445,
        protocol="tcp",
        condition_key="CVE-2017-0143",
        method="specific_check",
        result="negative",
        source="nmap_nse",
        source_script="smb-vuln-ms17-010",
        rule_id="nse:smb-vuln-ms17-010",
        rule_version="1",
        evidence="The MS17-010 check returned NOT VULNERABLE.",
        facts={
            "vulnerability_state": "NOT VULNERABLE",
            "table": "smb-vuln-ms17-010",
        },
    )
    scan_record = runtime_session.get(ScanRecord, job.scan_id)
    assert scan_record is not None
    port_record = runtime_session.get(PortRecord, job.port_id)
    assert port_record is not None
    port_record.port = 445
    runtime_session.add(port_record)
    scan_record.finding_evidence_policy_version = "1"
    scan_record.finding_observations_json = [
        standalone_negative.model_dump(mode="json")
    ]
    runtime_session.add(scan_record)
    runtime_session.commit()
    claim_pending_enrichment_jobs(runtime_session, batch_size=1)

    class _MatchedClient:
        def query_by_cpe(self, session: Session, cpe: str) -> dict:
            return {
                "vulnerabilities": [
                    {
                        "cve": {
                            "id": "CVE-2017-0143",
                            "descriptions": [{"lang": "en", "value": "Public CVE."}],
                            "references": [],
                            "metrics": {
                                "cvssMetricV31": [{"cvssData": {"baseScore": 8.0}}]
                            },
                        }
                    }
                ]
            }

    process_claimed_enrichment_job(
        runtime_session,
        job,
        client=_MatchedClient(),  # type: ignore[arg-type]
    )
    finding = runtime_session.exec(select(FindingRecord)).one()
    assert finding.confidence == "tentative"
    assert finding.finding_evidence_policy_version == "1"
    assert finding.evidence_observations_json is not None
    observation = next(
        item
        for item in finding.evidence_observations_json
        if item["method"] == "version_correlation"
    )
    assert observation["method"] == "version_correlation"
    assert observation["condition_key"] == "CVE-2017-0143"
    assert observation["facts"]["cpe"] == job.target_value
    assert {item["result"] for item in finding.evidence_observations_json} == {
        "negative",
        "positive",
    }


def test_nvd_cve_job_adds_context_without_replacing_evidence(
    runtime_session: Session,
    seeded_org: Org,
    provisioned_agent: Agent,
) -> None:
    cve_id = "CVE-2025-1234"
    observation = FindingEvidenceObservationPayload(
        ip="10.0.0.10",
        port=443,
        protocol="tcp",
        condition_key=cve_id,
        method="version_correlation",
        result="positive",
        source="nmap_vulners",
        source_script="vulners",
        rule_id="catalog:nmap-vulners",
        rule_version="1",
        evidence="Observed HTTPS product version matched a CVE.",
        facts={"product": "product", "version": "1.0", "cve_id": cve_id},
    )
    scan = ScanIngestRequest(
        scan_id=uuid4(),
        timestamp=datetime.now(timezone.utc),
        subnet="10.0.0.0/24",
        scan_mode="standard",
        hosts=[
            HostPayload(
                ip="10.0.0.10",
                mac=None,
                hostname="host",
                vendor="vendor",
                ports=[
                    PortPayload(
                        port=443,
                        protocol="tcp",
                        state="open",
                        service="https",
                        cpes=[],
                    )
                ],
            )
        ],
        findings=[
            FindingPayload(
                ip="10.0.0.10",
                port=443,
                protocol="tcp",
                issue_key=cve_id,
                source="nmap_vulners",
                cve_id=cve_id,
                severity="high",
                title="Version maps to a CVE",
                description="A version correlation was observed.",
                recommendation="Review the affected service.",
                evidence="Observed product version and CVE match.",
                evidence_observations=[observation],
            )
        ],
        finding_evidence_policy_version="1",
    )
    ingest_scan(
        runtime_session,
        scan,
        identity=AgentIdentity(agent_id=provisioned_agent.id, org_id=seeded_org.id),
        now=datetime.now(timezone.utc),
    )
    job = runtime_session.exec(
        select(EnrichmentJobRecord).where(
            EnrichmentJobRecord.scan_id == scan.scan_id,
            EnrichmentJobRecord.job_type == "nvd_cve",
        )
    ).one()
    finding = runtime_session.exec(select(FindingRecord)).one()
    original_observations = finding.evidence_observations_json
    original_confidence = finding.confidence

    class _CveClient:
        def query_by_cve(self, session: Session, target: str) -> dict:
            return {
                "vulnerabilities": [
                    {
                        "cve": {
                            "id": target,
                            "descriptions": [{"lang": "en", "value": "Public CVE."}],
                            "references": [],
                            "metrics": {
                                "cvssMetricV31": [{"cvssData": {"baseScore": 8.1}}]
                            },
                        }
                    }
                ]
            }

    process_claimed_enrichment_job(
        runtime_session,
        job,
        client=_CveClient(),  # type: ignore[arg-type]
    )
    runtime_session.refresh(finding)
    assert finding.evidence_observations_json == original_observations
    assert finding.confidence == original_confidence == "probable"
    assert finding.issue_key == cve_id
    assert "target applicability is unverified" in finding.evidence


def test_terminal_enrichment_can_enqueue_one_auto_analysis(
    monkeypatch: pytest.MonkeyPatch,
    runtime_session: Session,
    seeded_org: Org,
    provisioned_agent: Agent,
) -> None:
    monkeypatch.setenv("AI_ENABLED", "true")
    monkeypatch.setenv("AI_AUTO_ANALYSIS", "true")
    monkeypatch.setenv("AI_API_KEY", "test-key")
    get_settings.cache_clear()
    job = _one_nvd_job(
        runtime_session,
        org=seeded_org,
        agent=provisioned_agent,
    )
    claimed = claim_pending_enrichment_jobs(runtime_session, batch_size=1)

    class _EmptyClient:
        def query_by_cpe(self, session: Session, cpe: str) -> dict:
            return {"vulnerabilities": []}

    process_claimed_enrichment_job(
        runtime_session,
        claimed[0],
        client=_EmptyClient(),  # type: ignore[arg-type]
    )

    analysis = runtime_session.exec(
        select(AIScanAnalysisRecord).where(
            AIScanAnalysisRecord.scan_id == job.scan_id
        )
    ).one()
    assert analysis.status == "pending"
    get_settings.cache_clear()


def test_nvd_rate_limit_fails_after_attempt_budget(
    monkeypatch: pytest.MonkeyPatch,
    runtime_session: Session,
    seeded_org: Org,
    provisioned_agent: Agent,
) -> None:
    monkeypatch.setenv("ENRICHMENT_MAX_ATTEMPTS", "1")
    get_settings.cache_clear()
    job = _one_nvd_job(
        runtime_session,
        org=seeded_org,
        agent=provisioned_agent,
    )
    claimed = claim_pending_enrichment_jobs(runtime_session, batch_size=1)

    class _UnavailableClient:
        def query_by_cpe(self, session: Session, cpe: str) -> dict:
            raise NvdTemporaryError(
                "nvd_unavailable",
                retry_after_seconds=30,
            )

    process_claimed_enrichment_job(
        runtime_session,
        claimed[0],
        client=_UnavailableClient(),  # type: ignore[arg-type]
    )

    runtime_session.refresh(job)
    assert job.status == "failed"
    assert job.attempts == 1
    assert job.last_error == "nvd_unavailable"
    assert job.next_attempt_at is None
    assert job.completed_at is not None
    get_settings.cache_clear()


def test_stale_running_job_is_reclaimed(
    monkeypatch: pytest.MonkeyPatch,
    runtime_session: Session,
    seeded_org: Org,
    provisioned_agent: Agent,
) -> None:
    monkeypatch.setenv("ENRICHMENT_STALE_AFTER_SECONDS", "60")
    get_settings.cache_clear()
    job = _one_nvd_job(
        runtime_session,
        org=seeded_org,
        agent=provisioned_agent,
    )
    job.status = "running"
    job.attempts = 1
    job.started_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    runtime_session.add(job)
    runtime_session.commit()

    now = datetime(2026, 1, 1, 0, 2, tzinfo=timezone.utc)
    claimed = claim_pending_enrichment_jobs(
        runtime_session,
        batch_size=1,
        now=now,
    )

    assert claimed == [job]
    assert job.status == "running"
    assert job.attempts == 2
    assert job.started_at == now
    get_settings.cache_clear()
