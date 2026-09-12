from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from agent import headless
from agent.cli import main
from agent.transport.ingest import IngestConfigError


class _StubPayload:
    def __init__(self, scan_id: str) -> None:
        self.scan_id = scan_id


def _stub_result(
    outcome: str,
    scan_id: str | None = None,
    result_path: str | None = None,
    error: Exception | None = None,
) -> headless.HeadlessScanResult:
    payload = _StubPayload(scan_id) if scan_id is not None else None
    return headless.HeadlessScanResult(
        outcome=outcome,
        payload=payload,
        result_path=Path(result_path) if result_path is not None else None,
        error=error,
    )


def test_cli_agent_completed_exits_0(capsys: pytest.CaptureFixture[str]) -> None:
    result_path = str(Path("tmp") / "results" / "scan.json")
    result = _stub_result("completed", scan_id="abc-123", result_path=result_path)
    with (
        patch.object(sys, "argv", ["dmitri", "agent", "quick", "192.168.1.0/24"]),
        patch("agent.cli._check_nmap", return_value=True),
        patch("agent.headless.run_headless_scan", return_value=result),
    ):
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 0
        assert exc_info.value.code == headless.EXIT_CODES["completed"]

    out = json.loads(capsys.readouterr().out.strip())
    assert out["outcome"] == "completed"
    assert out["scan_id"] == "abc-123"
    assert out["result_path"] == result_path


def test_cli_passes_read_only_mapping_to_headless() -> None:
    result = _stub_result("completed", scan_id="abc-123", result_path="scan.json")
    with (
        patch.object(
            sys,
            "argv",
            [
                "dmitri",
                "agent",
                "nspi",
                "read_only_mapping",
                "192.168.1.0/24",
            ],
        ),
        patch("agent.cli._check_nmap", return_value=True),
        patch(
            "agent.headless.run_headless_scan", return_value=result
        ) as run_scan,
    ):
        with pytest.raises(SystemExit) as exc_info:
            main()

    assert exc_info.value.code == 0
    assert run_scan.call_args.kwargs["nspi_submode"] == "read_only_mapping"


def test_cli_agent_partial_exits_10(capsys: pytest.CaptureFixture[str]) -> None:
    result_path = str(Path("tmp") / "results" / "partial.json")
    result = _stub_result("partial", scan_id="def-456", result_path=result_path)
    with (
        patch.object(sys, "argv", ["dmitri", "agent", "standard", "192.168.1.0/24"]),
        patch("agent.cli._check_nmap", return_value=True),
        patch("agent.headless.run_headless_scan", return_value=result),
    ):
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 10
        assert exc_info.value.code == headless.EXIT_CODES["partial"]

    out = json.loads(capsys.readouterr().out.strip())
    assert out["outcome"] == "partial"
    assert out["scan_id"] == "def-456"
    assert out["result_path"] == result_path


def test_cli_agent_fatal_exits_20(capsys: pytest.CaptureFixture[str]) -> None:
    result = _stub_result("fatal")
    with (
        patch.object(sys, "argv", ["dmitri", "agent", "quick", "192.168.1.0/24"]),
        patch("agent.cli._check_nmap", return_value=True),
        patch("agent.headless.run_headless_scan", return_value=result),
    ):
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 20
        assert exc_info.value.code == headless.EXIT_CODES["fatal"]

    out = json.loads(capsys.readouterr().out.strip())
    assert out["outcome"] == "fatal"
    assert out["scan_id"] is None
    assert out["result_path"] is None


def test_cli_agent_write_failure_fatal_exits_20_and_prints_stderr(
    capsys: pytest.CaptureFixture[str],
) -> None:
    error = OSError(
        "Scan completed but the result file could not be written to /tmp: disk full"
    )
    result = _stub_result("fatal", scan_id="ghi-789", error=error)
    with (
        patch.object(sys, "argv", ["dmitri", "agent", "quick", "192.168.1.0/24"]),
        patch("agent.cli._check_nmap", return_value=True),
        patch("agent.headless.run_headless_scan", return_value=result),
    ):
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 20
        assert exc_info.value.code == headless.EXIT_CODES["fatal"]

    captured = capsys.readouterr()
    assert str(error) in captured.err

    lines = [line for line in captured.out.splitlines() if line.strip()]
    assert len(lines) == 1
    out = json.loads(lines[0])
    assert set(out.keys()) == {"outcome", "result_path", "scan_id"}
    assert out["outcome"] == "fatal"
    assert out["result_path"] is None
    assert out["scan_id"] == "ghi-789"


