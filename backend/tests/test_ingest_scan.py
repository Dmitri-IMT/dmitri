from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from api.models.persistence import (
    EnrichmentJobRecord,
    EpssCacheRecord,
    EpssRecord,
    FindingRecord,
    KevCacheRecord,
    KevRecord,
    RiskSnapshotRecord,
    ScanHostRecord,
)
from api.schemas import ScanResult
from api.services import worker
from api.services.epss import EpssClient
from api.services.kev import KevClient
from api.services.nvd import NvdClient
from api.services.persistence import persist_scan
from sqlmodel import Session, select

EXAMPLE_PATH = (
    Path(__file__).resolve().parents[2]
    / "contracts"
    / "examples"
    / "scan_result.example.json"
)


def _example_scan() -> tuple[dict[str, object], ScanResult]:
    payload = json.loads(EXAMPLE_PATH.read_text(encoding="utf-8"))
    return payload, ScanResult.model_validate(payload)


def _fake_nvd_payload(cve_id: str) -> dict[str, object]:
    return {
        "vulnerabilities": [
            {
                "cve": {
                    "id": cve_id,
                    "descriptions": [
                        {"lang": "en", "value": f"NVD description for {cve_id}."}
                    ],
                    "references": [
                        {"url": f"https://nvd.nist.gov/vuln/detail/{cve_id}"}
                    ],
                    "metrics": {"cvssMetricV31": [{"cvssData": {"baseScore": 8.1}}]},
                }
            }
        ]
    }


def _fake_kev_payload(cve_id: str) -> dict[str, object]:
    return {
        "cve_id": cve_id,
        "date_added": datetime(2026, 5, 12, tzinfo=timezone.utc),
        "known_ransomware": True,
        "required_action": "Patch immediately.",
        "raw_json": {
            "cveID": cve_id,
            "knownRansomwareCampaignUse": "Known",
            "requiredAction": "Patch immediately.",
        },
    }


def _fake_epss_payload(cve_id: str) -> dict[str, object]:
    return {
        "cve_id": cve_id,
        "epss_score": 0.91,
        "percentile": 0.98,
        "scored_at": datetime(2026, 5, 12, tzinfo=timezone.utc),
        "raw_json": {
            "cve": cve_id,
            "epss": "0.91",
            "percentile": "0.98",
        },
    }


def test_ingest_scan_accepts_enriched_findings_example(
    runtime_session: Session,
) -> None:
    payload, scan = _example_scan()

    record = persist_scan(runtime_session, scan)
    scan_hosts = runtime_session.exec(select(ScanHostRecord)).all()

    assert len(scan_hosts) == 2
    assert str(record.scan_id) == payload["scan_id"]
    assert record.scan_mode == scan.scan_mode
    assert record.status == "completed"


def test_worker_processes_pending_jobs_separately(
    monkeypatch, runtime_session: Session
) -> None:  # type: ignore[no-untyped-def]
    _, scan = _example_scan()
    monkeypatch.setattr(
        NvdClient,
        "query_by_cpe",
        lambda self, session, cpe: _fake_nvd_payload("CVE-2016-10012"),
    )
    monkeypatch.setattr(
        NvdClient,
        "query_by_cve",
        lambda self, session, cve_id: _fake_nvd_payload(cve_id),
    )
    monkeypatch.setattr(
        KevClient,
        "query_by_cve",
        lambda self, session, cve_id: _fake_kev_payload(cve_id),
    )
    monkeypatch.setattr(
        EpssClient,
        "query_by_cve",
        lambda self, session, cve_id: _fake_epss_payload(cve_id),
    )

    persist_scan(runtime_session, scan)
    jobs_before = runtime_session.exec(select(EnrichmentJobRecord)).all()
    findings_before = runtime_session.exec(select(FindingRecord)).all()
    assert jobs_before
    assert all(job.status == "pending" for job in jobs_before)
    assert all(finding.confidence != "confirmed" for finding in findings_before)

    monkeypatch.setattr(worker, "get_session", lambda: iter([runtime_session]))
    processed = worker.run_worker_once(batch_size=25)
    assert processed == len(jobs_before)

    jobs_after = runtime_session.exec(select(EnrichmentJobRecord)).all()
    findings_after = runtime_session.exec(select(FindingRecord)).all()
    kev_records = runtime_session.exec(select(KevRecord)).all()
    epss_records = runtime_session.exec(select(EpssRecord)).all()
    risk_snapshots = runtime_session.exec(select(RiskSnapshotRecord)).all()
    assert all(job.status == "completed" for job in jobs_after)
    assert all(job.attempts == 1 for job in jobs_after)
    assert any(finding.confidence == "confirmed" for finding in findings_after)
    assert any("nvd" in finding.source_labels_json for finding in findings_after)
    assert any("kev" in finding.source_labels_json for finding in findings_after)
    assert any("epss" in finding.source_labels_json for finding in findings_after)
    assert kev_records
    assert epss_records
    assert risk_snapshots
    assert any(snapshot.risk_score > 0 for snapshot in risk_snapshots)


def test_worker_marks_job_failed_when_processing_raises(
    monkeypatch, runtime_session: Session
) -> None:  # type: ignore[no-untyped-def]
    _, scan = _example_scan()
    monkeypatch.setattr(
        NvdClient,
        "query_by_cpe",
        lambda self, session, cpe: _fake_nvd_payload("CVE-2016-10012"),
    )
    monkeypatch.setattr(
        NvdClient,
        "query_by_cve",
        lambda self, session, cve_id: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    monkeypatch.setattr(
        KevClient,
        "query_by_cve",
        lambda self, session, cve_id: _fake_kev_payload(cve_id),
    )
    monkeypatch.setattr(
        EpssClient,
        "query_by_cve",
        lambda self, session, cve_id: _fake_epss_payload(cve_id),
    )

    persist_scan(runtime_session, scan)
    monkeypatch.setattr(worker, "get_session", lambda: iter([runtime_session]))
    processed = worker.run_worker_once(batch_size=1)
    assert processed == 1

    jobs = runtime_session.exec(
        select(EnrichmentJobRecord).order_by(EnrichmentJobRecord.id)
    ).all()
    assert jobs[0].status == "failed"
    assert jobs[0].last_error == "boom"
    assert jobs[0].attempts == 1
    assert jobs[0].completed_at is not None


def test_kev_and_epss_cache_store_json_safe_dates(
    monkeypatch, runtime_session: Session
) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(
        KevClient,
        "_fetch_from_remote",
        lambda self, cve_id: _fake_kev_payload(cve_id),
    )
    monkeypatch.setattr(
        EpssClient,
        "_fetch_from_remote",
        lambda self, cve_id: _fake_epss_payload(cve_id),
    )

    kev_payload = KevClient().query_by_cve(runtime_session, "CVE-2016-10012")
    epss_payload = EpssClient().query_by_cve(runtime_session, "CVE-2016-10012")
    kev_cache = runtime_session.get(KevCacheRecord, "CVE-2016-10012")
    epss_cache = runtime_session.get(EpssCacheRecord, "CVE-2016-10012")

    assert kev_payload is not None
    assert epss_payload is not None
    assert kev_cache is not None
    assert epss_cache is not None
    assert kev_cache.response_json["date_added"] == "2026-05-12"
    assert epss_cache.response_json["scored_at"] == "2026-05-12"
