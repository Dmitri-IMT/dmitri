"""Results persistence — write scan payloads to the configured results directory."""

from __future__ import annotations

import json
from pathlib import Path

from agent.normalize.contracts import ScanPayload


def write_scan_result(payload: ScanPayload, results_dir: str) -> Path:
    """Write a scan payload as JSON to the results directory. Returns the written path.

    Filename pattern: <ISO-timestamp>_<subnet-slug>.json
    Example: 2026-05-03T14-30-00_192-168-1-0_24.json
    """
    dir_path = Path(results_dir)
    dir_path.mkdir(parents=True, exist_ok=True)

    ts = payload.timestamp.strftime("%Y-%m-%dT%H-%M-%S")
    subnet_slug = payload.subnet.replace("/", "_").replace(".", "-")
    filename = f"{ts}_{subnet_slug}.json"

    file_path = dir_path / filename
    data = payload.model_dump(mode="json")
    file_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return file_path
