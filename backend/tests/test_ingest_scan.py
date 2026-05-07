from __future__ import annotations

import json
from pathlib import Path

from api.db.session import get_session, init_db
from api.main import app, ingest_scan
from api.models.persistence import EnrichmentJobRecord, FindingRecord
from api.schemas import ScanResult
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
        assert all(job.status == "completed" for job in jobs_after)
        assert all(job.attempts == 1 for job in jobs_after)
        assert any(finding.confidence == "confirmed" for finding in findings_after)
        assert any("nvd" in finding.source_labels_json for finding in findings_after)
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
