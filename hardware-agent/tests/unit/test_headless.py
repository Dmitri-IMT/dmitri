from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET

import pytest
from agent import headless
from agent.normalize.contracts import ScanPayload
from agent.scanner import stages
from agent.scanner.errors import FatalScanError
from agent.scanner.models import HostInfo
from agent.scanner.nmap import NmapRunner
from agent.scanner.runner import ScanRunner
from agent.scanner.workspace import write_scan_result

MODE = "standard"
SUBNET = "192.168.1.0/24"


class _FakeRunner(NmapRunner):
    def __init__(self) -> None:
        self.nmap_path = "fake-nmap"

    def run_xml(
        self, arguments: list[str], timeout: float | None = None
    ) -> ET.Element:
        return ET.fromstring("<nmaprun/>")


def _one_host() -> list[HostInfo]:
    return [HostInfo(ip="192.168.1.10", hostname="host-a")]


def _patch_discovery(monkeypatch: pytest.MonkeyPatch, hosts: list[HostInfo]) -> None:
    monkeypatch.setattr("agent.scanner.runner.check_network_connectivity", lambda: None)
    monkeypatch.setattr(
        "agent.scanner.runner.discover_hosts",
        lambda runner, subnet, timeout=None: hosts,
    )


class TestSameShape:
    def test_headless_payload_matches_direct_runner_shape(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path
    ) -> None:
        _patch_discovery(monkeypatch, [])
        headless_result = headless.run_headless_scan(
            MODE, SUBNET, workspace_root=tmp_path, runner=_FakeRunner()
        )

        results_dir = tmp_path / "results"
        files = list(results_dir.glob("*.json"))
        assert len(files) == 1
        assert re.match(
            r"^\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}_192-168-1-0_24\.json$",
            files[0].name,
        )
        data = json.loads(files[0].read_text(encoding="utf-8"))
        loaded_payload = ScanPayload.model_validate(data)
        assert loaded_payload == headless_result.payload

        completed: list[ScanPayload] = []
        direct_runner = ScanRunner(
            subnet=SUBNET,
            scan_mode=MODE,
            on_complete=completed.append,
            on_error=lambda exc: None,
            runner=_FakeRunner(),
        )
        direct_runner._run()
        direct_payload = completed[0]

        assert loaded_payload.subnet == direct_payload.subnet
        assert loaded_payload.scan_mode == direct_payload.scan_mode
        assert loaded_payload.devices == direct_payload.devices
        assert loaded_payload.findings == direct_payload.findings
        assert set(loaded_payload.metadata) == set(direct_payload.metadata)
        assert loaded_payload.metadata["partial_result"] == (
            direct_payload.metadata["partial_result"]
        )
        assert loaded_payload.metadata["terminated_by"] == (
            direct_payload.metadata["terminated_by"]
        )


class TestProgrammaticResult:
    def test_returns_completed_result_with_written_path(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path
    ) -> None:
        _patch_discovery(monkeypatch, [])
        result = headless.run_headless_scan(
            MODE, SUBNET, workspace_root=tmp_path, runner=_FakeRunner()
        )

        assert result.outcome == "completed"
        assert isinstance(result.payload, ScanPayload)
        assert result.error is None
        assert result.result_path is not None
        assert result.result_path.exists()
        assert result.result_path == tmp_path / "results" / result.result_path.name


class TestFailureSemantics:
    def test_post_discovery_fatal_yields_partial(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path
    ) -> None:
        _patch_discovery(monkeypatch, _one_host())

        def boom(*args, **kwargs):
            raise FatalScanError("ports blew up")

        monkeypatch.setattr(stages, "run_port_stage", boom)
        result = headless.run_headless_scan(
            MODE, SUBNET, workspace_root=tmp_path, runner=_FakeRunner()
        )

        assert result.outcome == "partial"
        assert result.result_path is not None
        data = json.loads(result.result_path.read_text(encoding="utf-8"))
        assert data["metadata"]["partial_result"] is True
        assert data["metadata"]["terminated_by"] == "error"
        assert data["metadata"]["interrupted_stage"] == "ports"

    def test_pre_discovery_fatal_yields_fatal_no_json(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path
    ) -> None:
        monkeypatch.setattr(
            "agent.scanner.runner.check_network_connectivity", lambda: None
        )

        def boom(runner, subnet, timeout=None):
            raise FatalScanError("discovery failed")

        monkeypatch.setattr("agent.scanner.runner.discover_hosts", boom)
        result = headless.run_headless_scan(
            MODE, SUBNET, workspace_root=tmp_path, runner=_FakeRunner()
        )

        assert result.outcome == "fatal"
        assert result.payload is None
        assert result.result_path is None
        assert isinstance(result.error, FatalScanError)
        results_dir = tmp_path / "results"
        assert list(results_dir.glob("*.json")) == []


class TestOnePipeline:
    def test_without_patch_one_host_completes(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path
    ) -> None:
        _patch_discovery(monkeypatch, _one_host())
        result = headless.run_headless_scan(
            MODE, SUBNET, workspace_root=tmp_path, runner=_FakeRunner()
        )

        assert result.outcome == "completed"

    def test_patching_port_stage_changes_outcome_to_partial(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path
    ) -> None:
        _patch_discovery(monkeypatch, _one_host())

        def boom(*args, **kwargs):
            raise FatalScanError("ports blew up")

        monkeypatch.setattr(stages, "run_port_stage", boom)
        result = headless.run_headless_scan(
            MODE, SUBNET, workspace_root=tmp_path, runner=_FakeRunner()
        )

        assert result.outcome == "partial"

    def test_headless_imports_shared_runner_and_writer(self) -> None:
        assert headless.ScanRunner is ScanRunner
        assert headless.write_scan_result is write_scan_result


class TestInputValidation:
    def test_unknown_mode_raises(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path
    ) -> None:
        calls: list[object] = []
        monkeypatch.setattr(
            "agent.scanner.runner.discover_hosts",
            lambda *args, **kwargs: calls.append(True),
        )

        with pytest.raises(headless.InvalidScanInput):
            headless.run_headless_scan("bogus", SUBNET, workspace_root=tmp_path)

        assert calls == []
        assert not (tmp_path / "results").exists()

    def test_subnet_without_slash_raises(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path
    ) -> None:
        calls: list[object] = []
        monkeypatch.setattr(
            "agent.scanner.runner.discover_hosts",
            lambda *args, **kwargs: calls.append(True),
        )

        with pytest.raises(headless.InvalidScanInput):
            headless.run_headless_scan(
                MODE, "192.168.1.5", workspace_root=tmp_path
            )

        assert calls == []
        assert not (tmp_path / "results").exists()

    def test_malformed_subnet_raises(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path
    ) -> None:
        calls: list[object] = []
        monkeypatch.setattr(
            "agent.scanner.runner.discover_hosts",
            lambda *args, **kwargs: calls.append(True),
        )

        with pytest.raises(headless.InvalidScanInput):
            headless.run_headless_scan(
                MODE, "999.999.999.0/24", workspace_root=tmp_path
            )

        assert calls == []
        assert not (tmp_path / "results").exists()


class TestExitCodeContract:
    def test_exit_codes_match_adr(self) -> None:
        assert headless.EXIT_CODES == {"completed": 0, "partial": 10, "fatal": 20}
        assert headless.INVALID_INPUT_EXIT == 2
