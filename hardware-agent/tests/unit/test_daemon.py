from __future__ import annotations

import asyncio
import logging
import subprocess
import sys
import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

import pytest
from agent.daemon import AgentDaemon
from agent.headless import HeadlessScanResult
from agent.scanner.finalization import ScanFinalizationCheckpoint
from agent.transport.command_channel import (
    AgentCancel,
    AgentCommand,
    AgentProgress,
    AgentStatus,
    AgentUpdate,
    NspiOptions,
    ScanStatusAck,
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
        self.leases: list[Any] = []

    def __call__(
        self,
        mode: str,
        subnet: str,
        *,
        reporter: Any = None,
        nspi_submode: str | None = None,
        bind_cancel: Any = None,
        scan_lease: Any = None,
    ) -> HeadlessScanResult:
        self.leases.append(scan_lease)
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
        self.supports_agent_updates = False
        self.session_id: UUID | None = None
        self.closed = False
        self.connected = True
        self.cancel_latencies: list[float] = []
        self._script = list(script or [])
        self.update_state_provider: Any = None

    def set_update_state_provider(self, provider: Any) -> None:
        self.update_state_provider = provider

    async def run(
        self,
        on_command: Any,
        on_connected: Any = None,
        on_parked: Any = None,
        *,
        on_cancel: Any = None,
        on_scan_status_ack: Any = None,
        on_agent_update: Any = None,
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


class TestRemoteUpdateDispatch:
    def test_local_updater_protocol_rejects_arbitrary_fields(self):
        from agent.daemon import _request_updater

        with pytest.raises(ValueError, match="unsupported updater request"):
            _request_updater("accept_update", shell="echo unsafe")
        with pytest.raises(ValueError, match="unsupported updater request"):
            _request_updater("inspect", update_id="unexpected")

    def test_hello_context_maps_local_operation_to_closed_wire_shape(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        update_id = "11111111-1111-4111-8111-111111111111"
        invocation_id = "22222222-2222-4222-8222-222222222222"
        daemon, _, _, _ = build()
        monkeypatch.setattr(
            "agent.transport.readiness.readiness_handshake",
            lambda version: {
                "ok": True,
                "app_version": version,
                "package_version": "1.2.3-1",
            },
        )
        monkeypatch.setattr(
            "agent.version.installed_version", lambda: "1.2.3"
        )
        daemon._updater_request = lambda command: {
            "ok": True,
            "agent_update_ready": True,
            "updater_version": 1,
            "os_suite": "stable",
            "architecture": "arm64",
            "update_context": {
                "operation_id": update_id,
                "invocation_id": invocation_id,
                "phase": "recovering",
                "target_package_version": "1.2.4-1",
            },
        }

        state = daemon._inspect_update_runtime()

        assert state["update_context"] == {
            "update_id": update_id,
            "invocation_id": invocation_id,
        }

    @pytest.mark.parametrize(
        ("observed_package", "expected_context"),
        [
            (
                "1.2.4-1",
                {
                    "update_id": "11111111-1111-4111-8111-111111111111",
                    "invocation_id": "22222222-2222-4222-8222-222222222222",
                },
            ),
            ("1.2.5-1", None),
        ],
    )
    def test_verifying_update_uses_live_readiness_invocation_only_for_matching_target(
        self, monkeypatch, observed_package, expected_context
    ):
        daemon, _, _, _ = build()
        monkeypatch.setattr(
            "agent.transport.readiness.readiness_handshake",
            lambda version: {
                "ok": True,
                "package_version": observed_package,
                "invocation_id": "22222222-2222-4222-8222-222222222222",
            },
        )
        monkeypatch.setattr("agent.version.installed_version", lambda: "1.2.4")
        daemon._updater_request = lambda command: {
            "ok": True,
            "agent_update_ready": True,
            "blocked": True,
            "updater_version": 1,
            "os_suite": "stable",
            "architecture": "arm64",
            "update_context": {
                "operation_id": "11111111-1111-4111-8111-111111111111",
                "phase": "verifying",
                "target_package_version": "1.2.4-1",
                "invocation_id": None,
            },
        }

        state = daemon._inspect_update_runtime()

        assert state["update_context"] == expected_context
        assert state["ready"] is False

    def test_readiness_subprocess_error_degrades_update_inspection(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        daemon, _, _, _ = build()
        monkeypatch.setattr(
            "agent.transport.readiness.readiness_handshake",
            lambda version: (_ for _ in ()).throw(
                subprocess.CalledProcessError(1, ["dpkg-query"])
            ),
        )
        monkeypatch.setattr("agent.version.installed_version", lambda: "1.2.4")
        daemon._updater_request = lambda command: {
            "ok": True,
            "agent_update_ready": True,
            "updater_version": 1,
        }

        assert daemon._inspect_update_runtime() is None

    @pytest.mark.asyncio
    async def test_update_handoff_is_session_bound_and_never_starts_a_scan(self):
        client = FakeClient()
        client.supports_agent_updates = True
        client.session_id = uuid4()
        calls: list[tuple[str, dict[str, object]]] = []

        def updater_request(command_name: str, **fields: object):
            calls.append((command_name, fields))
            return {"ok": True, "phase": "preparing"}

        scan = FakeScan()
        daemon = AgentDaemon(
            client,
            FakeIngest(),
            run_scan=scan,
            updater_request=updater_request,
            update_state_provider=lambda: {
                "ready": True,
                "updater_version": 1,
                "package_version": "1.0.0-1",
            },
        )
        future = datetime.now(UTC).replace(microsecond=0) + timedelta(minutes=2)
        frame = AgentUpdate(
            type="agent_update",
            update_id=uuid4(),
            session_id=client.session_id,
            release_id=uuid4(),
            target_package_version="1.2.3-1",
            sha256="a" * 64,
            expires_at=future,
        )

        await daemon.handle_agent_update(frame)
        await daemon.handle_agent_update(
            frame.model_copy(update={"session_id": uuid4()})
        )
        await daemon.handle_agent_update(
            frame.model_copy(
                update={
                    "expires_at": datetime.now(UTC) - timedelta(seconds=1)
                }
            )
        )

        assert len(calls) == 1
        assert calls[0][0] == "accept_update"
        assert calls[0][1]["session_id"] == str(client.session_id)
        assert scan.calls == []

    @pytest.mark.asyncio
    async def test_scan_checkpoint_is_reported_to_hello_capability_provider(
        self, tmp_path: Path
    ):
        client = FakeClient()
        store = tmp_path / "scan-finalization.json"
        store.write_text(
            '{"protocol":1,"command_id":"11111111-1111-4111-8111-111111111111",'
            '"scan_id":"22222222-2222-4222-8222-222222222222",'
            '"session_id":"33333333-3333-4333-8333-333333333333",'
            '"phase":"awaiting_ack","status":"done","error_code":null,'
            '"result_path":null}',
            encoding="utf-8",
        )
        AgentDaemon(
            client,
            FakeIngest(),
            checkpoint_path=store,
            update_state_provider=lambda: {"ready": True},
        )

        assert client.update_state_provider is not None
        state = await client.update_state_provider()
        assert state["scan_checkpoint_pending"] is True
        assert state["ready"] is True


class TestFrameOrder:
    @pytest.mark.asyncio
    @pytest.mark.skipif(sys.platform == "win32", reason="flock is POSIX")
    async def test_daemon_lease_is_borrowed_by_scan_and_held_through_upload_ack(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import fcntl

        from agent.scanner.scan_lock import scan_lock_path

        observed_during_upload: list[bool] = []
        original_submit = FakeIngest.submit

        def checked_submit(ingest, payload, *, scan_id):
            with scan_lock_path().open("r") as handle:
                try:
                    fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    observed_during_upload.append(True)
                else:
                    observed_during_upload.append(False)
            return original_submit(ingest, payload, scan_id=scan_id)

        monkeypatch.setattr(FakeIngest, "submit", checked_submit)
        daemon, _, scan, _ = build()
        await dispatch(daemon, command())

        assert len(scan.leases) == 1
        assert scan.leases[0] is not None
        assert observed_during_upload == [True]
        assert daemon._upgrade_hold is None
        with scan_lock_path().open("r") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)

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


class TestDurableFinalization:
    @pytest.mark.asyncio
    async def test_same_process_reconnect_replays_running_state_without_interruption(
        self, tmp_path: Path
    ) -> None:
        gate = threading.Event()
        scan = FakeScan(gate=gate)
        client = FakeClient()
        client.session_id = uuid4()
        client.supports_scan_finalization = True
        subject = command()
        path = tmp_path / "checkpoint.json"
        daemon = AgentDaemon(client, FakeIngest(), run_scan=scan, checkpoint_path=path)

        await daemon.handle_command(subject)
        await asyncio.to_thread(scan.started.wait, TIMEOUT)
        await daemon.replay_pending()

        assert daemon._checkpoint.load().phase == "running"
        assert len(scan.calls) == 1
        assert client.frames(subject) == [("running", None), ("running", None)]
        gate.set()
        await drain()

    @pytest.mark.asyncio
    async def test_same_process_reconnect_does_not_resubmit_live_upload(
        self, tmp_path: Path
    ) -> None:
        from agent.normalize.contracts import ScanPayload

        gate = threading.Event()
        client = FakeClient()
        client.session_id = uuid4()
        client.supports_scan_finalization = True
        artifact = tmp_path / "result.json"
        payload = ScanPayload(
            scan_id=uuid4(),
            timestamp=datetime.now(UTC),
            subnet="192.168.1.0/24",
            scan_mode="quick",
        )
        artifact.write_text(payload.model_dump_json(), encoding="utf-8")
        ingest = FakeIngest(gate=gate)
        subject = command()
        daemon = AgentDaemon(
            client,
            ingest,
            run_scan=FakeScan(scan_result(payload=payload, result_path=artifact)),
            checkpoint_path=tmp_path / "checkpoint.json",
        )

        await daemon.handle_command(subject)
        await asyncio.to_thread(ingest.started.wait, TIMEOUT)
        await daemon.replay_pending()

        assert len(ingest.calls) == 1
        assert daemon._checkpoint.load().phase == "uploading"
        assert daemon._upgrade_hold is not None
        assert daemon._task is not None and not daemon._task.done()

        gate.set()
        await drain()

        assert len(ingest.calls) == 1
        assert daemon._durable_checkpoint.phase == "awaiting_ack"
        assert daemon._upgrade_hold is not None
        await daemon.handle_scan_status_ack(
            ScanStatusAck(
                type="scan_status_ack",
                session_id=client.session_id,
                command_id=subject.command_id,
                status="done",
                has_results=True,
            )
        )
        assert daemon._checkpoint.load() is None
        assert daemon._upgrade_hold is None

    @pytest.mark.asyncio
    async def test_transient_ingest_keeps_artifact_checkpoint_for_replay(
        self, tmp_path: Path
    ) -> None:
        client = FakeClient()
        client.session_id = uuid4()
        client.supports_scan_finalization = True
        ingest = FakeIngest("unavailable")
        artifact = tmp_path / "result.json"
        artifact.write_text("{}", encoding="utf-8")
        scan = FakeScan(scan_result(result_path=artifact))
        path = tmp_path / "checkpoint.json"
        daemon = AgentDaemon(client, ingest, run_scan=scan, checkpoint_path=path)
        subject = command()

        await daemon.handle_command(subject)
        await asyncio.to_thread(ingest.started.wait, TIMEOUT)

        saved = daemon._checkpoint.load()
        assert saved is not None and saved.phase == "uploading"
        assert saved.result_path == str(artifact.resolve())
        assert artifact.exists()
        await daemon._cancel_active()

    @pytest.mark.asyncio
    async def test_transient_ingest_retries_while_connected_until_accepted(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import agent.daemon as daemon_module

        monkeypatch.setattr(daemon_module, "INGEST_RETRY_INITIAL_SECONDS", 0.001)
        client = FakeClient()
        client.session_id = uuid4()
        client.supports_scan_finalization = True
        ingest = FakeIngest("unavailable", "accepted")
        artifact = tmp_path / "result.json"
        artifact.write_text("{}", encoding="utf-8")
        daemon = AgentDaemon(
            client,
            ingest,
            run_scan=FakeScan(scan_result(result_path=artifact)),
            checkpoint_path=tmp_path / "checkpoint.json",
        )

        await daemon.handle_command(command())
        await drain()

        assert len(ingest.calls) == 2
        assert client.frames(command(daemon._durable_checkpoint.command_id)) == [
            ("running", None),
            ("uploading", None),
            ("done", None),
        ]
        assert daemon._durable_checkpoint.phase == "awaiting_ack"

    @pytest.mark.asyncio
    async def test_duplicate_uploading_checkpoint_replays_artifact_before_terminal(
        self, tmp_path: Path
    ) -> None:
        client = FakeClient()
        client.session_id = uuid4()
        client.supports_scan_finalization = True
        ingest = FakeIngest("unavailable")
        artifact = tmp_path / "result.json"
        from agent.normalize.contracts import ScanPayload

        payload = ScanPayload(
            scan_id=uuid4(),
            timestamp=datetime.now(UTC),
            subnet="192.168.1.0/24",
            scan_mode="quick",
        )
        artifact.write_text(payload.model_dump_json(), encoding="utf-8")
        checkpoint = ScanFinalizationCheckpoint(
            command_id=uuid4(),
            scan_id=payload.scan_id,
            session_id=uuid4(),
            phase="uploading",
            status="done",
            result_path=str(artifact),
        )
        from agent.scanner.finalization import ScanFinalizationStore

        store = ScanFinalizationStore(tmp_path / "checkpoint.json")
        store.save(checkpoint)
        daemon = AgentDaemon(
            client, ingest, checkpoint_path=tmp_path / "checkpoint.json"
        )

        await daemon.handle_command(command(checkpoint.command_id))

        assert len(ingest.calls) == 1
        assert client.frames(command(checkpoint.command_id)) == []
        assert store.load().phase == "uploading"

    @pytest.mark.asyncio
    async def test_restored_upload_retries_until_accepted_without_rescanning(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import agent.daemon as daemon_module
        from agent.normalize.contracts import ScanPayload
        from agent.scanner.finalization import ScanFinalizationStore

        monkeypatch.setattr(daemon_module, "INGEST_RETRY_INITIAL_SECONDS", 0.001)
        client = FakeClient()
        client.session_id = uuid4()
        client.supports_scan_finalization = True
        command_id, scan_id = uuid4(), uuid4()
        artifact = tmp_path / "saved-scan.json"
        payload = ScanPayload(
            scan_id=scan_id,
            timestamp=datetime.now(UTC),
            subnet="192.168.1.0/24",
            scan_mode="quick",
        )
        artifact.write_text(payload.model_dump_json(), encoding="utf-8")
        store_path = tmp_path / "checkpoint.json"
        ScanFinalizationStore(store_path).save(
            ScanFinalizationCheckpoint(
                command_id=command_id,
                scan_id=scan_id,
                session_id=uuid4(),
                phase="uploading",
                status="done",
                result_path=str(artifact),
            )
        )
        ingest = FakeIngest("unavailable", "accepted")
        scan = FakeScan()
        daemon = AgentDaemon(client, ingest, run_scan=scan, checkpoint_path=store_path)

        await daemon.replay_pending()
        await asyncio.wait_for(daemon._replay_retry_task, timeout=TIMEOUT)

        assert len(ingest.calls) == 2
        assert scan.calls == []
        assert daemon._durable_checkpoint.phase == "awaiting_ack"
        assert client.frames(command(command_id)) == [("done", None)]
        assert daemon._upgrade_hold is not None
        await daemon.handle_scan_status_ack(
            ScanStatusAck(
                type="scan_status_ack",
                session_id=client.session_id,
                command_id=command_id,
                status="done",
                has_results=True,
            )
        )
        assert daemon._upgrade_hold is None

    @pytest.mark.asyncio
    async def test_reconnect_during_restored_retry_shares_the_active_upload(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import agent.daemon as daemon_module
        from agent.normalize.contracts import ScanPayload
        from agent.scanner.finalization import ScanFinalizationStore

        monkeypatch.setattr(daemon_module, "INGEST_RETRY_INITIAL_SECONDS", 0.001)
        client = FakeClient()
        client.session_id = uuid4()
        client.supports_scan_finalization = True
        command_id, scan_id = uuid4(), uuid4()
        artifact = tmp_path / "saved-scan.json"
        payload = ScanPayload(
            scan_id=scan_id,
            timestamp=datetime.now(UTC),
            subnet="192.168.1.0/24",
            scan_mode="quick",
        )
        artifact.write_text(payload.model_dump_json(), encoding="utf-8")
        store_path = tmp_path / "checkpoint.json"
        ScanFinalizationStore(store_path).save(
            ScanFinalizationCheckpoint(
                command_id=command_id,
                scan_id=scan_id,
                session_id=uuid4(),
                phase="uploading",
                status="done",
                result_path=str(artifact),
            )
        )
        gate = threading.Event()

        class RetryGateIngest(FakeIngest):
            active = 0
            max_active = 0

            def submit(self, payload: Any, *, scan_id: UUID) -> SubmissionResult:
                self.calls.append((payload, scan_id))
                if len(self.calls) == 1:
                    return SubmissionResult("unavailable", scan_id, 1, None, "retry")
                self.active += 1
                self.max_active = max(self.max_active, self.active)
                self.started.set()
                try:
                    gate.wait(TIMEOUT)
                    return SubmissionResult("accepted", scan_id, 1, 202, "accepted")
                finally:
                    self.active -= 1

        ingest = RetryGateIngest()
        daemon = AgentDaemon(client, ingest, checkpoint_path=store_path)
        await daemon.replay_pending()
        assert await asyncio.to_thread(ingest.started.wait, TIMEOUT)

        reconnect_replay = asyncio.create_task(daemon.replay_pending())
        await asyncio.sleep(0.01)
        assert len(ingest.calls) == 2
        assert ingest.max_active == 1
        gate.set()
        await reconnect_replay
        await asyncio.wait_for(daemon._replay_retry_task, timeout=TIMEOUT)

        assert len(ingest.calls) == 2
        assert ingest.max_active == 1
        assert daemon._durable_checkpoint.phase == "awaiting_ack"

    @pytest.mark.asyncio
    async def test_park_waits_for_restored_upload_worker_and_keeps_checkpoint(
        self, tmp_path: Path
    ) -> None:
        from agent.normalize.contracts import ScanPayload
        from agent.scanner.finalization import ScanFinalizationStore

        client = FakeClient()
        client.session_id = uuid4()
        client.supports_scan_finalization = True
        command_id, scan_id = uuid4(), uuid4()
        artifact = tmp_path / "saved-scan.json"
        payload = ScanPayload(
            scan_id=scan_id,
            timestamp=datetime.now(UTC),
            subnet="192.168.1.0/24",
            scan_mode="quick",
        )
        artifact.write_text(payload.model_dump_json(), encoding="utf-8")
        store_path = tmp_path / "checkpoint.json"
        checkpoint = ScanFinalizationCheckpoint(
            command_id=command_id,
            scan_id=scan_id,
            session_id=uuid4(),
            phase="uploading",
            status="done",
            result_path=str(artifact),
        )
        store = ScanFinalizationStore(store_path)
        store.save(checkpoint)
        gate = threading.Event()
        ingest = FakeIngest(gate=gate)
        daemon = AgentDaemon(client, ingest, checkpoint_path=store_path)
        replay = asyncio.create_task(daemon.replay_pending())
        assert await asyncio.to_thread(ingest.started.wait, TIMEOUT)

        ackable = ScanFinalizationCheckpoint(
            command_id=command_id,
            scan_id=scan_id,
            session_id=checkpoint.session_id,
            phase="awaiting_ack",
            status="done",
            result_path=str(artifact),
        )
        daemon._durable_checkpoint = ackable
        store.save(ackable)

        park = asyncio.create_task(daemon._cancel_active())
        await asyncio.sleep(0.01)
        assert not park.done()
        assert daemon._upgrade_hold is not None
        assert ingest.calls == [(payload, scan_id)]
        assert store.load() == ackable
        await daemon.handle_scan_status_ack(
            ScanStatusAck(
                type="scan_status_ack",
                session_id=client.session_id,
                command_id=command_id,
                status="done",
                has_results=True,
            )
        )
        assert store.load() == ackable
        assert daemon._upgrade_hold is not None

        client.parked_reason = "revoked"
        gate.set()
        await park
        await replay
        assert store.load() == ackable
        assert daemon._durable_checkpoint == ackable
        assert daemon._upgrade_hold is not None
        assert len(ingest.calls) == 1

    @pytest.mark.asyncio
    async def test_checkpoint_write_failure_refuses_to_start_remote_scan(
        self, tmp_path: Path
    ) -> None:
        daemon, client, scan, _ = build()
        client.supports_scan_finalization = True
        client.session_id = uuid4()
        store_path = tmp_path / "scan-finalization.json"
        daemon = AgentDaemon(
            client, FakeIngest(), run_scan=scan, checkpoint_path=store_path
        )

        def fail_save(_checkpoint: ScanFinalizationCheckpoint) -> None:
            raise OSError("disk full")

        daemon._checkpoint.save = fail_save
        await daemon.handle_command(command())
        await drain()

        assert scan.calls == []
        assert not store_path.exists()

    @pytest.mark.asyncio
    async def test_closed_ingest_retains_artifact_and_lost_status_ack_replays(
        self, tmp_path: Path
    ) -> None:
        client = FakeClient()
        client.session_id = uuid4()
        client.supports_scan_finalization = True
        command_id, scan_id = uuid4(), uuid4()
        artifact = tmp_path / "saved-scan.json"
        from agent.normalize.contracts import ScanPayload
        from agent.scanner.finalization import ScanFinalizationStore

        payload = ScanPayload(
            scan_id=scan_id,
            timestamp=datetime.now(UTC),
            subnet="192.168.1.0/24",
            scan_mode="quick",
        )
        artifact.write_text(payload.model_dump_json(), encoding="utf-8")
        checkpoint = ScanFinalizationCheckpoint(
            command_id=command_id,
            scan_id=scan_id,
            session_id=uuid4(),
            phase="uploading",
            status="done",
            result_path=str(artifact),
        )
        store_path = tmp_path / "scan-finalization.json"
        store = ScanFinalizationStore(store_path)
        store.save(checkpoint)
        ingest = FakeIngest("forbidden")
        first = AgentDaemon(client, ingest, checkpoint_path=store_path)

        await first.replay_pending()

        assert len(ingest.calls) == 1
        assert artifact.exists()
        assert store.load().status == "failed"
        assert client.frames(command(command_id)) == [("failed", "ingest_failed")]
        first._release_hold()

        restarted_client = FakeClient()
        restarted_client.session_id = uuid4()
        restarted_client.supports_scan_finalization = True
        restarted_ingest = FakeIngest()
        restarted = AgentDaemon(
            restarted_client, restarted_ingest, checkpoint_path=store_path
        )
        await restarted.replay_pending()

        assert restarted_ingest.calls == []
        assert restarted_client.frames(command(command_id)) == [
            ("failed", "ingest_failed")
        ]
        assert artifact.exists()
        await restarted.handle_scan_status_ack(
            ScanStatusAck(
                type="scan_status_ack",
                session_id=restarted_client.session_id,
                command_id=command_id,
                status="failed",
                has_results=False,
            )
        )
        assert store.load() is None
        assert artifact.exists()

    @pytest.mark.asyncio
    async def test_legacy_connection_scans_without_creating_v1_checkpoint(
        self, tmp_path: Path
    ) -> None:
        client = FakeClient()
        scan = FakeScan()
        store_path = tmp_path / "scan-finalization.json"
        daemon = AgentDaemon(
            client, FakeIngest(), run_scan=scan, checkpoint_path=store_path
        )

        await daemon.handle_command(command())
        await drain()

        assert len(scan.calls) == 1
        assert not store_path.exists()

    @pytest.mark.asyncio
    async def test_restart_of_running_phase_reports_failure_without_rescanning(
        self, tmp_path: Path
    ) -> None:
        daemon, client, scan, _ = build()
        session_id = uuid4()
        client.session_id = session_id
        client.supports_scan_finalization = True
        checkpoint = ScanFinalizationCheckpoint(
            command_id=uuid4(), scan_id=uuid4(), session_id=uuid4(), phase="running"
        )
        store_path = tmp_path / "scan-finalization.json"
        from agent.scanner.finalization import ScanFinalizationStore

        store = ScanFinalizationStore(store_path)
        store.save(checkpoint)
        daemon = AgentDaemon(
            client, FakeIngest(), run_scan=scan, checkpoint_path=store_path
        )

        await daemon.replay_pending()

        assert scan.calls == []
        assert client.frames(command(checkpoint.command_id)) == [
            ("failed", "scan_failed")
        ]
        assert store.load().status == "failed"

        await daemon.handle_scan_status_ack(
            ScanStatusAck(
                type="scan_status_ack",
                session_id=session_id,
                command_id=checkpoint.command_id,
                status="failed",
                has_results=False,
            )
        )
        assert store.load() is None

    @pytest.mark.asyncio
    async def test_pending_v1_checkpoint_blocks_new_command_even_on_legacy_session(
        self, tmp_path: Path
    ) -> None:
        daemon, client, scan, _ = build()
        checkpoint = ScanFinalizationCheckpoint(
            command_id=uuid4(),
            scan_id=uuid4(),
            session_id=uuid4(),
            phase="awaiting_ack",
            status="done",
        )
        store_path = tmp_path / "scan-finalization.json"
        from agent.scanner.finalization import ScanFinalizationStore

        ScanFinalizationStore(store_path).save(checkpoint)
        daemon = AgentDaemon(
            client, FakeIngest(), run_scan=scan, checkpoint_path=store_path
        )

        await daemon.handle_command(command())

        assert scan.calls == []
        assert ScanFinalizationStore(store_path).load() == checkpoint

    @pytest.mark.asyncio
    async def test_only_matching_current_session_terminal_ack_clears_checkpoint(
        self, tmp_path: Path
    ) -> None:
        daemon, client, _, _ = build()
        session_id = uuid4()
        checkpoint = ScanFinalizationCheckpoint(
            command_id=uuid4(),
            scan_id=uuid4(),
            session_id=uuid4(),
            phase="awaiting_ack",
            status="done",
        )
        store_path = tmp_path / "scan-finalization.json"
        from agent.scanner.finalization import ScanFinalizationStore

        store = ScanFinalizationStore(store_path)
        store.save(checkpoint)
        daemon = AgentDaemon(client, FakeIngest(), checkpoint_path=store_path)
        client.session_id = session_id
        client.supports_scan_finalization = True

        await daemon.handle_scan_status_ack(
            ScanStatusAck(
                type="scan_status_ack",
                session_id=uuid4(),
                command_id=checkpoint.command_id,
                status="done",
                has_results=True,
            )
        )
        assert store.load() == checkpoint
        await daemon.handle_scan_status_ack(
            ScanStatusAck(
                type="scan_status_ack",
                session_id=session_id,
                command_id=uuid4(),
                status="done",
                has_results=True,
            )
        )
        assert store.load() == checkpoint
        await daemon.handle_scan_status_ack(
            ScanStatusAck(
                type="scan_status_ack",
                session_id=session_id,
                command_id=checkpoint.command_id,
                status="failed",
                has_results=True,
            )
        )

        assert store.load() is None


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
    async def test_park_cancels_the_active_scan_before_upload(
        self, tmp_path: Path
    ) -> None:
        gate = threading.Event()
        scan = FakeScan(gate=gate)
        subject = command()

        async def wait_until_started() -> None:
            await asyncio.to_thread(scan.started.wait, TIMEOUT)

        _, client, _, ingest = build(
            scan=scan, script=["connect", subject, wait_until_started, "park"]
        )
        client.session_id = uuid4()
        client.supports_scan_finalization = True
        daemon = AgentDaemon(
            client,
            ingest,
            run_scan=scan,
            checkpoint_path=tmp_path / "checkpoint.json",
        )

        try:
            await daemon.run()
        finally:
            gate.set()

        assert client.parked_reason == "revoked"
        assert scan.cancelled.is_set()
        assert daemon._active == subject.command_id
        assert client.frames(subject) == [("running", None)]
        checkpoint = daemon._checkpoint.load()
        assert checkpoint.phase == "awaiting_ack"
        assert checkpoint.status == "failed"
        assert checkpoint.error_code == "scan_failed"
        await daemon.replay_pending()
        assert len(scan.calls) == 1
        assert ingest.calls == []

    @pytest.mark.asyncio
    async def test_parked_running_checkpoint_reconnects_as_failed_until_ack(
        self, tmp_path: Path
    ) -> None:
        gate = threading.Event()
        scan = FakeScan(gate=gate)
        subject = command()
        client = FakeClient(["connect", subject, "park"])
        client.session_id = uuid4()
        client.supports_scan_finalization = True
        daemon = AgentDaemon(
            client,
            FakeIngest(),
            run_scan=scan,
            checkpoint_path=tmp_path / "checkpoint.json",
        )
        await daemon.run()

        checkpoint = daemon._checkpoint.load()
        assert checkpoint.phase == "awaiting_ack"
        assert (checkpoint.status, checkpoint.error_code) == ("failed", "scan_failed")
        assert scan.cancelled.is_set()
        assert len(scan.calls) == 1

        client.parked_reason = None
        client.connected = True
        await daemon.replay_pending()
        await daemon.replay_pending()

        assert client.frames(subject) == [
            ("running", None),
            ("failed", "scan_failed"),
            ("failed", "scan_failed"),
        ]
        assert len(scan.calls) == 1
        assert daemon._durable_checkpoint == checkpoint
        assert daemon._upgrade_hold is not None

        await daemon.handle_scan_status_ack(
            ScanStatusAck(
                type="scan_status_ack",
                session_id=client.session_id,
                command_id=subject.command_id,
                status="failed",
                has_results=False,
            )
        )
        assert daemon._checkpoint.load() is None
        assert daemon._durable_checkpoint is None
        assert daemon._upgrade_hold is None

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

    @pytest.mark.asyncio
    async def test_park_during_live_upload_backoff_stops_before_retry(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import agent.daemon as daemon_module

        monkeypatch.setattr(daemon_module, "INGEST_RETRY_INITIAL_SECONDS", 30.0)
        subject = command()
        client = FakeClient(["connect", subject])
        client.session_id = uuid4()
        client.supports_scan_finalization = True
        ingest = FakeIngest("unavailable")
        daemon = AgentDaemon(
            client,
            ingest,
            run_scan=FakeScan(),
            checkpoint_path=tmp_path / "checkpoint.json",
        )

        await daemon.handle_command(subject)
        await asyncio.to_thread(ingest.started.wait, TIMEOUT)
        while len(ingest.calls) == 0:
            await asyncio.sleep(0)
        await asyncio.sleep(0.02)
        assert daemon._task is not None
        assert not daemon._task.done()

        client.parked_reason = "revoked"
        await daemon._cancel_active()

        assert len(ingest.calls) == 1
        assert daemon._task is None
        assert client.frames(subject) == [("running", None), ("uploading", None)]
        checkpoint = daemon._checkpoint.load()
        assert checkpoint is not None and checkpoint.phase == "uploading"
        assert daemon._durable_checkpoint == checkpoint


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
