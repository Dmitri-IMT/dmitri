from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from api.db.session import get_session, init_db
from api.main import app, ingest_scan
from api.models.persistence import (
    EnrichmentJobRecord,
    EpssCacheRecord,
    EpssRecord,
    FindingRecord,
    KevCacheRecord,
    KevRecord,
    RiskSnapshotRecord,
)
from api.schemas import ScanResult
from api.services.epss import EpssClient
from api.services.kev import KevClient
from api.services.nvd import NvdClient
from api.services.worker import run_worker_once
from fastapi.testclient import TestClient
from sqlmodel import select


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
                    "metrics": {
                        "cvssMetricV31": [
                            {"cvssData": {"baseScore": 8.1}}
                        ]
                    },
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


def test_ingest_scan_accepts_enriched_findings_example() -> None:
    init_db()
    example_path = (
        Path(__file__).resolve().parents[2]
        / "contracts"
        / "examples"
        / "scan_result.example.json"
    )
    payload = json.loads(example_path.read_text(encoding="utf-8"))
    scan = ScanResult.model_validate(payload)
    session = next(get_session())
    try:
        response = ingest_scan(scan, session)
    finally:
        session.close()

    assert response.devices_received == 2
    assert str(response.scan_id) == payload["scan_id"]


def test_api_v1_scans_endpoint_accepts_payload() -> None:
    init_db()
    example_path = (
        Path(__file__).resolve().parents[2]
        / "contracts"
        / "examples"
        / "scan_result.example.json"
    )
    payload = json.loads(example_path.read_text(encoding="utf-8"))
    with TestClient(app) as client:
        response = client.post("/api/v1/scans", json=payload)

        assert response.status_code == 200
        body = response.json()
        assert body["devices_received"] == 2

        scans_response = client.get("/api/v1/scans")
        assert scans_response.status_code == 200
        scans = scans_response.json()
        assert len(scans) == 1
        assert scans[0]["finding_count"] >= 2

        detail_response = client.get(f"/api/v1/scans/{body['scan_id']}")
        assert detail_response.status_code == 200
        detail = detail_response.json()
        assert detail["enrichment_jobs"]
        assert all(job["status"] == "pending" for job in detail["enrichment_jobs"])
        assert all("risk" in finding for finding in detail["findings"])


def test_worker_processes_pending_jobs_separately(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    init_db()
    example_path = (
        Path(__file__).resolve().parents[2]
        / "contracts"
        / "examples"
        / "scan_result.example.json"
    )
    payload = json.loads(example_path.read_text(encoding="utf-8"))
    scan = ScanResult.model_validate(payload)
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

    session = next(get_session())
    try:
        ingest_scan(scan, session)
    finally:
        session.close()

    verify_session = next(get_session())
    try:
        jobs_before = verify_session.exec(select(EnrichmentJobRecord)).all()
        findings_before = verify_session.exec(select(FindingRecord)).all()
        assert jobs_before
        assert all(job.status == "pending" for job in jobs_before)
        assert all(finding.confidence != "confirmed" for finding in findings_before)
    finally:
        verify_session.close()

    processed = run_worker_once(batch_size=25)
    assert processed == len(jobs_before)

    final_session = next(get_session())
    try:
        jobs_after = final_session.exec(select(EnrichmentJobRecord)).all()
        findings_after = final_session.exec(select(FindingRecord)).all()
        kev_records = final_session.exec(select(KevRecord)).all()
        epss_records = final_session.exec(select(EpssRecord)).all()
        risk_snapshots = final_session.exec(select(RiskSnapshotRecord)).all()
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
    finally:
        final_session.close()


def test_worker_marks_job_failed_when_processing_raises(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    init_db()
    example_path = (
        Path(__file__).resolve().parents[2]
        / "contracts"
        / "examples"
        / "scan_result.example.json"
    )
    payload = json.loads(example_path.read_text(encoding="utf-8"))
    scan = ScanResult.model_validate(payload)
    monkeypatch.setattr(
        NvdClient,
        "query_by_cpe",
        lambda self, session, cpe: (_ for _ in ()).throw(RuntimeError("boom")),
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

    session = next(get_session())
    try:
        ingest_scan(scan, session)
    finally:
        session.close()

    processed = run_worker_once(batch_size=1)
    assert processed == 1

    verify_session = next(get_session())
    try:
        jobs = verify_session.exec(
            select(EnrichmentJobRecord).order_by(EnrichmentJobRecord.id)
        ).all()
        assert jobs[0].status == "failed"
        assert jobs[0].last_error == "boom"
        assert jobs[0].attempts == 1
        assert jobs[0].completed_at is not None
    finally:
        verify_session.close()


def test_api_exposes_finding_enrichment_and_risk_summary(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    init_db()
    example_path = (
        Path(__file__).resolve().parents[2]
        / "contracts"
        / "examples"
        / "scan_result.example.json"
    )
    payload = json.loads(example_path.read_text(encoding="utf-8"))
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

    with TestClient(app) as client:
        ingest_response = client.post("/api/v1/scans", json=payload)
        assert ingest_response.status_code == 200
        scan_id = ingest_response.json()["scan_id"]

        run_worker_once(batch_size=50)

        findings_response = client.get("/api/v1/findings")
        assert findings_response.status_code == 200
        findings = findings_response.json()
        enriched_finding = next(
            finding
            for finding in findings
            if finding["cve_id"] == "CVE-2016-10012"
            and finding["kev"] is not None
            and "kev" in finding["source_labels"]
        )
        assert enriched_finding["kev"]["known_ransomware"] is True
        assert enriched_finding["epss"]["epss_score"] == 0.91
        assert enriched_finding["risk"]["risk_score"] > 0
        assert "kev=yes" in enriched_finding["risk"]["rationale"]

        detail_response = client.get(f"/api/v1/findings/{enriched_finding['id']}")
        assert detail_response.status_code == 200
        assert detail_response.json()["id"] == enriched_finding["id"]

        summary_response = client.get(f"/api/v1/scans/{scan_id}/risk-summary")
        assert summary_response.status_code == 200
        summary = summary_response.json()
        assert summary["scan_id"] == scan_id
        assert summary["total_findings"] >= 1
        assert summary["kev_findings"] >= 1
        assert summary["max_risk_score"] >= summary["average_risk_score"]
        assert summary["top_findings"]


def test_kev_and_epss_cache_store_json_safe_dates(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    init_db()
    session = next(get_session())
    try:
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

        kev_payload = KevClient().query_by_cve(session, "CVE-2016-10012")
        epss_payload = EpssClient().query_by_cve(session, "CVE-2016-10012")
        kev_cache = session.get(KevCacheRecord, "CVE-2016-10012")
        epss_cache = session.get(EpssCacheRecord, "CVE-2016-10012")
    finally:
        session.close()

    assert kev_payload is not None
    assert epss_payload is not None
    assert kev_cache is not None
    assert epss_cache is not None
    assert kev_cache.response_json["date_added"] == "2026-05-12"
    assert epss_cache.response_json["scored_at"] == "2026-05-12"
