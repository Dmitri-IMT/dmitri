from __future__ import annotations

import asyncio
import logging
import sys
import threading
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

import pytest
from agent.daemon import AgentDaemon
from agent.headless import HeadlessScanResult
from agent.transport.command_channel import (
    AgentCancel,
    AgentCommand,
    AgentProgress,
    AgentStatus,
    NspiOptions,
)
from agent.transport.ingest import SubmissionResult

TIMEOUT = 5.0
PAYLOAD = SimpleNamespace(metadata={}, hosts=[], findings=[])
RESULT_PATH = Path("results/scan.json")
NON_ACCEPTED = [
    "unauthorized",
    "invalid",
    "rejected",
    "unavailable",
    "protocol_error",
]


def command(command_id: UUID | None = None) -> AgentCommand:
    return AgentCommand(
        type="command",
        command_id=command_id or uuid4(),
        scan_id=uuid4(),
        scan_mode="quick",
        subnet="192.168.1.0/24",
    )


def scan_result(
    outcome: str = "completed",
    payload: Any = PAYLOAD,
    result_path: Path | None = RESULT_PATH,
) -> HeadlessScanResult:
    return HeadlessScanResult(
        outcome=outcome, payload=payload, result_path=result_path, error=None
    )


class FakeScan:
    def __init__(self, *results: Any, gate: threading.Event | None = None) -> None:
        self.calls: list[tuple[str, str, str | None]] = []
        self.threads: list[int] = []
        self.started = threading.Event()
        self.cancelled = threading.Event()
        self._results = list(results) or [scan_result()]
        self._gate = gate

    def __call__(
        self,
        mode: str,
        subnet: str,
        *,
        reporter: Any = None,
        nspi_submode: str | None = None,
        bind_cancel: Any = None,
    ) -> HeadlessScanResult:
        self.calls.append((mode, subnet, nspi_submode))
        self.threads.append(threading.get_ident())
        if bind_cancel is not None:
            bind_cancel(self._cancel)
        if reporter is not None:
            from agent.scanner.progress import ScanEvent

            reporter.emit(ScanEvent(kind="discovery_started"))
            reporter.emit(ScanEvent(kind="hosts_found", hosts_total=2))
        self.started.set()
        if self._gate is not None:
            self._gate.wait(TIMEOUT)
        result = self._results.pop(0) if len(self._results) > 1 else self._results[0]
        if isinstance(result, BaseException):
            raise result
        return result

    def _cancel(self) -> None:
        self.cancelled.set()
        if self._gate is not None:
            self._gate.set()


class FakeIngest:
    def __init__(
        self,
        *outcomes: str,
        gate: threading.Event | None = None,
        message: str | None = None,
        status_code: int | None = 202,
    ) -> None:
        self.calls: list[tuple[Any, UUID]] = []
        self.threads: list[int] = []
        self.started = threading.Event()
        self.closed = False
        self._outcomes = list(outcomes) or ["accepted"]
        self._gate = gate
        self._message = message
        self._status_code = status_code

    def submit(self, payload: Any, *, scan_id: UUID) -> SubmissionResult:
        self.calls.append((payload, scan_id))
        self.threads.append(threading.get_ident())
        self.started.set()
        if self._gate is not None:
            self._gate.wait(TIMEOUT)
        outcome = (
            self._outcomes.pop(0) if len(self._outcomes) > 1 else self._outcomes[0]
        )
        return SubmissionResult(
            outcome=outcome,
            scan_id=scan_id,
            attempts=1,
            status_code=self._status_code,
            message=self._message or f"ingest said {outcome}",
        )

    def close(self) -> None:
        self.closed = True


