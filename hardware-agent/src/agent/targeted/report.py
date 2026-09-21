from __future__ import annotations

import json
import re
from collections.abc import Mapping
from typing import Any

from agent.config import TARGETED_EVIDENCE_LIMIT_CHARS
from agent.targeted.models import TargetedUnit

_SECRET_RE = re.compile(
    r"(?i)(password|passwd|token|secret|authorization|cookie|api[_-]?key)\s*[=:]\s*\S+"
)
_URL_PATH_RE = re.compile(r"(?i)(https?://[^/?#\s]+)(?:[/?#][^\s]*)")


def parse_json_payload(report: bytes | str | Mapping[str, Any]) -> Any:
    if isinstance(report, Mapping):
        return report
    try:
        return json.loads(
            report.decode("utf-8") if isinstance(report, bytes) else report
        )
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError):
        return None


def sanitize_evidence(value: Any, limit: int = TARGETED_EVIDENCE_LIMIT_CHARS) -> str:
    if isinstance(value, bytes):
        value = value.decode("utf-8", "replace")
    value = str(value)
    value = _SECRET_RE.sub(r"\1=[REDACTED]", value)
    value = _URL_PATH_RE.sub(r"\1/[REDACTED]", value)
    value = " ".join(value.split())
    value = "".join(character for character in value if character.isprintable())
    return value[:limit]


def target_value_matches(value: Any, unit: TargetedUnit) -> bool:
    """Match a report endpoint without accepting an address substring."""

    text = str(value).strip().casefold()
    host = unit.ip.casefold()
    if text == host:
        return True
    if text.startswith("[") and "]" in text:
        report_host, separator, report_port = text[1:].partition("]")
        if report_host != host:
            return False
        return not report_port or report_port.removeprefix(":") == str(unit.port)
    if text.count(":") == 1:
        report_host, report_port = text.rsplit(":", 1)
        return report_host == host and report_port == str(unit.port)
    return False
