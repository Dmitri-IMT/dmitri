from __future__ import annotations

import xml.etree.ElementTree as ET
from uuid import uuid4

import pytest
from agent.config import AgentSettings
from agent.normalize.contracts import ScanPayload
from agent.ot.modbus.models import ModbusService, ModbusUnit
from agent.scanner import stages
from agent.scanner.models import HostInfo, MacIdentity, PortInfo, ServiceInfo
from agent.scanner.nmap import NmapRunner
from agent.scanner.progress import ScanEvent
from agent.scanner.runner import ScanRunner
from agent.targeted.models import TargetedStageSummary
from agent.utils.network import LocalNetworkInfo


class _FakeReporter:
    def __init__(self) -> None:
        self.events: list[ScanEvent] = []

    def emit(self, event: ScanEvent) -> None:
        self.events.append(event)


class _FakeRunner(NmapRunner):
    def __init__(self) -> None:
        self.nmap_path = "fake-nmap"

    def run_xml(
        self, arguments: list[str], timeout: float | None = None
    ) -> ET.Element:
        return ET.fromstring("<nmaprun/>")


class _BoomRunner(NmapRunner):
    def __init__(self) -> None:
        self.nmap_path = "fake-nmap"

    def run_xml(
        self, arguments: list[str], timeout: float | None = None
    ) -> ET.Element:
        raise RuntimeError("nmap exploded")


def _kinds(events: list[ScanEvent]) -> list[str]:
    return [event.kind for event in events]


def _assessable_host() -> HostInfo:
    return HostInfo(
        ip="192.168.1.10",
        hostname="camera.local",
        identity=MacIdentity(mac="00:11:22:33:44:55", vendor="Acme"),
        ports=[
            PortInfo(
                port=80,
                protocol="tcp",
                state="open",
                service=ServiceInfo(name="http", product="Acme Camera"),
            ),
            PortInfo(port=443, protocol="tcp", state="closed"),
        ],
    )


@pytest.mark.parametrize("scan_mode", ["quick", "standard", "extensive", "nspi", "max"])
def test_build_payload_assesses_each_mode_once_and_preserves_raw_inventory(
    monkeypatch: pytest.MonkeyPatch, scan_mode: str
) -> None:
    host = _assessable_host()
    original = (
        host.ip,
        host.hostname,
        host.identity,
        [
            (port.port, port.protocol, port.state, port.service.name)
            for port in host.ports
        ],
    )
    calls = 0
    from agent.assessment.analyzer import assess_hosts as real_assess_hosts

    def counted_assessment(hosts):
        nonlocal calls
        calls += 1
        return real_assess_hosts(hosts)

    monkeypatch.setattr("agent.scanner.runner.assess_hosts", counted_assessment)
    runner = ScanRunner(
        subnet="192.168.1.0/24",
        scan_mode=scan_mode,  # type: ignore[arg-type]
        runner=_FakeRunner(),
    )
    payload = runner._build_payload(
        scan_id=uuid4(),
        settings=AgentSettings(scan_mode=scan_mode),  # type: ignore[arg-type]
        network_info=LocalNetworkInfo(
            ip="192.168.1.2",
            netmask="255.255.255.0",
            subnet="192.168.1.0/24",
            interface="test",
        ),
        runner=_FakeRunner(),
        started_counter=0.0,
        hosts=[host],
        partial_result=False,
        interrupted_stage=None,
        terminated_by="completed",
    )

    assert calls == 1
    assert payload.assessment_policy_version == "2026-09-15.2"
    assert payload.hosts[0].machine_type is not None
    assert payload.hosts[0].device_profile is not None
    assert [(str(item.ip), item.protocol, item.port) for item in payload.exposures] == [
        ("192.168.1.10", "tcp", 80)
    ]
    assert (
        host.ip,
        host.hostname,
        host.identity,
        [
            (port.port, port.protocol, port.state, port.service.name)
            for port in host.ports
        ],
    ) == original
    assert ScanPayload.model_validate_json(payload.model_dump_json()) == payload


@pytest.mark.parametrize(
    "terminated_by", ["completed", "error", "timeout", "user_cancel"]
)
def test_partial_payload_is_assessed_for_every_accepted_termination(
    terminated_by: str,
) -> None:
    completed: list[ScanPayload] = []
    runner = ScanRunner(
        subnet="192.168.1.0/24",
        scan_mode="standard",
        on_complete=completed.append,
        runner=_FakeRunner(),
    )
    runner._finalize_partial(
        scan_id=uuid4(),
        settings=AgentSettings(scan_mode="standard"),
        network_info=LocalNetworkInfo(
            ip="192.168.1.2",
            netmask="255.255.255.0",
            subnet="192.168.1.0/24",
            interface="test",
        ),
        runner=_FakeRunner(),
        started_counter=0.0,
        hosts=[_assessable_host()],
        interrupted_stage=None if terminated_by == "completed" else "ports",
        terminated_by=terminated_by,
        message="partial",
    )

    assert len(completed) == 1
    payload = completed[0]
    assert payload.metadata is not None
    assert payload.metadata["partial_result"] is True
    assert payload.metadata["terminated_by"] == terminated_by
    assert payload.hosts[0].device_profile is not None
    assert len(payload.exposures) == 1


