"""Tests for agent.tui.results — scan result persistence under results/ subdirectory."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import uuid4

from agent.normalize.contracts import ScanPayload
from agent.tui.results import write_scan_result


def _make_payload(subnet: str = "192.168.1.0/24") -> ScanPayload:
    return ScanPayload(
        scan_id=uuid4(),
        timestamp=datetime(2026, 5, 3, 14, 30, 0, tzinfo=timezone.utc),
        subnet=subnet,
        scan_mode="quick",
        devices=[],
        findings=[],
        metadata={"hosts_discovered": 0, "findings_count": 0},
    )


def test_write_creates_file_in_results_subdir(tmp_path):
    payload = _make_payload()
    result_path = write_scan_result(payload, str(tmp_path))
    assert result_path.exists()
    assert result_path.suffix == ".json"
    assert result_path.parent == tmp_path / "results"


def test_filename_contains_timestamp_and_subnet(tmp_path):
    payload = _make_payload("10.0.0.0/8")
    result_path = write_scan_result(payload, str(tmp_path))
    assert "2026-05-03T14-30-00" in result_path.name
    assert "10-0-0-0_8" in result_path.name


def test_written_json_is_valid(tmp_path):
    payload = _make_payload()
    result_path = write_scan_result(payload, str(tmp_path))
    data = json.loads(result_path.read_text(encoding="utf-8"))
    assert data["subnet"] == "192.168.1.0/24"
    assert data["scan_mode"] == "quick"
    assert isinstance(data["devices"], list)
    assert isinstance(data["findings"], list)


def test_two_scans_create_two_files(tmp_path):
    p1 = _make_payload()
    p2 = ScanPayload(
        scan_id=uuid4(),
        timestamp=datetime(2026, 5, 3, 14, 35, 0, tzinfo=timezone.utc),
        subnet="192.168.1.0/24",
        scan_mode="max",
        devices=[],
        findings=[],
        metadata={},
    )
    path1 = write_scan_result(p1, str(tmp_path))
    path2 = write_scan_result(p2, str(tmp_path))
    assert path1 != path2
    results_dir = tmp_path / "results"
    assert len(list(results_dir.glob("*.json"))) == 2


def test_creates_results_directory_if_missing(tmp_path):
    nested = tmp_path / "a" / "b" / "workspace"
    payload = _make_payload()
    result_path = write_scan_result(payload, str(nested))
    assert result_path.exists()
    assert (nested / "results").is_dir()


def test_prunes_to_10_after_writing(tmp_path):
    results_dir = tmp_path / "results"
    results_dir.mkdir(parents=True)
    for i in range(10):
        ts = f"2026-05-{i + 1:02d}T10-00-00"
        (results_dir / f"{ts}_192-168-1-0_24.json").write_text(
            '{"old": true}', encoding="utf-8"
        )
    assert len(list(results_dir.glob("*.json"))) == 10

    payload = _make_payload()
    write_scan_result(payload, str(tmp_path))

    remaining = list(results_dir.glob("*.json"))
    assert len(remaining) == 10
