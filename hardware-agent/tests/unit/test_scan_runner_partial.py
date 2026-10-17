from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest
from agent.normalize.contracts import ScanPayload
from agent.normalize.coverage import extract_coverage
from agent.scanner import stages
from agent.scanner.errors import (
    BudgetExceeded,
    CircuitBreakerError,
    FatalScanError,
    ScanCancelled,
    UnitScanError,
)
from agent.scanner.models import (
    HostInfo,
    PortInfo,
    ScriptResult,
    ServiceInfo,
    StageCoverage,
)
from agent.scanner.nmap import NmapRunner
from agent.scanner.runner import ScanRunner, _record_not_run
from agent.targeted.models import (
    TargetedGapReason,
    TargetedIssue,
    TargetedObservation,
    TargetedOutcome,
    TargetedTool,
    TargetedUnit,
    TargetedUnitResult,
)


class _FakeReporter:
    def __init__(self) -> None:
        self.events: list = []

    def emit(self, event) -> None:
        self.events.append(event)


class _FakeRunner(NmapRunner):
    def __init__(self) -> None:
        self.nmap_path = "fake-nmap"

    def run_xml(self, arguments: list[str], timeout: float | None = None) -> ET.Element:
        return ET.fromstring("<nmaprun/>")


def _one_host() -> list[HostInfo]:
    return [HostInfo(ip="192.168.1.10", hostname="host-a")]


def _build_runner(
    monkeypatch: pytest.MonkeyPatch,
    *,
    hosts: list[HostInfo],
    port_stage=None,
    deep_stage=None,
    scan_mode: str = "standard",
    targeted_stage=None,
) -> tuple[ScanRunner, list[ScanPayload], list[Exception], _FakeReporter]:
    monkeypatch.setattr("agent.scanner.runner.check_network_connectivity", lambda: None)
    monkeypatch.setattr(
        "agent.scanner.runner.discover_hosts",
        lambda runner, subnet, timeout=None: hosts,
    )
    if port_stage is not None:
        monkeypatch.setattr(stages, "run_port_stage", port_stage)
    if deep_stage is not None:
        monkeypatch.setattr(stages, "run_deep_inspection_stage", deep_stage)
    if targeted_stage is not None:
        monkeypatch.setattr("agent.scanner.runner.run_targeted_stage", targeted_stage)
    completed: list[ScanPayload] = []
    errors: list[Exception] = []
    reporter = _FakeReporter()
    runner = ScanRunner(
        subnet="192.168.1.0/24",
        scan_mode=scan_mode,  # type: ignore[arg-type]
        reporter=reporter,
        on_complete=completed.append,
        on_error=errors.append,
        runner=_FakeRunner(),
    )
    return runner, completed, errors, reporter