class TestScanRunnerSuccess:
    def test_nspi_runs_ot_inventory_after_existing_deep_stage(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "agent.scanner.runner.check_network_connectivity", lambda: None
        )
        host = HostInfo(ip="192.168.10.30", hostname="plc-lab")
        monkeypatch.setattr(
            "agent.scanner.runner.discover_hosts",
            lambda runner, subnet, timeout=None: [host],
        )
        order = []

        def port_stage(runner, settings, hosts, **kwargs):
            order.append("ports")
            hosts[0].ports = [
                PortInfo(port=502, service=ServiceInfo(name="modbus"))
            ]

        def deep_stage(runner, settings, hosts, **kwargs):
            order.append("deep")

        def ot_stage(settings, hosts, **kwargs):
            order.append("ot")
            hosts[0].industrial_services = [
                ModbusService(
                    port=502,
                    confidence="confirmed",
                    units=[ModbusUnit(unit_id=1, status="responding")],
                    requests_sent=1,
                )
            ]

        monkeypatch.setattr("agent.scanner.stages.run_port_stage", port_stage)
        monkeypatch.setattr(
            "agent.scanner.stages.run_deep_inspection_stage",
            deep_stage,
        )
        monkeypatch.setattr(
            "agent.scanner.stages.run_ot_inspection_stage",
            ot_stage,
        )
        completed = []
        scan_runner = ScanRunner(
            subnet="192.168.10.0/24",
            scan_mode="nspi",
            on_complete=completed.append,
            runner=_FakeRunner(),
        )

        scan_runner.run_blocking()

        assert order == ["ports", "deep", "ot"]
        assert len(completed) == 1
        assert completed[0].metadata["nspi_submode"] == "inventory"
        assert completed[0].metadata["modbus_confirmed"] == 1
        assert completed[0].hosts[0].industrial_services[0].units[0].unit_id == 1

    def test_emits_discovery_normalize_completed_in_order(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "agent.scanner.runner.check_network_connectivity", lambda: None
        )
        reporter = _FakeReporter()
        runner = ScanRunner(
            subnet="192.168.1.0/24",
            scan_mode="standard",
            reporter=reporter,
            runner=_FakeRunner(),
        )
        runner._run()

        kinds = _kinds(reporter.events)
        assert kinds[0] == "discovery_started"
        assert "hosts_found" in kinds
        assert "normalize_started" in kinds
        assert kinds[-1] == "completed"
        assert kinds.index("discovery_started") < kinds.index("hosts_found")
        assert kinds.index("hosts_found") < kinds.index("normalize_started")
        assert kinds.index("normalize_started") < kinds.index("completed")
        assert "failed" not in kinds

    def test_hosts_found_reports_zero_total_for_empty_run(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "agent.scanner.runner.check_network_connectivity", lambda: None
        )
        reporter = _FakeReporter()
        runner = ScanRunner(
            subnet="192.168.1.0/24",
            scan_mode="standard",
            reporter=reporter,
            runner=_FakeRunner(),
        )
        runner._run()

        hosts_found = next(e for e in reporter.events if e.kind == "hosts_found")
        assert hosts_found.hosts_total == 0

    def test_no_port_or_deep_events_when_no_hosts(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "agent.scanner.runner.check_network_connectivity", lambda: None
        )
        reporter = _FakeReporter()
        runner = ScanRunner(
            subnet="192.168.1.0/24",
            scan_mode="standard",
            reporter=reporter,
            runner=_FakeRunner(),
        )
        runner._run()

        kinds = _kinds(reporter.events)
        assert "port_stage_started" not in kinds
        assert "deep_stage_started" not in kinds

    def test_eligible_zero_host_scan_runs_zero_targeted_stage(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "agent.scanner.runner.check_network_connectivity", lambda: None
        )
        calls: list[list[HostInfo]] = []

        def targeted_stage(hosts, *, reporter=None, **kwargs):
            calls.append(hosts)
            reporter.emit(ScanEvent(kind="targeted_stage_started", units_total=0))
            reporter.emit(ScanEvent(kind="targeted_stage_done", units_total=0))
            return TargetedStageSummary()

        monkeypatch.setattr("agent.scanner.runner.run_targeted_stage", targeted_stage)
        reporter = _FakeReporter()
        completed: list[ScanPayload] = []
        ScanRunner(
            subnet="192.168.1.0/24",
            scan_mode="extensive",
            reporter=reporter,
            on_complete=completed.append,
            runner=_FakeRunner(),
        ).run_blocking()

        assert calls == [[]]
        kinds = _kinds(reporter.events)
        assert kinds.index("targeted_stage_started") < kinds.index("normalize_started")
        assert kinds.index("targeted_stage_done") < kinds.index("normalize_started")
        assert completed[0].metadata["targeted_units_eligible"] == 0
        assert completed[0].metadata["targeted_units_planned"] == 0

    @pytest.mark.parametrize("scan_mode", ["extensive", "max", "nspi"])
    def test_targeted_stage_is_last_probe_before_normalization(
        self, monkeypatch: pytest.MonkeyPatch, scan_mode: str
    ) -> None:
        monkeypatch.setattr(
            "agent.scanner.runner.check_network_connectivity", lambda: None
        )
        host = HostInfo(ip="192.168.1.10", hostname="target")
        monkeypatch.setattr(
            "agent.scanner.runner.discover_hosts",
            lambda runner, subnet, timeout=None: [host],
        )
        order: list[str] = []

        def port_stage(*args, **kwargs):
            order.append("ports")
            return 0

        def deep_stage(*args, **kwargs):
            order.append("deep")
            return 0

        def ot_stage(*args, **kwargs):
            order.append("ot")
            return stages.OtInspectionResult()

        def targeted_stage(hosts, *, reporter=None, **kwargs):
            order.append("targeted")
            assert kwargs["scan_mode"] == scan_mode
            assert reporter is not None
            reporter.emit(ScanEvent(kind="targeted_stage_started", units_total=0))
            reporter.emit(
                ScanEvent(
                    kind="targeted_stage_done",
                    units_total=0,
                )
            )
            return TargetedStageSummary()

        monkeypatch.setattr(stages, "run_port_stage", port_stage)
        monkeypatch.setattr(stages, "run_deep_inspection_stage", deep_stage)
        monkeypatch.setattr(stages, "run_ot_inspection_stage", ot_stage)
        monkeypatch.setattr("agent.scanner.runner.run_targeted_stage", targeted_stage)
        reporter = _FakeReporter()
        completed: list[ScanPayload] = []
        runner = ScanRunner(
            subnet="192.168.1.0/24",
            scan_mode=scan_mode,  # type: ignore[arg-type]
            reporter=reporter,
            on_complete=completed.append,
            runner=_FakeRunner(),
        )

        runner.run_blocking()

        expected_order = (
            ["ports", "deep", "ot", "targeted"]
            if scan_mode == "nspi"
            else ["ports", "deep", "targeted"]
        )
        assert order == expected_order
        kinds = _kinds(reporter.events)
        targeted_index = kinds.index("targeted_stage_started")
        assert kinds.index("normalize_started") > targeted_index
        assert kinds.index("targeted_stage_done") < kinds.index("normalize_started")
        assert completed[0].metadata["targeted_units_eligible"] == 0

    @pytest.mark.parametrize("scan_mode", ["quick", "standard"])
    def test_quick_and_standard_never_call_or_emit_targeted_stage(
        self, monkeypatch: pytest.MonkeyPatch, scan_mode: str
    ) -> None:
        monkeypatch.setattr(
            "agent.scanner.runner.check_network_connectivity", lambda: None
        )
        monkeypatch.setattr(
            "agent.scanner.runner.discover_hosts",
            lambda runner, subnet, timeout=None: [
                HostInfo(ip="192.168.1.10", hostname="target")
            ],
        )
        monkeypatch.setattr(stages, "run_port_stage", lambda *args, **kwargs: 0)
        monkeypatch.setattr(
            stages, "run_deep_inspection_stage", lambda *args, **kwargs: 0
        )

        def forbidden(*args, **kwargs):
            raise AssertionError("Quick/Standard called targeted stage")

        monkeypatch.setattr("agent.scanner.runner.run_targeted_stage", forbidden)
        reporter = _FakeReporter()
        completed: list[ScanPayload] = []
        ScanRunner(
            subnet="192.168.1.0/24",
            scan_mode=scan_mode,  # type: ignore[arg-type]
            reporter=reporter,
            on_complete=completed.append,
            runner=_FakeRunner(),
        ).run_blocking()

        assert "targeted_stage_started" not in _kinds(reporter.events)
        assert "targeted_unit_done" not in _kinds(reporter.events)
        assert "targeted_stage_done" not in _kinds(reporter.events)
        assert completed[0].metadata["partial_result"] is False

    def test_completed_targeted_gaps_are_partial_without_interrupted_stage(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "agent.scanner.runner.check_network_connectivity", lambda: None
        )
        monkeypatch.setattr(
            "agent.scanner.runner.discover_hosts",
            lambda runner, subnet, timeout=None: [
                HostInfo(ip="192.168.1.10", hostname="target")
            ],
        )
        monkeypatch.setattr(stages, "run_port_stage", lambda *args, **kwargs: 0)
        monkeypatch.setattr(
            stages, "run_deep_inspection_stage", lambda *args, **kwargs: 0
        )
        summary = TargetedStageSummary(
            eligible=2,
            planned=2,
            failed=1,
        )
        monkeypatch.setattr(
            "agent.scanner.runner.run_targeted_stage",
            lambda *args, **kwargs: summary,
        )
        completed: list[ScanPayload] = []
        ScanRunner(
            subnet="192.168.1.0/24",
            scan_mode="extensive",
            on_complete=completed.append,
            runner=_FakeRunner(),
        ).run_blocking()

        metadata = completed[0].metadata
        assert metadata["partial_result"] is True
        assert metadata["terminated_by"] == "completed"
        assert "interrupted_stage" not in metadata
        assert metadata["targeted_units_failed"] == 1


