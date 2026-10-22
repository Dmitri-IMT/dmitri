from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from uuid import UUID

Phase = Literal["running", "uploading", "awaiting_ack"]


@dataclass(frozen=True, slots=True)
class ScanFinalizationCheckpoint:
    command_id: UUID
    scan_id: UUID
    session_id: UUID
    phase: Phase
    status: Literal["done", "failed", "cancelled"] | None = None
    error_code: str | None = None
    result_path: str | None = None
    protocol: int = 1


class ScanFinalizationStore:

    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> ScanFinalizationCheckpoint | None:
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None
        if not isinstance(value, dict) or set(value) != {
            "command_id",
            "scan_id",
            "session_id",
            "phase",
            "status",
            "error_code",
            "result_path",
            "protocol",
        }:
            raise ValueError("invalid scan finalization checkpoint")
        if (
            value["phase"] not in {"running", "uploading", "awaiting_ack"}
            or value["status"] not in {None, "done", "failed", "cancelled"}
            or value["protocol"] != 1
            or (
                value["result_path"] is not None
                and not isinstance(value["result_path"], str)
            )
            or (
                value["error_code"] is not None
                and not isinstance(value["error_code"], str)
            )
        ):
            raise ValueError("invalid scan finalization checkpoint")
        return ScanFinalizationCheckpoint(
            command_id=UUID(value["command_id"]),
            scan_id=UUID(value["scan_id"]),
            session_id=UUID(value["session_id"]),
            phase=value["phase"],
            status=value["status"],
            error_code=value["error_code"],
            result_path=value["result_path"],
            protocol=value["protocol"],
        )

    def save(self, checkpoint: ScanFinalizationCheckpoint) -> None:
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(prefix=f".{self.path.name}.", dir=self.path.parent)
        temp = Path(name)
        try:
            if hasattr(os, "fchmod"):
                os.fchmod(fd, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(
                    {
                        "command_id": str(checkpoint.command_id),
                        "scan_id": str(checkpoint.scan_id),
                        "session_id": str(checkpoint.session_id),
                        "phase": checkpoint.phase,
                        "status": checkpoint.status,
                        "error_code": checkpoint.error_code,
                        "result_path": checkpoint.result_path,
                        "protocol": checkpoint.protocol,
                    },
                    stream,
                    separators=(",", ":"),
                )
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp, self.path)
            if os.name == "posix":
                directory_fd = os.open(self.path.parent, os.O_RDONLY)
                try:
                    os.fsync(directory_fd)
                finally:
                    os.close(directory_fd)
        finally:
            try:
                temp.unlink(missing_ok=True)
            except PermissionError:
                pass

    def clear(self) -> None:
        self.path.unlink(missing_ok=True)