class FakeClient:
    def __init__(self, script: list[Any] | None = None) -> None:
        self.sent: list[AgentStatus] = []
        self.delivered: list[AgentStatus] = []
        self.sent_progress: list[AgentProgress] = []
        self.delivered_progress: list[AgentProgress] = []
        self.order: list[tuple[str, Any]] = []
        self.parked_reason: str | None = None
        self.closed = False
        self.connected = True
        self.cancel_latencies: list[float] = []
        self._script = list(script or [])

    async def run(
        self,
        on_command: Any,
        on_connected: Any = None,
        on_parked: Any = None,
        *,
        on_cancel: Any = None,
    ) -> None:
        for step in self._script:
            if self.parked_reason is not None:
                return
            if step == "connect":
                self.connected = True
                if on_connected is not None:
                    await on_connected()
            elif step == "drop":
                self.connected = False
            elif step == "park":
                self.parked_reason = "revoked"
                self.connected = False
                if on_parked is not None:
                    await on_parked()
            elif isinstance(step, AgentCancel):
                if on_cancel is not None:
                    started_at = asyncio.get_running_loop().time()
                    await on_cancel(step.command_id)
                    self.cancel_latencies.append(
                        asyncio.get_running_loop().time() - started_at
                    )
            elif callable(step):
                await step()
            else:
                await on_command(step)

    async def send_status(self, status: AgentStatus) -> bool:
        self.sent.append(status)
        self.order.append(("status", status))
        if not self.connected:
            return False
        self.delivered.append(status)
        return True

    async def send_progress(self, progress: AgentProgress) -> bool:
        self.sent_progress.append(progress)
        self.order.append(("progress", progress))
        if not self.connected:
            return False
        self.delivered_progress.append(progress)
        return True

    async def park(self, reason: str) -> None:
        if self.parked_reason is None:
            self.parked_reason = reason
        self.connected = False

    async def close(self) -> None:
        self.closed = True
        self.connected = False

    def frames(self, subject: AgentCommand) -> list[tuple[str, str | None]]:
        return [
            (status.status, status.error_code)
            for status in self.sent
            if status.command_id == subject.command_id
        ]


def build(
    scan: FakeScan | None = None,
    ingest: FakeIngest | None = None,
    script: list[Any] | None = None,
) -> tuple[AgentDaemon, FakeClient, FakeScan, FakeIngest]:
    client = FakeClient(script)
    scan = scan or FakeScan()
    ingest = ingest or FakeIngest()
    return AgentDaemon(client, ingest, run_scan=scan), client, scan, ingest


async def drain() -> None:
    while True:
        pending = [
            task for task in asyncio.all_tasks() if task is not asyncio.current_task()
        ]
        if not pending:
            return
        await asyncio.wait(pending)


async def dispatch(daemon: AgentDaemon, subject: AgentCommand) -> None:
    await daemon.handle_command(subject)
    await drain()


