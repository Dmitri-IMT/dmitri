from __future__ import annotations

import json
from pathlib import Path

from api.db.session import get_session, init_db
from api.main import app, ingest_scan
from api.schemas import ScanResult
from api.services.nvd import NvdClient
from fastapi.testclient import TestClient


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
    NvdClient.query_by_cpe = lambda self, session, cpe: _fake_nvd_payload(  # type: ignore[method-assign]
        "CVE-2016-10012"
    )
    NvdClient.query_by_cve = lambda self, session, cve_id: _fake_nvd_payload(  # type: ignore[method-assign]
        cve_id
    )

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

        findings_response = client.get("/api/v1/findings")
        assert findings_response.status_code == 200
        findings = findings_response.json()
        assert any(finding["confidence"] == "confirmed" for finding in findings)
        assert any("nvd" in finding["source_labels"] for finding in findings)
