from __future__ import annotations

import asyncio
import logging
import sys
import threading
from collections.abc import Callable
from contextlib import ExitStack
from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from agent.headless import HeadlessScanResult, InvalidScanInput, run_headless_scan
from agent.scanner.scan_lock import UpgradeInProgressError, scan_lock
from agent.transport.command_channel import (
    AgentCommand,
    AgentStatus,
    CommandChannelClient,
)
from agent.transport.ingest import (
    IngestConfigError,
    ScanIngestClient,
    load_ingest_config,
)

LOGGER = logging.getLogger(__name__)

CommandStatus = Literal["running", "uploading", "done", "failed", "cancelled"]


@dataclass(slots=True)
class CommandRecord:
    status: CommandStatus
    error_code: str | None = None
    pending: bool = True


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


class AgentDaemon:
    def __init__(
        self,
        client: CommandChannelClient,
        ingest: ScanIngestClient,
        *,
        run_scan: Callable[..., HeadlessScanResult] = run_headless_scan,
    ) -> None:
        self._client = client
        self._ingest = ingest
        self._run_scan = run_scan
        self.ledger: dict[UUID, CommandRecord] = {}
        self._active: UUID | None = None
        self._task: asyncio.Task[None] | None = None
        self._stop = _ScanStop()
        self._upgrade_hold: ExitStack | None = None

    async def run(self) -> None:
        try:
            await self._client.run(
                self.handle_command,
                self.replay_pending,
                self._cancel_active,
                on_cancel=self.handle_cancel,
            )
        finally:
            await self.close()

    async def close(self) -> None:
        await self._cancel_active()
        await self._client.close()
        self._ingest.close()

    async def _cancel_active(self) -> None:
        task, self._task = self._task, None
        try:
            if task is not None and not task.done():
                self._stop.request_park()
                await task
        finally:
            self._release_hold()

    async def handle_command(self, command: AgentCommand) -> None:
        if self._client.parked_reason is not None:
            return
        record = self.ledger.get(command.command_id)
        if record is not None:
            await self._send(command.command_id, record)
            return
        if self._active is not None:
            await self._update(command.command_id, "failed", "device_busy")
            return
        lock = ExitStack()
        try:
            lock.enter_context(scan_lock())
        except UpgradeInProgressError:
            lock.close()
            await self._update(command.command_id, "failed", "device_busy")
            return
        except OSError:
            lock.close()
            LOGGER.exception("Cannot acquire appliance update lock")
            await self._update(command.command_id, "failed", "scan_failed")
            return
        self._upgrade_hold = lock
        self._active = command.command_id
        self._stop = _ScanStop()
        try:
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

    async def replay_pending(self) -> None:
        for command_id, record in list(self.ledger.items()):
            if record.pending:
                await self._send(command_id, record)

    async def _execute(self, command: AgentCommand) -> None:
        try:
            await self._run_command(command)
        except Exception:
            LOGGER.exception("command %s ended unexpectedly", command.command_id)
            await self._update(command.command_id, "failed", "scan_failed")

    async def _run_command(self, command: AgentCommand) -> None:
        stop = self._stop

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
        if result.payload is None:
            if stop.cancelled:
                await self._update(command.command_id, "cancelled")
            else:
                await self._update(command.command_id, "failed", "scan_failed")
            return
        # A stopped scan still uploads its partial payload when the local copy
        # failed to write: ingest needs only the payload (spec 049, decision 2).
        if not stop.cancelled:
            if result.result_path is None:
                await self._update(command.command_id, "failed", "result_unavailable")
                return
            if result.outcome == "fatal":
                await self._update(command.command_id, "failed", "scan_failed")
                return
        uploaded_status: CommandStatus = "cancelled" if stop.cancelled else "done"
        await self._update(command.command_id, "uploading")
        submission = await asyncio.to_thread(
            self._ingest.submit, result.payload, scan_id=command.scan_id
        )
        # Park stays silent even after a cancel: an accepted upload already moved
        # the command to its terminal status on the backend.
        if stop.parked:
            return
        if submission.outcome == "accepted":
            LOGGER.info(
                "scan upload accepted: command=%s scan=%s status=%s",
                command.command_id,
                command.scan_id,
                submission.status_code,
            )
            await self._update(command.command_id, uploaded_status)
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
        self.ledger[command_id] = record
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
        ):
            self._release_hold()

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
    daemon = AgentDaemon(CommandChannelClient(config), ScanIngestClient(config))
    asyncio.run(daemon.run())
