"""Unit tests for agent.scanner.workspace.

Coverage: layout, migration, pruning, basename, argv, meta, scan result persistence.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from agent.normalize.contracts import (
    HostPayload,
    OperatingSystemDetection,
    ScanPayload,
)
from agent.scanner.workspace import (
    _FAILED_TERMINATED_BY,
    build_nmap_argv,
    ensure_workspace_layout,
    make_run_folder_name,
    prune_logs,
    prune_results,
    write_meta_json,
    write_scan_result,
)


class TestEnsureWorkspaceLayout:
    def test_creates_results_and_logs(self, tmp_path: Path) -> None:
        workspace = tmp_path / "scan-workspace"
        ensure_workspace_layout(workspace)
        assert (workspace / "results").is_dir()
        assert (workspace / "logs").is_dir()

    def test_creates_workspace_root_if_missing(self, tmp_path: Path) -> None:
        workspace = tmp_path / "deep" / "nested" / "workspace"
        assert not workspace.exists()
        ensure_workspace_layout(workspace)
        assert workspace.is_dir()
        assert (workspace / "results").is_dir()
        assert (workspace / "logs").is_dir()

    def test_idempotent_second_call(self, tmp_path: Path) -> None:
        workspace = tmp_path / "workspace"
        ensure_workspace_layout(workspace)
        ensure_workspace_layout(workspace)
        assert (workspace / "results").is_dir()
        assert (workspace / "logs").is_dir()

    def test_preserves_existing_content(self, tmp_path: Path) -> None:
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        (workspace / "results").mkdir()
        existing_file = workspace / "results" / "scan.json"
        existing_file.write_text('{"test": true}', encoding="utf-8")

        ensure_workspace_layout(workspace)

        assert existing_file.exists()
        assert existing_file.read_text(encoding="utf-8") == '{"test": true}'

    def test_creates_logs_when_results_already_exists(self, tmp_path: Path) -> None:
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        (workspace / "results").mkdir()

        ensure_workspace_layout(workspace)

        assert (workspace / "results").is_dir()
        assert (workspace / "logs").is_dir()

    def test_creates_results_when_logs_already_exists(self, tmp_path: Path) -> None:
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        (workspace / "logs").mkdir()

        ensure_workspace_layout(workspace)

        assert (workspace / "results").is_dir()
        assert (workspace / "logs").is_dir()


class TestLegacyJsonMigration:
    def test_moves_root_json_into_results(self, tmp_path: Path) -> None:
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        legacy = workspace / "2026-05-03T14-30-00_192-168-1-0_24.json"
        legacy.write_text('{"subnet": "192.168.1.0/24"}', encoding="utf-8")

        ensure_workspace_layout(workspace)

        assert not legacy.exists()
        migrated = workspace / "results" / legacy.name
        assert migrated.exists()
        assert migrated.read_text(encoding="utf-8") == '{"subnet": "192.168.1.0/24"}'

    def test_moves_multiple_json_files(self, tmp_path: Path) -> None:
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        for i in range(3):
            (workspace / f"scan-{i}.json").write_text(
                f'{{"id": {i}}}', encoding="utf-8"
            )

        ensure_workspace_layout(workspace)

        for i in range(3):
            assert not (workspace / f"scan-{i}.json").exists()
            assert (workspace / "results" / f"scan-{i}.json").exists()

    def test_skips_when_destination_already_exists(self, tmp_path: Path) -> None:
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        (workspace / "results").mkdir()
        root_file = workspace / "scan.json"
        root_file.write_text('{"old": true}', encoding="utf-8")
        dest_file = workspace / "results" / "scan.json"
        dest_file.write_text('{"new": true}', encoding="utf-8")

        ensure_workspace_layout(workspace)

        # Root file not moved because destination exists — root copy stays
        assert root_file.exists()
        # Destination keeps its original content
        assert dest_file.read_text(encoding="utf-8") == '{"new": true}'

    def test_idempotent_after_migration(self, tmp_path: Path) -> None:
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        (workspace / "old.json").write_text('{"x": 1}', encoding="utf-8")

        ensure_workspace_layout(workspace)
        ensure_workspace_layout(workspace)

        assert not (workspace / "old.json").exists()
        assert (workspace / "results" / "old.json").exists()

    def test_ignores_non_json_files_at_root(self, tmp_path: Path) -> None:
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        (workspace / "notes.txt").write_text("hello", encoding="utf-8")
        (workspace / "config.toml").write_text("key = 1", encoding="utf-8")

        ensure_workspace_layout(workspace)

        assert (workspace / "notes.txt").exists()
        assert (workspace / "config.toml").exists()
        assert not list((workspace / "results").glob("*.txt"))
        assert not list((workspace / "results").glob("*.toml"))

    def test_no_op_on_empty_workspace(self, tmp_path: Path) -> None:
        workspace = tmp_path / "workspace"

        ensure_workspace_layout(workspace)

        assert list((workspace / "results").iterdir()) == []


class TestFailedTerminatedBy:
    def test_completed_is_not_a_failure_termination(self) -> None:
        assert "completed" not in _FAILED_TERMINATED_BY

    def test_completed_with_partial_is_not_retained_as_failed(
        self, tmp_path: Path
    ) -> None:
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir(parents=True)
        completed_partial = logs_dir / "2026-05-01-10-00-00-discovery-cp01"
        completed_partial.mkdir()
        (completed_partial / "console.log").write_text("run", encoding="utf-8")
        (completed_partial / "meta.json").write_text(
            json.dumps(
                {
                    "parent_scan_id": "scan-completed-partial",
                    "terminated_by": "completed",
                }
            ),
            encoding="utf-8",
        )
        newer = logs_dir / "2026-05-02-10-00-00-discovery-new01"
        newer.mkdir()
        (newer / "console.log").write_text("run", encoding="utf-8")
        (newer / "meta.json").write_text(
            json.dumps({"parent_scan_id": "scan-new", "terminated_by": "completed"}),
            encoding="utf-8",
        )

        prune_logs(logs_dir, max_scans=1)

        assert not completed_partial.exists()
        assert newer.exists()


class TestPruneLogs:
    def _make_run_dirs(self, logs_dir: Path, count: int) -> list[Path]:
        dirs = []
        for i in range(count):
            name = f"2026-05-{i + 1:02d}-10-00-00-discovery-aa{i:02x}"
            d = logs_dir / name
            d.mkdir(parents=True)
            (d / "console.log").write_text(f"run {i}", encoding="utf-8")
            dirs.append(d)
        return dirs

    def test_no_op_under_limit(self, tmp_path: Path) -> None:
        logs_dir = tmp_path / "logs"
        dirs = self._make_run_dirs(logs_dir, 5)

        prune_logs(logs_dir, max_scans=10)

        for d in dirs:
            assert d.exists()

    def test_no_op_at_exactly_limit(self, tmp_path: Path) -> None:
        logs_dir = tmp_path / "logs"
        dirs = self._make_run_dirs(logs_dir, 10)

        prune_logs(logs_dir, max_scans=10)

        for d in dirs:
            assert d.exists()

    def test_prunes_oldest_when_over_limit(self, tmp_path: Path) -> None:
        logs_dir = tmp_path / "logs"
        dirs = self._make_run_dirs(logs_dir, 12)

        prune_logs(logs_dir, max_scans=10)

        assert not dirs[0].exists()
        assert not dirs[1].exists()
        for d in dirs[2:]:
            assert d.exists()

    def test_prunes_to_exact_count(self, tmp_path: Path) -> None:
        logs_dir = tmp_path / "logs"
        self._make_run_dirs(logs_dir, 15)

        prune_logs(logs_dir, max_scans=10)

        remaining = [d for d in logs_dir.iterdir() if d.is_dir()]
        assert len(remaining) == 10

    def test_removes_directory_contents(self, tmp_path: Path) -> None:
        logs_dir = tmp_path / "logs"
        dirs = self._make_run_dirs(logs_dir, 11)

        prune_logs(logs_dir, max_scans=10)

        assert not dirs[0].exists()
        assert not (dirs[0] / "console.log").exists()

    def test_no_op_on_empty_dir(self, tmp_path: Path) -> None:
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()

        prune_logs(logs_dir, max_scans=10)

        assert list(logs_dir.iterdir()) == []

    def test_ignores_files_in_logs_dir(self, tmp_path: Path) -> None:
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()
        stray_file = logs_dir / "stray.txt"
        stray_file.write_text("stray", encoding="utf-8")
        self._make_run_dirs(logs_dir, 11)

        prune_logs(logs_dir, max_scans=10)

        assert stray_file.exists()
        remaining_dirs = [d for d in logs_dir.iterdir() if d.is_dir()]
        assert len(remaining_dirs) == 10

    def test_skips_protected_directories(self, tmp_path: Path) -> None:
        logs_dir = tmp_path / "logs"
        dirs = self._make_run_dirs(logs_dir, 12)
        protected = frozenset({dirs[0]})

        prune_logs(logs_dir, max_scans=10, protected=protected)

        assert dirs[0].exists()
        assert not dirs[1].exists()
        for d in dirs[2:]:
            assert d.exists()

    def _make_run_dir(
        self,
        logs_dir: Path,
        day: int,
        suffix: str,
        *,
        parent_scan_id: str | None = None,
        terminated_by: str = "completed",
        meta: str = "valid",
    ) -> Path:
        logs_dir.mkdir(parents=True, exist_ok=True)
        name = f"2026-05-{day:02d}-10-00-00-discovery-{suffix}"
        d = logs_dir / name
        d.mkdir()
        (d / "console.log").write_text(f"run {suffix}", encoding="utf-8")
        if meta == "valid":
            payload = {
                "parent_scan_id": parent_scan_id,
                "terminated_by": terminated_by,
            }
            (d / "meta.json").write_text(json.dumps(payload), encoding="utf-8")
        elif meta == "malformed":
            (d / "meta.json").write_text("{not valid json", encoding="utf-8")
        elif meta == "empty":
            (d / "meta.json").write_text("", encoding="utf-8")
        return d

    def test_grouping_counts_scans_not_folders(self, tmp_path: Path) -> None:
        logs_dir = tmp_path / "logs"
        a1 = self._make_run_dir(logs_dir, 1, "a1", parent_scan_id="scan-a")
        a2 = self._make_run_dir(logs_dir, 2, "a2", parent_scan_id="scan-a")
        b1 = self._make_run_dir(logs_dir, 3, "b1", parent_scan_id="scan-b")
        b2 = self._make_run_dir(logs_dir, 4, "b2", parent_scan_id="scan-b")
        c1 = self._make_run_dir(logs_dir, 5, "c1", parent_scan_id="scan-c")
        c2 = self._make_run_dir(logs_dir, 6, "c2", parent_scan_id="scan-c")

        prune_logs(logs_dir, max_scans=2)

        assert not a1.exists()
        assert not a2.exists()
        assert b1.exists()
        assert b2.exists()
        assert c1.exists()
        assert c2.exists()
        remaining = [d for d in logs_dir.iterdir() if d.is_dir()]
        assert len(remaining) == 4

    def test_failed_scan_survives_later_completed_scans(self, tmp_path: Path) -> None:
        logs_dir = tmp_path / "logs"
        failed = self._make_run_dir(
            logs_dir, 1, "f1", parent_scan_id="scan-failed", terminated_by="error"
        )
        c1 = self._make_run_dir(logs_dir, 2, "c1", parent_scan_id="scan-c1")
        c2 = self._make_run_dir(logs_dir, 3, "c2", parent_scan_id="scan-c2")
        c3 = self._make_run_dir(logs_dir, 4, "c3", parent_scan_id="scan-c3")

        prune_logs(logs_dir, max_scans=2)

        assert failed.exists()
        assert not c1.exists()
        assert c2.exists()
        assert c3.exists()

    def test_failed_scan_all_folders_survive(self, tmp_path: Path) -> None:
        logs_dir = tmp_path / "logs"
        f1 = self._make_run_dir(
            logs_dir, 1, "f1", parent_scan_id="scan-failed", terminated_by="completed"
        )
        f2 = self._make_run_dir(
            logs_dir, 2, "f2", parent_scan_id="scan-failed", terminated_by="timeout"
        )
        c1 = self._make_run_dir(logs_dir, 3, "c1", parent_scan_id="scan-c1")
        c2 = self._make_run_dir(logs_dir, 4, "c2", parent_scan_id="scan-c2")

        prune_logs(logs_dir, max_scans=1)

        assert f1.exists()
        assert f2.exists()
        assert not c1.exists()
        assert c2.exists()

    def test_malformed_meta_does_not_raise(self, tmp_path: Path) -> None:
        logs_dir = tmp_path / "logs"
        malformed = self._make_run_dir(logs_dir, 1, "m1", meta="malformed")
        empty = self._make_run_dir(logs_dir, 2, "m2", meta="empty")
        missing = self._make_run_dir(logs_dir, 3, "m3", meta="none")

        prune_logs(logs_dir, max_scans=10)

        assert malformed.exists()
        assert empty.exists()
        assert missing.exists()

    def test_malformed_meta_treated_as_singleton(self, tmp_path: Path) -> None:
        logs_dir = tmp_path / "logs"
        grouped_1 = self._make_run_dir(logs_dir, 1, "g1", parent_scan_id="scan-g")
        grouped_2 = self._make_run_dir(logs_dir, 2, "g2", parent_scan_id="scan-g")
        malformed = self._make_run_dir(logs_dir, 3, "m1", meta="malformed")

        prune_logs(logs_dir, max_scans=1)

        assert malformed.exists()
        assert not grouped_1.exists()
        assert not grouped_2.exists()

    def test_protected_grouped_dirs_never_deleted(self, tmp_path: Path) -> None:
        logs_dir = tmp_path / "logs"
        old_1 = self._make_run_dir(logs_dir, 1, "o1", parent_scan_id="scan-old")
        old_2 = self._make_run_dir(logs_dir, 2, "o2", parent_scan_id="scan-old")
        new_1 = self._make_run_dir(logs_dir, 3, "n1", parent_scan_id="scan-new")

        prune_logs(logs_dir, max_scans=1, protected=frozenset({old_1}))

        assert old_1.exists()
        assert not old_2.exists()
        assert new_1.exists()


class TestPruneResults:
    def _make_result_files(self, results_dir: Path, count: int) -> list[Path]:
        results_dir.mkdir(parents=True, exist_ok=True)
        files = []
        for i in range(count):
            name = f"2026-05-{i + 1:02d}T10-00-00_192-168-1-0_24.json"
            f = results_dir / name
            f.write_text(f'{{"id": {i}}}', encoding="utf-8")
            files.append(f)
        return files

    def test_no_op_under_limit(self, tmp_path: Path) -> None:
        results_dir = tmp_path / "results"
        files = self._make_result_files(results_dir, 5)

        prune_results(results_dir, max_count=10)

        for f in files:
            assert f.exists()

    def test_no_op_at_exactly_limit(self, tmp_path: Path) -> None:
        results_dir = tmp_path / "results"
        files = self._make_result_files(results_dir, 10)

        prune_results(results_dir, max_count=10)

        for f in files:
            assert f.exists()

    def test_prunes_oldest_when_over_limit(self, tmp_path: Path) -> None:
        results_dir = tmp_path / "results"
        files = self._make_result_files(results_dir, 12)

        prune_results(results_dir, max_count=10)

        assert not files[0].exists()
        assert not files[1].exists()
        for f in files[2:]:
            assert f.exists()

    def test_prunes_to_exact_count(self, tmp_path: Path) -> None:
        results_dir = tmp_path / "results"
        self._make_result_files(results_dir, 15)

        prune_results(results_dir, max_count=10)

        remaining = list(results_dir.glob("*.json"))
        assert len(remaining) == 10

    def test_no_op_on_empty_dir(self, tmp_path: Path) -> None:
        results_dir = tmp_path / "results"
        results_dir.mkdir()

        prune_results(results_dir, max_count=10)

        assert list(results_dir.iterdir()) == []

    def test_ignores_non_json_files(self, tmp_path: Path) -> None:
        results_dir = tmp_path / "results"
        results_dir.mkdir()
        readme = results_dir / "README.md"
        readme.write_text("keep me", encoding="utf-8")
        self._make_result_files(results_dir, 11)

        prune_results(results_dir, max_count=10)

        assert readme.exists()
        remaining_json = list(results_dir.glob("*.json"))
        assert len(remaining_json) == 10

    def test_unlink_oserror_does_not_propagate(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        results_dir = tmp_path / "results"
        self._make_result_files(results_dir, 12)

        def _raise(self: Path) -> None:
            raise OSError("boom")

        monkeypatch.setattr(Path, "unlink", _raise)

        prune_results(results_dir, max_count=10)

    def test_one_stuck_file_does_not_block_rest(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        results_dir = tmp_path / "results"
        files = self._make_result_files(results_dir, 12)
        stuck = files[0]
        original_unlink = Path.unlink

        def _raise_for_stuck(self: Path, *args, **kwargs) -> None:
            if self == stuck:
                raise OSError("boom")
            original_unlink(self, *args, **kwargs)

        monkeypatch.setattr(Path, "unlink", _raise_for_stuck)

        prune_results(results_dir, max_count=10)

        assert stuck.exists()
        assert not files[1].exists()
        for f in files[2:]:
            assert f.exists()


# Regex matching the contract grammar: {YYYY-MM-DD}-{HH-MM-SS}-{stage}-{unique}
_BASENAME_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}-\d{2}-\d{2}-\d{2}-[a-z][a-z0-9-]*-[0-9a-f]{4}$"
)


class TestMakeRunFolderName:
    def test_matches_contract_grammar(self) -> None:
        name = make_run_folder_name("discovery")
        assert _BASENAME_RE.match(name), f"'{name}' does not match grammar"

    def test_uses_local_time_not_utc(self) -> None:
        local_now = datetime(2026, 5, 7, 14, 30, 0)
        name = make_run_folder_name("discovery", now=local_now)
        assert name.startswith("2026-05-07-14-30-00-")

    def test_stage_appears_in_name(self) -> None:
        name = make_run_folder_name("port-batch")
        parts = name.split("-")
        # After date (3 parts) and time (3 parts), stage starts
        stage_and_rest = "-".join(parts[6:])
        assert stage_and_rest.startswith("port-batch-")

    def test_unique_suffix_is_4_hex_chars(self) -> None:
        name = make_run_folder_name("discovery")
        unique = name.rsplit("-", 1)[-1]
        assert len(unique) == 4
        assert all(c in "0123456789abcdef" for c in unique)

    def test_successive_calls_differ(self) -> None:
        fixed = datetime(2026, 5, 7, 14, 30, 0)
        names = {make_run_folder_name("discovery", now=fixed) for _ in range(20)}
        assert len(names) == 20

    def test_no_forbidden_characters(self) -> None:
        name = make_run_folder_name("nse-vuln")
        forbidden = set(':/"\\<>|?*')
        assert not forbidden.intersection(name)

    def test_filesystem_safe_on_windows(self, tmp_path: Path) -> None:
        name = make_run_folder_name("discovery")
        d = tmp_path / name
        d.mkdir()
        assert d.is_dir()

    def test_hyphenated_stage(self) -> None:
        name = make_run_folder_name("port-batch")
        assert _BASENAME_RE.match(name), f"'{name}' does not match grammar"

    def test_single_word_stages(self) -> None:
        for stage in ("discovery", "ports", "nse"):
            name = make_run_folder_name(stage)
            assert _BASENAME_RE.match(name), f"'{name}' does not match for {stage}"


class TestBuildNmapArgv:
    def test_injects_all_flags(self, tmp_path: Path) -> None:
        xml = tmp_path / "nmaprun.xml"
        result = build_nmap_argv(["-sn", "-T4", "192.168.1.0/24"], xml)
        assert "-oX" in result
        assert str(xml) in result
        assert "-v" in result
        assert "--stats-every" in result
        assert "30s" in result

    def test_preserves_base_args(self, tmp_path: Path) -> None:
        xml = tmp_path / "nmaprun.xml"
        base = ["-sn", "-PE", "-T4", "192.168.1.0/24"]
        result = build_nmap_argv(base, xml)
        for arg in base:
            assert arg in result

    def test_no_duplicate_oX(self, tmp_path: Path) -> None:
        xml = tmp_path / "nmaprun.xml"
        base = ["-oX", "/other/path.xml", "-sn"]
        result = build_nmap_argv(base, xml)
        assert result.count("-oX") == 1
        assert "/other/path.xml" in result
        assert str(xml) not in result

    def test_no_duplicate_v(self, tmp_path: Path) -> None:
        xml = tmp_path / "nmaprun.xml"
        result = build_nmap_argv(["-v", "-sn"], xml)
        assert result.count("-v") == 1

    def test_no_v_when_vv_present(self, tmp_path: Path) -> None:
        xml = tmp_path / "nmaprun.xml"
        result = build_nmap_argv(["-vv", "-sn"], xml)
        assert "-v" not in result
        assert "-vv" in result

    def test_no_duplicate_stats_every(self, tmp_path: Path) -> None:
        xml = tmp_path / "nmaprun.xml"
        result = build_nmap_argv(["--stats-every", "10s", "-sn"], xml)
        assert result.count("--stats-every") == 1
        assert "10s" in result
        assert "30s" not in result

    def test_does_not_mutate_input(self, tmp_path: Path) -> None:
        xml = tmp_path / "nmaprun.xml"
        base = ["-sn", "-T4"]
        original = list(base)
        build_nmap_argv(base, xml)
        assert base == original

    def test_empty_base_args(self, tmp_path: Path) -> None:
        xml = tmp_path / "nmaprun.xml"
        result = build_nmap_argv([], xml)
        assert "-oX" in result
        assert "-v" in result
        assert "--stats-every" in result


_STARTED = datetime(2026, 5, 7, 14, 30, 0, tzinfo=timezone.utc)
_FINISHED = datetime(2026, 5, 7, 14, 35, 12, tzinfo=timezone.utc)
_REQUIRED_FIELDS = {
    "run_id",
    "nmap_path",
    "argv",
    "started_at",
    "finished_at",
    "exit_code",
    "terminated_by",
    "scan_workspace_root",
}


class TestWriteMetaJson:
    def _write(self, run_dir: Path, **overrides) -> dict:
        defaults = dict(
            nmap_path="/usr/bin/nmap",
            argv=["-sn", "-T4", "192.168.1.0/24"],
            started_at=_STARTED,
            finished_at=_FINISHED,
            exit_code=0,
            terminated_by="completed",
            scan_workspace_root=run_dir.parent.parent,
        )
        defaults.update(overrides)
        path = write_meta_json(run_dir, **defaults)
        return json.loads(path.read_text(encoding="utf-8"))

    def test_creates_meta_json_file(self, tmp_path: Path) -> None:
        run_dir = tmp_path / "logs" / "2026-05-07-14-30-00-discovery-a3f2"
        run_dir.mkdir(parents=True)

        path = write_meta_json(
            run_dir,
            nmap_path="/usr/bin/nmap",
            argv=["-sn"],
            started_at=_STARTED,
            finished_at=_FINISHED,
            exit_code=0,
            terminated_by="completed",
            scan_workspace_root=tmp_path,
        )

        assert path == run_dir / "meta.json"
        assert path.exists()

    def test_contains_all_required_fields(self, tmp_path: Path) -> None:
        run_dir = tmp_path / "logs" / "2026-05-07-14-30-00-discovery-a3f2"
        run_dir.mkdir(parents=True)

        data = self._write(run_dir)

        assert _REQUIRED_FIELDS.issubset(data.keys())

    def test_run_id_equals_folder_name(self, tmp_path: Path) -> None:
        folder_name = "2026-05-07-14-30-00-discovery-a3f2"
        run_dir = tmp_path / "logs" / folder_name
        run_dir.mkdir(parents=True)

        data = self._write(run_dir)

        assert data["run_id"] == folder_name

    def test_timestamps_are_iso8601_utc(self, tmp_path: Path) -> None:
        run_dir = tmp_path / "logs" / "2026-05-07-14-30-00-discovery-a3f2"
        run_dir.mkdir(parents=True)

        data = self._write(run_dir)

        started = datetime.fromisoformat(data["started_at"])
        finished = datetime.fromisoformat(data["finished_at"])
        assert started.tzinfo is not None
        assert finished.tzinfo is not None

    def test_terminated_by_completed(self, tmp_path: Path) -> None:
        run_dir = tmp_path / "logs" / "run1"
        run_dir.mkdir(parents=True)
        data = self._write(run_dir, terminated_by="completed", exit_code=0)
        assert data["terminated_by"] == "completed"

    def test_terminated_by_error(self, tmp_path: Path) -> None:
        run_dir = tmp_path / "logs" / "run2"
        run_dir.mkdir(parents=True)
        data = self._write(run_dir, terminated_by="error", exit_code=1)
        assert data["terminated_by"] == "error"
        assert data["exit_code"] == 1

    def test_terminated_by_user_cancel(self, tmp_path: Path) -> None:
        run_dir = tmp_path / "logs" / "run3"
        run_dir.mkdir(parents=True)
        data = self._write(run_dir, terminated_by="user_cancel", exit_code=None)
        assert data["terminated_by"] == "user_cancel"

    def test_terminated_by_timeout(self, tmp_path: Path) -> None:
        run_dir = tmp_path / "logs" / "run4"
        run_dir.mkdir(parents=True)
        data = self._write(run_dir, terminated_by="timeout", exit_code=None)
        assert data["terminated_by"] == "timeout"

    def test_null_exit_code(self, tmp_path: Path) -> None:
        run_dir = tmp_path / "logs" / "run5"
        run_dir.mkdir(parents=True)
        data = self._write(run_dir, exit_code=None)
        assert data["exit_code"] is None

    def test_argv_is_list(self, tmp_path: Path) -> None:
        run_dir = tmp_path / "logs" / "run6"
        run_dir.mkdir(parents=True)
        data = self._write(run_dir, argv=["-sn", "-v", "--stats-every", "30s"])
        assert isinstance(data["argv"], list)
        assert data["argv"] == ["-sn", "-v", "--stats-every", "30s"]

    def test_optional_parent_scan_id(self, tmp_path: Path) -> None:
        run_dir = tmp_path / "logs" / "run7"
        run_dir.mkdir(parents=True)
        data = self._write(run_dir, parent_scan_id="abc-123-def")
        assert data["parent_scan_id"] == "abc-123-def"

    def test_optional_agent_version(self, tmp_path: Path) -> None:
        run_dir = tmp_path / "logs" / "run8"
        run_dir.mkdir(parents=True)
        data = self._write(run_dir, agent_version="0.1.0")
        assert data["agent_version"] == "0.1.0"

    def test_omits_optional_fields_when_not_provided(self, tmp_path: Path) -> None:
        run_dir = tmp_path / "logs" / "run9"
        run_dir.mkdir(parents=True)
        data = self._write(run_dir)
        assert "parent_scan_id" not in data
        assert "agent_version" not in data

    def test_scan_workspace_root_is_absolute(self, tmp_path: Path) -> None:
        run_dir = tmp_path / "logs" / "run10"
        run_dir.mkdir(parents=True)
        data = self._write(run_dir, scan_workspace_root=tmp_path)
        root_path = Path(data["scan_workspace_root"])
        assert root_path.is_absolute()


def _make_payload(subnet: str = "192.168.1.0/24") -> ScanPayload:
    return ScanPayload(
        scan_id=uuid4(),
        timestamp=datetime(2026, 5, 3, 14, 30, 0, tzinfo=timezone.utc),
        subnet=subnet,
        scan_mode="quick",
        hosts=[],
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
    assert isinstance(data["hosts"], list)
    assert isinstance(data["findings"], list)


def test_legacy_workspace_json_marks_assessment_unavailable(tmp_path: Path) -> None:
    legacy = _make_payload().model_dump(
        mode="json", exclude={"assessment_policy_version", "exposures"}
    )
    loaded = ScanPayload.model_validate(legacy)

    assert loaded.assessment_policy_version is None
    assert loaded.exposures == []


def test_current_assessment_round_trips_without_information_loss(
    tmp_path: Path,
) -> None:
    from agent.assessment.analyzer import assess_hosts
    from agent.assessment.policy import LOCAL_ASSESSMENT_POLICY_VERSION
    from agent.scanner.models import HostInfo, PortInfo, ServiceInfo
    from agent.scanner.stages import build_host_payload

    host = HostInfo(
        ip="192.168.1.10",
        hostname="camera.local",
        ports=[PortInfo(port=80, service=ServiceInfo(name="http"))],
    )
    assessment = assess_hosts([host])
    payload = _make_payload().model_copy(
        update={
            "hosts": [
                build_host_payload(
                    host,
                    machine_type=assessment.machine_types[host.ip],
                    device_profile=assessment.device_profiles[host.ip],
                )
            ],
            "assessment_policy_version": LOCAL_ASSESSMENT_POLICY_VERSION,
            "exposures": assessment.exposures,
        }
    )
    validated = ScanPayload.model_validate(payload.model_dump(mode="json"))
    path = write_scan_result(validated, str(tmp_path))
    loaded = ScanPayload.model_validate_json(path.read_text(encoding="utf-8"))

    assert loaded == validated
    assert loaded.hosts[0].device_profile == assessment.device_profiles[host.ip]
    assert loaded.exposures == assessment.exposures


def test_operating_system_round_trips_through_workspace_json(tmp_path: Path) -> None:
    payload = _make_payload().model_copy(
        update={
            "hosts": [
                HostPayload(
                    ip="192.168.1.10",
                    hostname="controller.local",
                    vendor="Vendor",
                    operating_system=OperatingSystemDetection(
                        name="Linux 5.4 - 5.10",
                        accuracy=96,
                        vendor="Linux",
                        family="Linux",
                        generation="5.X",
                        device_type="general purpose",
                        cpes=[
                            "cpe:/o:linux:linux_kernel:5",
                            "cpe:/o:linux:linux_kernel:6",
                        ],
                    ),
                )
            ]
        }
    )

    result_path = write_scan_result(payload, str(tmp_path))
    result_json = result_path.read_text(encoding="utf-8")
    saved = json.loads(result_json)
    loaded = ScanPayload.model_validate_json(result_json)

    assert saved["hosts"][0]["operating_system"] == {
        "name": "Linux 5.4 - 5.10",
        "accuracy": 96,
        "vendor": "Linux",
        "family": "Linux",
        "generation": "5.X",
        "device_type": "general purpose",
        "cpes": [
            "cpe:/o:linux:linux_kernel:5",
            "cpe:/o:linux:linux_kernel:6",
        ],
    }
    assert loaded == payload
    assert loaded.hosts[0].operating_system == payload.hosts[0].operating_system


def test_legacy_workspace_json_without_operating_system_remains_valid(
    tmp_path: Path,
) -> None:
    legacy = _make_payload().model_dump(mode="json")
    legacy["hosts"] = [
        {
            "ip": "192.168.1.10",
            "mac": None,
            "hostname": "legacy.local",
            "vendor": "unknown",
            "ports": [],
            "industrial_services": [],
        }
    ]
    legacy_path = tmp_path / "legacy.json"
    legacy_path.write_text(json.dumps(legacy), encoding="utf-8")

    loaded = ScanPayload.model_validate_json(legacy_path.read_text(encoding="utf-8"))

    assert loaded.hosts[0].operating_system is None


def test_workspace_json_with_explicit_null_operating_system_remains_valid(
    tmp_path: Path,
) -> None:
    current = _make_payload().model_dump(mode="json")
    current["hosts"] = [
        {
            "ip": "192.168.1.10",
            "mac": None,
            "hostname": "current.local",
            "vendor": "unknown",
            "operating_system": None,
            "ports": [],
            "industrial_services": [],
        }
    ]
    payload = ScanPayload.model_validate(current)
    current_path = write_scan_result(payload, str(tmp_path))
    current_json = current_path.read_text(encoding="utf-8")
    saved = json.loads(current_json)
    loaded = ScanPayload.model_validate_json(current_json)

    assert saved["hosts"][0]["operating_system"] is None
    assert loaded.hosts[0].operating_system is None


def test_two_scans_create_two_files(tmp_path):
    p1 = _make_payload()
    p2 = ScanPayload(
        scan_id=uuid4(),
        timestamp=datetime(2026, 5, 3, 14, 35, 0, tzinfo=timezone.utc),
        subnet="192.168.1.0/24",
        scan_mode="max",
        hosts=[],
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


def test_returns_path_and_writes_file_when_pruning_fails(tmp_path, monkeypatch):
    results_dir = tmp_path / "results"
    results_dir.mkdir(parents=True)
    for i in range(12):
        ts = f"2026-05-{i + 1:02d}T10-00-00"
        (results_dir / f"{ts}_192-168-1-0_24.json").write_text(
            '{"old": true}', encoding="utf-8"
        )

    def _raise(self: Path) -> None:
        raise OSError("boom")

    monkeypatch.setattr(Path, "unlink", _raise)

    payload = _make_payload()
    result_path = write_scan_result(payload, str(tmp_path))

    assert result_path.exists()
    data = json.loads(result_path.read_text(encoding="utf-8"))
    assert data["subnet"] == "192.168.1.0/24"
    assert data["scan_mode"] == "quick"


def test_mkdir_oserror_propagates(tmp_path, monkeypatch):
    def _raise(self: Path, *args, **kwargs) -> None:
        raise OSError("mkdir boom")

    monkeypatch.setattr(Path, "mkdir", _raise)

    payload = _make_payload()
    with pytest.raises(OSError):
        write_scan_result(payload, str(tmp_path))


def test_write_text_oserror_propagates(tmp_path, monkeypatch):
    original_open = Path.open

    def _raise(self: Path, *args, **kwargs):
        if self.name.endswith(".json"):
            raise OSError("write boom")
        return original_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", _raise)

    payload = _make_payload()
    with pytest.raises(OSError):
        write_scan_result(payload, str(tmp_path))
