from __future__ import annotations

import os
import sys
import tempfile
import threading
import time
from os import kill
from pathlib import Path
from time import perf_counter

import agent.targeted.executor as executor_module
import pytest
from agent.targeted.executor import TargetedExecutor, ToolCommand
from agent.targeted.models import TargetedGapReason, TargetedOutcome, TargetedTool


@pytest.fixture(autouse=True)
def _require_linux_runtime(request: pytest.FixtureRequest) -> None:
    if request.node.name.startswith("test_report_limit_hit"):
        return
    if sys.platform != "linux":
        pytest.skip("targeted subprocess runtime requires Linux")


def _file_command(script: str) -> ToolCommand:
    return ToolCommand(
        tool=TargetedTool.SSH_AUDIT,
        argv=(sys.executable, "-c", script, "report-placeholder"),
        report_mode="file",
        report_argument_index=3,
        timeout_s=2,
    )


def _assert_process_not_running(pid: int) -> None:
    """Reject live descendants without mistaking a transient zombie for one."""

    deadline = time.monotonic() + 2
    proc_stat = Path(f"/proc/{pid}/stat")
    while time.monotonic() < deadline:
        try:
            kill(pid, 0)
        except ProcessLookupError:
            return
        try:
            state = proc_stat.read_text().split()[2]
        except FileNotFoundError:
            return
        if state == "Z":
            return
        time.sleep(0.01)
    raise AssertionError(f"process {pid} is still running")


def _read_pid_when_ready(path: Path, timeout: float = 2) -> int:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            pid = int(path.read_text())
        except (FileNotFoundError, ValueError):
            time.sleep(0.01)
            continue
        if pid > 0:
            return pid
        time.sleep(0.01)
    raise AssertionError(f"process id was not written to {path}")


def test_file_report_is_read_and_private_temp_file_is_removed(tmp_path: Path) -> None:
    recorded_path = tmp_path / "report-path.txt"
    command = _file_command(
        "from pathlib import Path; "
        f"Path({str(recorded_path)!r}).write_text(__import__('sys').argv[1]); "
        "Path(__import__('sys').argv[1]).write_bytes(b'{\"ok\": true}')"
    )

    result = TargetedExecutor().execute(command)

    assert result.outcome is TargetedOutcome.COMPLETED
    assert result.report == b'{"ok": true}'
    assert result.report_present is True
    assert not Path(recorded_path.read_text()).exists()


def test_subprocess_config_is_writable_and_isolated_from_protected_home(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    inherited_config = tmp_path / "protected-config"
    inherited_config.write_text("not a directory")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(inherited_config))
    command = _file_command(
        "import os,sys; from pathlib import Path; "
        "config=Path(os.environ['XDG_CONFIG_HOME']); "
        "(config/'ffuf'/'scraper').mkdir(parents=True); "
        "Path(sys.argv[1]).write_text(str(config))"
    )

    result = TargetedExecutor().execute(command)

    assert result.exit_code == 0
    assert result.report_present
    assert not Path(result.report.decode()).exists()
    assert os.environ["XDG_CONFIG_HOME"] == str(inherited_config)


def test_structured_stdout_is_report_not_diagnostic() -> None:
    command = ToolCommand(
        tool=TargetedTool.SSH_AUDIT,
        argv=(sys.executable, "-c", "print('{\"ok\": true}')"),
        report_mode="stdout",
        timeout_s=2,
    )

    result = TargetedExecutor().execute(command)

    assert result.outcome is TargetedOutcome.COMPLETED
    assert result.report.replace(b"\r\n", b"\n") == b'{"ok": true}\n'
    assert result.report_present is True
    assert result.stdout == b""
    assert result.diagnostic is None