class TestFrameOrder:
    @pytest.mark.asyncio
    async def test_progress_is_compact_and_final_snapshot_precedes_upload(self) -> None:
        daemon, client, _, _ = build()
        subject = command()

        await dispatch(daemon, subject)

        assert client.delivered_progress
        assert client.delivered_progress[-1].progress.stage == "uploading"
        assert client.delivered_progress[-1].progress.percent == 99
        assert client.delivered_progress[-1].progress.machines == 0
        assert client.delivered_progress[-1].progress.vulnerabilities == 0
        assert all(
            left.sequence < right.sequence
            for left, right in zip(
                client.delivered_progress, client.delivered_progress[1:]
            )
        )
        uploading_index = next(
            index
            for index, (kind, frame) in enumerate(client.order)
            if kind == "status" and frame.status == "uploading"
        )
        final_progress_index = next(
            index
            for index, (kind, frame) in enumerate(client.order)
            if kind == "progress" and frame.progress.stage == "uploading"
        )
        assert final_progress_index < uploading_index
        assert subject.command_id not in daemon._latest_progress

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("result", "expected", "uploads"),
        [
            (
                scan_result("completed"),
                [("running", None), ("uploading", None), ("done", None)],
                1,
            ),
            (
                scan_result("partial"),
                [("running", None), ("uploading", None), ("done", None)],
                1,
            ),
            (
                scan_result("fatal", payload=None, result_path=None),
                [("running", None), ("failed", "scan_failed")],
                0,
            ),
            (
                scan_result("completed", result_path=None),
                [("running", None), ("failed", "result_unavailable")],
                0,
            ),
        ],
    )
    async def test_scan_outcome_drives_frames(
        self, result: HeadlessScanResult, expected: list[Any], uploads: int
    ) -> None:
        daemon, client, _, ingest = build(scan=FakeScan(result))
        subject = command()

        await dispatch(daemon, subject)

        assert client.frames(subject) == expected
        assert len(ingest.calls) == uploads

    @pytest.mark.asyncio
    @pytest.mark.parametrize("outcome", NON_ACCEPTED)
    async def test_non_accepted_ingest_fails_after_uploading(
        self, outcome: str
    ) -> None:
        daemon, client, _, _ = build(ingest=FakeIngest(outcome))
        subject = command()

        await dispatch(daemon, subject)

        assert client.frames(subject) == [
            ("running", None),
            ("uploading", None),
            ("failed", "ingest_failed"),
        ]

    @pytest.mark.asyncio
    async def test_unexpected_scan_exception_ends_failed(self) -> None:
        daemon, client, _, ingest = build(scan=FakeScan(RuntimeError("boom")))
        subject = command()

        await dispatch(daemon, subject)

        assert client.frames(subject)[-1] == ("failed", "scan_failed")
        assert ingest.calls == []

    @pytest.mark.asyncio
    async def test_upload_carries_the_commands_scan_id(self) -> None:
        daemon, _, scan, ingest = build()
        subject = command()

        await dispatch(daemon, subject)

        assert scan.calls == [(subject.scan_mode, subject.subnet, None)]
        assert ingest.calls == [(PAYLOAD, subject.scan_id)]

    @pytest.mark.asyncio
    async def test_nspi_submode_is_forwarded_to_headless_runner(self) -> None:
        daemon, _, scan, _ = build()
        subject = AgentCommand(
            type="command",
            command_id=uuid4(),
            scan_id=uuid4(),
            scan_mode="nspi",
            subnet="192.168.1.0/24",
            nspi_options=NspiOptions(submode="read_only_mapping"),
        )

        await dispatch(daemon, subject)

        assert scan.calls == [("nspi", "192.168.1.0/24", "read_only_mapping")]

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("outcome", "status_code", "witness"),
        [
            ("accepted", 202, "scan upload accepted"),
            ("unavailable", None, "outcome=unavailable status=None"),
            ("forbidden", 403, "outcome=forbidden status=403"),
        ],
    )
    async def test_upload_logs_witness_without_credentials(
        self,
        outcome: str,
        status_code: int | None,
        witness: str,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        private_key = "ab" * 32
        bearer_token = "Bearer header.payload.signature"
        ingest = FakeIngest(
            outcome,
            message=f"upstream echoed {private_key} and {bearer_token}",
            status_code=status_code,
        )
        daemon, _, _, _ = build(ingest=ingest)

        with caplog.at_level(logging.INFO):
            await dispatch(daemon, command())

        messages = [record.getMessage() for record in caplog.records]
        assert any(witness in message for message in messages)
        assert all(private_key not in message for message in messages)
        assert all(bearer_token not in message for message in messages)


class TestResponsiveness:
    @pytest.mark.asyncio
    async def test_reconnect_replays_only_the_newest_active_snapshot(self) -> None:
        gate = threading.Event()
        daemon, client, scan, _ = build(scan=FakeScan(gate=gate))
        subject = command()

        await daemon.handle_command(subject)
        await asyncio.to_thread(scan.started.wait, TIMEOUT)
        for _ in range(20):
            await asyncio.sleep(0.01)
            if client.delivered_progress and (
                client.delivered_progress[-1]
                == daemon._latest_progress[subject.command_id]
            ):
                break
        latest = daemon._latest_progress[subject.command_id]

        client.connected = False
        client.sent_progress.clear()
        client.delivered_progress.clear()
        await daemon.replay_pending()
        assert client.sent_progress == [latest]
        assert client.delivered_progress == []

        client.connected = True
        client.sent_progress.clear()
        await daemon.replay_pending()
        assert client.sent_progress == [latest]
        assert client.delivered_progress[-1] == latest

        gate.set()
        await drain()

    @pytest.mark.asyncio
    async def test_receive_loop_answers_while_a_scan_blocks(self) -> None:
        gate = threading.Event()
        daemon, client, scan, ingest = build(scan=FakeScan(gate=gate))
        active, other = command(), command()

        await daemon.handle_command(active)
        await asyncio.to_thread(scan.started.wait, TIMEOUT)
        await daemon.handle_command(active)
        await daemon.handle_command(other)

        assert client.frames(active) == [("running", None), ("running", None)]
        assert client.frames(other) == [("failed", "device_busy")]

        gate.set()
        await drain()

        assert client.frames(active)[-1] == ("done", None)
        assert scan.calls == [(active.scan_mode, active.subnet, None)]
        assert len(ingest.calls) == 1


class TestRemoteCancel:
    @pytest.mark.asyncio
    async def test_running_cancel_uploads_partial_and_allows_next_command(self) -> None:
        gate = threading.Event()
        partial = SimpleNamespace(
            metadata={"terminated_by": "user_cancel"}, hosts=[], findings=[]
        )
        scan = FakeScan(
            scan_result("fatal", partial, result_path=None), scan_result(), gate=gate
        )
        active, later = command(), command()

        async def wait_until_started() -> None:
            await asyncio.to_thread(scan.started.wait, TIMEOUT)

        daemon, client, _, ingest = build(
            scan=scan,
            script=[
                "connect",
                active,
                wait_until_started,
                AgentCancel(type="cancel", command_id=active.command_id),
                drain,
                later,
                drain,
            ],
        )

        await daemon.run()

        assert scan.cancelled.is_set()
        assert client.cancel_latencies[0] <= 15
        assert client.frames(active) == [
            ("running", None),
            ("uploading", None),
            ("cancelled", None),
        ]
        assert ingest.calls == [(partial, active.scan_id), (PAYLOAD, later.scan_id)]
        assert client.frames(later) == [
            ("running", None),
            ("uploading", None),
            ("done", None),
        ]

    @pytest.mark.asyncio
    async def test_cancel_without_payload_reports_cancelled_without_upload(
        self,
    ) -> None:
        gate = threading.Event()
        daemon, client, scan, ingest = build(
            scan=FakeScan(
                scan_result("fatal", payload=None, result_path=None), gate=gate
            )
        )
        subject = command()

        await daemon.handle_command(subject)
        await asyncio.to_thread(scan.started.wait, TIMEOUT)
        await asyncio.wait_for(daemon.handle_cancel(subject.command_id), timeout=15)
        await drain()

        assert scan.cancelled.is_set()
        assert client.frames(subject) == [("running", None), ("cancelled", None)]
        assert ingest.calls == []

    @pytest.mark.asyncio
    async def test_cancelled_partial_upload_failure_reports_ingest_failed(self) -> None:
        gate = threading.Event()
        partial = SimpleNamespace(
            metadata={"terminated_by": "user_cancel"}, hosts=[], findings=[]
        )
        daemon, client, scan, ingest = build(
            scan=FakeScan(scan_result("fatal", partial, result_path=None), gate=gate),
            ingest=FakeIngest("unavailable"),
        )
        subject = command()

        await daemon.handle_command(subject)
        await asyncio.to_thread(scan.started.wait, TIMEOUT)
        await daemon.handle_cancel(subject.command_id)
        await drain()

        assert scan.cancelled.is_set()
        assert ingest.calls == [(partial, subject.scan_id)]
        assert client.frames(subject) == [
            ("running", None),
            ("uploading", None),
            ("failed", "ingest_failed"),
        ]

    @pytest.mark.asyncio
    async def test_completed_scan_wins_cancel_race_and_reports_done(self) -> None:
        gate = threading.Event()
        daemon, client, scan, ingest = build(scan=FakeScan(gate=gate))
        subject = command()

        await daemon.handle_command(subject)
        await asyncio.to_thread(scan.started.wait, TIMEOUT)
        stop = daemon._stop
        original_finish = stop.finish
        stop_finished = threading.Event()
        resume_scan = threading.Event()

        def finish() -> None:
            original_finish()
            stop_finished.set()
            resume_scan.wait(TIMEOUT)

        stop.finish = finish
        gate.set()
        assert await asyncio.to_thread(stop_finished.wait, TIMEOUT)
        await daemon.handle_cancel(subject.command_id)
        assert not scan.cancelled.is_set()
        resume_scan.set()
        await drain()

        assert ingest.calls == [(PAYLOAD, subject.scan_id)]
        assert client.frames(subject) == [
            ("running", None),
            ("uploading", None),
            ("done", None),
        ]

    @pytest.mark.asyncio
    async def test_unknown_and_finished_cancels_do_not_stop_a_scan(self) -> None:
        daemon, client, scan, _ = build()
        finished = command()

        await daemon.handle_cancel(uuid4())
        await dispatch(daemon, finished)
        await daemon.handle_cancel(finished.command_id)

        assert not scan.cancelled.is_set()
        assert client.frames(finished) == [
            ("running", None),
            ("uploading", None),
            ("done", None),
            ("done", None),
        ]

    @pytest.mark.asyncio
    async def test_uploading_cancel_does_not_stop_or_interrupt_upload(self) -> None:
        gate = threading.Event()
        daemon, client, scan, ingest = build(ingest=FakeIngest(gate=gate))
        subject = command()

        await daemon.handle_command(subject)
        await asyncio.to_thread(ingest.started.wait, TIMEOUT)
        await daemon.handle_cancel(subject.command_id)
        assert not scan.cancelled.is_set()
        gate.set()
        await drain()

        assert len(ingest.calls) == 1
        assert client.frames(subject) == [
            ("running", None),
            ("uploading", None),
            ("done", None),
        ]


class TestIdempotency:
    @pytest.mark.asyncio
    async def test_duplicate_during_running_starts_no_second_scan(self) -> None:
        gate = threading.Event()
        daemon, client, scan, ingest = build(scan=FakeScan(gate=gate))
        subject = command()

        await daemon.handle_command(subject)
        await asyncio.to_thread(scan.started.wait, TIMEOUT)
        await daemon.handle_command(subject)
        gate.set()
        await drain()

        assert len(scan.calls) == 1
        assert len(ingest.calls) == 1
        assert client.frames(subject) == [
            ("running", None),
            ("running", None),
            ("uploading", None),
            ("done", None),
        ]

    @pytest.mark.asyncio
    async def test_duplicate_during_uploading_starts_no_second_upload(self) -> None:
        gate = threading.Event()
        daemon, client, scan, ingest = build(ingest=FakeIngest(gate=gate))
        subject = command()

        await daemon.handle_command(subject)
        await asyncio.to_thread(ingest.started.wait, TIMEOUT)
        await daemon.handle_command(subject)
        gate.set()
        await drain()

        assert len(scan.calls) == 1
        assert len(ingest.calls) == 1
        assert client.frames(subject) == [
            ("running", None),
            ("uploading", None),
            ("uploading", None),
            ("done", None),
        ]

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("result", "terminal"),
        [
            (scan_result("completed"), ("done", None)),
            (
                scan_result("fatal", payload=None, result_path=None),
                ("failed", "scan_failed"),
            ),
            (
                scan_result("completed", result_path=None),
                ("failed", "result_unavailable"),
            ),
        ],
    )
    async def test_duplicate_after_terminal_replays_the_recorded_status(
        self, result: HeadlessScanResult, terminal: tuple[str, str | None]
    ) -> None:
        daemon, client, scan, ingest = build(scan=FakeScan(result))
        subject = command()

        await dispatch(daemon, subject)
        await dispatch(daemon, subject)

        assert len(scan.calls) == 1
        assert len(ingest.calls) <= 1
        assert client.frames(subject)[-2:] == [terminal, terminal]


