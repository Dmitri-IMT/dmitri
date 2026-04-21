from __future__ import annotations

import json
from pathlib import Path

from api.main import ingest_scan
from api.schemas import ScanResult


def test_ingest_scan_accepts_enriched_findings_example() -> None:
    example_path = (
        Path(__file__).resolve().parents[2]
        / "contracts"
        / "examples"
        / "scan_result.example.json"
    )
    payload = json.loads(example_path.read_text(encoding="utf-8"))
    scan = ScanResult.model_validate(payload)
    response = ingest_scan(scan)

    assert response.devices_received == 2
    assert str(response.scan_id) == payload["scan_id"]
