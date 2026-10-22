"""Bounded Linux process and socket lifecycle for targeted adapters.

The targeted runtime is deliberately Linux-only (Raspberry Pi 3/4). Windows is
kept as a development and test host, but never starts a targeted subprocess.
Adapters provide literal argument vectors; this module owns process groups,
temporary reports, deadlines, and output limits.
"""

from __future__ import annotations

import os
import signal
import socket
import subprocess
import sys
import tempfile
import threading
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Literal

try:
    import resource
except ImportError:
    resource = None

from agent.config import (
    TARGETED_DIAGNOSTIC_LIMIT_CHARS,
    TARGETED_REPORT_LIMIT_BYTES,
    TARGETED_STDIO_LIMIT_BYTES,
    TARGETED_UNIT_TIMEOUT_S,
)
from agent.scanner.scan_lock import ScanLease
from agent.targeted.models import TargetedGapReason, TargetedOutcome, TargetedTool

ReportMode = Literal["file", "stdout"]
ReportPathMode = Literal["exact", "base"]
DeadlineScope = Literal["unit", "stage", "overall"]


@dataclass(frozen=True, slots=True)
class ToolCommand:
    """One literal command and its structured-report ownership contract."""

    tool: TargetedTool
    argv: Sequence[str]
    report_mode: ReportMode
    report_argument_index: int | None = None
    timeout_s: float | None = None
    report_path_mode: ReportPathMode = "exact"


@dataclass(frozen=True, slots=True)
class ToolExecution:
    """A bounded, cleaned-up execution result for an adapter to parse."""

    outcome: TargetedOutcome
    exit_code: int | None = None
    reason_code: TargetedGapReason | None = None
    diagnostic: str | None = None
    report: bytes = b""
    report_present: bool = False
    stdout: bytes = b""
    stderr: bytes = b""
    stdout_truncated: bool = False
    stderr_truncated: bool = False
    report_truncated: bool = False
    cancelled: bool = False
    deadline_scope: DeadlineScope | None = None


class _CappedBuffer:
    def __init__(self, limit: int) -> None:
        self._limit = limit
        self.data = bytearray()
        self.truncated = False

    def append(self, chunk: bytes) -> None:
        available = self._limit - len(self.data)
        if available > 0:
            self.data.extend(chunk[:available])
        if len(chunk) > max(available, 0):
            self.truncated = True


class _CappedReport:
    """Write structured stdout to an executor-owned, bounded temp file."""

    def __init__(self, path: Path, limit: int) -> None:
        self._file = path.open("wb")
        self._limit = limit
        self._written = 0
        self.truncated = False

    def append(self, chunk: bytes) -> None:
        available = self._limit - self._written
        if available > 0:
            accepted = chunk[:available]
            self._file.write(accepted)
            self._written += len(accepted)
        if len(chunk) > max(available, 0):
            self.truncated = True

    def close(self) -> None:
        self._file.close()


