"""Tests for agent.tui.screens.past_scans — S6 past scans picker."""

from __future__ import annotations

import json
from uuid import uuid4

from agent.tui.screens.past_scans import PastScansScreen


def _write_scan_file(
    tmp_path,
    subnet="192.168.1.0/24",
    ts="2026-05-03T14:30:00+00:00",
    name=None,
):
    data = {
        "scan_id": str(uuid4()),
        "timestamp": ts,
        "subnet": subnet,
        "scan_mode": "quick",
        "devices": [],
        "findings": [],
        "metadata": {},
    }
    if name:
        filename = name
    else:
        slug = subnet.replace("/", "_").replace(".", "-")
        ts_slug = ts.replace(":", "-")
        filename = f"scan_{slug}_{ts_slug}.json"
    path = tmp_path / filename
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_parse_entry_valid(tmp_path):
    path = _write_scan_file(tmp_path, "10.0.0.0/8", "2026-05-01T10:00:00+00:00")
    screen = PastScansScreen()
    entry = screen._parse_entry(path)
    assert entry is not None
    assert entry.subnet == "10.0.0.0/8"
    assert entry.timestamp.year == 2026


def test_parse_entry_missing_subnet(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({"scan_mode": "quick"}), encoding="utf-8")
    screen = PastScansScreen()
    entry = screen._parse_entry(path)
    assert entry is None


def test_parse_entry_malformed_json(tmp_path):
    path = tmp_path / "broken.json"
    path.write_text("not json at all", encoding="utf-8")
    screen = PastScansScreen()
    entry = screen._parse_entry(path)
    assert entry is None


def test_parse_entry_missing_timestamp_uses_mtime(tmp_path):
    data = {
        "scan_id": str(uuid4()),
        "subnet": "10.0.0.0/8",
        "scan_mode": "quick",
        "devices": [],
        "findings": [],
    }
    path = tmp_path / "no_ts.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    screen = PastScansScreen()
    entry = screen._parse_entry(path)
    assert entry is not None
    assert entry.timestamp is not None


def test_entries_sorted_newest_first(tmp_path):
    _write_scan_file(
        tmp_path,
        "10.0.0.0/8",
        "2026-05-01T10:00:00+00:00",
        name="a.json",
    )
    _write_scan_file(
        tmp_path,
        "192.168.1.0/24",
        "2026-05-03T14:00:00+00:00",
        name="b.json",
    )
    _write_scan_file(
        tmp_path,
        "172.16.0.0/16",
        "2026-05-02T12:00:00+00:00",
        name="c.json",
    )

    screen = PastScansScreen()
    entries = []
    for f in tmp_path.glob("*.json"):
        entry = screen._parse_entry(f)
        if entry:
            entries.append(entry)
    entries.sort(key=lambda e: e.timestamp, reverse=True)

    assert entries[0].subnet == "192.168.1.0/24"
    assert entries[1].subnet == "172.16.0.0/16"
    assert entries[2].subnet == "10.0.0.0/8"


def test_skips_non_json_files(tmp_path):
    _write_scan_file(tmp_path, "10.0.0.0/8", name="good.json")
    (tmp_path / "readme.txt").write_text("not a scan", encoding="utf-8")

    screen = PastScansScreen()
    entries = []
    for f in tmp_path.glob("*.json"):
        entry = screen._parse_entry(f)
        if entry:
            entries.append(entry)

    assert len(entries) == 1
