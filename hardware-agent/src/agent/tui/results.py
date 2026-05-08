"""Results persistence — write scan payloads to the workspace results/ subdirectory."""

from __future__ import annotations

import json
from pathlib import Path

from agent.normalize.contracts import ScanPayload
from agent.scanner.workspace import prune_results


def write_scan_result(payload: ScanPayload, workspace_root: str) -> Path:
    """Write a scan payload as JSON to workspace_root/results/. Returns the written path.

    Filename pattern: <ISO-timestamp>_<subnet-slug>.json
    Example: 2026-05-03T14-30-00_192-168-1-0_24.json
    """
    dir_path = Path(workspace_root) / "results"
    dir_path.mkdir(parents=True, exist_ok=True)

    ts = payload.timestamp.strftime("%Y-%m-%dT%H-%M-%S")
    subnet_slug = payload.subnet.replace("/", "_").replace(".", "-")
    filename = f"{ts}_{subnet_slug}.json"

    file_path = dir_path / filename
    data = payload.model_dump(mode="json")
    file_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    prune_results(dir_path)
    return file_path
