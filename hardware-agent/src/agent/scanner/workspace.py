"""Workspace layout management — results/ and logs/ under the scan workspace root."""

from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Literal
from uuid import uuid4

TerminatedBy = Literal["completed", "error", "user_cancel", "timeout"]


def ensure_workspace_layout(workspace_root: Path) -> None:
    """Create results/ and logs/ under workspace_root if missing (idempotent).

    Also migrates legacy scan *.json files from the workspace root into results/.
    """
    workspace_root.mkdir(parents=True, exist_ok=True)
    results_dir = workspace_root / "results"
    results_dir.mkdir(exist_ok=True)
    (workspace_root / "logs").mkdir(exist_ok=True)
    _migrate_legacy_json(workspace_root, results_dir)


def make_run_folder_name(stage: str, now: datetime | None = None) -> str:
    """Build a unique run folder basename: {YYYY-MM-DD}-{HH-MM-SS}-{stage}-{unique}.

    *now* defaults to the host's local wall-clock time (not UTC).
    """
    now = now or datetime.now()
    timestamp = now.strftime("%Y-%m-%d-%H-%M-%S")
    unique = uuid4().hex[:4]
    return f"{timestamp}-{stage}-{unique}"


def build_nmap_argv(
    base_args: list[str],
    xml_path: Path,
) -> list[str]:
    """Inject -oX, -v, and --stats-every 30s into nmap arguments without duplicating."""
    args = list(base_args)
    if "-oX" not in args:
        args.extend(["-oX", str(xml_path)])
    if "-v" not in args and "-vv" not in args:
        args.append("-v")
    if "--stats-every" not in args:
        args.extend(["--stats-every", "30s"])
    return args


def write_meta_json(
    run_dir: Path,
    *,
    nmap_path: str,
    argv: list[str],
    started_at: datetime,
    finished_at: datetime,
    exit_code: int | None,
    terminated_by: TerminatedBy,
    scan_workspace_root: Path,
    parent_scan_id: str | None = None,
    agent_version: str | None = None,
) -> Path:
    """Write meta.json into run_dir per contracts/metadata.schema.md."""
    run_id = run_dir.name
    meta: dict = {
        "run_id": run_id,
        "nmap_path": nmap_path,
        "argv": argv,
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "exit_code": exit_code,
        "terminated_by": terminated_by,
        "scan_workspace_root": str(scan_workspace_root.resolve()),
    }
    if parent_scan_id is not None:
        meta["parent_scan_id"] = parent_scan_id
    if agent_version is not None:
        meta["agent_version"] = agent_version
    meta_path = run_dir / "meta.json"
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return meta_path


def prune_logs(logs_dir: Path, max_count: int = 10) -> None:
    """Delete oldest run directories under logs/ when count exceeds max_count."""
    dirs = sorted(
        (d for d in logs_dir.iterdir() if d.is_dir()),
        key=lambda d: d.name,
    )
    excess = len(dirs) - max_count
    for d in dirs[:excess]:
        shutil.rmtree(d)


def prune_results(results_dir: Path, max_count: int = 10) -> None:
    """Delete oldest JSON files under results/ when count exceeds max_count."""
    files = sorted(
        (f for f in results_dir.glob("*.json") if f.is_file()),
        key=lambda f: f.name,
    )
    excess = len(files) - max_count
    for f in files[:excess]:
        f.unlink()


def _migrate_legacy_json(workspace_root: Path, results_dir: Path) -> None:
    """Move *.json files from workspace root into results/ (idempotent)."""
    for json_file in workspace_root.glob("*.json"):
        dest = results_dir / json_file.name
        if dest.exists():
            continue
        shutil.move(str(json_file), str(dest))
