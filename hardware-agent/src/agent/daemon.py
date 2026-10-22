from __future__ import annotations

import asyncio
import json
import logging
import os
import socket
import subprocess
import sys
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal
from uuid import UUID

from agent.headless import HeadlessScanResult, InvalidScanInput, run_headless_scan
from agent.scanner.finalization import ScanFinalizationCheckpoint, ScanFinalizationStore
from agent.scanner.live_progress import LiveProgressReporter, LiveProgressSnapshot
from agent.scanner.scan_lock import (
    ScanLease,
    UpgradeInProgressError,
    acquire_scan_lease,
)
from agent.transport.command_channel import (
    AgentCommand,
    AgentProgress,
    AgentProgressSnapshot,
    AgentStatus,
    AgentUpdate,
    CommandChannelClient,
    ScanStatusAck,
)
from agent.transport.ingest import (
    IngestConfigError,
    ScanIngestClient,
    SubmissionResult,
    load_ingest_config,
)

LOGGER = logging.getLogger(__name__)
UPDATER_SOCKET = Path("/run/dmitri-agent-updater/control.sock")
UPDATER_MESSAGE_LIMIT = 4096
UPDATER_UPDATE_TIMEOUT_SECONDS = 20 * 60 + 30
INGEST_RETRY_INITIAL_SECONDS = 1.0
INGEST_RETRY_MAX_SECONDS = 30.0

CommandStatus = Literal["running", "uploading", "done", "failed", "cancelled"]


@dataclass(slots=True)
class CommandRecord:
    status: CommandStatus
    error_code: str | None = None
    pending: bool = True


def _request_updater(
    command: str,
    *,
    socket_path: Path = UPDATER_SOCKET,
    **fields: object,
) -> dict[str, object]:
    allowed = {
        "inspect": set(),
        "accept_update": {
            "update_id",
            "session_id",
            "release_id",
            "target_package_version",
            "sha256",
            "expires_at",
        },
    }
    if command not in allowed or set(fields) != allowed[command]:
        raise ValueError("unsupported updater request")
    payload = (
        json.dumps({"command": command, **fields}, separators=(",", ":")).encode()
        + b"\n"
    )
    if len(payload) > UPDATER_MESSAGE_LIMIT:
        raise ValueError("updater request too large")
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
        connection.settimeout(
            UPDATER_UPDATE_TIMEOUT_SECONDS if command == "accept_update" else 3
        )
        connection.connect(str(socket_path))
        connection.sendall(payload)
        response = bytearray()
        while len(response) <= UPDATER_MESSAGE_LIMIT:
            chunk = connection.recv(UPDATER_MESSAGE_LIMIT + 1 - len(response))
            if not chunk:
                break
            response.extend(chunk)
    if len(response) > UPDATER_MESSAGE_LIMIT:
        raise OSError("invalid updater response")
    try:
        result = json.loads(response)
    except (ValueError, TypeError) as exc:
        raise OSError("invalid updater response") from exc
    if not isinstance(result, dict):
        raise OSError("invalid updater response")
    return result


