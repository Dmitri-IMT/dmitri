from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest
from agent.scanner.nmap import NmapRunner
from agent.scanner.progress import ScanEvent
from agent.tui.scanner import ScanRunner


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


class TestScanRunnerSuccess:
    def test_emits_discovery_normalize_completed_in_order(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "agent.tui.scanner.check_network_connectivity", lambda: None
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
            "agent.tui.scanner.check_network_connectivity", lambda: None
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
            "agent.tui.scanner.check_network_connectivity", lambda: None
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


class TestScanRunnerFailure:
    def test_failure_emits_failed_and_no_completed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "agent.tui.scanner.check_network_connectivity", lambda: None
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
            "agent.tui.scanner.check_network_connectivity", lambda: None
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
            "agent.tui.scanner.check_network_connectivity", lambda: None
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
            "agent.tui.scanner.check_network_connectivity", lambda: None
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
            "agent.tui.scanner.check_network_connectivity", lambda: None
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
