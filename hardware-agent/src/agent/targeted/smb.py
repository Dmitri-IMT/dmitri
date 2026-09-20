from __future__ import annotations

import json

# ruff: noqa: E501
from collections.abc import Mapping
from typing import Any

from agent.config import TARGETED_EVIDENCE_LIMIT_CHARS, TARGETED_MAX_ISSUES_PER_UNIT
from agent.targeted.executor import TargetedExecutor, ToolCommand, ToolExecution
from agent.targeted.models import (
    TargetedGapReason,
    TargetedIssue,
    TargetedObservation,
    TargetedOutcome,
    TargetedTool,
    TargetedUnit,
    TargetedUnitResult,
)


def _payload(report: bytes | str | Mapping[str, Any]) -> Any:
    if isinstance(report, Mapping):
        return report
    try:
        return json.loads(report.decode("utf-8") if isinstance(report, bytes) else report)
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError):
        return None


def _text(value: Any, limit: int = TARGETED_EVIDENCE_LIMIT_CHARS) -> str:
    value = " ".join(str(value).split())
    value = "".join(character for character in value if character.isprintable())
    return value[:limit]


def _truth(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).casefold().strip() in {"true", "yes", "ok", "success", "successful", "enabled"}


def _target_value_matches(value: Any, unit: TargetedUnit) -> bool:
    text = str(value).strip().casefold()
    host = unit.ip.casefold()
    if text == host:
        return True
    if text.startswith("[") and "]" in text:
        report_host, _, report_port = text[1:].partition("]")
        return report_host == host and (
            not report_port or report_port.removeprefix(":") == str(unit.port)
        )
    if text.count(":") == 1:
        report_host, report_port = text.rsplit(":", 1)
        return report_host == host and report_port == str(unit.port)
    return False


def _target_ok(payload: Any, unit: TargetedUnit) -> bool:
    if not isinstance(payload, Mapping):
        return False
    values = []
    for key in ("ip", "host", "hostname", "target"):
        value = payload.get(key)
        if value not in (None, "") and not (key == "target" and isinstance(value, Mapping)):
            values.append(str(value).casefold())
    if values and not all(_target_value_matches(value, unit) for value in values):
        return False
    port = payload.get("port")
    if port not in (None, "") and str(port) != str(unit.port):
        return False
    target = payload.get("target")
    if isinstance(target, Mapping):
        for key in ("host", "ip"):
            host = target.get(key)
            if host not in (None, "") and not _target_value_matches(host, unit):
                return False
        port = target.get("port")
        if port not in (None, "") and str(port) != str(unit.port):
            return False
    return True


def _account_count(value: Any) -> int:
    if isinstance(value, list):
        return len(value[:256])
    return 0


def _account_count_alias(value: Any, aliases: tuple[str, ...]) -> int:
    if not isinstance(value, Mapping):
        return 0
    for alias in aliases:
        if alias in value:
            return _account_count(value[alias])
    return 0


def _rows(value: Any) -> list[Mapping[str, Any]]:
    if isinstance(value, list):
        return [row for row in value[:256] if isinstance(row, Mapping)]
    if isinstance(value, Mapping):
        if any(key in {"name", "share", "sharename", "access"} for key in value):
            return [value]
    return []


def _row_target_conflict(rows: list[Mapping[str, Any]], unit: TargetedUnit) -> bool:
    return any(
        any(key in row for key in ("ip", "host", "hostname", "target", "port")) and not _target_ok(row, unit)
        for row in rows
    )


def _schema_valid(payload: Mapping[str, Any]) -> bool:
    """Reject malformed values under enum4linux's recognized containers."""

    recognized = {
        "target",
        "sessions",
        "shares",
        "users",
        "groups",
        "os_info",
        "domain",
        "errors",
        "password_policy",
    }
    if not any(str(key).casefold() in recognized for key in payload):
        return False
    for key, value in payload.items():
        normalized = str(key)
        if normalized == "target" and not isinstance(value, (str, Mapping)):
            return False
        if normalized in {"sessions", "os_info", "domain", "password_policy"} and not isinstance(value, Mapping):
            return False
        if normalized in {"shares", "users", "groups", "errors"} and not isinstance(value, (list, Mapping)):
            return False
    return True


