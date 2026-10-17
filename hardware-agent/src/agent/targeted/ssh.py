from __future__ import annotations

import re

# ruff: noqa: E501
from collections.abc import Mapping
from typing import Any, Iterable

from agent.config import TARGETED_MAX_ISSUES_PER_UNIT
from agent.targeted.executor import TargetedExecutor, ToolCommand, ToolExecution
from agent.targeted.models import (
    TargetedGapReason,
    TargetedIssue,
    TargetedOutcome,
    TargetedTool,
    TargetedUnit,
    TargetedUnitResult,
)
from agent.targeted.report import (
    parse_json_payload,
    sanitize_evidence,
    target_value_matches,
)

_PQ_WARNING = "does not provide protection against post-quantum attacks"
_SECTIONS = {
    "protocol": "protocol",
    "kex": "kex",
    "key": "host-key",
    "host-key": "host-key",
    "host_key": "host-key",
    "enc": "cipher",
    "cipher": "cipher",
    "mac": "mac",
}


def _target_ok(payload: Any, unit: TargetedUnit) -> bool:
    if not isinstance(payload, Mapping):
        return False
    target = payload.get("target")
    if isinstance(target, Mapping):
        host = target.get("host", target.get("ip"))
        port = target.get("port")
        if host not in (None, "") and not target_value_matches(host, unit):
            return False
        if port not in (None, "") and str(port) != str(unit.port):
            return False
    elif target not in (None, ""):
        if not target_value_matches(target, unit):
            return False
    return True


def _notes(value: Any) -> tuple[list[str], list[str]]:
    if not isinstance(value, Mapping):
        return [], []
    fails = value.get("fail", [])
    warns = value.get("warn", [])
    if isinstance(fails, str):
        fails = [fails]
    elif not isinstance(fails, list):
        fails = []
    if isinstance(warns, str):
        warns = [warns]
    elif not isinstance(warns, list):
        warns = []
    clean_fail = [
        text
        for item in fails
        if isinstance(item, str) and item.strip()
        if (text := sanitize_evidence(item))
    ]
    clean_warn = [
        text
        for item in warns
        if isinstance(item, str) and item.strip()
        if (text := sanitize_evidence(item))
    ]
    clean_fail = [item for item in clean_fail if item.casefold() != _PQ_WARNING]
    clean_warn = [item for item in clean_warn if item.casefold() != _PQ_WARNING]
    return clean_fail, clean_warn


def _score(value: Any) -> float | None:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return None
    return score if 0 <= score <= 10 else None


def _severity(fail: bool, score: float | None) -> str:
    if score is not None:
        if score >= 9:
            return "critical"
        if score >= 7:
            return "high"
        if score >= 4:
            return "medium"
        return "low"
    return "high" if fail else "medium"


def _cve(value: Any) -> str | None:
    match = re.search(r"(?i)\bCVE-\d{4}-\d{4,7}\b", str(value or ""))
    return match.group(0).upper() if match else None


def _iter_algorithms(
    value: Any, section: str, name: str = "", depth: int = 0
) -> Iterable[tuple[str, str, list[str], list[str], Mapping[str, Any]]]:
    if depth > 32:
        return
    if isinstance(value, list):
        # Native ssh-audit 3.9.0 sections contain algorithm/notes records.
        for row in value:
            yield from _iter_algorithms(
                row.get("notes", {}), section, row["algorithm"], depth + 1
            )
        return
    if not isinstance(value, Mapping):
        return
    fails, warns = _notes(value)
    normalized_name = name.casefold().replace("_", "-")
    # ssh-audit may add advisory/schema buckets that look like algorithm
    # records.  They are not supported primitives and must never become
    # findings merely because they contain fail/warn fields.
    unsupported = ("unknown", "unsupported", "vendor-extension", "schema")
    if any(marker in normalized_name for marker in unsupported):
        return
    if fails or warns:
        yield section, name or section, fails, warns, value
    for key, child in value.items():
        if str(key).casefold() in {
            "fail",
            "warn",
            "info",
            "notes",
            "cve",
            "cvss",
            "recommendations",
        }:
            continue
        if isinstance(child, Mapping):
            yield from _iter_algorithms(child, section, str(key), depth + 1)