def test_nse_failure_with_service_recovery_marks_payload_partial(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    host = _one_host()[0]

    def ports(*args, **kwargs):
        host.ports = [PortInfo(port=502, service=ServiceInfo(name="modbus-tcp"))]
        return 0

    def nse_failure(*args, **kwargs):
        raise UnitScanError("NSE failed")

    monkeypatch.setattr(stages, "run_nse_vulnerability_scan", nse_failure)
    monkeypatch.setattr(
        stages,
        "detect_services",
        lambda *args, **kwargs: [
            PortInfo(port=502, service=ServiceInfo(name="modbus", product="PLC"))
        ],
    )
    runner, completed, errors, _ = _build_runner(
        monkeypatch, hosts=[host], port_stage=ports
    )
    runner.run_blocking()

    assert errors == []
    assert completed[0].finding_evidence_policy_version == "1"
    assert completed[0].finding_observations == []
    assert completed[0].metadata["partial_result"] is True
    assert completed[0].metadata["terminated_by"] == "completed"
    assert completed[0].hosts[0].ports[0].service == "modbus"
    deep_coverage = next(
        unit for unit in completed[0].coverage if unit.stage == "deep_inspection"
    )
    assert deep_coverage.model_dump(mode="json") == {
        "ip": host.ip,
        "stage": "deep_inspection",
        "port": None,
        "protocol": None,
        "tool": None,
        "outcome": "partial",
        "reason_code": "nse_failed",
        "evidence_source": "service_recovery",
        "issue_keys": [],
        "observations": [],
    }


def test_runner_emits_standalone_nse_observations_separately_from_coverage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    host = _one_host()[0]
    host.ports = [
        PortInfo(
            port=445,
            scripts=[
                ScriptResult(
                    "unmapped-nse",
                    "Explicit negative response.",
                    {"state": "NOT VULNERABLE", "ids": {"CVE": "CVE-2020-1234"}},
                )
            ],
        )
    ]
    runner, completed, errors, _ = _build_runner(
        monkeypatch,
        hosts=[host],
        port_stage=lambda *args, **kwargs: 0,
        deep_stage=lambda *args, **kwargs: 0,
    )

    runner.run_blocking()

    assert errors == []
    assert completed[0].finding_evidence_policy_version == "1"
    assert len(completed[0].finding_observations) == 1
    assert completed[0].finding_observations[0].condition_key == "CVE-2020-1234"
    assert completed[0].finding_observations[0].result == "negative"
    assert all(not unit.observations for unit in completed[0].coverage)


def test_ot_deadline_marks_completed_scan_payload_partial(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(stages, "run_port_stage", lambda *args, **kwargs: 0)
    monkeypatch.setattr(stages, "run_deep_inspection_stage", lambda *args, **kwargs: 0)
    monkeypatch.setattr(
        stages,
        "run_ot_inspection_stage",
        lambda *args, **kwargs: stages.OtInspectionResult(
            stage_deadline_reached=True, stage_deadline_seconds=120
        ),
    )
    runner, completed, errors, _ = _build_runner(
        monkeypatch, hosts=_one_host(), scan_mode="nspi"
    )

    runner.run_blocking()

    assert errors == []
    assert completed[0].metadata["partial_result"] is True
    assert completed[0].metadata["modbus_stage_deadline_reached"] is True


def test_targeted_timeout_retains_endpoint_observation_and_issue_provenance() -> None:
    host = _one_host()[0]
    unit = TargetedUnit(host.ip, 80, "tcp", "http", TargetedTool.NIKTO)
    host.targeted_results.append(
        TargetedUnitResult(
            unit,
            TargetedOutcome.TIMED_OUT,
            issues=[
                TargetedIssue(
                    "web:exposure",
                    "Exposure",
                    "Description",
                    "high",
                    "Recommendation",
                    "Evidence",
                )
            ],
            observations=[
                TargetedObservation(
                    "web:administration:/admin",
                    "administration",
                    "Administration interface found",
                    "status=403; protected surface",
                    path="/admin",
                    rule_id="admin",
                    policy_version="v1",
                )
            ],
            reason_code=TargetedGapReason.UNIT_TIMEOUT,
        )
    )

    coverage = extract_coverage([host])

    assert len(coverage) == 1
    assert (str(coverage[0].ip), coverage[0].port, coverage[0].tool) == (
        host.ip,
        80,
        "nikto",
    )
    assert coverage[0].outcome == "timed_out"
    assert coverage[0].reason_code == "unit_timeout"
    assert coverage[0].evidence_source == "targeted_tool_partial_report"
    assert coverage[0].issue_keys == ["web:exposure"]
    assert coverage[0].observations[0].evidence == "status=403; protected surface"


def _stop(
    host: HostInfo,
    stage: str,
    terminated_by: str,
    *,
    targeted: bool,
    ot: bool = False,
):
    _record_not_run(
        [host],
        interrupted_stage=stage,
        terminated_by=terminated_by,
        ot=ot,
        targeted=targeted,
    )
    return [
        (unit.stage, unit.outcome, unit.reason_code, unit.evidence_source)
        for unit in extract_coverage([host])
    ]


def test_stop_records_stages_that_never_ran() -> None:
    host = _one_host()[0]
    assert _stop(host, "ports", "user_cancel", targeted=True) == [
        ("ports", "skipped", "scan_cancelled", "not_run")
    ]

    host = _one_host()[0]
    host.ports = [PortInfo(port=80, service=ServiceInfo(name="http"))]
    assert _stop(host, "ports", "user_cancel", targeted=True) == [
        ("ports", "skipped", "scan_cancelled", "not_run"),
        ("deep_inspection", "skipped", "scan_cancelled", "not_run"),
        ("targeted_assessment", "skipped", "scan_cancelled", "not_run"),
    ]
    targeted_line = extract_coverage([host])[-1]
    assert (targeted_line.port, targeted_line.tool) == (None, None)

    host = _one_host()[0]
    host.ports = [PortInfo(port=80, service=ServiceInfo(name="http"))]
    assert _stop(host, "deep_inspection", "timeout", targeted=False) == [
        ("deep_inspection", "skipped", "scan_timeout", "not_run")
    ]


def test_stop_before_ot_records_ot_only_for_modbus_hosts() -> None:
    modbus = _one_host()[0]
    modbus.ports = [PortInfo(port=502, service=ServiceInfo(name="modbus"))]
    assert _stop(modbus, "deep_inspection", "timeout", targeted=False, ot=True) == [
        ("deep_inspection", "skipped", "scan_timeout", "not_run"),
        ("ot_inspection", "skipped", "scan_timeout", "not_run"),
    ]

    web = _one_host()[0]
    web.ports = [PortInfo(port=80, service=ServiceInfo(name="http"))]
    assert _stop(web, "deep_inspection", "timeout", targeted=False, ot=True) == [
        ("deep_inspection", "skipped", "scan_timeout", "not_run")
    ]

    modbus = _one_host()[0]
    modbus.ports = [PortInfo(port=502, service=ServiceInfo(name="modbus"))]
    modbus.stage_coverage.append(StageCoverage("ports", "completed", "nmap_ports"))
    modbus.stage_coverage.append(
        StageCoverage("deep_inspection", "completed", "nmap_nse")
    )
    assert _stop(modbus, "ot_inspection", "user_cancel", targeted=False, ot=True) == [
        ("ports", "completed", None, "nmap_ports"),
        ("deep_inspection", "completed", None, "nmap_nse"),
    ]


def test_stop_keeps_recorded_stages_and_leaves_targeted_stage_to_itself() -> None:
    host = _one_host()[0]
    host.ports = [PortInfo(port=80, service=ServiceInfo(name="http"))]
    host.stage_coverage.append(StageCoverage("ports", "completed", "nmap_ports"))
    host.stage_coverage.append(
        StageCoverage("deep_inspection", "completed", "nmap_nse")
    )
    assert _stop(host, "targeted_assessment", "error", targeted=True) == [
        ("ports", "completed", None, "nmap_ports"),
        ("deep_inspection", "completed", None, "nmap_nse"),
    ]


def test_targeted_unit_skipped_by_a_stop_reports_not_run() -> None:
    host = _one_host()[0]
    unit = TargetedUnit(host.ip, 80, "tcp", "http", TargetedTool.NIKTO)
    host.targeted_results.append(
        TargetedUnitResult(
            unit,
            TargetedOutcome.SKIPPED,
            reason_code=TargetedGapReason.SCAN_CANCELLED,
        )
    )

    [coverage] = extract_coverage([host])

    assert (coverage.port, coverage.tool, coverage.outcome) == (80, "nikto", "skipped")
    assert coverage.reason_code == "scan_cancelled"
    assert coverage.evidence_source == "not_run"


class TestPostDiscoveryFatal:
    def test_fatal_after_discovery_finalizes_partial(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def boom(*args, **kwargs):
            raise FatalScanError("ports blew up")

        runner, completed, errors, _ = _build_runner(
            monkeypatch, hosts=_one_host(), port_stage=boom
        )
        runner._run()

        assert len(completed) == 1
        assert len(errors) == 0
        meta = completed[0].metadata
        assert meta["partial_result"] is True
        assert meta["interrupted_stage"] == "ports"
        assert meta["terminated_by"] == "error"

    def test_partial_payload_keeps_discovered_devices(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        host = _one_host()[0]
        host.ports = [
            PortInfo(
                port=445,
                scripts=[
                    ScriptResult(
                        "unmapped-nse",
                        "Explicit negative response.",
                        {
                            "state": "NOT VULNERABLE",
                            "ids": {"CVE": "CVE-2020-1234"},
                        },
                    )
                ],
            )
        ]

        def boom(*args, **kwargs):
            raise FatalScanError("ports blew up")

        runner, completed, _, _ = _build_runner(
            monkeypatch, hosts=[host], port_stage=boom
        )
        runner._run()

        payload = completed[0]
        assert payload.finding_evidence_policy_version == "1"
        assert [item.condition_key for item in payload.finding_observations] == [
            "CVE-2020-1234"
        ]
        assert [str(device.ip) for device in payload.hosts] == ["192.168.1.10"]

    def test_partial_payload_bounds_oversized_unknown_nse_state(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        host = _one_host()[0]
        oversized_state = "ERROR " + ("x" * 200)
        host.ports = [
            PortInfo(
                port=445,
                scripts=[
                    ScriptResult(
                        "unmapped-nse",
                        "The script returned an unsupported state.",
                        {
                            "state": oversized_state,
                            "ids": {"CVE": "CVE-2024-1234"},
                        },
                    )
                ],
            )
        ]

        def boom(*args, **kwargs):
            raise FatalScanError("ports blew up")

        runner, completed, errors, _ = _build_runner(
            monkeypatch, hosts=[host], port_stage=boom
        )
        runner._run()

        assert errors == []
        payload = completed[0]
        assert payload.metadata["partial_result"] is True
        assert len(payload.finding_observations) == 1
        observation = payload.finding_observations[0]
        assert observation.result == "inconclusive"
        assert observation.facts == {
            "vulnerability_state": oversized_state.upper()[:160]
        }


class TestPostDiscoveryUnexpected:
    def test_unexpected_after_discovery_finalizes_partial(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def boom(*args, **kwargs):
            raise RuntimeError("something unforeseen")

        runner, completed, errors, _ = _build_runner(
            monkeypatch, hosts=_one_host(), port_stage=boom
        )
        runner._run()

        assert len(completed) == 1
        assert len(errors) == 0
        payload = completed[0]
        assert payload.finding_evidence_policy_version == "1"
        assert payload.finding_observations == []
        assert payload.metadata["partial_result"] is True
        assert payload.metadata["terminated_by"] == "error"
        assert [str(device.ip) for device in payload.hosts] == ["192.168.1.10"]

    def test_unexpected_before_discovery_calls_on_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "agent.scanner.runner.check_network_connectivity", lambda: None
        )

        def boom(runner, subnet, timeout=None):
            raise RuntimeError("discovery exploded")

        monkeypatch.setattr("agent.scanner.runner.discover_hosts", boom)
        completed: list[ScanPayload] = []
        errors: list[Exception] = []
        runner = ScanRunner(
            subnet="192.168.1.0/24",
            scan_mode="standard",
            on_complete=completed.append,
            on_error=errors.append,
            runner=_FakeRunner(),
        )
        runner._run()

        assert len(completed) == 0
        assert len(errors) == 1
        assert isinstance(errors[0], RuntimeError)


class TestFatalBeforeDiscovery:
    def test_fatal_before_discovery_calls_on_error_no_payload(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "agent.scanner.runner.check_network_connectivity", lambda: None
        )

        def boom(runner, subnet, timeout=None):
            raise FatalScanError("discovery failed")

        monkeypatch.setattr("agent.scanner.runner.discover_hosts", boom)
        completed: list[ScanPayload] = []
        errors: list[Exception] = []
        runner = ScanRunner(
            subnet="192.168.1.0/24",
            scan_mode="standard",
            on_complete=completed.append,
            on_error=errors.append,
            runner=_FakeRunner(),
        )
        runner._run()

        assert len(completed) == 0
        assert len(errors) == 1
        assert isinstance(errors[0], FatalScanError)


class TestTimeout:
    def test_budget_exceeded_finalizes_partial_timeout(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def boom(*args, **kwargs):
            raise BudgetExceeded()

        runner, completed, _, _ = _build_runner(
            monkeypatch, hosts=_one_host(), port_stage=boom
        )
        runner._run()

        assert len(completed) == 1
        meta = completed[0].metadata
        assert meta["partial_result"] is True
        assert meta["interrupted_stage"] == "ports"
        assert meta["terminated_by"] == "timeout"

    def test_circuit_breaker_finalizes_partial_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def boom(*args, **kwargs):
            raise CircuitBreakerError()

        runner, completed, _, _ = _build_runner(
            monkeypatch, hosts=_one_host(), port_stage=boom
        )
        runner._run()

        assert len(completed) == 1
        meta = completed[0].metadata
        assert meta["partial_result"] is True
        assert meta["terminated_by"] == "error"


class TestZeroHosts:
    def test_zero_hosts_yields_non_partial_completed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        runner, completed, errors, _ = _build_runner(monkeypatch, hosts=[])
        runner._run()

        assert len(completed) == 1
        assert len(errors) == 0
        meta = completed[0].metadata
        assert meta["partial_result"] is not True
        assert meta["terminated_by"] == "completed"
        assert "interrupted_stage" not in meta

    def test_zero_hosts_has_no_devices(self, monkeypatch: pytest.MonkeyPatch) -> None:
        runner, completed, _, _ = _build_runner(monkeypatch, hosts=[])
        runner._run()

        assert completed[0].hosts == []


class TestTargetedInterruption:
    @pytest.mark.parametrize(
        ("exception", "terminated_by"),
        [
            (BudgetExceeded(), "timeout"),
            (FatalScanError("targeted failed"), "error"),
        ],
    )
    def test_targeted_interruptions_retain_partial_stage_metadata(
        self,
        monkeypatch: pytest.MonkeyPatch,
        exception: Exception,
        terminated_by: str,
    ) -> None:
        def targeted_stage(*args, **kwargs):
            raise exception

        runner, completed, errors, _ = _build_runner(
            monkeypatch,
            hosts=_one_host(),
            port_stage=lambda *args, **kwargs: 0,
            deep_stage=lambda *args, **kwargs: 0,
            scan_mode="extensive",
            targeted_stage=targeted_stage,
        )

        runner._run()

        assert errors == []
        assert len(completed) == 1
        metadata = completed[0].metadata
        assert metadata["partial_result"] is True
        assert metadata["interrupted_stage"] == "targeted_assessment"
        assert metadata["terminated_by"] == terminated_by

    def test_targeted_cancellation_retains_hosts_and_previous_findings(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        host = _one_host()[0]
        host.ports = []
        from agent.scanner.models import ScriptResult

        host.host_scripts = [
            ScriptResult(
                "banner",
                "CVE-2024-1234 is present",
            )
        ]

        def targeted_stage(*args, **kwargs):
            raise ScanCancelled()

        runner, completed, errors, _ = _build_runner(
            monkeypatch,
            hosts=[host],
            port_stage=lambda *args, **kwargs: 0,
            deep_stage=lambda *args, **kwargs: 0,
            scan_mode="extensive",
            targeted_stage=targeted_stage,
        )

        runner._run()

        assert errors == []
        assert len(completed) == 1
        payload = completed[0]
        assert [str(device.ip) for device in payload.hosts] == [host.ip]
        assert len(payload.findings) == 1
        assert payload.metadata["interrupted_stage"] == "targeted_assessment"
        assert payload.metadata["terminated_by"] == "user_cancel"

    def test_cancellation_after_completed_targeted_unit_retains_targeted_finding(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        host = _one_host()[0]
        host.ports = [
            PortInfo(port=443, service=ServiceInfo(name="https")),
        ]
        issue = TargetedIssue(
            issue_key="tls:weak-cipher:rc4",
            title="RC4 cipher accepted",
            description="The endpoint accepts RC4.",
            severity="high",
            recommendation="Disable RC4.",
            evidence="RC4",
        )

        def adapter(unit, _executor, **kwargs):
            kwargs["cancel_event"].set()
            return TargetedUnitResult(
                unit,
                TargetedOutcome.COMPLETED,
                issues=[issue],
            )

        monkeypatch.setattr("agent.targeted.stage._adapter_for", lambda tool: adapter)
        runner, completed, errors, _ = _build_runner(
            monkeypatch,
            hosts=[host],
            port_stage=lambda *args, **kwargs: 0,
            deep_stage=lambda *args, **kwargs: 0,
            scan_mode="extensive",
        )

        runner._run()

        assert errors == []
        assert len(completed) == 1
        payload = completed[0]
        assert payload.metadata["interrupted_stage"] == "targeted_assessment"
        assert payload.metadata["terminated_by"] == "user_cancel"
        assert len(payload.findings) == 1
        assert payload.findings[0].source == "targeted_service_assessment"


class TestCompletedWithSkippedHosts:
    def test_marks_payload_partial_when_port_stage_skips_host(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        runner, completed, errors, _ = _build_runner(
            monkeypatch,
            hosts=_one_host(),
            port_stage=lambda *args, **kwargs: 1,
        )

        runner._run()

        assert len(completed) == 1
        assert errors == []
        metadata = completed[0].metadata
        assert metadata["partial_result"] is True
        assert metadata["terminated_by"] == "completed"
        assert metadata.get("interrupted_stage") is None

    def test_marks_payload_partial_when_deep_stage_skips_host(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        runner, completed, errors, _ = _build_runner(
            monkeypatch,
            hosts=_one_host(),
            port_stage=lambda *args, **kwargs: 0,
            deep_stage=lambda *args, **kwargs: 1,
        )

        runner._run()

        assert errors == []
        metadata = completed[0].metadata
        assert metadata["partial_result"] is True
        assert metadata["terminated_by"] == "completed"
        assert metadata.get("interrupted_stage") is None

    def test_port_skip_has_priority_when_both_stages_skip(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        runner, completed, _, _ = _build_runner(
            monkeypatch,
            hosts=_one_host(),
            port_stage=lambda *args, **kwargs: 1,
            deep_stage=lambda *args, **kwargs: 1,
        )

        runner._run()

        metadata = completed[0].metadata
        assert metadata["partial_result"] is True
        assert metadata["terminated_by"] == "completed"
        assert metadata.get("interrupted_stage") is None

    def test_zero_skips_finishes_complete(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        runner, completed, _, _ = _build_runner(
            monkeypatch,
            hosts=_one_host(),
            port_stage=lambda *args, **kwargs: 0,
            deep_stage=lambda *args, **kwargs: 0,
        )

        runner._run()

        metadata = completed[0].metadata
        assert metadata["partial_result"] is False
        assert metadata["terminated_by"] == "completed"
        assert "interrupted_stage" not in metadata
