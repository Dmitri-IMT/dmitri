from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest
from agent.normalize.contracts import ScanPayload
from agent.scanner import stages
from agent.scanner.models import HostInfo
from agent.scanner.nmap import NmapRunner
from agent.scanner.runner import ScanCancelled, ScanRunner


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


class _RecordingRunner(_FakeRunner):
    def __init__(self) -> None:
        super().__init__()
        self.terminate_calls = 0

    def terminate_active(self) -> None:
        self.terminate_calls += 1


class _RecordingTargetedExecutor:
    def __init__(self) -> None:
        self.terminate_calls = 0

    def terminate_active(self) -> None:
        self.terminate_calls += 1


def _kinds(events) -> list[str]:
    return [event.kind for event in events]


class TestRequestCancel:
    def test_request_cancel_sets_event_and_terminates_runner(self) -> None:
        recording = _RecordingRunner()
        runner = ScanRunner(
            subnet="192.168.1.0/24",
            scan_mode="standard",
            runner=_FakeRunner(),
        )
        runner._active_runner = recording

        runner.request_cancel()

        assert runner.is_cancelled is True
        assert recording.terminate_calls == 1

    def test_request_cancel_without_active_runner_only_sets_event(self) -> None:
        runner = ScanRunner(
            subnet="192.168.1.0/24",
            scan_mode="standard",
            runner=_FakeRunner(),
        )

        runner.request_cancel()

        assert runner.is_cancelled is True

    def test_request_cancel_terminates_active_targeted_operation(self) -> None:
        targeted = _RecordingTargetedExecutor()
        runner = ScanRunner(
            subnet="192.168.1.0/24",
            scan_mode="extensive",
            runner=_FakeRunner(),
        )
        runner._targeted_executor = targeted  # type: ignore[assignment]

        runner.request_cancel()

        assert runner.is_cancelled is True
        assert targeted.terminate_calls == 1


class TestCancelDuringStage:
    def test_cancel_in_port_stage_finalizes_partial(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "agent.scanner.runner.check_network_connectivity", lambda: None
        )
        monkeypatch.setattr(
            "agent.scanner.runner.discover_hosts",
            lambda runner, subnet, timeout=None: [
                HostInfo(ip="192.168.1.10", hostname="host-a")
            ],
        )

        def cancel(*args, **kwargs):
            raise ScanCancelled()

        monkeypatch.setattr(stages, "run_port_stage", cancel)
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
        runner._run()

        assert len(completed) == 1
        assert len(errors) == 0
        meta = completed[0].metadata
        assert meta["partial_result"] is True
        assert meta["interrupted_stage"] == "ports"
        assert meta["terminated_by"] == "user_cancel"

    def test_cancel_partial_emits_no_failed_or_completed_event(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "agent.scanner.runner.check_network_connectivity", lambda: None
        )
        monkeypatch.setattr(
            "agent.scanner.runner.discover_hosts",
            lambda runner, subnet, timeout=None: [
                HostInfo(ip="192.168.1.10", hostname="host-a")
            ],
        )

        def cancel(*args, **kwargs):
            raise ScanCancelled()

        monkeypatch.setattr(stages, "run_port_stage", cancel)
        reporter = _FakeReporter()
        runner = ScanRunner(
            subnet="192.168.1.0/24",
            scan_mode="standard",
            reporter=reporter,
            on_complete=lambda payload: None,
            runner=_FakeRunner(),
        )
        runner._run()

        kinds = _kinds(reporter.events)
        assert "failed" not in kinds
        assert "completed" not in kinds

    def test_cancel_partial_keeps_discovered_devices(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "agent.scanner.runner.check_network_connectivity", lambda: None
        )
        monkeypatch.setattr(
            "agent.scanner.runner.discover_hosts",
            lambda runner, subnet, timeout=None: [
                HostInfo(ip="192.168.1.10", hostname="host-a")
            ],
        )

        def cancel(*args, **kwargs):
            raise ScanCancelled()

        monkeypatch.setattr(stages, "run_port_stage", cancel)
        completed: list[ScanPayload] = []
        runner = ScanRunner(
            subnet="192.168.1.0/24",
            scan_mode="standard",
            on_complete=completed.append,
            runner=_FakeRunner(),
        )
        runner._run()

        assert [str(device.ip) for device in completed[0].hosts] == ["192.168.1.10"]