class _ScanStop:
    """Stops one command's scan from the event loop, before or after it binds.

    Park (DMI-178) and an operator cancel are separate flags: a parked Pi stays
    silent, a cancelled scan still uploads its partial result. A cancel that
    lands after the runner finished is ignored, so the command ends `done`.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._cancel: Callable[[], None] | None = None
        self._finished = False
        self.cancelled = False
        self.parked = False

    def bind(self, cancel: Callable[[], None]) -> None:
        with self._lock:
            if self._finished:
                return
            self._cancel = cancel
            requested = self.cancelled or self.parked
        if requested:
            cancel()

    def finish(self) -> None:
        with self._lock:
            self._finished = True
            self._cancel = None

    def request_cancel(self) -> None:
        with self._lock:
            if self._finished:
                return
            self.cancelled = True
            cancel = self._cancel
        if cancel is not None:
            cancel()

    def request_park(self) -> None:
        with self._lock:
            self.parked = True
            cancel = self._cancel
        if cancel is not None:
            cancel()


def _scan_outcome(
    result: HeadlessScanResult, *, cancelled: bool
) -> tuple[CommandStatus, str | None]:
    """The status a finished scan ends with. `done` and `cancelled` upload first.

    A stopped scan uploads whatever payload it has, even when the local copy
    failed to write: ingest needs only the payload (spec 049, decision 2).
    """
    if cancelled:
        return "cancelled", None
    if result.payload is None:
        return "failed", "scan_failed"
    if result.result_path is None:
        return "failed", "result_unavailable"
    if result.outcome == "fatal":
        return "failed", "scan_failed"
    return "done", None


class AgentDaemon:
    def __init__(
        self,
        client: CommandChannelClient,
        ingest: ScanIngestClient,
        *,
        run_scan: Callable[..., HeadlessScanResult] = run_headless_scan,
        checkpoint_path: Path | None = None,
        update_state_provider: Callable[[], dict[str, object]] | None = None,
        updater_request: Callable[..., dict[str, object]] = _request_updater,
    ) -> None:
        self._client = client
        self._update_state_provider = update_state_provider
        self._updater_request = updater_request
        self._ingest = ingest
        self._run_scan = run_scan
        self._checkpoint = ScanFinalizationStore(
            checkpoint_path
            or Path(
                os.environ.get(
                    "DMITRI_SCAN_FINALIZATION_PATH",
                    "/var/lib/dmitri/scan-finalization.json",
                )
            )
        )
        self._durable_checkpoint = self._checkpoint.load()
        self.ledger: dict[UUID, CommandRecord] = {}
        self._active: UUID | None = None
        self._latest_progress: dict[UUID, AgentProgress] = {}
        self._progress_sequence: dict[UUID, int] = {}
        self._progress_revision: dict[UUID, int] = {}
        self._task: asyncio.Task[None] | None = None
        self._stop = _ScanStop()
        self._retry_stop = asyncio.Event()
        self._replay_retry_task: asyncio.Task[None] | None = None
        self._replay_lock = asyncio.Lock()
        self._upload_lock = asyncio.Lock()
        self._upload_worker: asyncio.Task[SubmissionResult] | None = None
        self._upload_worker_key: tuple[UUID, UUID] | None = None
        self._upgrade_hold: ScanLease | None = None
        set_provider = getattr(self._client, "set_update_state_provider", None)
        if set_provider is not None:
            set_provider(self._update_hello_state)

    async def run(self) -> None:
        try:
            await self._client.run(
                self.handle_command,
                self.replay_pending,
                self._cancel_active,
                on_cancel=self.handle_cancel,
                on_scan_status_ack=self.handle_scan_status_ack,
                on_agent_update=self.handle_agent_update,
            )
        finally:
            await self.close()

    async def close(self) -> None:
        await self._cancel_active()
        await self._client.close()
        self._ingest.close()

    async def _cancel_active(self) -> None:
        task, self._task = self._task, None
        retry_task, self._replay_retry_task = self._replay_retry_task, None
        try:
            self._retry_stop.set()
            if retry_task is not None and not retry_task.done():
                retry_task.cancel()
                await asyncio.gather(retry_task, return_exceptions=True)
            if task is not None and not task.done():
                self._stop.request_park()
                await task
            worker = self._upload_worker
            if worker is not None and not worker.done():
                await asyncio.shield(worker)
            checkpoint = self._durable_checkpoint
            if checkpoint is not None and checkpoint.phase == "running":
                checkpoint = ScanFinalizationCheckpoint(
                    command_id=checkpoint.command_id,
                    scan_id=checkpoint.scan_id,
                    session_id=checkpoint.session_id,
                    phase="awaiting_ack",
                    status="failed",
                    error_code="scan_failed",
                )
                self._durable_checkpoint = checkpoint
                self._checkpoint.save(checkpoint)
                self.ledger[checkpoint.command_id] = CommandRecord(
                    "failed", "scan_failed"
                )
        finally:
            if self._durable_checkpoint is None:
                self._release_hold()

    async def handle_command(self, command: AgentCommand) -> None:
        if self._client.parked_reason is not None:
            return
        record = self.ledger.get(command.command_id)
        if record is not None:
            await self._send(command.command_id, record)
            return
        checkpoint = self._durable_checkpoint
        if checkpoint is not None and checkpoint.command_id == command.command_id:
            if checkpoint.phase == "uploading" and checkpoint.result_path is not None:
                await self.replay_pending()
                return
            if checkpoint.status is not None:
                record = CommandRecord(checkpoint.status, checkpoint.error_code)
                self.ledger[command.command_id] = record
                await self._send(command.command_id, record)
            return
        if self._durable_checkpoint is not None:
            await self._update(command.command_id, "failed", "device_busy")
            return
        if getattr(self._client, "supports_scan_finalization", False):
            session_id = getattr(self._client, "session_id", None)
            if session_id is None:
                await self._update(command.command_id, "failed", "device_busy")
                return
        if self._active is not None:
            await self._update(command.command_id, "failed", "device_busy")
            return
        try:
            lock = acquire_scan_lease()
        except UpgradeInProgressError:
            await self._update(command.command_id, "failed", "device_busy")
            return
        except OSError:
            LOGGER.exception("Cannot acquire appliance update lock")
            await self._update(command.command_id, "failed", "scan_failed")
            return
        self._upgrade_hold = lock
        self._active = command.command_id
        self._stop = _ScanStop()
        self._retry_stop = asyncio.Event()
        try:
            if getattr(self._client, "supports_scan_finalization", False):
                self._durable_checkpoint = ScanFinalizationCheckpoint(
                    command_id=command.command_id,
                    scan_id=command.scan_id,
                    session_id=self._client.session_id,
                    phase="running",
                )
                try:
                    self._checkpoint.save(self._durable_checkpoint)
                except OSError:
                    self._durable_checkpoint = None
                    self._release_hold()
                    LOGGER.exception("Cannot persist remote scan checkpoint")
                    return
            await self._update(command.command_id, "running")
            self._task = asyncio.create_task(self._execute(command))
        except BaseException:
            self._release_hold()
            raise

    async def handle_cancel(self, command_id: UUID) -> None:
        record = self.ledger.get(command_id)
        if record is None or record.status == "uploading":
            return
        if command_id == self._active and record.status == "running":
            self._stop.request_cancel()
            return
        await self._send(command_id, record)

    async def handle_agent_update(self, frame: AgentUpdate) -> None:
        if (
            getattr(self._client, "parked_reason", None) is not None
            or not getattr(self._client, "supports_agent_updates", False)
            or frame.session_id != getattr(self._client, "session_id", None)
            or frame.expires_at <= datetime.now(UTC)
        ):
            return
        try:
            result = await asyncio.to_thread(
                self._updater_request,
                "accept_update",
                update_id=str(frame.update_id),
                session_id=str(frame.session_id),
                release_id=str(frame.release_id),
                target_package_version=frame.target_package_version,
                sha256=frame.sha256,
                expires_at=frame.expires_at.isoformat(),
            )
        except (OSError, ValueError, TypeError):
            LOGGER.exception("Local updater did not accept the update request")
            return
        if result.get("ok") is not True:
            LOGGER.warning(
                "Local updater refused update request: %s",
                result.get("error", "unknown"),
            )

    async def _update_hello_state(self) -> dict[str, object] | None:
        if self._update_state_provider is not None:
            state = await asyncio.to_thread(self._update_state_provider)
        else:
            state = await asyncio.to_thread(self._inspect_update_runtime)
        if not isinstance(state, dict):
            return None
        state = dict(state)
        if self._durable_checkpoint is not None:
            state["scan_checkpoint_pending"] = True
        return state

    def _inspect_update_runtime(self) -> dict[str, object] | None:
        try:
            from agent.transport.readiness import readiness_handshake
            from agent.version import installed_version

            inspection = self._updater_request("inspect")
            if inspection.get("ok") is not True:
                return None
            updater_version = inspection.get("updater_version")
            ready = (
                inspection.get("agent_update_ready") is True
                and inspection.get("blocked") is not True
                and type(updater_version) is int
                and updater_version == 1
            )
            evidence = readiness_handshake(installed_version())
            package_version = evidence.get("package_version")
            if not isinstance(package_version, str) or not package_version:
                return None
            context = inspection.get("update_context")
            safe_context = None
            if isinstance(context, dict):
                update_id = context.get("update_id", context.get("operation_id"))
                invocation_id = context.get("invocation_id")
                if (
                    not invocation_id
                    and context.get("phase") in {"verifying", "awaiting_confirmation"}
                    and context.get("target_package_version") == package_version
                ):
                    invocation_id = evidence.get("invocation_id")
                if isinstance(update_id, str) and isinstance(invocation_id, str):
                    try:
                        safe_context = {
                            "update_id": str(UUID(update_id)),
                            "invocation_id": str(UUID(invocation_id)),
                        }
                    except ValueError:
                        safe_context = None
            return {
                "ready": ready,
                "supervisor_ready": True,
                "updater_version": updater_version,
                "package_version": package_version,
                "os_suite": inspection.get("os_suite"),
                "architecture": inspection.get("architecture"),
                "scan_checkpoint_pending": inspection.get(
                    "scan_checkpoint_pending", False
                ),
                "update_context": safe_context,
            }
        except (
            OSError,
            ValueError,
            TypeError,
            RuntimeError,
            subprocess.SubprocessError,
        ):
            LOGGER.info("Remote update capability unavailable: local readiness failed")
            return None

    async def replay_pending(self) -> None:
        async with self._replay_lock:
            await self._replay_pending()

    async def _replay_pending(self) -> None:
        checkpoint = self._durable_checkpoint
        if checkpoint is not None and getattr(
            self._client, "supports_scan_finalization", False
        ):
            if self._upgrade_hold is None:
                try:
                    self._upgrade_hold = acquire_scan_lease(
                        allow_pending_finalization=True
                    )
                    self._active = checkpoint.command_id
                except (UpgradeInProgressError, OSError):
                    LOGGER.exception("Cannot restore scan finalization lease")
                    return
            if (
                checkpoint.phase in {"running", "uploading"}
                and self._active == checkpoint.command_id
                and self._task is not None
                and not self._task.done()
            ):
                record = self.ledger.get(checkpoint.command_id)
                if record is not None:
                    record.pending = True
            elif checkpoint.phase == "running" or (
                checkpoint.phase == "uploading" and checkpoint.result_path is None
            ):
                checkpoint = ScanFinalizationCheckpoint(
                    command_id=checkpoint.command_id,
                    scan_id=checkpoint.scan_id,
                    session_id=checkpoint.session_id,
                    phase="awaiting_ack",
                    status="failed",
                    error_code="scan_failed",
                )
                self._durable_checkpoint = checkpoint
                self._checkpoint.save(checkpoint)
                record = CommandRecord("failed", "scan_failed")
                self.ledger[checkpoint.command_id] = record
                await self._send(checkpoint.command_id, record)
            elif checkpoint.phase == "uploading" and checkpoint.result_path is not None:
                result_path = Path(checkpoint.result_path)
                try:
                    from agent.normalize.contracts import ScanPayload

                    payload = ScanPayload.model_validate_json(
                        result_path.read_text(encoding="utf-8")
                    )
                    submission = await self._submit_upload(
                        payload, checkpoint.command_id, checkpoint.scan_id
                    )
                    if self._client.parked_reason is not None:
                        return
                    if submission.outcome == "accepted":
                        checkpoint = ScanFinalizationCheckpoint(
                            command_id=checkpoint.command_id,
                            scan_id=checkpoint.scan_id,
                            session_id=checkpoint.session_id,
                            phase="awaiting_ack",
                            status=checkpoint.status or "done",
                            error_code=checkpoint.error_code,
                            result_path=checkpoint.result_path,
                        )
                    elif submission.outcome in {"unavailable", "protocol_error"}:
                        self._schedule_replay_retry()
                        return
                    else:
                        checkpoint = ScanFinalizationCheckpoint(
                            command_id=checkpoint.command_id,
                            scan_id=checkpoint.scan_id,
                            session_id=checkpoint.session_id,
                            phase="awaiting_ack",
                            status="failed",
                            error_code="ingest_failed",
                            result_path=checkpoint.result_path,
                        )
                    self._durable_checkpoint = checkpoint
                    self._checkpoint.save(checkpoint)
                    record = CommandRecord(checkpoint.status, checkpoint.error_code)
                    self.ledger[checkpoint.command_id] = record
                    await self._send(checkpoint.command_id, record)
                except (OSError, ValueError):
                    LOGGER.exception("Cannot replay saved scan result")
                    return
            elif checkpoint.status is not None:
                record = CommandRecord(checkpoint.status, checkpoint.error_code)
                self.ledger[checkpoint.command_id] = record
                await self._send(checkpoint.command_id, record)
        for command_id, record in list(self.ledger.items()):
            if record.pending:
                await self._send(command_id, record)
            progress = self._latest_progress.get(command_id)
            if progress is not None and record.status in {"running", "uploading"}:
                await self._send_progress(progress)

    async def _execute(self, command: AgentCommand) -> None:
        try:
            await self._run_command(command)
        except Exception:
            LOGGER.exception("command %s ended unexpectedly", command.command_id)
            await self._update(command.command_id, "failed", "scan_failed")

    def _schedule_replay_retry(self) -> None:
        if self._replay_retry_task is None or self._replay_retry_task.done():
            self._retry_stop.clear()
            self._replay_retry_task = asyncio.create_task(self._retry_replay_pending())

    async def _retry_replay_pending(self) -> None:
        delay = INGEST_RETRY_INITIAL_SECONDS
        try:
            while (
                self._durable_checkpoint is not None
                and self._durable_checkpoint.phase == "uploading"
                and self._client.parked_reason is None
            ):
                try:
                    await asyncio.wait_for(self._retry_stop.wait(), timeout=delay)
                    return
                except TimeoutError:
                    pass
                await self.replay_pending()
                delay = min(delay * 2, INGEST_RETRY_MAX_SECONDS)
        except asyncio.CancelledError:
            raise

    async def _run_command(self, command: AgentCommand) -> None:
        stop = self._stop
        lease = self._upgrade_hold
        loop = asyncio.get_running_loop()
        reporter = LiveProgressReporter(
            command.scan_mode,
            lambda snapshot: loop.call_soon_threadsafe(
                self._record_progress, command.command_id, command.scan_id, snapshot
            ),
        )

        def run_scan() -> HeadlessScanResult:
            try:
                return self._run_scan(
                    command.scan_mode,
                    command.subnet,
                    nspi_submode=(
                        command.nspi_options.submode
                        if command.nspi_options is not None
                        else None
                    ),
                    bind_cancel=stop.bind,
                    scan_lease=lease,
                    reporter=reporter,
                )
            finally:
                stop.finish()

        try:
            result = await asyncio.to_thread(run_scan)
        except InvalidScanInput:
            await self._update(command.command_id, "failed", "invalid_command")
            return
        if stop.parked:
            return
        status, error_code = _scan_outcome(result, cancelled=stop.cancelled)
        if status == "failed" or result.payload is None:
            await self._update(command.command_id, status, error_code)
            return
        final_progress = self._record_progress(
            command.command_id,
            command.scan_id,
            reporter.reconcile_payload(result.payload),
            schedule_send=False,
        )
        if final_progress is not None:
            await self._send_progress(final_progress)
        if self._durable_checkpoint is not None:
            self._durable_checkpoint = ScanFinalizationCheckpoint(
                command_id=command.command_id,
                scan_id=command.scan_id,
                session_id=self._durable_checkpoint.session_id,
                phase="uploading",
                status=status,
                error_code=error_code,
                result_path=(
                    str(Path(result.result_path).resolve())
                    if result.result_path
                    else None
                ),
            )
            self._checkpoint.save(self._durable_checkpoint)
        await self._update(command.command_id, "uploading")
        retry_delay = INGEST_RETRY_INITIAL_SECONDS
        while True:
            if stop.parked or self._retry_stop.is_set():
                return
            submission = await self._submit_upload(
                result.payload, command.command_id, command.scan_id
            )
            if (
                submission.outcome not in {"unavailable", "protocol_error"}
                or self._durable_checkpoint is None
                or stop.parked
            ):
                break
            LOGGER.warning(
                "scan ingest remains pending: outcome=%s; retrying in %.0f seconds",
                submission.outcome,
                retry_delay,
            )
            try:
                await asyncio.wait_for(self._retry_stop.wait(), timeout=retry_delay)
                return
            except TimeoutError:
                pass
            retry_delay = min(retry_delay * 2, INGEST_RETRY_MAX_SECONDS)
        # Park stays silent even after a cancel: an accepted upload already moved
        # the command to its terminal status on the backend.
        if stop.parked:
            return
        if (
            submission.outcome in {"unavailable", "protocol_error"}
            and self._durable_checkpoint is not None
        ):
            LOGGER.warning(
                "scan ingest remains pending: outcome=%s", submission.outcome
            )
            return
        if submission.outcome == "accepted":
            LOGGER.info(
                "scan upload accepted: command=%s scan=%s status=%s",
                command.command_id,
                command.scan_id,
                submission.status_code,
            )
            await self._update(command.command_id, status)
            return
        LOGGER.error(
            "scan upload failed: command=%s scan=%s outcome=%s status=%s attempts=%s",
            command.command_id,
            command.scan_id,
            submission.outcome,
            submission.status_code,
            submission.attempts,
        )
        await self._update(command.command_id, "failed", "ingest_failed")
        if submission.outcome == "forbidden":
            await self._client.park("upload_refused")

    async def _update(
        self, command_id: UUID, status: CommandStatus, error_code: str | None = None
    ) -> None:
        record = CommandRecord(status=status, error_code=error_code)
        if (
            self._durable_checkpoint is not None
            and command_id == self._durable_checkpoint.command_id
        ):
            phase = (
                "awaiting_ack"
                if status in {"done", "failed", "cancelled"}
                else ("uploading" if status == "uploading" else "running")
            )
            self._durable_checkpoint = ScanFinalizationCheckpoint(
                command_id=self._durable_checkpoint.command_id,
                scan_id=self._durable_checkpoint.scan_id,
                session_id=self._durable_checkpoint.session_id,
                phase=phase,
                status=(
                    status
                    if phase == "awaiting_ack"
                    else self._durable_checkpoint.status
                ),
                error_code=(
                    error_code
                    if phase == "awaiting_ack"
                    else self._durable_checkpoint.error_code
                ),
                result_path=self._durable_checkpoint.result_path,
            )
            self._checkpoint.save(self._durable_checkpoint)
        self.ledger[command_id] = record
        if status in {"done", "failed", "cancelled"}:
            self._latest_progress.pop(command_id, None)
            self._progress_sequence.pop(command_id, None)
            self._progress_revision.pop(command_id, None)
        await self._send(command_id, record)

    async def _send(self, command_id: UUID, record: CommandRecord) -> None:
        record.pending = not await self._client.send_status(
            AgentStatus(
                command_id=command_id,
                status=record.status,
                error_code=record.error_code,
            )
        )
        # Keep protection across a dropped connection until terminal replay.
        if (
            command_id == self._active
            and not record.pending
            and record.status in {"done", "failed", "cancelled"}
            and self._durable_checkpoint is None
        ):
            self._release_hold()

    async def handle_scan_status_ack(self, receipt: ScanStatusAck) -> None:
        checkpoint = self._durable_checkpoint
        if (
            checkpoint is None
            or receipt.session_id != getattr(self._client, "session_id", None)
            or receipt.command_id != checkpoint.command_id
            or checkpoint.status is None
            or checkpoint.phase != "awaiting_ack"
            or (
                self._upload_worker is not None
                and not self._upload_worker.done()
                and self._upload_worker_key
                == (checkpoint.command_id, checkpoint.scan_id)
            )
        ):
            return
        self._checkpoint.clear()
        self._durable_checkpoint = None
        record = self.ledger.get(receipt.command_id)
        if record is not None:
            record.pending = False
        self._release_hold()

    async def _submit_upload(
        self, payload: object, command_id: UUID, scan_id: UUID
    ) -> SubmissionResult:
        key = (command_id, scan_id)
        async with self._upload_lock:
            worker = self._upload_worker
            if worker is None or worker.done():
                worker = asyncio.create_task(
                    asyncio.to_thread(self._ingest.submit, payload, scan_id=scan_id)
                )
                self._upload_worker = worker
                self._upload_worker_key = key
            elif self._upload_worker_key != key:
                raise RuntimeError("another scan upload is still running")
        try:
            return await asyncio.shield(worker)
        finally:
            if worker.done() and self._upload_worker is worker:
                self._upload_worker = None
                self._upload_worker_key = None

    def _record_progress(
        self,
        command_id: UUID,
        scan_id: UUID,
        snapshot: LiveProgressSnapshot,
        *,
        schedule_send: bool = True,
    ) -> AgentProgress | None:
        record = self.ledger.get(command_id)
        if (
            record is None
            or record.status not in {"running", "uploading"}
            or snapshot.revision <= self._progress_revision.get(command_id, 0)
        ):
            return None
        sequence = self._progress_sequence.get(command_id, 0) + 1
        self._progress_sequence[command_id] = sequence
        self._progress_revision[command_id] = snapshot.revision
        frame = AgentProgress(
            command_id=command_id,
            scan_id=scan_id,
            sequence=sequence,
            progress=AgentProgressSnapshot(
                stage=snapshot.stage,
                percent=snapshot.percent,
                machines=snapshot.machines,
                open_ports=snapshot.open_ports,
                filtered_ports=snapshot.filtered_ports,
                industrial_services=snapshot.industrial_services,
                vulnerabilities=snapshot.vulnerabilities,
            ),
        )
        self._latest_progress[command_id] = frame
        if schedule_send:
            asyncio.create_task(self._send_progress(frame))
        return frame

    async def _send_progress(self, frame: AgentProgress) -> None:
        record = self.ledger.get(frame.command_id)
        if (
            record is not None
            and record.status in {"running", "uploading"}
            and self._client.parked_reason is None
        ):
            await self._client.send_progress(frame)

    def _release_hold(self) -> None:
        if self._upgrade_hold is not None:
            self._upgrade_hold.close()
            self._upgrade_hold = None
        self._active = None


def run_daemon() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stdout,
    )
    try:
        config = load_ingest_config()
    except IngestConfigError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(20) from exc
    from agent.transport.readiness import SOCKET_PATH, readiness_handshake
    from agent.version import installed_version

    if SOCKET_PATH.exists():
        try:
            readiness_handshake(installed_version())
        except OSError as exc:
            LOGGER.error("Local updater readiness check failed: %s", type(exc).__name__)
            raise SystemExit(20) from None
    daemon = AgentDaemon(CommandChannelClient(config), ScanIngestClient(config))
    asyncio.run(daemon.run())
