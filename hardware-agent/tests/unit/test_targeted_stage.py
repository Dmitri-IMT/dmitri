from __future__ import annotations

import threading

import pytest
from agent.scanner.models import HostInfo, PortInfo, ServiceInfo
from agent.scanner.progress import ScanEvent
from agent.targeted import stage
from agent.targeted.models import (
    TargetedGapReason,
    TargetedOutcome,
    TargetedStageSummary,
    TargetedTool,
    TargetedUnit,
    TargetedUnitResult,
)


class _Reporter:
    def __init__(self) -> None:
        self.events: list[ScanEvent] = []

    def emit(self, event: ScanEvent) -> None:
        self.events.append(event)


class _Executor:
    def __init__(self) -> None:
        self.calls = 0


def _host() -> HostInfo:
    return HostInfo(
        ip="192.168.1.10",
        hostname="target",
        ports=[
            PortInfo(
                port=443,
                protocol="tcp",
                state="open",
                service=ServiceInfo(name="https"),
            )
        ],
    )


def _units() -> list[TargetedUnit]:
    return [
        TargetedUnit("192.168.1.10", 443, "tcp", "https", TargetedTool.FFUF),
        TargetedUnit("192.168.1.10", 443, "tcp", "https", TargetedTool.NIKTO),
        TargetedUnit("192.168.1.10", 443, "tcp", "https", TargetedTool.TESTSSL),
    ]


def test_plan_limit_retains_bounded_endpoint_reasons(monkeypatch) -> None:
    hosts = [
        HostInfo(
            ip=f"10.0.{index // 254}.{index % 254 + 1}",
            hostname="target",
            ports=[PortInfo(port=80, service=ServiceInfo(name="http"))],
        )
        for index in range(150)
    ]
    monkeypatch.setattr(
        stage,
        "_adapter_for",
        lambda tool: lambda unit, executor, **kwargs: TargetedUnitResult(
            unit, TargetedOutcome.COMPLETED
        ),
    )

    summary = stage.run_targeted_stage(hosts, scan_mode="extensive")

    assert summary.eligible == 300
    assert summary.planned == 96
    assert summary.omitted == 204
    assert summary.omitted_unlisted == 108
    omitted = [
        result
        for host in hosts
        for result in host.targeted_results
        if result.reason_code == TargetedGapReason.PLAN_LIMIT
    ]
    assert len(omitted) == 96
    assert all(result.outcome == TargetedOutcome.SKIPPED for result in omitted)
    assert all(result.unit.port == 80 for result in omitted)


def _install_plan(monkeypatch: pytest.MonkeyPatch, units: list[TargetedUnit]) -> None:
    def select(hosts, *, scan_mode, summary=None):
        assert scan_mode in {"extensive", "max", "nspi"}
        if summary is not None:
            summary.eligible = len(units)
            summary.planned = len(units)
        return units

    monkeypatch.setattr(stage, "select_targeted_units", select)