class TestThreading:
    @pytest.mark.asyncio
    async def test_scan_and_upload_run_off_the_event_loop(self) -> None:
        daemon, _, scan, ingest = build()

        await dispatch(daemon, command())

        assert threading.get_ident() not in scan.threads
        assert threading.get_ident() not in ingest.threads


class TestReconnect:
    @pytest.mark.asyncio
    async def test_pending_status_replays_before_new_commands_are_acted_on(
        self,
    ) -> None:
        gate = threading.Event()
        scan = FakeScan(gate=gate)
        first, second = command(), command()

        async def release() -> None:
            gate.set()
            await drain()

        script = ["connect", first, "drop", release, "connect", first, second, drain]
        daemon, client, scan, ingest = build(scan=scan, script=script)

        await daemon.run()

        assert [(status.command_id, status.status) for status in client.delivered] == [
            (first.command_id, "running"),
            (first.command_id, "done"),
            (first.command_id, "done"),
            (second.command_id, "running"),
            (second.command_id, "uploading"),
            (second.command_id, "done"),
        ]
        assert len(scan.calls) == 2
        assert len(ingest.calls) == 2


class TestForbiddenIngest:
    @pytest.mark.asyncio
    async def test_forbidden_upload_parks_the_daemon(self) -> None:
        daemon, client, scan, _ = build(ingest=FakeIngest("forbidden"))
        subject, later = command(), command()

        await dispatch(daemon, subject)
        await dispatch(daemon, later)

        assert client.frames(subject) == [
            ("running", None),
            ("uploading", None),
            ("failed", "ingest_failed"),
        ]
        assert client.closed is False
        assert client.parked_reason == "upload_refused"
        assert client.frames(later) == []
        assert len(scan.calls) == 1

    @pytest.mark.asyncio
    async def test_park_cancels_the_active_scan_before_upload(self) -> None:
        gate = threading.Event()
        scan = FakeScan(gate=gate)
        subject = command()

        async def wait_until_started() -> None:
            await asyncio.to_thread(scan.started.wait, TIMEOUT)

        daemon, client, _, ingest = build(
            scan=scan, script=["connect", subject, wait_until_started, "park"]
        )

        try:
            await daemon.run()
        finally:
            gate.set()

        assert client.parked_reason == "revoked"
        assert scan.cancelled.is_set()
        assert daemon._active is None
        assert client.frames(subject) == [("running", None)]
        assert ingest.calls == []

    @pytest.mark.asyncio
    async def test_park_discards_an_in_flight_ingest_result(self) -> None:
        gate = threading.Event()
        ingest = FakeIngest(gate=gate)
        subject = command()

        async def wait_until_started() -> None:
            await asyncio.to_thread(ingest.started.wait, TIMEOUT)
            asyncio.get_running_loop().call_later(0.05, gate.set)

        daemon, client, _, _ = build(
            ingest=ingest,
            script=["connect", subject, wait_until_started, "park"],
        )

        try:
            await daemon.run()
        finally:
            gate.set()

        assert client.parked_reason == "revoked"
        assert daemon._active is None
        assert client.frames(subject) == [
            ("running", None),
            ("uploading", None),
        ]
        assert len(ingest.calls) == 1


