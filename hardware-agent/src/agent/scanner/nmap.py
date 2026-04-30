"""Nmap process execution helpers."""

from __future__ import annotations

import shutil
import subprocess
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path


class NmapExecutionError(RuntimeError):
    """Raised when Nmap fails to execute or emits invalid XML."""


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


@dataclass(slots=True)
class NmapRunResult:
    """Parsed XML plus the raw XML text returned by Nmap."""

    root: ET.Element
    raw_xml: str


class NmapRunner:
    """Thin wrapper around the Nmap CLI that always requests XML output."""

    def __init__(self, nmap_path: str | None = None) -> None:
        self.nmap_path = _resolve_nmap_path(nmap_path)

    def run_xml(
        self,
        arguments: list[str],
        *,
        output_path: str | Path | None = None,
    ) -> ET.Element:
        """Execute Nmap and parse its XML output."""

        result = self.run(arguments, output_path=output_path)
        return result.root

    def run(
        self,
        arguments: list[str],
        *,
        output_path: str | Path | None = None,
    ) -> NmapRunResult:
        """Execute Nmap and return parsed plus raw XML."""

        command = [self.nmap_path, *arguments, "-oX", "-"]
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            raise NmapExecutionError(
                result.stderr.strip() or "Nmap returned a non-zero exit code."
            )

        if output_path is not None:
            target = Path(output_path)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(result.stdout, encoding="utf-8")

        try:
            root = ET.fromstring(result.stdout)
        except ET.ParseError as exc:
            raise NmapExecutionError("Nmap did not return valid XML output.") from exc

        _strip_namespaces(root)
        return NmapRunResult(root=root, raw_xml=result.stdout)


def _strip_namespaces(root: ET.Element) -> None:
    for element in root.iter():
        if "}" in element.tag:
            element.tag = element.tag.split("}", 1)[1]