def _parse(payload: Any, unit: TargetedUnit) -> tuple[list[TargetedIssue], list[TargetedObservation], bool]:
    if not isinstance(payload, Mapping) or not payload or not _target_ok(payload, unit) or not _schema_valid(payload):
        return [], [], False

    containers = dict(payload)
    sessions = containers.get("sessions")
    shares = containers.get("shares")
    users = containers.get("users")
    groups = containers.get("groups")
    policy = containers.get("password_policy")
    session_rows = [sessions] if isinstance(sessions, Mapping) else []
    share_rows = _rows(shares)
    user_rows = _rows(users)
    group_rows = _rows(groups)
    if (
        _row_target_conflict(session_rows, unit)
        or _row_target_conflict(share_rows, unit)
        or _row_target_conflict(user_rows, unit)
        or _row_target_conflict(group_rows, unit)
    ):
        return [], [], False
    issues: list[TargetedIssue] = []
    observations: list[TargetedObservation] = []
    has_session = any(key in {"null", "null_session", "null session", "anonymous_session", "anonymous session"} and _truth(value) for key, value in sessions.items()) if isinstance(sessions, Mapping) else False
    has_guest = any(key in {"guest", "guest_session", "guest session", "anonymous_guest"} and _truth(value) for key, value in sessions.items()) if isinstance(sessions, Mapping) else False
    if has_session:
        issues.append(TargetedIssue("smb:anonymous-session", "SMB null session is available", "The SMB service accepted an unauthenticated null session.", "medium", "Disable null sessions and restrict unauthenticated SMB/RPC access.", "enum4linux-ng: null session confirmed"))
    if has_guest:
        issues.append(TargetedIssue("smb:guest-session", "SMB guest session is available", "The SMB service accepted a guest session without supplied credentials.", "medium", "Disable guest access and require authenticated SMB sessions.", "enum4linux-ng: guest session confirmed"))
    for row in share_rows:
        access = row.get("access")
        if not isinstance(access, Mapping):
            continue
        name = ""
        for alias in ("name", "share", "sharename"):
            if alias in row:
                name = str(row[alias])
                break
        if not name or name.casefold().rstrip("$") == "ipc":
            continue
        if _truth(access.get("mapping")) and _truth(access.get("listing")):
            issues.append(TargetedIssue(f"smb:anonymous-share:{name.casefold()}", f"SMB share {name} is anonymously readable", "An unauthenticated SMB session mapped and listed a disk share.", "medium", "Require authentication before mapping or listing the share.", _text(f"enum4linux-ng: share={name}; mapping=ok; listing=ok")))
    account_count = _account_count_alias(users, ("users", "user_accounts", "accounts"))
    group_count = _account_count_alias(groups, ("groups", "group_accounts"))
    if (has_session or has_guest) and account_count + group_count:
        issues.append(TargetedIssue("smb:anonymous-account-enumeration", "SMB accounts are enumerable without authentication", "The unauthenticated SMB session returned user or group identities.", "medium", "Restrict account and group enumeration to authenticated administrators.", f"enum4linux-ng: users={min(account_count, 256)}; groups={min(group_count, 256)}"))
    if isinstance(policy, Mapping):
        for key, value in policy.items():
            normalized = str(key)
            if normalized in {"store_passwords_in_cleartext", "passwords_stored_in_cleartext", "cleartext_passwords"} and _truth(value):
                if not isinstance(value, bool):
                    continue
                issues.append(TargetedIssue("smb:passwords-cleartext", "SMB policy stores passwords in cleartext", "The reported SMB password policy permits cleartext password storage.", "high", "Disable cleartext password storage and rotate affected credentials.", "enum4linux-ng: cleartext password storage enabled"))
            elif normalized in {"minimum_password_length", "min_password_length", "password_min_length"}:
                minimum_length = 0 if value == "None" else value if isinstance(value, int) and not isinstance(value, bool) else None
                if minimum_length is not None and minimum_length < 8:
                    issues.append(TargetedIssue("smb:password-length", "SMB minimum password length is weak", "The reported SMB policy permits passwords shorter than eight characters.", "medium", "Set the minimum password length to at least eight characters.", f"enum4linux-ng: minimum password length={minimum_length}"))
            elif normalized in {"password_complexity", "complexity_enabled", "password_must_meet_complexity_requirements"} and isinstance(value, bool) and not value:
                issues.append(TargetedIssue("smb:password-complexity", "SMB password complexity is disabled", "The reported SMB policy disables password complexity requirements.", "medium", "Enable password complexity requirements.", "enum4linux-ng: password complexity disabled"))
            elif normalized in {"lockout_threshold", "account_lockout_threshold"}:
                if (isinstance(value, int) and not isinstance(value, bool) and value == 0) or value == "None":
                    issues.append(TargetedIssue("smb:lockout-threshold", "SMB account lockout is disabled", "The reported SMB policy has an account lockout threshold of zero.", "low", "Configure a nonzero account lockout threshold with appropriate recovery controls.", "enum4linux-ng: lockout threshold=0"))
    if not issues and any(key in {"os_info", "domain", "users", "groups", "shares", "sessions"} for key in payload):
        observations.append(TargetedObservation("smb:inventory", "service_identity", "SMB inventory was collected without a supported exposure finding.", "enum4linux-ng: bounded inventory only"))
    deduped: list[TargetedIssue] = []
    seen: set[str] = set()
    for issue in issues:
        if issue.issue_key not in seen:
            seen.add(issue.issue_key)
            deduped.append(issue)
    return deduped[: TARGETED_MAX_ISSUES_PER_UNIT + 1], observations, True


