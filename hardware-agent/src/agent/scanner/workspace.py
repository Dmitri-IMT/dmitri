"""Workspace layout management — results/ and logs/ under the scan workspace root."""

from __future__ import annotations

import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Literal
from uuid import uuid4

from agent.normalize.contracts import ScanPayload

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


_FAILED_TERMINATED_BY = frozenset({"timeout", "error", "user_cancel"})


def _read_run_meta(run_dir: Path) -> tuple[str | None, str | None]:
    try:
        meta = json.loads((run_dir / "meta.json").read_text(encoding="utf-8"))
        return meta.get("parent_scan_id"), meta.get("terminated_by")
    except (OSError, ValueError, AttributeError):
        return None, None


def prune_logs(
    logs_dir: Path,
    max_scans: int = 10,
    *,
    protected: frozenset[Path] = frozenset(),
) -> None:
    groups: dict[object, list[Path]] = {}
    failed: set[object] = set()
    for d in logs_dir.iterdir():
        if not d.is_dir():
            continue
        parent_scan_id, terminated_by = _read_run_meta(d)
        key = parent_scan_id if parent_scan_id is not None else d
        groups.setdefault(key, []).append(d)
        if terminated_by in _FAILED_TERMINATED_BY:
            failed.add(key)
    ordered = sorted(
        groups,
        key=lambda k: max(d.name for d in groups[k]),
        reverse=True,
    )
    keep = set(ordered[:max_scans])
    for key in ordered:
        if key in failed:
            keep.add(key)
            break
    for key in ordered:
        if key in keep:
            continue
        for d in groups[key]:
            if d in protected:
                continue
            shutil.rmtree(d)


def prune_results(results_dir: Path, max_count: int = 10) -> None:
    """Delete oldest JSON files under results/ when count exceeds max_count."""
    files = sorted(
        (f for f in results_dir.glob("*.json") if f.is_file()),
        key=lambda f: f.name,
    )
    excess = len(files) - max_count
    for f in files[:excess]:
        try:
            f.unlink()
        except OSError:
            pass


def _migrate_legacy_json(workspace_root: Path, results_dir: Path) -> None:
    """Move *.json files from workspace root into results/ (idempotent)."""
    for json_file in workspace_root.glob("*.json"):
        dest = results_dir / json_file.name
        if dest.exists():
            continue
        shutil.move(str(json_file), str(dest))


def write_scan_result(payload: ScanPayload, workspace_root: str) -> Path:
    """Write a scan payload as JSON to workspace_root/results/.

    Returns the written path.

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
    with file_path.open("w", encoding="utf-8") as stream:
        stream.write(json.dumps(data, indent=2))
        stream.flush()
        os.fsync(stream.fileno())
    if os.name == "posix":
        directory_fd = os.open(dir_path, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    prune_results(dir_path)
    return file_path