@pytest.mark.parametrize(
    "argv",
    [
        ["dmitri", "agent", "quick"],
        ["dmitri", "agent", "quick", "192.168.1.0/24", "extra"],
    ],
)
def test_cli_agent_bad_arity_exits_2(
    argv: list[str], capsys: pytest.CaptureFixture[str]
) -> None:
    with patch.object(sys, "argv", argv):
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 2

    err = capsys.readouterr().err
    assert "Usage: dmitri agent [<mode> [<nspi-submode>] <subnet>]" in err


def test_cli_agent_invalid_scan_input_exits_2(
    capsys: pytest.CaptureFixture[str],
) -> None:
    def _raise(*args: object, **kwargs: object) -> headless.HeadlessScanResult:
        raise headless.InvalidScanInput("Unknown scan mode 'bogus'")

    with (
        patch.object(sys, "argv", ["dmitri", "agent", "bogus", "192.168.1.0/24"]),
        patch("agent.cli._check_nmap", return_value=True),
        patch("agent.headless.run_headless_scan", side_effect=_raise),
    ):
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 2

    err = capsys.readouterr().err
    assert "Unknown scan mode 'bogus'" in err


def test_cli_agent_nmap_missing_exits_20(capsys: pytest.CaptureFixture[str]) -> None:
    called: list[object] = []

    def _fail_if_called(*args: object, **kwargs: object) -> headless.HeadlessScanResult:
        called.append(True)
        raise AssertionError("run_headless_scan must not be called")

    with (
        patch.object(sys, "argv", ["dmitri", "agent", "quick", "192.168.1.0/24"]),
        patch("agent.cli._check_nmap", return_value=False),
        patch("agent.headless.run_headless_scan", side_effect=_fail_if_called),
    ):
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 20
        assert exc_info.value.code == headless.EXIT_CODES["fatal"]

    assert called == []


def test_cli_bare_agent_checks_nmap_then_runs_daemon() -> None:
    order: list[str] = []

    def _nmap() -> bool:
        order.append("nmap")
        return True

    def _daemon() -> None:
        order.append("daemon")

    with (
        patch.object(sys, "argv", ["dmitri", "agent"]),
        patch("agent.cli._check_nmap", side_effect=_nmap),
        patch("agent.daemon.run_daemon", side_effect=_daemon),
    ):
        main()

    assert order == ["nmap", "daemon"]


def test_cli_bare_agent_nmap_missing_exits_20_without_daemon(
    capsys: pytest.CaptureFixture[str],
) -> None:
    def _fail_if_called() -> None:
        raise AssertionError("run_daemon must not be called")

    with (
        patch.object(sys, "argv", ["dmitri", "agent"]),
        patch("agent.cli._check_nmap", return_value=False),
        patch("agent.daemon.run_daemon", side_effect=_fail_if_called),
    ):
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 20

    err = capsys.readouterr().err
    assert "Error: nmap is not installed or not on PATH." in err
    assert "Install nmap: https://nmap.org/download.html" in err


def test_cli_bare_agent_ingest_config_error_exits_20(
    capsys: pytest.CaptureFixture[str],
) -> None:
    def _raise() -> None:
        raise IngestConfigError("DMITRI_INGEST_URL is not set")

    with (
        patch.object(sys, "argv", ["dmitri", "agent"]),
        patch("agent.cli._check_nmap", return_value=True),
        patch("agent.daemon.load_ingest_config", side_effect=_raise),
    ):
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 20

    assert "DMITRI_INGEST_URL is not set" in capsys.readouterr().err


def test_cli_bare_agent_configures_info_logging_to_stdout() -> None:
    with (
        patch.object(sys, "argv", ["dmitri", "agent"]),
        patch("agent.cli._check_nmap", return_value=True),
        patch("agent.daemon.logging.basicConfig") as configure,
        patch(
            "agent.daemon.load_ingest_config",
            side_effect=IngestConfigError("DEVICE_ID is required"),
        ),
    ):
        with pytest.raises(SystemExit):
            main()

    configure.assert_called_once_with(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stdout,
    )