class TestScanRunnerFailure:
    def test_failure_emits_failed_and_no_completed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "agent.scanner.runner.check_network_connectivity", lambda: None
        )
        reporter = _FakeReporter()
        errors: list[Exception] = []
        runner = ScanRunner(
            subnet="192.168.1.0/24",
            scan_mode="standard",
            reporter=reporter,
            on_error=errors.append,
            runner=_BoomRunner(),
        )
        runner._run()

        kinds = _kinds(reporter.events)
        assert "failed" in kinds
        assert "completed" not in kinds

    def test_on_error_receives_exception(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "agent.scanner.runner.check_network_connectivity", lambda: None
        )
        reporter = _FakeReporter()
        errors: list[Exception] = []
        runner = ScanRunner(
            subnet="192.168.1.0/24",
            scan_mode="standard",
            reporter=reporter,
            on_error=errors.append,
            runner=_BoomRunner(),
        )
        runner._run()

        assert len(errors) == 1
        assert isinstance(errors[0], RuntimeError)


class TestScanRunnerAbort:
    def test_cancel_before_run_emits_failed_not_completed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "agent.scanner.runner.check_network_connectivity", lambda: None
        )
        reporter = _FakeReporter()
        runner = ScanRunner(
            subnet="192.168.1.0/24",
            scan_mode="standard",
            reporter=reporter,
            runner=_FakeRunner(),
        )
        runner.request_cancel()
        runner._run()

        kinds = _kinds(reporter.events)
        assert "failed" in kinds
        assert "completed" not in kinds

    def test_abort_message_reflects_abort(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "agent.scanner.runner.check_network_connectivity", lambda: None
        )
        reporter = _FakeReporter()
        runner = ScanRunner(
            subnet="192.168.1.0/24",
            scan_mode="standard",
            reporter=reporter,
            runner=_FakeRunner(),
        )
        runner.request_cancel()
        runner._run()

        failed = next(e for e in reporter.events if e.kind == "failed")
        assert "abort" in failed.message.lower()


