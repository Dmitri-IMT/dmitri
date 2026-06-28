"""Unit tests for LoggedNmapRunner — streaming + meta.json + pruning integration."""

from __future__ import annotations

import json
import sys
import textwrap
import threading
from pathlib import Path
from uuid import uuid4

import pytest
from agent.config import AgentSettings
from agent.scanner.errors import UnitScanError
from agent.scanner.nmap import (
    LoggedNmapRunner,
    NmapRunner,
    build_runner,
)

VALID_XML = textwrap.dedent("""\
    <?xml version="1.0"?>
    <nmaprun scanner="nmap">
      <host>
        <status state="up"/>
        <address addr="192.168.1.1" addrtype="ipv4"/>
      </host>
    </nmaprun>
""")


def _make_logged_runner(workspace: Path, stage: str = "discovery") -> LoggedNmapRunner:
    """Create a LoggedNmapRunner using Python as the executable."""
    runner = LoggedNmapRunner.__new__(LoggedNmapRunner)
    runner.nmap_path = sys.executable
    runner.workspace_root = workspace
    runner.logs_dir = workspace / "logs"
    runner.parent_scan_id = "test-scan-123"
    runner.agent_version = "0.1.0"
    runner._current_stage = stage
    runner._run_lock = threading.Lock()
    runner._active_run_dirs = set()
    runner._proc_lock = threading.Lock()
    runner._active_procs = set()
    runner._cancelled = False
    return runner


class TestLoggedNmapRunnerRunXml:
    def test_creates_run_folder_with_artifacts(self, tmp_path: Path) -> None:
        workspace = tmp_path / "workspace"
        (workspace / "logs").mkdir(parents=True)
        runner = _make_logged_runner(workspace)

        script = (
            "import sys; "
            f"open(sys.argv[sys.argv.index('-oX')+1], 'w').write('''{VALID_XML}''')"
        )
        runner.run_xml(["-c", script])

        logs_dir = workspace / "logs"
        run_dirs = [d for d in logs_dir.iterdir() if d.is_dir()]
        assert len(run_dirs) == 1

        run_dir = run_dirs[0]
        assert (run_dir / "console.log").exists()
        assert (run_dir / "stderr.log").exists()
        assert (run_dir / "meta.json").exists()
        assert (run_dir / "nmaprun.xml").exists()

    def test_meta_json_has_required_fields(self, tmp_path: Path) -> None:
        workspace = tmp_path / "workspace"
        (workspace / "logs").mkdir(parents=True)
        runner = _make_logged_runner(workspace)

        script = (
            "import sys; "
            f"open(sys.argv[sys.argv.index('-oX')+1], 'w').write('''{VALID_XML}''')"
        )
        runner.run_xml(["-c", script])

        run_dir = next((workspace / "logs").iterdir())
        meta = json.loads((run_dir / "meta.json").read_text(encoding="utf-8"))

        assert meta["run_id"] == run_dir.name
        assert meta["terminated_by"] == "completed"
        assert meta["exit_code"] == 0
        assert meta["parent_scan_id"] == "test-scan-123"
        assert meta["agent_version"] == "0.1.0"
        assert "started_at" in meta
        assert "finished_at" in meta

    def test_returns_parsed_xml_element(self, tmp_path: Path) -> None:
        workspace = tmp_path / "workspace"
        (workspace / "logs").mkdir(parents=True)
        runner = _make_logged_runner(workspace)

        script = (
            "import sys; "
            f"open(sys.argv[sys.argv.index('-oX')+1], 'w').write('''{VALID_XML}''')"
        )
        root = runner.run_xml(["-c", script])

        assert root.tag == "nmaprun"
        host = root.find("host")
        assert host is not None

    def test_raises_on_nonzero_exit_but_writes_meta(self, tmp_path: Path) -> None:
        workspace = tmp_path / "workspace"
        (workspace / "logs").mkdir(parents=True)
        runner = _make_logged_runner(workspace)

        with pytest.raises(UnitScanError):
            runner.run_xml(["-c", "raise SystemExit(1)"])

        run_dir = next((workspace / "logs").iterdir())
        meta = json.loads((run_dir / "meta.json").read_text(encoding="utf-8"))
        assert meta["terminated_by"] == "error"
        assert meta["exit_code"] == 1

    def test_stage_appears_in_folder_name(self, tmp_path: Path) -> None:
        workspace = tmp_path / "workspace"
        (workspace / "logs").mkdir(parents=True)
        runner = _make_logged_runner(workspace, stage="ports")

        script = (
            "import sys; "
            f"open(sys.argv[sys.argv.index('-oX')+1], 'w').write('''{VALID_XML}''')"
        )
        runner.run_xml(["-c", script])

        run_dir = next((workspace / "logs").iterdir())
        assert "-ports-" in run_dir.name

    def test_set_stage_changes_folder_name(self, tmp_path: Path) -> None:
        workspace = tmp_path / "workspace"
        (workspace / "logs").mkdir(parents=True)
        runner = _make_logged_runner(workspace, stage="discovery")

        runner.set_stage("nse")

        script = (
            "import sys; "
            f"open(sys.argv[sys.argv.index('-oX')+1], 'w').write('''{VALID_XML}''')"
        )
        runner.run_xml(["-c", script])

        run_dir = next((workspace / "logs").iterdir())
        assert "-nse-" in run_dir.name

    def test_prunes_logs_after_run(self, tmp_path: Path) -> None:
        workspace = tmp_path / "workspace"
        logs_dir = workspace / "logs"
        logs_dir.mkdir(parents=True)

        for i in range(10):
            d = logs_dir / f"2026-05-{i + 1:02d}-10-00-00-old-aa{i:02x}"
            d.mkdir()
            (d / "meta.json").write_text("{}", encoding="utf-8")

        runner = _make_logged_runner(workspace)
        script = (
            "import sys; "
            f"open(sys.argv[sys.argv.index('-oX')+1], 'w').write('''{VALID_XML}''')"
        )
        runner.run_xml(["-c", script])

        run_dirs = [d for d in logs_dir.iterdir() if d.is_dir()]
        assert len(run_dirs) == 10

    def test_argv_includes_injected_flags(self, tmp_path: Path) -> None:
        workspace = tmp_path / "workspace"
        (workspace / "logs").mkdir(parents=True)
        runner = _make_logged_runner(workspace)

        script = (
            "import sys; "
            f"open(sys.argv[sys.argv.index('-oX')+1], 'w').write('''{VALID_XML}''')"
        )
        runner.run_xml(["-c", script])

        run_dir = next((workspace / "logs").iterdir())
        meta = json.loads((run_dir / "meta.json").read_text(encoding="utf-8"))
        argv = meta["argv"]
        assert "-v" in argv
        assert "--stats-every" in argv
        assert "-oX" in argv


