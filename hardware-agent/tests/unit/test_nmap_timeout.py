"""Unit tests for NmapRunner timeout, taxonomy raising, and Popen tracking."""

from __future__ import annotations

import json
import sys
import threading
import time
from pathlib import Path

import pytest
from agent.scanner import nmap as nmap_module
from agent.scanner.errors import (
    BudgetExceeded,
    FatalScanError,
    TransientScanError,
    UnitScanError,
)
from agent.scanner.nmap import LoggedNmapRunner, NmapRunner

VALID_XML_SCRIPT = (
    "import sys; sys.stdout.write('<nmaprun scanner=\"nmap\"></nmaprun>')"
)
SLEEP_SCRIPT = "import time; time.sleep(5)"


def _make_runner() -> NmapRunner:
    runner = NmapRunner.__new__(NmapRunner)
    runner.nmap_path = sys.executable
    runner._proc_lock = threading.Lock()
    runner._active_procs = set()
    runner._cancelled = False
    return runner


def _make_logged_runner(workspace: Path, stage: str = "discovery") -> LoggedNmapRunner:
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


def test_legacy_runner_without_lease_attribute_has_no_pass_fds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = _make_runner()
    monkeypatch.setattr(nmap_module.os, "name", "posix")

    assert runner._lease_popen_options() == {}


class TestRunXmlTimeout:
    def test_slow_run_xml_raises_budget_exceeded(self) -> None:
        runner = _make_runner()

        with pytest.raises(BudgetExceeded):
            runner.run_xml(["-c", SLEEP_SCRIPT], timeout=0.2)

    def test_run_xml_kills_process_on_timeout(self) -> None:
        runner = _make_runner()

        with pytest.raises(BudgetExceeded):
            runner.run_xml(["-c", SLEEP_SCRIPT], timeout=0.2)

        assert runner._active_procs == set()

    def test_run_xml_no_timeout_completes(self) -> None:
        runner = _make_runner()

        root = runner.run_xml(["-c", VALID_XML_SCRIPT])

        assert root.tag == "nmaprun"

    def test_run_xml_explicit_none_timeout_completes(self) -> None:
        runner = _make_runner()

        root = runner.run_xml(["-c", VALID_XML_SCRIPT], timeout=None)

        assert root.tag == "nmaprun"


class TestRunStreamedTimeout:
    def test_slow_run_streamed_raises_budget_exceeded(self, tmp_path: Path) -> None:
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        runner = _make_runner()

        with pytest.raises(BudgetExceeded):
            runner.run_streamed(["-c", SLEEP_SCRIPT], run_dir, timeout=0.2)

    def test_run_streamed_deregisters_proc_on_timeout(self, tmp_path: Path) -> None:
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        runner = _make_runner()

        with pytest.raises(BudgetExceeded):
            runner.run_streamed(["-c", SLEEP_SCRIPT], run_dir, timeout=0.2)

        assert runner._active_procs == set()

    def test_run_streamed_no_timeout_completes(self, tmp_path: Path) -> None:
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        runner = _make_runner()

        result = runner.run_streamed(["-c", "pass"], run_dir)

        assert result.exit_code == 0
        assert runner._active_procs == set()


class TestLoggedRunnerTimeoutMeta:
    def test_timeout_writes_terminated_by_timeout(self, tmp_path: Path) -> None:
        workspace = tmp_path / "workspace"
        (workspace / "logs").mkdir(parents=True)
        runner = _make_logged_runner(workspace)

        with pytest.raises(BudgetExceeded):
            runner.run_xml(["-c", SLEEP_SCRIPT], timeout=0.2)

        run_dir = next((workspace / "logs").iterdir())
        meta = json.loads((run_dir / "meta.json").read_text(encoding="utf-8"))
        assert meta["terminated_by"] == "timeout"
        assert meta["exit_code"] is None

    def test_no_timeout_writes_completed(self, tmp_path: Path) -> None:
        workspace = tmp_path / "workspace"
        (workspace / "logs").mkdir(parents=True)
        runner = _make_logged_runner(workspace)

        script = (
            "import sys; "
            "open(sys.argv[sys.argv.index('-oX')+1], 'w')"
            ".write('<nmaprun scanner=\"nmap\"></nmaprun>')"
        )
        runner.run_xml(["-c", script])

        run_dir = next((workspace / "logs").iterdir())
        meta = json.loads((run_dir / "meta.json").read_text(encoding="utf-8"))
        assert meta["terminated_by"] == "completed"


class TestRunXmlTaxonomy:
    def test_nonzero_exit_raises_unit_scan_error(self) -> None:
        runner = _make_runner()

        with pytest.raises(UnitScanError):
            runner.run_xml(["-c", "raise SystemExit(2)"])

    def test_bad_xml_raises_unit_scan_error(self) -> None:
        runner = _make_runner()

        with pytest.raises(UnitScanError):
            runner.run_xml(["-c", "import sys; sys.stdout.write('not xml at all')"])

    def test_nmap_not_found_raises_fatal_scan_error(self) -> None:
        runner = _make_runner()
        runner.nmap_path = str(Path(__file__).parent / "does-not-exist-nmap")

        with pytest.raises(FatalScanError):
            runner.run_xml(["-c", "pass"])

    def test_transient_marker_raises_transient_scan_error(self) -> None:
        runner = _make_runner()
        script = (
            "import sys; "
            "sys.stderr.write('connection reset by peer'); "
            "sys.exit(1)"
        )

        with pytest.raises(TransientScanError):
            runner.run_xml(["-c", script])

    def test_other_stderr_stays_unit_scan_error(self) -> None:
        runner = _make_runner()
        script = "import sys; sys.stderr.write('some other failure'); sys.exit(1)"

        with pytest.raises(UnitScanError):
            runner.run_xml(["-c", script])


class TestTerminateActive:
    def test_terminate_active_kills_tracked_proc(self, tmp_path: Path) -> None:
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        runner = _make_runner()
        captured: dict[str, object] = {}

        def _run() -> None:
            try:
                captured["result"] = runner.run_streamed(["-c", SLEEP_SCRIPT], run_dir)
            except Exception as exc:
                captured["error"] = exc

        thread = threading.Thread(target=_run)
        thread.start()

        deadline = time.time() + 5.0
        while not runner._active_procs and time.time() < deadline:
            time.sleep(0.01)
        assert runner._active_procs

        runner.terminate_active()
        thread.join(timeout=5.0)

        assert not thread.is_alive()
        assert runner._cancelled is True
        assert runner._active_procs == set()

    def test_terminate_active_with_no_procs_is_noop(self) -> None:
        runner = _make_runner()

        runner.terminate_active()

        assert runner._cancelled is True