class TestShutdown:
    @pytest.mark.asyncio
    async def test_idle_shutdown_closes_the_owned_clients(self) -> None:
        daemon, client, _, ingest = build(script=["connect"])

        await daemon.run()

        assert client.closed is True
        assert ingest.closed is True


@pytest.mark.skipif(sys.platform == "win32", reason="flock is POSIX")
@pytest.mark.asyncio
async def test_upgrade_refuses_command_before_running() -> None:
    import fcntl

    from agent.scanner.scan_lock import scan_lock_path

    daemon, client, scan, ingest = build()
    subject = command()
    with scan_lock_path().open("a") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        await dispatch(daemon, subject)
    assert client.frames(subject) == [("failed", "device_busy")]
    assert not scan.calls
    assert not ingest.calls


@pytest.mark.skipif(sys.platform == "win32", reason="flock is POSIX")
@pytest.mark.asyncio
async def test_pending_terminal_status_keeps_lock_until_replay() -> None:
    import fcntl

    from agent.scanner.scan_lock import scan_lock_path

    gate = threading.Event()
    daemon, client, _, ingest = build(ingest=FakeIngest(gate=gate))
    subject = command()
    await daemon.handle_command(subject)
    try:
        assert await asyncio.to_thread(ingest.started.wait, TIMEOUT)
        with scan_lock_path().open("a") as handle:
            with pytest.raises(BlockingIOError):
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        client.connected = False
    finally:
        gate.set()
        await drain()
    with scan_lock_path().open("a") as handle:
        with pytest.raises(BlockingIOError):
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert daemon._active == subject.command_id
        later = command()
        await daemon.handle_command(later)
        assert client.frames(later) == [("failed", "device_busy")]
        client.connected = True
        await daemon.replay_pending()
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    assert daemon._active is None
    assert client.frames(subject)[-1] == ("done", None)


@pytest.mark.skipif(sys.platform == "win32", reason="flock is POSIX")
@pytest.mark.asyncio
async def test_missing_lock_is_scan_failure_not_contention() -> None:
    from agent.scanner.scan_lock import scan_lock_path

    scan_lock_path().unlink()
    daemon, client, scan, _ = build()
    subject = command()
    await dispatch(daemon, subject)
    assert client.frames(subject) == [("failed", "scan_failed")]
    assert not scan.calls