class TestLoggedNmapRunnerConcurrentPrune:
    def test_prune_skips_in_flight_run_directory(self, tmp_path: Path) -> None:
        workspace = tmp_path / "workspace"
        logs_dir = workspace / "logs"
        logs_dir.mkdir(parents=True)

        slow_dir = logs_dir / "2026-05-01-10-00-00-nse-slow"
        slow_dir.mkdir()
        (slow_dir / "console.log").write_text("still running", encoding="utf-8")

        for i in range(10):
            d = logs_dir / f"2026-05-{i + 2:02d}-10-00-00-old-aa{i:02x}"
            d.mkdir()
            (d / "meta.json").write_text("{}", encoding="utf-8")

        runner = _make_logged_runner(workspace, stage="nse")
        runner._active_run_dirs.add(slow_dir)

        script = (
            "import sys; "
            f"open(sys.argv[sys.argv.index('-oX')+1], 'w').write('''{VALID_XML}''')"
        )
        runner.run_xml(["-c", script])

        assert slow_dir.exists()
        assert (slow_dir / "console.log").read_text(encoding="utf-8") == "still running"
        run_dirs = [d for d in logs_dir.iterdir() if d.is_dir()]
        assert len(run_dirs) == 10
        assert any(d.name.startswith("2026-") and "-nse-" in d.name for d in run_dirs)


class TestBuildRunner:
    def test_creates_logged_runner_when_workspace_provided(
        self, tmp_path: Path
    ) -> None:
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        (workspace / "logs").mkdir()
        settings = AgentSettings(
            scan_subnet="192.168.1.0/24",
            nmap_path=sys.executable,
        )
        scan_id = uuid4()

        runner = build_runner(settings, workspace_root=workspace, scan_id=scan_id)

        assert isinstance(runner, LoggedNmapRunner)
        assert runner.parent_scan_id == str(scan_id)

    def test_creates_regular_runner_without_workspace(self) -> None:
        settings = AgentSettings(
            scan_subnet="192.168.1.0/24",
            nmap_path=sys.executable,
        )
        runner = build_runner(settings, workspace_root=None, scan_id=uuid4())
        assert type(runner) is NmapRunner

    def test_explicit_runner_takes_precedence(self, tmp_path: Path) -> None:
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        settings = AgentSettings(scan_subnet="192.168.1.0/24")
        custom_runner = NmapRunner.__new__(NmapRunner)
        custom_runner.nmap_path = "/custom/nmap"

        runner = build_runner(
            settings,
            workspace_root=workspace,
            scan_id=uuid4(),
            runner=custom_runner,
        )

        assert runner is custom_runner
