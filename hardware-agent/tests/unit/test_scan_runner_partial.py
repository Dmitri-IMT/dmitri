from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest
from agent.normalize.contracts import ScanPayload
from agent.scanner import stages
from agent.scanner.errors import (
    BudgetExceeded,
    CircuitBreakerError,
    FatalScanError,
)
from agent.scanner.models import HostInfo
from agent.scanner.nmap import NmapRunner
from agent.scanner.runner import ScanRunner


class _FakeReporter:
    def __init__(self) -> None:
        self.events: list = []

    def emit(self, event) -> None:
        self.events.append(event)


class _FakeRunner(NmapRunner):
    def __init__(self) -> None:
        self.nmap_path = "fake-nmap"

    def run_xml(
        self, arguments: list[str], timeout: float | None = None
    ) -> ET.Element:
        return ET.fromstring("<nmaprun/>")


def _one_host() -> list[HostInfo]:
    return [HostInfo(ip="192.168.1.10", hostname="host-a")]


def _build_runner(
    monkeypatch: pytest.MonkeyPatch,
    *,
    hosts: list[HostInfo],
    port_stage=None,
) -> tuple[ScanRunner, list[ScanPayload], list[Exception], _FakeReporter]:
    monkeypatch.setattr("agent.scanner.runner.check_network_connectivity", lambda: None)
    monkeypatch.setattr(
        "agent.scanner.runner.discover_hosts",
        lambda runner, subnet, timeout=None: hosts,
    )
    if port_stage is not None:
        monkeypatch.setattr(stages, "run_port_stage", port_stage)
    completed: list[ScanPayload] = []
    errors: list[Exception] = []
    reporter = _FakeReporter()
    runner = ScanRunner(
        subnet="192.168.1.0/24",
        scan_mode="standard",
        reporter=reporter,
        on_complete=completed.append,
        on_error=errors.append,
        runner=_FakeRunner(),
    )
    return runner, completed, errors, reporter


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
        def boom(*args, **kwargs):
            raise FatalScanError("ports blew up")

        runner, completed, _, _ = _build_runner(
            monkeypatch, hosts=_one_host(), port_stage=boom
        )
        runner._run()

        payload = completed[0]
        assert [str(device.ip) for device in payload.devices] == ["192.168.1.10"]


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
        assert payload.metadata["partial_result"] is True
        assert payload.metadata["terminated_by"] == "error"
        assert [str(device.ip) for device in payload.devices] == ["192.168.1.10"]

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

    def test_zero_hosts_has_no_devices(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        runner, completed, _, _ = _build_runner(monkeypatch, hosts=[])
        runner._run()

        assert completed[0].devices == []