def _parse(payload: Any, unit: TargetedUnit) -> tuple[list[TargetedIssue], bool]:
    if not _target_ok(payload, unit):
        return [], False
    issues: list[TargetedIssue] = []
    if not isinstance(payload, Mapping) or not payload:
        return [], False
    for key, value in payload.items():
        if str(key).casefold() not in _SECTIONS:
            continue
        if isinstance(value, list):
            if any(
                not isinstance(row, Mapping)
                or not isinstance(row.get("algorithm"), str)
                or not row["algorithm"].strip()
                or not isinstance(row.get("notes", {}), Mapping)
                for row in value
            ):
                return [], False
        elif not isinstance(value, Mapping):
            return [], False
    if not any(
        str(key).casefold() in _SECTIONS
        or str(key).casefold() in {"target", "banner", "cve", "cves"}
        for key in payload
    ):
        return [], False
    for key, value in payload.items():
        section = _SECTIONS.get(str(key).casefold())
        if section is None:
            continue
        for category, name, fails, warns, row in _iter_algorithms(value, section):
            text = "; ".join(fails + warns)
            score = _score(row.get("cvss", row.get("cvss_score")))
            cve_id = _cve(row.get("cve", row.get("cve_id")))
            key_name = (
                re.sub(r"[^a-z0-9_.@+-]+", "-", name.casefold()).strip("-") or category
            )
            issue = TargetedIssue(
                f"ssh.algorithm:{category}:{key_name}",
                f"SSH {category} algorithm policy issue: {name}",
                text,
                _severity(bool(fails), score),
                "Disable the affected SSH algorithm and apply the server hardening guidance.",
                sanitize_evidence(f"ssh-audit: {category}={name}; {text}"),
                cve_id=cve_id,
                cvss_score=score,
            )
            if issue.issue_key not in {existing.issue_key for existing in issues}:
                issues.append(issue)
    return issues, True


def parse_ssh_audit_json(
    report: bytes | str | Mapping[str, Any] | TargetedUnit,
    unit: TargetedUnit | bytes | str | Mapping[str, Any] | None = None,
) -> list[TargetedIssue]:
    if isinstance(report, TargetedUnit):
        report, unit = unit, report
    if not isinstance(unit, TargetedUnit):
        return []
    issues, valid = _parse(parse_json_payload(report), unit)
    return issues[:TARGETED_MAX_ISSUES_PER_UNIT] if valid else []


def _result(unit: TargetedUnit, execution: ToolExecution) -> TargetedUnitResult:
    return TargetedUnitResult(
        unit,
        execution.outcome,
        exit_code=execution.exit_code,
        reason_code=execution.reason_code,
        diagnostic=execution.diagnostic,
    )


def run_ssh_audit(
    unit: TargetedUnit, executor: TargetedExecutor, **deadline: Any
) -> TargetedUnitResult:
    command = ToolCommand(
        TargetedTool.SSH_AUDIT,
        [
            "ssh-audit",
            "-j",
            "-t",
            "5",
            "--skip-rate-test",
            "-p",
            str(unit.port),
            unit.ip,
        ],
        "stdout",
    )
    execution = executor.execute(command, **deadline)
    if execution.outcome != TargetedOutcome.COMPLETED:
        return _result(unit, execution)
    if execution.report_truncated or execution.stdout_truncated:
        return TargetedUnitResult(
            unit,
            TargetedOutcome.FAILED,
            exit_code=execution.exit_code,
            reason_code=TargetedGapReason.OUTPUT_LIMIT,
        )
    report = execution.report or execution.stdout
    if not execution.report_present and not report:
        return TargetedUnitResult(
            unit,
            TargetedOutcome.FAILED,
            exit_code=execution.exit_code,
            reason_code=TargetedGapReason.MALFORMED_REPORT,
        )
    payload = parse_json_payload(report)
    if isinstance(payload, Mapping) and not _target_ok(payload, unit):
        return TargetedUnitResult(
            unit,
            TargetedOutcome.FAILED,
            exit_code=execution.exit_code,
            reason_code=TargetedGapReason.WRONG_TARGET,
        )
    issues, valid = _parse(payload, unit)
    if not valid:
        return TargetedUnitResult(
            unit,
            TargetedOutcome.FAILED,
            exit_code=execution.exit_code,
            reason_code=TargetedGapReason.MALFORMED_REPORT,
        )
    if len(issues) > TARGETED_MAX_ISSUES_PER_UNIT:
        return TargetedUnitResult(
            unit,
            TargetedOutcome.FAILED,
            issues=issues[:TARGETED_MAX_ISSUES_PER_UNIT],
            exit_code=execution.exit_code,
            reason_code=TargetedGapReason.ISSUE_LIMIT,
        )
    return TargetedUnitResult(
        unit, TargetedOutcome.COMPLETED, issues=issues, exit_code=execution.exit_code
    )