def _has_nested_target_conflict(payload: Any, unit: TargetedUnit) -> bool:
    if not isinstance(payload, Mapping):
        return False
    containers = dict(payload)
    sessions = containers.get("sessions")
    rows = ([sessions] if isinstance(sessions, Mapping) else [])
    rows.extend(_rows(containers.get("shares")))
    for name, aliases in (("users", ("users", "user_accounts", "accounts")), ("groups", ("groups", "group_accounts"))):
        container = containers.get(name)
        if isinstance(container, Mapping):
            for alias in aliases:
                rows.extend(_rows(container.get(alias)))
    return _row_target_conflict(rows, unit)


def parse_enum4linux_json(
    report: bytes | str | Mapping[str, Any] | TargetedUnit,
    unit: TargetedUnit | bytes | str | Mapping[str, Any] | None = None,
) -> list[TargetedIssue]:
    if isinstance(report, TargetedUnit):
        report, unit = unit, report
    if not isinstance(unit, TargetedUnit):
        return []
    payload = _payload(report)
    issues, _, valid = _parse(payload, unit)
    return issues if valid else []


def _result(unit: TargetedUnit, execution: ToolExecution) -> TargetedUnitResult:
    return TargetedUnitResult(unit, execution.outcome, exit_code=execution.exit_code, reason_code=execution.reason_code, diagnostic=execution.diagnostic)


def run_enum4linux(unit: TargetedUnit, executor: TargetedExecutor, **deadline: Any) -> TargetedUnitResult:
    command = ToolCommand(
        TargetedTool.ENUM4LINUX,
        ["enum4linux-ng", "-As", "-t", "5", "-oJ", "REPORT", unit.ip],
        "file",
        5,
        report_path_mode="base",
    )
    execution = executor.execute(command, **deadline)
    if execution.outcome != TargetedOutcome.COMPLETED:
        return _result(unit, execution)
    if execution.report_truncated:
        return TargetedUnitResult(unit, TargetedOutcome.FAILED, exit_code=execution.exit_code, reason_code=TargetedGapReason.OUTPUT_LIMIT)
    if not execution.report_present:
        return TargetedUnitResult(unit, TargetedOutcome.FAILED, exit_code=execution.exit_code, reason_code=TargetedGapReason.MALFORMED_REPORT)
    payload = _payload(execution.report)
    if isinstance(payload, Mapping) and not _target_ok(payload, unit):
        return TargetedUnitResult(unit, TargetedOutcome.FAILED, exit_code=execution.exit_code, reason_code=TargetedGapReason.WRONG_TARGET)
    if _has_nested_target_conflict(payload, unit):
        return TargetedUnitResult(unit, TargetedOutcome.FAILED, exit_code=execution.exit_code, reason_code=TargetedGapReason.WRONG_TARGET)
    issues, observations, valid = _parse(payload, unit)
    if not valid:
        return TargetedUnitResult(unit, TargetedOutcome.FAILED, exit_code=execution.exit_code, reason_code=TargetedGapReason.MALFORMED_REPORT)
    if len(issues) > TARGETED_MAX_ISSUES_PER_UNIT:
        return TargetedUnitResult(unit, TargetedOutcome.FAILED, issues=issues[:TARGETED_MAX_ISSUES_PER_UNIT], observations=observations, exit_code=execution.exit_code, reason_code=TargetedGapReason.ISSUE_LIMIT)
    return TargetedUnitResult(unit, TargetedOutcome.COMPLETED, issues=issues, observations=observations, exit_code=execution.exit_code)
