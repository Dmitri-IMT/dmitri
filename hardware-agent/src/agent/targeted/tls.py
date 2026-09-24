from __future__ import annotations

import re
import shutil

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

_SEVERITIES = {"low", "medium", "high", "critical"}
_IGNORED_FINDINGS = {"ok", "info", "debug", "warn", "warning", "error", "n/a", "na"}
_SUPPORTED_ID_WORDS = (
    "cert",
    "cipher",
    "beast",
    "ccs",
    "crime",
    "drown",
    "freak",
    "heartbleed",
    "logjam",
    "lucky13",
    "md5",
    "protocol",
    "poodle",
    "robot",
    "ssl",
    "sweet32",
    "tls",
    "ticketbleed",
)


def _walk(value: Any, depth: int = 0) -> Iterable[Mapping[str, Any]]:
    if depth > 32:
        return
    if isinstance(value, Mapping):
        yield value
        for child in value.values():
            yield from _walk(child, depth + 1)
    elif isinstance(value, list):
        for child in value[:4096]:
            yield from _walk(child, depth + 1)


def _slug(value: str) -> str:
    value = value.casefold().replace("tlsv", "tls")
    value = re.sub(r"[^a-z0-9]+", ".", value).strip(".")
    replacements = {"tls.1.0": "tls1.0", "tls.1.1": "tls1.1", "ssl.3.0": "ssl3.0"}
    return replacements.get(value, value)[:96] or "unknown"


def _issue_value(identifier: str, finding: str, kind: str) -> str:
    value = f"{identifier} {finding}"
    if kind == "protocol":
        match = re.search(r"(?i)(tls|ssl)\s*v?\s*(\d(?:[._]\d)?)", value)
        if match:
            return f"{match.group(1).casefold()}{match.group(2).replace('_', '.')}"
    if kind == "cipher":
        match = re.search(r"(?i)(rc4|3des|des|null|export|aNULL|anonymous)", value)
        if match:
            return match.group(0).casefold()
    if kind == "certificate":
        match = re.search(r"(?i)(expired|revoked|self[- ]signed|hostname|weak)", value)
        if match:
            return match.group(1).casefold().replace(" ", "-")
    return _slug(finding if kind != "weakness" else identifier)


def _number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if 0 <= number <= 10 else None


def _target_matches(row: Mapping[str, Any], unit: TargetedUnit) -> bool:
    host_values = [
        row.get(key) for key in ("ip", "host", "hostname", "fqdn", "target", "node")
    ]
    hosts = [value for value in host_values if value not in (None, "")]
    if hosts and not all(target_value_matches(value, unit) for value in hosts):
        return False
    port = row.get("port")
    if port not in (None, ""):
        try:
            parsed_port = int(str(port).strip())
        except (TypeError, ValueError):
            return False
        if parsed_port != unit.port:
            return False
    return True


def _records(
    payload: Any, unit: TargetedUnit | None
) -> tuple[list[Mapping[str, Any]], bool]:
    if not isinstance(payload, (Mapping, list)):
        return [], False
    if isinstance(payload, list) and not payload:
        return [], False
    scan_result = payload.get("scanResult") if isinstance(payload, Mapping) else None
    if isinstance(scan_result, list):
        flat_records = all(
            isinstance(row, Mapping)
            and {"id", "severity", "finding"}.issubset(row)
            for row in scan_result
        )
        if scan_result and not flat_records:
            records: list[Mapping[str, Any]] = []
            saw_target_conflict = False
            for host in scan_result:
                if not isinstance(host, Mapping) or not any(
                    isinstance(value, list) for value in host.values()
                ):
                    return [], False
                host_values = [
                    host.get(key)
                    for key in ("ip", "host", "hostname", "fqdn", "target", "node")
                ]
                has_host = any(value not in (None, "") for value in host_values)
                if unit is not None and (
                    not has_host or not _target_matches(host, unit)
                ):
                    saw_target_conflict = True
                    continue
                for row in _walk(host):
                    if not {"id", "severity", "finding"}.issubset(row):
                        continue
                    record = dict(row)
                    for key in ("ip", "host", "port"):
                        if host.get(key) not in (None, ""):
                            record.setdefault(key, host[key])
                    if unit is not None and not _target_matches(record, unit):
                        saw_target_conflict = True
                        continue
                    records.append(record)
            return records, not saw_target_conflict
        if not flat_records:
            return [], False
    records: list[Mapping[str, Any]] = []
    saw_target_conflict = False
    for row in _walk(payload):
        if (
            unit is not None
            and any(
                row.get(key) not in (None, "")
                for key in ("ip", "host", "hostname", "fqdn", "target", "node")
            )
            and not _target_matches(row, unit)
        ):
            saw_target_conflict = True
        if not {"id", "severity", "finding"}.issubset(row):
            continue
        if unit is not None and not _target_matches(row, unit):
            saw_target_conflict = True
            continue
        records.append(row)
    if isinstance(payload, Mapping) and not records:
        valid_container = isinstance(payload.get("scanResult"), list) or any(
            isinstance(value, list) for value in payload.values()
        )
        return records, valid_container and not saw_target_conflict
    return records, not saw_target_conflict


def _cve(value: Any) -> str | None:
    match = re.search(r"(?i)\bCVE-\d{4}-\d{4,7}\b", str(value or ""))
    return match.group(0).upper() if match else None


