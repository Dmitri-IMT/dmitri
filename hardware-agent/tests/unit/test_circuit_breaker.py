from __future__ import annotations

import pytest
from agent.config import AgentSettings
from agent.scanner.errors import BudgetExceeded, CircuitBreakerError, UnitScanError
from agent.scanner.models import HostInfo, PortInfo, ScriptResult
from agent.scanner.progress import ScanEvent
from agent.scanner.stages import run_deep_inspection_stage, run_port_stage


class _FakeReporter:
    def __init__(self) -> None:
        self.events: list[ScanEvent] = []

    def emit(self, event: ScanEvent) -> None:
        self.events.append(event)


class _DummyRunner:
    def __init__(self) -> None:
        self.nmap_path = "nmap"


def _kinds(events: list[ScanEvent], kind: str) -> list[ScanEvent]:
    return [event for event in events if event.kind == kind]


def _nse_fake(failures: dict[str, Exception]):
    def fake(runner, ip, ports, *, version_intensity, scripts, min_cvss, timeout=None):
        exc = failures.get(ip)
        if exc is not None:
            raise exc
        return HostInfo(
            ip=ip,
            hostname=ip,
            ports=ports,
            host_scripts=[ScriptResult(script_id="vulners", is_host_script=True)],
        )

    return fake


def _ports_fake(failures: dict[str, Exception]):
    def fake(runner, ips, scan_mode, timeout=None):
        for ip in ips:
            exc = failures.get(ip)
            if exc is not None:
                raise exc
        return {ip: [PortInfo(port=22)] for ip in ips}

    return fake


def _eligible_hosts() -> list[HostInfo]:
    return [
        HostInfo(ip="10.0.0.1", hostname="10.0.0.1", ports=[PortInfo(port=22)]),
        HostInfo(ip="10.0.0.2", hostname="10.0.0.2", ports=[PortInfo(port=80)]),
        HostInfo(ip="10.0.0.3", hostname="10.0.0.3", ports=[PortInfo(port=443)]),
    ]


def _bare_hosts() -> list[HostInfo]:
    return [
        HostInfo(ip="10.0.0.1", hostname="10.0.0.1"),
        HostInfo(ip="10.0.0.2", hostname="10.0.0.2"),
        HostInfo(ip="10.0.0.3", hostname="10.0.0.3"),
        HostInfo(ip="10.0.0.4", hostname="10.0.0.4"),
    ]


class TestDeepStageCircuitBreaker:
    def test_raises_when_above_threshold(self, monkeypatch) -> None:
        hosts = _eligible_hosts()
        failures = {host.ip: UnitScanError("boom") for host in hosts}
        monkeypatch.setattr(
            "agent.scanner.stages.run_nse_vulnerability_scan", _nse_fake(failures)
        )
        settings = AgentSettings(scan_mode="standard", max_workers=1)
        with pytest.raises(CircuitBreakerError):
            run_deep_inspection_stage(
                _DummyRunner(), settings, hosts, reporter=_FakeReporter()
            )

    def test_breaker_is_budget_exceeded(self, monkeypatch) -> None:
        hosts = _eligible_hosts()
        failures = {host.ip: UnitScanError("boom") for host in hosts}
        monkeypatch.setattr(
            "agent.scanner.stages.run_nse_vulnerability_scan", _nse_fake(failures)
        )
        settings = AgentSettings(scan_mode="standard", max_workers=1)
        with pytest.raises(BudgetExceeded):
            run_deep_inspection_stage(
                _DummyRunner(), settings, hosts, reporter=_FakeReporter()
            )

    def test_below_threshold_continues(self, monkeypatch) -> None:
        hosts = _eligible_hosts()
        monkeypatch.setattr(
            "agent.scanner.stages.run_nse_vulnerability_scan",
            _nse_fake({"10.0.0.2": UnitScanError("boom")}),
        )
        settings = AgentSettings(scan_mode="standard", max_workers=1)
        reporter = _FakeReporter()
        run_deep_inspection_stage(_DummyRunner(), settings, hosts, reporter=reporter)
        done = _kinds(reporter.events, "deep_stage_done")
        assert len(done) == 1
        assert done[0].units_skipped == 1


class TestPortStageCircuitBreaker:
    def test_raises_when_above_threshold(self, monkeypatch) -> None:
        hosts = _bare_hosts()
        failures = {host.ip: UnitScanError("boom") for host in hosts}
        monkeypatch.setattr(
            "agent.scanner.stages.scan_ports_batch", _ports_fake(failures)
        )
        settings = AgentSettings(
            scan_mode="standard", max_workers=1, host_batch_size=1
        )
        with pytest.raises(CircuitBreakerError):
            run_port_stage(_DummyRunner(), settings, hosts, reporter=_FakeReporter())

    def test_below_threshold_continues(self, monkeypatch) -> None:
        hosts = _bare_hosts()
        monkeypatch.setattr(
            "agent.scanner.stages.scan_ports_batch",
            _ports_fake({"10.0.0.1": UnitScanError("boom")}),
        )
        settings = AgentSettings(
            scan_mode="standard", max_workers=1, host_batch_size=1
        )
        reporter = _FakeReporter()
        run_port_stage(_DummyRunner(), settings, hosts, reporter=reporter)
        done = _kinds(reporter.events, "port_stage_done")
        assert len(done) == 1
        assert done[0].units_skipped == 1