def test_structured_stdout_report_is_file_backed_capped_and_cleaned(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(executor_module, "TARGETED_REPORT_LIMIT_BYTES", 32)
    recorded = tmp_path / "report-path"
    created_directories: list[Path] = []
    original_temporary_directory = tempfile.TemporaryDirectory

    class RecordingTemporaryDirectory:
        def __init__(self, *args, **kwargs) -> None:
            self._manager = original_temporary_directory(*args, **kwargs)

        def __enter__(self) -> str:
            directory = self._manager.__enter__()
            created_directories.append(Path(directory))
            return directory

        def __exit__(self, *args) -> None:
            self._manager.__exit__(*args)

    monkeypatch.setattr(
        executor_module.tempfile, "TemporaryDirectory", RecordingTemporaryDirectory
    )
    # The child cannot write the executor-owned path directly.  It records its
    # temporary working directory so the test can prove the report is not left
    # behind after execution.
    command = ToolCommand(
        tool=TargetedTool.SSH_AUDIT,
        argv=(
            sys.executable,
            "-c",
            "from pathlib import Path; import os, sys; "
            f"Path({str(recorded)!r}).write_text(os.path.dirname(sys.executable)); "
            "sys.stdout.write('x'*1000)",
        ),
        report_mode="stdout",
        timeout_s=2,
    )

    result = TargetedExecutor().execute(command)

    assert result.outcome is TargetedOutcome.FAILED
    assert result.reason_code is TargetedGapReason.OUTPUT_LIMIT
    assert result.report == b"x" * 32
    assert result.report_truncated is True
    # The executor's TemporaryDirectory is cleaned even after a capped report.
    assert created_directories and not created_directories[0].exists()


def test_cancel_before_spawn_is_isolated() -> None:
    cancelled = threading.Event()
    cancelled.set()
    command = ToolCommand(
        tool=TargetedTool.SSH_AUDIT,
        argv=("not-run",),
        report_mode="stdout",
    )

    result = TargetedExecutor().execute(command, cancel_event=cancelled)

    assert result.outcome is TargetedOutcome.SKIPPED
    assert result.cancelled is True
    assert result.reason_code is TargetedGapReason.SCAN_CANCELLED


def test_cancellation_rechecked_after_tempdir_setup_before_spawn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cancelled = threading.Event()
    original = tempfile.TemporaryDirectory

    class CancelDuringTempdir:
        def __init__(self, *args, **kwargs) -> None:
            self._manager = original(*args, **kwargs)

        def __enter__(self) -> str:
            directory = self._manager.__enter__()
            cancelled.set()
            return directory

        def __exit__(self, *args) -> None:
            self._manager.__exit__(*args)

    calls = []
    original_popen = executor_module.subprocess.Popen

    def recording_popen(*args, **kwargs):
        calls.append(1)
        return original_popen(*args, **kwargs)

    monkeypatch.setattr(executor_module.subprocess, "Popen", recording_popen)
    monkeypatch.setattr(
        executor_module.tempfile, "TemporaryDirectory", CancelDuringTempdir
    )
    result = TargetedExecutor().execute(
        ToolCommand(
            tool=TargetedTool.SSH_AUDIT,
            argv=(sys.executable, "-c", "raise SystemExit(99)"),
            report_mode="stdout",
        ),
        cancel_event=cancelled,
    )

    assert result.outcome is TargetedOutcome.SKIPPED
    assert result.cancelled is True
    assert not calls


def test_deadline_rechecked_after_tempdir_setup_before_spawn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = tempfile.TemporaryDirectory
    stage_deadline = perf_counter() + 0.01

    class ExpireDuringTempdir:
        def __init__(self, *args, **kwargs) -> None:
            self._manager = original(*args, **kwargs)

        def __enter__(self) -> str:
            directory = self._manager.__enter__()
            monkeypatch.setattr(executor_module, "perf_counter", lambda: float("inf"))
            return directory

        def __exit__(self, *args) -> None:
            self._manager.__exit__(*args)

    monkeypatch.setattr(
        executor_module.tempfile, "TemporaryDirectory", ExpireDuringTempdir
    )
    result = TargetedExecutor().execute(
        ToolCommand(
            tool=TargetedTool.SSH_AUDIT,
            argv=(sys.executable, "-c", "raise SystemExit(99)"),
            report_mode="stdout",
        ),
        stage_deadline=stage_deadline,
    )

    assert result.outcome is TargetedOutcome.SKIPPED
    assert result.reason_code is TargetedGapReason.STAGE_BUDGET


def test_stage_deadline_precedes_tool_allowance_without_spawn() -> None:
    command = ToolCommand(
        tool=TargetedTool.SSH_AUDIT,
        argv=("not-run",),
        report_mode="stdout",
        timeout_s=10,
    )

    result = TargetedExecutor().execute(command, stage_deadline=perf_counter() - 1)

    assert result.outcome is TargetedOutcome.SKIPPED
    assert result.reason_code is TargetedGapReason.STAGE_BUDGET
    assert result.deadline_scope is None


def test_missing_executable_is_a_skipped_coverage_gap() -> None:
    command = ToolCommand(
        tool=TargetedTool.SSH_AUDIT,
        argv=("definitely-not-a-dmitri-tool",),
        report_mode="stdout",
    )

    result = TargetedExecutor().execute(command)

    assert result.outcome is TargetedOutcome.SKIPPED
    assert result.reason_code is TargetedGapReason.TOOL_UNAVAILABLE


def test_literal_argv_is_not_interpreted_as_shell_code(tmp_path: Path) -> None:
    observed = tmp_path / "argv.txt"
    marker = tmp_path / "should-not-exist"
    hostile = f"x; touch {marker} $(echo pwned)"
    command = ToolCommand(
        tool=TargetedTool.SSH_AUDIT,
        argv=(
            sys.executable,
            "-c",
            "from pathlib import Path; import sys; "
            "Path(sys.argv[1]).write_text(sys.argv[2])",
            str(observed),
            hostile,
        ),
        report_mode="stdout",
        timeout_s=2,
    )

    result = TargetedExecutor().execute(command)

    assert result.outcome is TargetedOutcome.COMPLETED
    assert observed.read_text() == hostile
    assert not marker.exists()


def test_concurrent_execute_calls_are_serialized(tmp_path: Path) -> None:
    marker = tmp_path / "active"
    overlap = tmp_path / "overlap"
    script = (
        "from pathlib import Path\nimport time\n"
        f"marker=Path({str(marker)!r})\n"
        f"overlap=Path({str(overlap)!r})\n"
        "if marker.exists(): overlap.write_text('yes')\n"
        "marker.write_text('1')\n"
        "time.sleep(.15)\n"
        "marker.unlink()\n"
    )
    command = ToolCommand(
        tool=TargetedTool.SSH_AUDIT,
        argv=(sys.executable, "-c", script),
        report_mode="stdout",
        timeout_s=2,
    )
    executor = TargetedExecutor()
    threads = [
        threading.Thread(target=executor.execute, args=(command,)) for _ in range(2)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert not overlap.exists()


def test_cancelled_queued_execution_does_not_start_after_serialized_call(
    tmp_path: Path,
) -> None:
    started = tmp_path / "started"
    cancel_event = threading.Event()
    command = ToolCommand(
        tool=TargetedTool.SSH_AUDIT,
        argv=(
            sys.executable,
            "-c",
            f"from pathlib import Path; Path({str(started)!r}).write_text('yes')",
        ),
        report_mode="stdout",
        timeout_s=2,
    )
    executor = TargetedExecutor()
    first = threading.Thread(
        target=executor.execute,
        args=(
            ToolCommand(
                tool=TargetedTool.SSH_AUDIT,
                argv=(sys.executable, "-c", "import time; time.sleep(.2)"),
                report_mode="stdout",
                timeout_s=2,
            ),
        ),
    )
    first.start()
    time.sleep(0.03)
    cancel_event.set()
    result = executor.execute(command, cancel_event=cancel_event)
    first.join(timeout=3)

    assert result.outcome is TargetedOutcome.SKIPPED
    assert result.reason_code is TargetedGapReason.SCAN_CANCELLED
    assert result.deadline_scope is None
    assert not started.exists()


def test_stdout_and_stderr_are_drained_and_capped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(executor_module, "TARGETED_STDIO_LIMIT_BYTES", 128)
    monkeypatch.setattr(executor_module, "TARGETED_REPORT_LIMIT_BYTES", 128)
    script = "import sys; sys.stdout.write('o'*10000); sys.stderr.write('e'*10000)"
    result = TargetedExecutor().execute(
        ToolCommand(
            tool=TargetedTool.SSH_AUDIT,
            argv=(sys.executable, "-c", script),
            report_mode="stdout",
            timeout_s=2,
        )
    )

    assert result.outcome is TargetedOutcome.FAILED
    assert result.reason_code is TargetedGapReason.OUTPUT_LIMIT
    assert len(result.report) == 128
    assert len(result.stderr) == 128
    assert result.report_truncated is True
    assert result.stderr_truncated is True


def test_oversized_file_report_is_bounded_and_cleaned(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(executor_module, "TARGETED_REPORT_LIMIT_BYTES", 128)
    recorded = tmp_path / "report-path"
    command = _file_command(
        f"from pathlib import Path; import sys; "
        f"Path({str(recorded)!r}).write_text(sys.argv[1]); "
        "Path(sys.argv[1]).write_bytes(b'x'*10000)"
    )

    result = TargetedExecutor().execute(command)

    assert result.outcome is TargetedOutcome.FAILED
    assert result.reason_code is TargetedGapReason.OUTPUT_LIMIT
    assert result.report == b"x" * 128
    assert result.report_truncated is True
    assert not Path(recorded.read_text()).exists()


def test_missing_report_is_preserved_for_adapter_and_temp_file_is_removed(
    tmp_path: Path,
) -> None:
    recorded = tmp_path / "report-path"
    command = _file_command(
        f"from pathlib import Path; import sys; "
        f"Path({str(recorded)!r}).write_text(sys.argv[1])"
    )

    result = TargetedExecutor().execute(command)

    assert result.outcome is TargetedOutcome.COMPLETED
    assert result.reason_code is None
    assert result.report == b""
    assert result.report_present is False
    assert not Path(recorded.read_text()).exists()


@pytest.mark.parametrize(
    ("script", "report", "present"),
    [
        (
            "from pathlib import Path; import sys; "
            "Path(sys.argv[1]).write_bytes(b'{}'); raise SystemExit(7)",
            b"{}",
            True,
        ),
        ("raise SystemExit(7)", b"", False),
        (
            "from pathlib import Path; import sys; "
            "Path(sys.argv[1]).write_bytes(b'not-json'); raise SystemExit(7)",
            b"not-json",
            True,
        ),
        (
            "from pathlib import Path; import sys; "
            "Path(sys.argv[1]).write_bytes(b''); raise SystemExit(7)",
            b"",
            True,
        ),
    ],
    ids=["valid", "missing", "malformed", "empty"],
)
def test_nonzero_exit_preserves_raw_report_for_adapter(
    script: str, report: bytes, present: bool
) -> None:
    result = TargetedExecutor().execute(_file_command(script))

    assert result.outcome is TargetedOutcome.COMPLETED
    assert result.reason_code is None
    assert result.exit_code == 7
    assert result.report == report
    assert result.report_present is present
    assert result.deadline_scope is None


def test_stage_deadline_does_not_leak_scope_on_cancelled_execution() -> None:
    cancel_event = threading.Event()
    cancel_event.set()
    result = TargetedExecutor().execute(
        ToolCommand(
            tool=TargetedTool.SSH_AUDIT,
            argv=("not-run",),
            report_mode="stdout",
        ),
        cancel_event=cancel_event,
        stage_deadline=perf_counter() + 30,
    )

    assert result.outcome is TargetedOutcome.SKIPPED
    assert result.deadline_scope is None


def test_unit_timeout_terminates_active_process() -> None:
    result = TargetedExecutor().execute(
        ToolCommand(
            tool=TargetedTool.SSH_AUDIT,
            argv=(sys.executable, "-c", "import time; time.sleep(10)"),
            report_mode="stdout",
            timeout_s=0.05,
        )
    )

    assert result.outcome is TargetedOutcome.TIMED_OUT
    assert result.reason_code is TargetedGapReason.UNIT_TIMEOUT
    assert result.deadline_scope == "unit"


def test_zero_timeout_is_an_immediate_unit_timeout() -> None:
    result = TargetedExecutor().execute(
        ToolCommand(
            tool=TargetedTool.SSH_AUDIT,
            argv=("not-run",),
            report_mode="stdout",
            timeout_s=0,
        )
    )

    assert result.outcome is TargetedOutcome.TIMED_OUT
    assert result.reason_code is TargetedGapReason.UNIT_TIMEOUT
    assert result.deadline_scope == "unit"


def test_completion_after_effective_deadline_is_not_accepted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = iter((100.0, 100.01, 100.2))
    monkeypatch.setattr(executor_module, "perf_counter", lambda: next(clock, 100.2))
    result = TargetedExecutor().execute(
        ToolCommand(
            tool=TargetedTool.SSH_AUDIT,
            argv=(sys.executable, "-c", "print('{}')"),
            report_mode="stdout",
            timeout_s=0.1,
        )
    )

    assert result.outcome is TargetedOutcome.TIMED_OUT
    assert result.reason_code is TargetedGapReason.UNIT_TIMEOUT
    assert result.deadline_scope == "unit"


@pytest.mark.parametrize(
    ("kwargs", "scope", "outcome", "reason"),
    [
        (
            {
                "stage_deadline": perf_counter() - 2,
                "overall_deadline": perf_counter() - 1,
            },
            "stage",
            TargetedOutcome.SKIPPED,
            TargetedGapReason.STAGE_BUDGET,
        ),
        (
            {
                "stage_deadline": perf_counter() + 1,
                "overall_deadline": perf_counter() - 1,
            },
            "overall",
            TargetedOutcome.TIMED_OUT,
            None,
        ),
    ],
)
def test_earliest_deadline_scope_wins(kwargs, scope, outcome, reason) -> None:
    result = TargetedExecutor().execute(
        ToolCommand(
            tool=TargetedTool.SSH_AUDIT,
            argv=("not-run",),
            report_mode="stdout",
        ),
        **kwargs,
    )

    assert result.outcome is outcome
    assert result.reason_code is reason
    assert result.deadline_scope == (
        scope if outcome is TargetedOutcome.TIMED_OUT else None
    )


def test_posix_report_at_exact_rlimit_ceiling_is_not_marked_truncated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if os.name != "posix":
        pytest.skip("requires POSIX RLIMIT_FSIZE")
    monkeypatch.setattr(executor_module, "TARGETED_REPORT_LIMIT_BYTES", 128)
    command = _file_command(
        "from pathlib import Path; import sys; "
        "Path(sys.argv[1]).write_bytes(b'x' * 128)"
    )

    result = TargetedExecutor().execute(command)

    assert result.outcome is TargetedOutcome.COMPLETED
    assert result.report == b"x" * 128
    assert result.report_truncated is False


def test_posix_exact_rlimit_ceiling_with_nonzero_exit_stays_completed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if os.name != "posix":
        pytest.skip("requires POSIX RLIMIT_FSIZE")
    monkeypatch.setattr(executor_module, "TARGETED_REPORT_LIMIT_BYTES", 128)
    command = _file_command(
        "from pathlib import Path; import sys; "
        "Path(sys.argv[1]).write_bytes(b'x' * 128); raise SystemExit(7)"
    )

    result = TargetedExecutor().execute(command)

    assert result.outcome is TargetedOutcome.COMPLETED
    assert result.reason_code is None
    assert result.exit_code == 7
    assert result.report == b"x" * 128
    assert result.report_truncated is False


def test_report_limit_hit_exact_size_is_not_truncated(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(executor_module, "TARGETED_REPORT_LIMIT_BYTES", 128)
    path = tmp_path / "report"
    path.write_bytes(b"x" * 128)

    assert TargetedExecutor._report_limit_hit(path) is False


def test_report_limit_hit_over_limit_is_truncated(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(executor_module, "TARGETED_REPORT_LIMIT_BYTES", 128)
    path = tmp_path / "report"
    path.write_bytes(b"x" * 129)

    assert TargetedExecutor._report_limit_hit(path) is True


def test_malformed_nonempty_file_report_is_retained_for_adapter_parsing() -> None:
    result = TargetedExecutor().execute(
        _file_command(
            "from pathlib import Path; import sys; "
            "Path(sys.argv[1]).write_bytes(b'not-json')"
        )
    )

    assert result.outcome is TargetedOutcome.COMPLETED
    assert result.report == b"not-json"
    assert result.report_present is True


def test_report_setup_failure_terminates_spawned_process(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    child_pid = tmp_path / "child-pid"
    script = (
        "import time; "
        f"open({str(child_pid)!r}, 'w').write(str(__import__('os').getpid())); "
        "time.sleep(30)"
    )

    def fail_report(*args, **kwargs):
        raise OSError("report setup failed")

    monkeypatch.setattr(executor_module, "_CappedReport", fail_report)

    original_popen = executor_module.subprocess.Popen

    def wait_for_child_pid(*args, **kwargs):
        process = original_popen(*args, **kwargs)
        _read_pid_when_ready(child_pid)
        return process

    monkeypatch.setattr(executor_module.subprocess, "Popen", wait_for_child_pid)
    result = TargetedExecutor().execute(
        ToolCommand(
            tool=TargetedTool.SSH_AUDIT,
            argv=(sys.executable, "-c", script),
            report_mode="stdout",
            timeout_s=2,
        )
    )

    assert result.outcome is TargetedOutcome.FAILED
    assert result.reason_code is TargetedGapReason.EXECUTION_ERROR
    _assert_process_not_running(_read_pid_when_ready(child_pid))


def test_tempdir_creation_failure_is_execution_error_without_spawn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_tempdir(*args, **kwargs):
        raise OSError("tempdir setup failed")

    monkeypatch.setattr(executor_module.tempfile, "TemporaryDirectory", fail_tempdir)
    calls = []
    original_popen = executor_module.subprocess.Popen

    def recording_popen(*args, **kwargs):
        calls.append(1)
        return original_popen(*args, **kwargs)

    monkeypatch.setattr(executor_module.subprocess, "Popen", recording_popen)
    result = TargetedExecutor().execute(
        ToolCommand(
            tool=TargetedTool.SSH_AUDIT,
            argv=(sys.executable, "-c", "raise SystemExit(99)"),
            report_mode="stdout",
        )
    )

    assert result.outcome is TargetedOutcome.FAILED
    assert result.reason_code is TargetedGapReason.EXECUTION_ERROR
    assert not calls


@pytest.mark.skipif(sys.platform == "win32", reason="requires POSIX process groups")
def test_cancellation_kills_child_after_parent_exits(tmp_path: Path) -> None:
    child_pid = tmp_path / "child-pid"
    script = (
        "import subprocess, sys; "
        "child=subprocess.Popen([sys.executable, '-c', "
        "'import time; time.sleep(30)']); "
        f"open({str(child_pid)!r}, 'w').write(str(child.pid))"
    )
    executor = TargetedExecutor()
    result_holder = {}
    thread = threading.Thread(
        target=lambda: result_holder.setdefault(
            "result",
            executor.execute(
                ToolCommand(
                    tool=TargetedTool.SSH_AUDIT,
                    argv=(sys.executable, "-c", script),
                    report_mode="stdout",
                    timeout_s=10,
                )
            ),
        )
    )
    thread.start()
    deadline = time.monotonic() + 3
    while not child_pid.exists() and time.monotonic() < deadline:
        time.sleep(0.01)
    executor.terminate_active()
    thread.join(timeout=3)

    assert not thread.is_alive()
    assert result_holder["result"].cancelled is True
    child = int(child_pid.read_text())
    _assert_process_not_running(child)


@pytest.mark.skipif(sys.platform == "win32", reason="requires POSIX process groups")
def test_timeout_kills_child_after_parent_exits(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    child_pid = tmp_path / "child-pid"
    script = (
        "import subprocess, sys; "
        "child=subprocess.Popen([sys.executable, '-c', "
        "'import time; time.sleep(30)']); "
        f"open({str(child_pid)!r}, 'w').write(str(child.pid)); "
        "import time; time.sleep(30)"
    )
    timeout_s = 1.0
    now = time.monotonic()
    deadline = now + timeout_s

    def expire_after_child_starts() -> float:
        try:
            pid = int(child_pid.read_text())
        except (FileNotFoundError, ValueError):
            return now
        return deadline + 0.001 if pid > 0 else now

    monkeypatch.setattr(executor_module, "perf_counter", expire_after_child_starts)
    result = TargetedExecutor().execute(
        ToolCommand(
            tool=TargetedTool.SSH_AUDIT,
            argv=(sys.executable, "-c", script),
            report_mode="stdout",
            timeout_s=timeout_s,
        )
    )

    assert result.outcome is TargetedOutcome.TIMED_OUT
    assert result.deadline_scope == "unit"
    child = _read_pid_when_ready(child_pid)
    _assert_process_not_running(child)


@pytest.mark.skipif(sys.platform == "win32", reason="requires POSIX process groups")
def test_parent_exit_does_not_leave_process_group_descendant(
    tmp_path: Path,
) -> None:
    child_pid = tmp_path / "child-pid"
    script = (
        "import subprocess, sys; "
        "child=subprocess.Popen([sys.executable, '-c', "
        "'import time; time.sleep(30)']); "
        f"open({str(child_pid)!r}, 'w').write(str(child.pid))"
    )
    result = TargetedExecutor().execute(
        ToolCommand(
            tool=TargetedTool.SSH_AUDIT,
            argv=(sys.executable, "-c", script),
            report_mode="stdout",
            timeout_s=2,
        )
    )

    assert result.outcome is TargetedOutcome.COMPLETED
    child = int(child_pid.read_text())
    _assert_process_not_running(child)


def test_registered_socket_is_closed_on_cancellation() -> None:
    left, right = __import__("socket").socketpair()
    executor = TargetedExecutor()
    executor.register_socket(left)
    executor.terminate_active()

    with pytest.raises(OSError):
        left.getsockname()
    right.close()