class TargetedExecutor:
    """Run one targeted unit at a time and own its process group and sockets."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._execution_lock = threading.Lock()
        self._active_process: subprocess.Popen[bytes] | None = None
        self._active_sockets: set[socket.socket] = set()
        self._cancelled = False
        self._scan_lease: ScanLease | None = None

    def set_scan_lease(self, lease: ScanLease | None) -> None:
        self._scan_lease = lease

    def terminate_active(self) -> None:
        """Stop the active process group and close active native-probe sockets."""

        self._cancelled = True
        with self._lock:
            process = self._active_process
            sockets = tuple(self._active_sockets)
        for active_socket in sockets:
            try:
                active_socket.close()
            except OSError:
                pass
        if process is not None:
            self._terminate_process_group(process)

    def register_socket(self, active_socket: socket.socket) -> None:
        """Register a native probe socket so cancellation can close it."""

        with self._lock:
            if self._cancelled:
                active_socket.close()
                return
            self._active_sockets.add(active_socket)

    def unregister_socket(self, active_socket: socket.socket) -> None:
        with self._lock:
            self._active_sockets.discard(active_socket)

    def execute(
        self,
        command: ToolCommand,
        *,
        cancel_event: threading.Event | None = None,
        stage_deadline: float | None = None,
        overall_deadline: float | None = None,
    ) -> ToolExecution:
        """Run one command with the earliest applicable monotonic deadline."""

        with self._execution_lock:
            return self._execute(
                command,
                cancel_event=cancel_event,
                stage_deadline=stage_deadline,
                overall_deadline=overall_deadline,
            )

    def _execute(
        self,
        command: ToolCommand,
        *,
        cancel_event: threading.Event | None,
        stage_deadline: float | None,
        overall_deadline: float | None,
    ) -> ToolExecution:
        if self._is_cancelled(cancel_event):
            return self._cancelled_execution()
        if not self._platform_supported():
            return ToolExecution(
                outcome=TargetedOutcome.SKIPPED,
                reason_code=TargetedGapReason.INCOMPATIBLE_TOOL,
                diagnostic=(
                    "Targeted subprocess execution is unsupported on this platform; "
                    "Raspberry Pi Linux is required."
                ),
            )

        now = perf_counter()
        allowance = (
            TARGETED_UNIT_TIMEOUT_S[command.tool.value]
            if command.timeout_s is None
            else command.timeout_s
        )
        candidates: tuple[tuple[float, DeadlineScope], ...] = (
            (now + allowance, "unit"),
        )
        if stage_deadline is not None:
            candidates += ((stage_deadline, "stage"),)
        if overall_deadline is not None:
            candidates += ((overall_deadline, "overall"),)
        deadline, deadline_scope = min(candidates, key=lambda candidate: candidate[0])
        if deadline <= now:
            outcome, reason = self._deadline_outcome(deadline_scope)
            return ToolExecution(
                outcome=outcome,
                reason_code=reason,
                diagnostic="Targeted tool deadline elapsed before spawn.",
                deadline_scope=(
                    deadline_scope if outcome == TargetedOutcome.TIMED_OUT else None
                ),
            )

        try:
            with tempfile.TemporaryDirectory(prefix="dmitri-targeted-") as directory:
                report_path = Path(directory) / "report.json"
                report_argument_path = (
                    report_path.with_suffix("")
                    if command.report_path_mode == "base"
                    else report_path
                )
                argv = self._report_argv(command, report_argument_path)
                if argv is None:
                    return ToolExecution(
                        outcome=TargetedOutcome.FAILED,
                        reason_code=TargetedGapReason.SPAWN_ERROR,
                        diagnostic="Invalid file-report command contract.",
                    )
                return self._run(
                    argv,
                    command.report_mode,
                    report_path,
                    deadline,
                    deadline_scope,
                    cancel_event,
                )
        except OSError as exc:
            return ToolExecution(
                outcome=TargetedOutcome.FAILED,
                reason_code=TargetedGapReason.EXECUTION_ERROR,
                diagnostic=self._diagnostic(str(exc)),
            )

    def _run(
        self,
        argv: list[str],
        report_mode: ReportMode,
        report_path: Path,
        deadline: float,
        deadline_scope: DeadlineScope,
        cancel_event: threading.Event | None,
    ) -> ToolExecution:
        pre_spawn = self._pre_spawn_status(cancel_event, deadline, deadline_scope)
        if pre_spawn is not None:
            return pre_spawn
        pass_fds = (
            self._scan_lease.pass_fds
            if os.name == "posix" and self._scan_lease is not None
            else ()
        )
        popen_options = {"pass_fds": pass_fds} if pass_fds else {}
        try:
            process = subprocess.Popen(
                argv,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=False,
                start_new_session=True,
                env={
                    **os.environ,
                    "XDG_CONFIG_HOME": str(report_path.parent / "config"),
                },
                preexec_fn=(
                    self._set_report_size_limit if report_mode == "file" else None
                ),
                **popen_options,
            )
        except FileNotFoundError:
            return ToolExecution(
                outcome=TargetedOutcome.SKIPPED,
                reason_code=TargetedGapReason.TOOL_UNAVAILABLE,
                diagnostic="Targeted executable is unavailable.",
            )
        except (OSError, subprocess.SubprocessError) as exc:
            return ToolExecution(
                outcome=TargetedOutcome.FAILED,
                reason_code=TargetedGapReason.SPAWN_ERROR,
                diagnostic=self._diagnostic(str(exc)),
            )

        with self._lock:
            if self._cancelled:
                self._terminate_process_group(process)
                return self._cancelled_execution()
            self._active_process = process

        stdout = _CappedBuffer(TARGETED_STDIO_LIMIT_BYTES)
        stderr = _CappedBuffer(TARGETED_STDIO_LIMIT_BYTES)
        streamed_report = None
        try:
            if report_mode == "stdout":
                streamed_report = _CappedReport(
                    report_path, TARGETED_REPORT_LIMIT_BYTES
                )
        except OSError as exc:
            self._terminate_process_group(process)
            try:
                process.communicate(timeout=1)
            except (OSError, subprocess.TimeoutExpired):
                pass
            with self._lock:
                if self._active_process is process:
                    self._active_process = None
            return ToolExecution(
                outcome=TargetedOutcome.FAILED,
                exit_code=process.returncode,
                reason_code=TargetedGapReason.EXECUTION_ERROR,
                diagnostic=self._diagnostic(str(exc)),
            )
        report_limit_hit = threading.Event()
        readers = [
            threading.Thread(
                target=self._drain,
                args=(process.stderr, stderr, None),
                daemon=True,
            ),
            threading.Thread(
                target=self._drain,
                args=(
                    process.stdout,
                    streamed_report if streamed_report is not None else stdout,
                    report_limit_hit if streamed_report is not None else None,
                ),
                daemon=True,
            ),
        ]
        for reader in readers:
            reader.start()

        outcome: TargetedOutcome | None = None
        reason: TargetedGapReason | None = None
        completed_at: float | None = None
        try:
            while process.poll() is None:
                if self._is_cancelled(cancel_event):
                    self._terminate_process_group(process)
                    outcome, reason = (
                        TargetedOutcome.SKIPPED,
                        TargetedGapReason.SCAN_CANCELLED,
                    )
                    break
                if perf_counter() >= deadline:
                    self._terminate_process_group(process)
                    outcome, reason = self._deadline_outcome(deadline_scope)
                    break
                if report_limit_hit.is_set() or self._report_limit_hit(report_path):
                    self._terminate_process_group(process)
                    outcome, reason = (
                        TargetedOutcome.FAILED,
                        TargetedGapReason.OUTPUT_LIMIT,
                    )
                    break
                threading.Event().wait(0.02)
            if process.poll() is None:
                process.wait(timeout=1)
            if process.poll() is not None and outcome is None:
                completed_at = perf_counter()
        finally:
            # The leader can exit while helper descendants remain in the session.
            self._terminate_process_group(process)
            for reader in readers:
                reader.join(timeout=1)
            if streamed_report is not None:
                streamed_report.close()
            with self._lock:
                if self._active_process is process:
                    self._active_process = None

        report_truncated = streamed_report.truncated if streamed_report else False
        if outcome is None and self._is_cancelled(cancel_event):
            outcome, reason = TargetedOutcome.SKIPPED, TargetedGapReason.STAGE_BUDGET
        if outcome is None and completed_at is not None and completed_at >= deadline:
            outcome, reason = self._deadline_outcome(deadline_scope)
        if report_mode == "file" and self._report_limit_hit(report_path):
            report_truncated = True
            if outcome is None:
                outcome, reason = TargetedOutcome.FAILED, TargetedGapReason.OUTPUT_LIMIT

        report = b""
        report_present = report_path.exists()
        try:
            # Always retain the bounded report bytes, including when another
            # lifecycle limit already classified the execution. Adapters own
            # report validity and need to distinguish absent from empty data.
            report, read_truncated = self._read_report(report_path)
            report_present = True
            report_truncated = report_truncated or read_truncated
        except FileNotFoundError:
            report_present = False
        except OSError as exc:
            outcome, reason = (
                TargetedOutcome.FAILED,
                TargetedGapReason.EXECUTION_ERROR,
            )
            stderr.append(str(exc).encode())

        if outcome is None and (
            report_truncated or stdout.truncated or stderr.truncated
        ):
            outcome, reason = TargetedOutcome.FAILED, TargetedGapReason.OUTPUT_LIMIT
        # Exit status is diagnostic only. A structured adapter decides if the
        # retained report is valid and what final unit outcome means.
        if outcome is None:
            outcome = TargetedOutcome.COMPLETED
        return ToolExecution(
            outcome=outcome,
            exit_code=process.returncode,
            reason_code=reason,
            diagnostic=self._diagnostic(bytes(stderr.data).decode(errors="replace")),
            report=report,
            report_present=report_present,
            stdout=bytes(stdout.data),
            stderr=bytes(stderr.data),
            stdout_truncated=stdout.truncated,
            stderr_truncated=stderr.truncated,
            report_truncated=report_truncated,
            cancelled=self._is_cancelled(cancel_event),
            deadline_scope=(
                deadline_scope if outcome == TargetedOutcome.TIMED_OUT else None
            ),
        )

    @staticmethod
    def _drain(
        pipe,
        buffer: _CappedBuffer | _CappedReport,
        limit_hit: threading.Event | None,
    ) -> None:
        try:
            while chunk := pipe.read(65_536):
                buffer.append(chunk)
                if getattr(buffer, "truncated", False) and limit_hit is not None:
                    limit_hit.set()
        finally:
            pipe.close()

    @staticmethod
    def _read_report(path: Path) -> tuple[bytes, bool]:
        with path.open("rb") as report_file:
            data = report_file.read(TARGETED_REPORT_LIMIT_BYTES + 1)
        return (
            data[:TARGETED_REPORT_LIMIT_BYTES],
            len(data) > TARGETED_REPORT_LIMIT_BYTES,
        )

    @staticmethod
    def _report_limit_hit(path: Path) -> bool:
        try:
            size = path.stat().st_size
        except FileNotFoundError:
            return False
        return size > TARGETED_REPORT_LIMIT_BYTES

    def _pre_spawn_status(
        self,
        cancel_event: threading.Event | None,
        deadline: float,
        deadline_scope: DeadlineScope,
    ) -> ToolExecution | None:
        if self._is_cancelled(cancel_event):
            return self._cancelled_execution()
        if perf_counter() >= deadline:
            outcome, reason = self._deadline_outcome(deadline_scope)
            return ToolExecution(
                outcome=outcome,
                reason_code=reason,
                diagnostic="Targeted tool deadline elapsed before spawn.",
                deadline_scope=(
                    deadline_scope if outcome == TargetedOutcome.TIMED_OUT else None
                ),
            )
        return None

    @staticmethod
    def _set_report_size_limit() -> None:
        if resource is None:
            return
        ceiling = TARGETED_REPORT_LIMIT_BYTES + 1
        resource.setrlimit(resource.RLIMIT_FSIZE, (ceiling, ceiling))

    @staticmethod
    def _report_argv(command: ToolCommand, report_path: Path) -> list[str] | None:
        argv = list(command.argv)
        if not argv or any(not isinstance(argument, str) for argument in argv):
            return None
        if command.report_mode == "stdout":
            return argv
        index = command.report_argument_index
        if index is None or index < 0 or index >= len(argv):
            return None
        argv[index] = str(report_path)
        return argv

    @staticmethod
    def _platform_supported() -> bool:
        return os.name == "posix" and sys.platform == "linux"

    def _is_cancelled(self, cancel_event: threading.Event | None) -> bool:
        return self._cancelled or (cancel_event is not None and cancel_event.is_set())

    @staticmethod
    def _diagnostic(value: str) -> str | None:
        compact = " ".join(value.split())[:TARGETED_DIAGNOSTIC_LIMIT_CHARS]
        return compact or None

    @staticmethod
    def _deadline_outcome(
        scope: DeadlineScope,
    ) -> tuple[TargetedOutcome, TargetedGapReason | None]:
        if scope == "stage":
            return TargetedOutcome.SKIPPED, TargetedGapReason.STAGE_BUDGET
        if scope == "overall":
            return TargetedOutcome.TIMED_OUT, None
        return TargetedOutcome.TIMED_OUT, TargetedGapReason.UNIT_TIMEOUT

    @staticmethod
    def _terminate_process_group(process: subprocess.Popen[bytes]) -> None:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            pass
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        try:
            process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()

    @staticmethod
    def _cancelled_execution() -> ToolExecution:
        return ToolExecution(
            outcome=TargetedOutcome.SKIPPED,
            reason_code=TargetedGapReason.SCAN_CANCELLED,
            diagnostic="Targeted execution cancelled.",
            cancelled=True,
        )
