from __future__ import annotations

import subprocess
import sys
import textwrap
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest
from agent.scanner.errors import ScanCancelled
from agent.scanner.nmap import LoggedNmapRunner, NmapRunner

VALID_XML = textwrap.dedent("""\
    <?xml version="1.0"?>
    <nmaprun scanner="nmap">
      <host>
        <status state="up"/>
        <address addr="192.168.1.1" addrtype="ipv4"/>
      </host>
    </nmaprun>
""")


def _make_runner() -> NmapRunner:
    runner = NmapRunner.__new__(NmapRunner)
    runner.nmap_path = sys.executable
    runner._proc_lock = threading.Lock()
    runner._active_procs = set()
    runner._cancelled = False
    return runner


def _make_logged_runner(workspace: Path, stage: str = "ports") -> LoggedNmapRunner:
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


def _xml_write_script() -> str:
    return (
        "import sys; "
        f"open(sys.argv[sys.argv.index('-oX')+1], 'w').write('''{VALID_XML}''')"
    )


class TestNmapRunnerRunXmlGuard:
    def test_cancelled_raises_before_subprocess_run(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        runner = _make_runner()
        runner._cancelled = True
        calls: list = []
        monkeypatch.setattr(subprocess, "run", lambda *a, **k: calls.append(a))

        with pytest.raises(ScanCancelled):
            runner.run_xml(["-sn"])

        assert calls == []

    def test_uncancelled_spawns_and_returns_xml(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        runner = _make_runner()
        calls: list = []

        def fake_run(command, **kwargs):
            calls.append(command)
            return SimpleNamespace(returncode=0, stdout="<nmaprun/>", stderr="")

        monkeypatch.setattr(subprocess, "run", fake_run)

        root = runner.run_xml(["-sn"])

        assert root.tag == "nmaprun"
        assert len(calls) == 1


class TestNmapRunnerRunStreamedGuard:
    def test_cancelled_raises_before_popen_and_writes_no_files(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        runner = _make_runner()
        runner._cancelled = True
        calls: list = []
        monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: calls.append(a))

        with pytest.raises(ScanCancelled):
            runner.run_streamed(["-c", "pass"], run_dir)

        assert calls == []
        assert list(run_dir.iterdir()) == []

    def test_uncancelled_spawns(self, tmp_path: Path) -> None:
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        runner = _make_runner()

        result = runner.run_streamed(["-c", "pass"], run_dir)

        assert result.exit_code == 0


class TestLoggedNmapRunnerRunXmlGuard:
    def test_cancelled_raises_before_run_folder_and_subprocess(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        workspace = tmp_path / "workspace"
        logs_dir = workspace / "logs"
        logs_dir.mkdir(parents=True)
        runner = _make_logged_runner(workspace)
        runner._cancelled = True
        calls: list = []
        monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: calls.append(a))
        monkeypatch.setattr(subprocess, "run", lambda *a, **k: calls.append(a))

        with pytest.raises(ScanCancelled):
            runner.run_xml(["-sn"])

        assert calls == []
        assert list(logs_dir.iterdir()) == []

    def test_uncancelled_writes_run_folder(self, tmp_path: Path) -> None:
        workspace = tmp_path / "workspace"
        (workspace / "logs").mkdir(parents=True)
        runner = _make_logged_runner(workspace)

        runner.run_xml(["-c", _xml_write_script()])

        run_dirs = [d for d in (workspace / "logs").iterdir() if d.is_dir()]
        assert len(run_dirs) == 1
