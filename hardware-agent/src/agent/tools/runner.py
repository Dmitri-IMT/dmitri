"""Subprocess runner for optional external security tools."""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from enum import StrEnum


class ToolRunStatus(StrEnum):
    """Normalized status for optional external tool runs."""

    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    TIMED_OUT = "timed_out"


@dataclass(frozen=True, slots=True)
class ToolRunResult:
    """Captured result from one external tool invocation."""

    tool: str
    argv: list[str]
    status: ToolRunStatus
    exit_code: int | None = None
    stdout: str = ""
    stderr: str = ""
    error: str = ""


class ExternalToolRunner:
    """Run optional CLI tools without making them hard scan dependencies."""

    def __init__(self, *, timeout_seconds: int) -> None:
        self.timeout_seconds = timeout_seconds

    def run(self, executable: str, arguments: list[str]) -> ToolRunResult:
        resolved = shutil.which(executable)
        argv = [executable, *arguments]
        if resolved is None:
            return ToolRunResult(
                tool=executable,
                argv=argv,
                status=ToolRunStatus.SKIPPED,
                error=f"{executable} not found in PATH.",
            )

        command = [resolved, *arguments]
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                errors="replace",
                timeout=self.timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            return ToolRunResult(
                tool=executable,
                argv=argv,
                status=ToolRunStatus.TIMED_OUT,
                stdout=exc.stdout or "",
                stderr=exc.stderr or "",
                error=f"{executable} timed out after {self.timeout_seconds}s.",
            )

        status = (
            ToolRunStatus.COMPLETED
            if completed.returncode == 0
            else ToolRunStatus.FAILED
        )
        return ToolRunResult(
            tool=executable,
            argv=argv,
            status=status,
            exit_code=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
            error=completed.stderr.strip() if completed.returncode != 0 else "",
        )