def _issue(row: Mapping[str, Any]) -> TargetedIssue | None:
    identifier = str(row.get("id", "")).strip()
    finding = sanitize_evidence(row.get("finding", ""))
    severity = str(row.get("severity", "")).casefold().strip()
    identifier_lower = identifier.casefold()
    finding_lower = finding.casefold()
    if not identifier or not finding or severity not in _SEVERITIES:
        return None
    if finding_lower in _IGNORED_FINDINGS or finding_lower.startswith("not "):
        return None
    if not any(
        word in identifier_lower or word in finding_lower
        for word in _SUPPORTED_ID_WORDS
    ):
        return None
    kind = (
        "certificate"
        if any(
            word in identifier_lower or word in finding_lower
            for word in ("cert", "x509")
        )
        else (
            "protocol"
            if any(
                word in identifier_lower or word in finding_lower
                for word in ("protocol", "tls", "ssl")
            )
            else (
                "cipher"
                if "cipher" in identifier_lower
                or "cipher" in finding_lower
                or any(
                    word in identifier_lower
                    for word in ("rc4", "3des", "des", "null", "export")
                )
                else "weakness"
            )
        )
    )
    value = _issue_value(identifier, finding, kind)
    issue_key = f"tls.{kind}:{value}"
    cve_id = _cve(row.get("cve", row.get("cve_id", finding)))
    references: list[str] = []
    for key in ("cwe", "reference", "references"):
        raw = row.get(key)
        values = raw if isinstance(raw, list) else [raw]
        references.extend(
            sanitize_evidence(item, 256)
            for item in values
            if isinstance(item, str)
            and (
                item.casefold().startswith("http://")
                or item.casefold().startswith("https://")
            )
        )
    return TargetedIssue(
        issue_key,
        f"TLS {kind} weakness: {identifier}",
        finding,
        severity,
        "Disable the affected TLS protocol or primitive and apply the vendor remediation.",
        sanitize_evidence(
            f"testssl:{identifier}; severity={severity}; finding={finding}"
        ),
        cve_id=cve_id,
        cvss_score=_number(row.get("cvss", row.get("cvss_score"))),
        references=list(dict.fromkeys(references))[:8],
    )


def parse_testssl_json(
    report: bytes | str | Mapping[str, Any] | TargetedUnit,
    unit: TargetedUnit | bytes | str | Mapping[str, Any] | None = None,
) -> list[TargetedIssue]:
    if isinstance(report, TargetedUnit):
        report, unit = unit, report
    target = unit if isinstance(unit, TargetedUnit) else None
    payload = parse_json_payload(report)
    records, valid = _records(payload, target)
    if not valid:
        return []
    issues: list[TargetedIssue] = []
    for row in records:
        issue = _issue(row)
        if issue is not None and len(issues) < TARGETED_MAX_ISSUES_PER_UNIT:
            issues.append(issue)
    return issues


def _result(unit: TargetedUnit, execution: ToolExecution) -> TargetedUnitResult:
    return TargetedUnitResult(
        unit,
        execution.outcome,
        exit_code=execution.exit_code,
        reason_code=execution.reason_code,
        diagnostic=execution.diagnostic,
    )


def run_testssl(
    unit: TargetedUnit, executor: TargetedExecutor, **deadline: Any
) -> TargetedUnitResult:
    executable = shutil.which("testssl") or shutil.which("testssl.sh") or "testssl"
    command = ToolCommand(
        TargetedTool.TESTSSL,
        [
            executable,
            "--warnings",
            "batch",
            "--color",
            "0",
            "--connect-timeout",
            "5",
            "--openssl-timeout",
            "5",
            "--protocols",
            "--server-defaults",
            "--header",
            "--vulnerable",
            "--jsonfile-pretty",
            "REPORT",
            f"{unit.ip}:{unit.port}",
        ],
        "file",
        14,
    )
    execution = executor.execute(command, **deadline)
    if execution.outcome != TargetedOutcome.COMPLETED and not execution.report_present:
        return _result(unit, execution)
    if execution.report_truncated:
        return TargetedUnitResult(
            unit,
            TargetedOutcome.FAILED,
            exit_code=execution.exit_code,
            reason_code=TargetedGapReason.OUTPUT_LIMIT,
        )
    if not execution.report_present:
        return TargetedUnitResult(
            unit,
            TargetedOutcome.FAILED,
            exit_code=execution.exit_code,
            reason_code=TargetedGapReason.MALFORMED_REPORT,
        )
    payload = parse_json_payload(execution.report)
    records, valid = _records(payload, unit)
    if not valid:
        if execution.outcome != TargetedOutcome.COMPLETED:
            return _result(unit, execution)
        malformed_scan_result = (
            isinstance(payload, Mapping)
            and isinstance(payload.get("scanResult"), list)
            and any(
                not isinstance(row, Mapping)
                or not {"id", "severity", "finding"}.issubset(row)
                for row in payload["scanResult"]
            )
        )
        reason = (
            TargetedGapReason.MALFORMED_REPORT
            if malformed_scan_result
            else (
                TargetedGapReason.WRONG_TARGET
                if isinstance(payload, (Mapping, list))
                else TargetedGapReason.MALFORMED_REPORT
            )
        )
        return TargetedUnitResult(
            unit,
            TargetedOutcome.FAILED,
            exit_code=execution.exit_code,
            reason_code=reason,
            diagnostic=execution.diagnostic or "testssl JSON report has an unsupported schema.",
        )
    issues = parse_testssl_json(execution.report, unit)
    if (
        len([row for row in records if _issue(row) is not None])
        > TARGETED_MAX_ISSUES_PER_UNIT
    ):
        return TargetedUnitResult(
            unit,
            TargetedOutcome.FAILED,
            issues=issues,
            exit_code=execution.exit_code,
            reason_code=TargetedGapReason.ISSUE_LIMIT,
        )
    return TargetedUnitResult(
        unit,
        execution.outcome,
        issues=issues,
        exit_code=execution.exit_code,
        reason_code=execution.reason_code,
        diagnostic=execution.diagnostic,
    )
