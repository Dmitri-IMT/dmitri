"""Nmap process execution helpers."""

from __future__ import annotations

import logging
import shutil
import subprocess
import threading
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uuid import UUID

    from agent.config import AgentSettings

LOGGER = logging.getLogger(__name__)
AGENT_VERSION = "0.1.2"


class NmapExecutionError(RuntimeError):
    """Raised when Nmap fails to execute or emits invalid XML."""


@dataclass(slots=True)
class StreamedRunResult:
    """Outcome of a streamed Nmap subprocess."""

    exit_code: int | None
    console_log: Path
    stderr_log: Path
    xml_path: Path


def _resolve_nmap_path(candidate: str | None) -> str:
    if candidate:
        return candidate

    discovered = shutil.which("nmap")
    if discovered:
        return discovered

    common_locations = (
        Path("/usr/bin/nmap"),
        Path("/usr/local/bin/nmap"),
        Path(r"C:\Program Files (x86)\Nmap\nmap.exe"),
        Path(r"C:\Program Files\Nmap\nmap.exe"),
    )
    for location in common_locations:
        if location.exists():
            return str(location)

    raise NmapExecutionError(
        "Nmap executable not found. Set AGENT_NMAP_PATH or install nmap in PATH."
    )


def _stream_pipe_to_file(pipe, file_path: Path) -> None:
    """Read lines from a subprocess pipe and write them to a file as they arrive."""
    with open(file_path, "w", encoding="utf-8", errors="replace") as fh:
        for line in pipe:
            fh.write(line)
            fh.flush()


class NmapRunner:
    """Thin wrapper around the Nmap CLI that always requests XML output."""

    def __init__(self, nmap_path: str | None = None) -> None:
        self.nmap_path = _resolve_nmap_path(nmap_path)

    def run_xml(self, arguments: list[str]) -> ET.Element:
        """Execute Nmap and parse its XML output."""

        command = [self.nmap_path, *arguments, "-oX", "-"]
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            raise NmapExecutionError(
                result.stderr.strip() or "Nmap returned a non-zero exit code."
            )

        try:
            root = ET.fromstring(result.stdout)
        except ET.ParseError as exc:
            raise NmapExecutionError("Nmap did not return valid XML output.") from exc

        _strip_namespaces(root)
        return root

    def run_streamed(
        self,
        arguments: list[str],
        run_dir: Path,
    ) -> StreamedRunResult:
        """Execute Nmap with streaming stdout/stderr to files in run_dir.

        XML output is written by Nmap itself via -oX in the arguments.
        """
        console_log = run_dir / "console.log"
        stderr_log = run_dir / "stderr.log"
        xml_path = run_dir / "nmaprun.xml"

        command = [self.nmap_path, *arguments]
        proc = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            errors="replace",
        )

        stdout_thread = threading.Thread(
            target=_stream_pipe_to_file,
            args=(proc.stdout, console_log),
        )
        stderr_thread = threading.Thread(
            target=_stream_pipe_to_file,
            args=(proc.stderr, stderr_log),
        )
        stdout_thread.start()
        stderr_thread.start()

        proc.wait()
        stdout_thread.join()
        stderr_thread.join()

        return StreamedRunResult(
            exit_code=proc.returncode,
            console_log=console_log,
            stderr_log=stderr_log,
            xml_path=xml_path,
        )


def _strip_namespaces(root: ET.Element) -> None:
    for element in root.iter():
        if "}" in element.tag:
            element.tag = element.tag.split("}", 1)[1]


class LoggedNmapRunner(NmapRunner):
    """NmapRunner that streams output to log files under a workspace.

    Discovery functions call ``run_xml()`` as usual; this subclass transparently
    creates a run folder, streams stdout/stderr, writes ``meta.json``, prunes
    old runs, and returns parsed XML from the on-disk file.
    """

    def __init__(
        self,
        nmap_path: str | None,
        workspace_root: Path,
        parent_scan_id: str | None = None,
        agent_version: str | None = None,
    ) -> None:
        super().__init__(nmap_path)
        self.workspace_root = workspace_root
        self.logs_dir = workspace_root / "logs"
        self.parent_scan_id = parent_scan_id
        self.agent_version = agent_version
        self._current_stage = "unknown"

    def set_stage(self, stage: str) -> None:
        self._current_stage = stage

    def run_xml(self, arguments: list[str]) -> ET.Element:
        from agent.scanner.workspace import (
            build_nmap_argv,
            make_run_folder_name,
            prune_logs,
            write_meta_json,
        )

        run_name = make_run_folder_name(self._current_stage)
        run_dir = self.logs_dir / run_name
        run_dir.mkdir(parents=True, exist_ok=True)

        xml_path = run_dir / "nmaprun.xml"
        full_argv = build_nmap_argv(arguments, xml_path)

        started_at = datetime.now(timezone.utc)
        result = self.run_streamed(full_argv, run_dir)
        finished_at = datetime.now(timezone.utc)

        if result.exit_code == 0:
            terminated_by = "completed"
        else:
            terminated_by = "error"

        write_meta_json(
            run_dir,
            nmap_path=self.nmap_path,
            argv=full_argv,
            started_at=started_at,
            finished_at=finished_at,
            exit_code=result.exit_code,
            terminated_by=terminated_by,
            scan_workspace_root=self.workspace_root,
            parent_scan_id=self.parent_scan_id,
            agent_version=self.agent_version,
        )

        prune_logs(self.logs_dir)

        if result.exit_code != 0:
            stderr_text = ""
            if result.stderr_log.exists():
                stderr_text = result.stderr_log.read_text(encoding="utf-8").strip()
            raise NmapExecutionError(
                stderr_text or "Nmap returned a non-zero exit code."
            )

        if not xml_path.exists():
            raise NmapExecutionError("Nmap did not produce XML output.")

        try:
            root = ET.fromstring(xml_path.read_text(encoding="utf-8"))
        except ET.ParseError as exc:
            raise NmapExecutionError("Nmap did not return valid XML output.") from exc

        _strip_namespaces(root)
        LOGGER.info("Logged nmap run: %s", run_name)
        return root


def build_runner(
    settings: AgentSettings,
    workspace_root: Path | None,
    scan_id: UUID | str,
    runner: NmapRunner | None = None,
) -> NmapRunner:
    if runner is not None:
        return runner
    if workspace_root is not None:
        return LoggedNmapRunner(
            settings.nmap_path,
            workspace_root,
            parent_scan_id=str(scan_id),
            agent_version=AGENT_VERSION,
        )
    return NmapRunner(settings.nmap_path)