@pytest.mark.parametrize("mode", ["quick", "standard"])
def test_ineligible_modes_do_not_build_a_plan_or_emit_events(
    monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    selected = False

    def forbidden(*args, **kwargs):
        nonlocal selected
        selected = True
        raise AssertionError("ineligible mode built a targeted plan")

    monkeypatch.setattr(stage, "select_targeted_units", forbidden)
    reporter = _Reporter()
    host = _host()

    summary = stage.run_targeted_stage(
        [host], scan_mode=mode, reporter=reporter, executor=_Executor()
    )

    assert selected is False
    assert summary == TargetedStageSummary()
    assert reporter.events == []
    assert host.targeted_results == []


@pytest.mark.parametrize("mode", ["extensive", "max", "nspi"])
def test_eligible_modes_dispatch_serially_in_deterministic_order(
    monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    units = _units()
    _install_plan(monkeypatch, units)
    reporter = _Reporter()
    executor = _Executor()
    dispatch: list[TargetedTool] = []
    active = 0
    peak = 0

    def adapter(unit, _executor, **kwargs):
        nonlocal active, peak
        assert _executor is executor
        active += 1
        peak = max(peak, active)
        dispatch.append(unit.tool)
        result = TargetedUnitResult(unit, TargetedOutcome.COMPLETED)
        active -= 1
        return result

    monkeypatch.setattr(stage, "_adapter_for", lambda tool: adapter)
    summary = stage.run_targeted_stage(
        [_host()], scan_mode=mode, reporter=reporter, executor=executor
    )

    assert dispatch == [unit.tool for unit in units]
    assert peak == 1
    assert summary.eligible == summary.planned == summary.completed == len(units)
    assert summary.failed == summary.timed_out == summary.skipped == 0
    assert [event.kind for event in reporter.events] == [
        "targeted_stage_started",
        "targeted_unit_done",
        "targeted_unit_done",
        "targeted_unit_done",
        "targeted_stage_done",
    ]
    unit_events = reporter.events[1:-1]
    assert [
        (event.units_done, event.units_total, event.outcome) for event in unit_events
    ] == [
        (1, 3, "completed"),
        (2, 3, "completed"),
        (3, 3, "completed"),
    ]
    done = reporter.events[-1]
    assert (done.units_completed, done.units_failed, done.units_timed_out) == (3, 0, 0)
    assert done.units_skipped == 0


def test_one_unit_failure_isolated_and_later_units_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    units = _units()
    _install_plan(monkeypatch, units)
    dispatch: list[TargetedTool] = []

    def adapter(unit, _executor, **kwargs):
        dispatch.append(unit.tool)
        if unit.tool == TargetedTool.FFUF:
            raise RuntimeError("tool failed")
        return TargetedUnitResult(unit, TargetedOutcome.COMPLETED)

    monkeypatch.setattr(stage, "_adapter_for", lambda tool: adapter)
    host = _host()
    summary = stage.run_targeted_stage(
        [host], scan_mode="extensive", executor=_Executor()
    )

    assert dispatch == [unit.tool for unit in units]
    assert [result.outcome for result in host.targeted_results] == [
        TargetedOutcome.FAILED,
        TargetedOutcome.COMPLETED,
        TargetedOutcome.COMPLETED,
    ]
    assert host.targeted_results[0].reason_code == TargetedGapReason.EXECUTION_ERROR
    assert summary.failed == 1
    assert summary.completed == 2


def test_failed_unit_logs_reason_and_redacts_diagnostic(monkeypatch, caplog):
    units = _units()[:1]
    _install_plan(monkeypatch, units)
    monkeypatch.setattr(
        stage,
        "_adapter_for",
        lambda tool: lambda unit, executor, **kwargs: TargetedUnitResult(
            unit,
            TargetedOutcome.FAILED,
            reason_code=TargetedGapReason.EXECUTION_ERROR,
            diagnostic="permission denied password=private-value\nsecond line",
        ),
    )
    with caplog.at_level("INFO", logger="agent.targeted.stage"):
        stage.run_targeted_stage([_host()], scan_mode="extensive", executor=_Executor())

    assert "reason=execution_error" in caplog.text
    assert "permission denied" in caplog.text
    assert "private-value" not in caplog.text


def test_stage_budget_skips_remaining_units_and_reaches_stage_done(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    units = _units()
    _install_plan(monkeypatch, units)
    monkeypatch.setattr(stage, "_stage_deadline", lambda *args, **kwargs: 0.0)
    monkeypatch.setattr(stage, "perf_counter", lambda: 1.0)
    monkeypatch.setattr(
        stage,
        "_adapter_for",
        lambda tool: pytest.fail("stage-budget gap must not spawn an adapter"),
    )
    reporter = _Reporter()
    host = _host()

    summary = stage.run_targeted_stage(
        [host], scan_mode="extensive", reporter=reporter, executor=_Executor()
    )

    assert summary.skipped == len(units)
    assert summary.completed == summary.failed == summary.timed_out == 0
    assert all(
        result.reason_code == TargetedGapReason.STAGE_BUDGET
        for result in host.targeted_results
    )
    assert [event.kind for event in reporter.events] == [
        "targeted_stage_started",
        "targeted_stage_done",
    ]
    done = reporter.events[-1]
    assert (
        done.units_completed,
        done.units_failed,
        done.units_timed_out,
        done.units_skipped,
    ) == (
        0,
        0,
        0,
        len(units),
    )


def test_stage_budget_covers_selected_unit_allowances(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    units = [_units()[0]] * 6
    _install_plan(monkeypatch, units)
    elapsed = 0.0
    dispatch: list[TargetedUnit] = []

    def clock() -> float:
        return elapsed

    def adapter(unit, _executor, **kwargs):
        nonlocal elapsed
        dispatch.append(unit)
        elapsed += 400.0
        return TargetedUnitResult(unit, TargetedOutcome.COMPLETED)

    monkeypatch.setattr(stage, "perf_counter", clock)
    monkeypatch.setattr(stage, "_adapter_for", lambda _tool: adapter)
    host = _host()

    summary = stage.run_targeted_stage(
        [host], scan_mode="extensive", executor=_Executor()
    )

    assert len(dispatch) == len(units)
    assert summary.completed == len(units)
    assert summary.skipped == 0


def test_overall_deadline_remains_hard_stage_budget_ceiling(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    units = [_units()[0]] * 4
    _install_plan(monkeypatch, units)
    elapsed = 0.0
    dispatch: list[TargetedUnit] = []

    def clock() -> float:
        return elapsed

    def adapter(unit, _executor, **kwargs):
        nonlocal elapsed
        dispatch.append(unit)
        elapsed += 200.0
        return TargetedUnitResult(unit, TargetedOutcome.COMPLETED)

    monkeypatch.setattr(stage, "perf_counter", clock)
    monkeypatch.setattr(stage, "_adapter_for", lambda _tool: adapter)
    host = _host()

    summary = stage.run_targeted_stage(
        [host],
        scan_mode="extensive",
        executor=_Executor(),
        overall_deadline=500.0,
    )

    assert len(dispatch) == 3
    assert summary.completed == 3
    assert summary.skipped == 1
    assert host.targeted_results[-1].reason_code == TargetedGapReason.SCAN_TIMEOUT


@pytest.mark.parametrize("mode", ["max", "nspi"])
def test_other_modes_keep_their_fixed_stage_budget(
    monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    monkeypatch.setattr(stage, "perf_counter", lambda: 100.0)

    deadline = stage._stage_deadline(mode, _units() * 40, None)

    assert deadline == 100.0 + stage.TARGETED_STAGE_TIMEOUT_S[mode]


def test_cancellation_stops_new_units_and_omits_stage_done(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    units = _units()
    _install_plan(monkeypatch, units)
    cancel_event = threading.Event()
    dispatch: list[TargetedTool] = []

    def adapter(unit, _executor, **kwargs):
        dispatch.append(unit.tool)
        cancel_event.set()
        return TargetedUnitResult(unit, TargetedOutcome.COMPLETED)

    monkeypatch.setattr(stage, "_adapter_for", lambda tool: adapter)
    reporter = _Reporter()
    host = _host()

    summary = stage.run_targeted_stage(
        [host],
        scan_mode="extensive",
        reporter=reporter,
        cancel_event=cancel_event,
        executor=_Executor(),
    )

    assert dispatch == [units[0].tool]
    assert summary.completed == 1
    assert [event.kind for event in reporter.events] == [
        "targeted_stage_started",
        "targeted_unit_done",
    ]
    assert summary.skipped == len(units) - 1
    assert [
        (result.outcome, result.reason_code) for result in host.targeted_results[1:]
    ] == [(TargetedOutcome.SKIPPED, TargetedGapReason.SCAN_CANCELLED)] * (
        len(units) - 1
    )


def test_overall_deadline_records_remaining_units_as_scan_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    units = _units()
    _install_plan(monkeypatch, units)
    monkeypatch.setattr(stage, "_stage_deadline", lambda *args, **kwargs: 0.0)
    monkeypatch.setattr(stage, "perf_counter", lambda: 1.0)
    monkeypatch.setattr(
        stage,
        "_adapter_for",
        lambda tool: pytest.fail("an overall-deadline stop must not spawn an adapter"),
    )
    reporter = _Reporter()
    host = _host()

    summary = stage.run_targeted_stage(
        [host],
        scan_mode="extensive",
        reporter=reporter,
        executor=_Executor(),
        overall_deadline=0.0,
    )

    assert summary.skipped == len(units)
    assert all(
        result.reason_code == TargetedGapReason.SCAN_TIMEOUT
        for result in host.targeted_results
    )
    assert [event.kind for event in reporter.events] == ["targeted_stage_started"]