class TestScanRunnerNoReporter:
    def test_run_completes_without_reporter(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "agent.scanner.runner.check_network_connectivity", lambda: None
        )
        completed: list[object] = []
        runner = ScanRunner(
            subnet="192.168.1.0/24",
            scan_mode="standard",
            reporter=None,
            on_complete=completed.append,
            runner=_FakeRunner(),
        )
        runner._run()

        assert len(completed) == 1


class TestScanRunnerRunBlocking:
    def test_run_blocking_delivers_payload_via_on_complete(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "agent.scanner.runner.check_network_connectivity", lambda: None
        )
        completed: list[object] = []
        runner = ScanRunner(
            subnet="192.168.1.0/24",
            scan_mode="standard",
            reporter=None,
            on_complete=completed.append,
            runner=_FakeRunner(),
        )
        runner.run_blocking()

        assert len(completed) == 1

    def test_run_blocking_does_not_spawn_thread(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "agent.scanner.runner.check_network_connectivity", lambda: None
        )

        def _boom(*args, **kwargs):
            raise AssertionError("threading.Thread should not be constructed")

        monkeypatch.setattr("agent.scanner.runner.threading.Thread", _boom)
        completed: list[object] = []
        runner = ScanRunner(
            subnet="192.168.1.0/24",
            scan_mode="standard",
            reporter=None,
            on_complete=completed.append,
            runner=_FakeRunner(),
        )
        runner.run_blocking()

        assert len(completed) == 1
        assert runner._thread is None
