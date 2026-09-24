"""Serial dispatch for the bounded service-targeted assessment."""

from __future__ import annotations

import threading
from time import perf_counter
from typing import Callable

from agent.config import TARGETED_MODES, TARGETED_STAGE_TIMEOUT_S
from agent.scanner.errors import BudgetExceeded, ScanCancelled
from agent.scanner.models import HostInfo
from agent.scanner.progress import ScanEvent, ScanReporter
from agent.targeted.cleartext import run_ftp_check, run_telnet_check
from agent.targeted.executor import TargetedExecutor
from agent.targeted.models import (
    TargetedGapReason,
    TargetedOutcome,
    TargetedStageSummary,
    TargetedTool,
    TargetedUnit,
    TargetedUnitResult,
)
from agent.targeted.selection import (
    select_omitted_targeted_units,
    select_targeted_units,
)
from agent.targeted.smb import run_enum4linux
from agent.targeted.ssh import run_ssh_audit
from agent.targeted.tls import run_testssl
from agent.targeted.web import run_ffuf, run_nikto


def _adapter_for(tool: TargetedTool) -> Callable[..., TargetedUnitResult]:
    """Resolve from module globals so focused tests can replace an adapter."""

    return {
        TargetedTool.FFUF: run_ffuf,
        TargetedTool.NIKTO: run_nikto,
        TargetedTool.TESTSSL: run_testssl,
        TargetedTool.ENUM4LINUX: run_enum4linux,
        TargetedTool.SSH_AUDIT: run_ssh_audit,
        TargetedTool.FTP_CHECK: run_ftp_check,
        TargetedTool.TELNET_CHECK: run_telnet_check,
    }[tool]


def _emit(
    reporter: ScanReporter | None,
    kind: str,
    *,
    message: str = "",
    units_total: int = 0,
    units_done: int = 0,
    units_completed: int = 0,
    units_failed: int = 0,
    units_timed_out: int = 0,
    units_skipped: int = 0,
    outcome: str = "",
    ip: str | None = None,
) -> None:
    if reporter is None:
        return
    reporter.emit(
        ScanEvent(
            kind=kind,  # type: ignore[arg-type]
            message=message,
            units_total=units_total,
            units_done=units_done,
            units_completed=units_completed,
            units_failed=units_failed,
            units_timed_out=units_timed_out,
            units_skipped=units_skipped,
            outcome=outcome,
            ip=ip,
        )
    )


def _record(
    summary: TargetedStageSummary,
    result: TargetedUnitResult,
) -> None:
    outcome = result.outcome
    summary.per_tool[result.unit.tool][outcome] += 1
    if result.reason_code is not None:
        summary.gap_by_tool[result.unit.tool][result.reason_code] += 1
    if outcome == TargetedOutcome.COMPLETED:
        summary.completed += 1
    elif outcome == TargetedOutcome.FAILED:
        summary.failed += 1
    elif outcome == TargetedOutcome.TIMED_OUT:
        summary.timed_out += 1
    elif outcome == TargetedOutcome.SKIPPED:
        summary.skipped += 1
    summary.finding_candidates += len(result.issues)
    summary.observation_candidates += len(result.observations)


def _stage_deadline(
    scan_mode: str,
    overall_deadline: float | None,
) -> float:
    deadline = perf_counter() + TARGETED_STAGE_TIMEOUT_S[scan_mode]
    return min(deadline, overall_deadline) if overall_deadline is not None else deadline


def _deadline_scope(
    deadline: float,
    overall_deadline: float | None,
) -> str:
    if overall_deadline is not None and overall_deadline <= deadline:
        return "overall"
    return "stage"


def _skipped_result(unit: TargetedUnit) -> TargetedUnitResult:
    return TargetedUnitResult(
        unit,
        TargetedOutcome.SKIPPED,
        reason_code=TargetedGapReason.STAGE_BUDGET,
    )


def run_targeted_stage(
    hosts: list[HostInfo],
    *,
    scan_mode: str,
    reporter: ScanReporter | None = None,
    cancel_event: threading.Event | None = None,
    executor: TargetedExecutor | None = None,
    overall_deadline: float | None = None,
    wordlist: str | None = None,
    scan_id: str = "",
) -> TargetedStageSummary:
    """Select and execute targeted units serially.

    A stage-budget expiry is an isolated coverage gap and therefore reaches
    normalization. Cancellation and the overall scan deadline return control
    to ``ScanRunner`` so its existing partial-result semantics remain intact.
    """

    summary = TargetedStageSummary()
    if scan_mode not in TARGETED_MODES:
        return summary

    units = select_targeted_units(hosts, scan_mode=scan_mode, summary=summary)
    _emit(
        reporter,
        "targeted_stage_started",
        message="Assessing supported services…",
        units_total=summary.eligible,
    )

    host_by_ip = {host.ip: host for host in hosts}
    if summary.omitted:
        omitted_units = select_omitted_targeted_units(hosts, units)
        summary.omitted_unlisted = summary.omitted - len(omitted_units)
        for unit in omitted_units:
            host_by_ip[unit.ip].targeted_results.append(
                TargetedUnitResult(
                    unit,
                    TargetedOutcome.SKIPPED,
                    reason_code=TargetedGapReason.PLAN_LIMIT,
                )
            )
    active_executor = executor or TargetedExecutor()
    stage_deadline = _stage_deadline(scan_mode, overall_deadline)
    interrupted = False
    for index, unit in enumerate(units):
        if cancel_event is not None and cancel_event.is_set():
            interrupted = True
            break
        now = perf_counter()
        if now >= stage_deadline:
            if _deadline_scope(stage_deadline, overall_deadline) == "overall":
                interrupted = True
                break
            for remaining in units[index:]:
                result = _skipped_result(remaining)
                host_by_ip[remaining.ip].targeted_results.append(result)
                _record(summary, result)
            break

        adapter = _adapter_for(unit.tool)
        try:
            adapter_kwargs: dict[str, object] = {
                "cancel_event": cancel_event,
                "stage_deadline": stage_deadline,
                "overall_deadline": overall_deadline,
            }
            if unit.tool == TargetedTool.FFUF:
                adapter_kwargs.update(wordlist=wordlist, scan_id=scan_id)
            result = adapter(unit, active_executor, **adapter_kwargs)
        except (ScanCancelled, BudgetExceeded):
            raise
        except Exception as exc:  # one adapter must not stop later units
            result = TargetedUnitResult(
                unit,
                TargetedOutcome.FAILED,
                reason_code=TargetedGapReason.EXECUTION_ERROR,
                diagnostic=str(exc)[:512],
            )
        host_by_ip[unit.ip].targeted_results.append(result)
        _record(summary, result)
        _emit(
            reporter,
            "targeted_unit_done",
            message=f"Checked {unit.ip}:{unit.port} with {unit.tool.value}",
            units_total=summary.eligible,
            units_done=(
                summary.completed + summary.failed + summary.timed_out + summary.skipped
            ),
            outcome=result.outcome.value,
            ip=unit.ip,
        )

        if result.outcome == TargetedOutcome.TIMED_OUT and overall_deadline is not None:
            if perf_counter() >= overall_deadline:
                interrupted = True
                break

    if cancel_event is not None and cancel_event.is_set():
        interrupted = True
    if not interrupted:
        _emit(
            reporter,
            "targeted_stage_done",
            message="Targeted service assessment complete",
            units_total=summary.eligible,
            units_completed=summary.completed,
            units_failed=summary.failed,
            units_timed_out=summary.timed_out,
            units_skipped=summary.skipped,
        )
    return summary


__all__ = ["run_targeted_stage"]
