from __future__ import annotations

import asyncio
import contextlib
import logging
import sys
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from agent.headless import HeadlessScanResult, InvalidScanInput, run_headless_scan
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

CommandStatus = Literal["running", "uploading", "done", "failed"]

_FORBIDDEN_PARK = "backend refused the upload; not reconnecting"


@dataclass(slots=True)
class CommandRecord:
    status: CommandStatus
    error_code: str | None = None
    pending: bool = True


class AgentDaemon:
    def __init__(
        self,
        client: CommandChannelClient,
        ingest: ScanIngestClient,
        *,
        run_scan: Callable[[str, str], HeadlessScanResult] = run_headless_scan,
    ) -> None:
        self._client = client
        self._ingest = ingest
        self._run_scan = run_scan
        self.ledger: dict[UUID, CommandRecord] = {}
        self._active: UUID | None = None
        self._task: asyncio.Task[None] | None = None

    async def run(self) -> None:
        try:
            await self._client.run(self.handle_command, self.replay_pending)
        finally:
            await self.close()

    async def close(self) -> None:
        await self._cancel_active()
        await self._client.close()
        self._ingest.close()

    async def _cancel_active(self) -> None:
        task, self._task = self._task, None
        if task is None or task.done():
            return
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task

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
        self._active = command.command_id
        await self._update(command.command_id, "running")
        self._task = asyncio.create_task(self._execute(command))

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
        finally:
            self._active = None

    async def _run_command(self, command: AgentCommand) -> None:
        try:
            result = await asyncio.to_thread(
                self._run_scan, command.scan_mode, command.subnet
            )
        except InvalidScanInput:
            await self._update(command.command_id, "failed", "invalid_command")
            return
        if result.payload is None:
            await self._update(command.command_id, "failed", "scan_failed")
            return
        if result.result_path is None:
            await self._update(command.command_id, "failed", "result_unavailable")
            return
        if result.outcome == "fatal":
            await self._update(command.command_id, "failed", "scan_failed")
            return
        await self._update(command.command_id, "uploading")
        submission = await asyncio.to_thread(
            self._ingest.submit, result.payload, scan_id=command.scan_id
        )
        if submission.outcome == "accepted":
            await self._update(command.command_id, "done")
            return
        LOGGER.error("upload rejected: %s", submission.message)
        await self._update(command.command_id, "failed", "ingest_failed")
        if submission.outcome == "forbidden":
            await self._client.close(_FORBIDDEN_PARK)

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


def run_daemon() -> None:
    try:
        config = load_ingest_config()
    except IngestConfigError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(20) from exc
    daemon = AgentDaemon(CommandChannelClient(config), ScanIngestClient(config))
    asyncio.run(daemon.run())
