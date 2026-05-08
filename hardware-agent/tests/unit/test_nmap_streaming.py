"""Unit tests for NmapRunner.run_streamed — streaming stdout/stderr to disk."""

from __future__ import annotations

import sys
from pathlib import Path

from agent.scanner.nmap import NmapRunner, StreamedRunResult


def _make_runner() -> NmapRunner:
    """Create a runner pointing at the Python interpreter (used as a fake nmap)."""
    runner = NmapRunner.__new__(NmapRunner)
    runner.nmap_path = sys.executable
    return runner


class TestRunStreamed:
    def test_captures_stdout_to_console_log(self, tmp_path: Path) -> None:
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        runner = _make_runner()

        result = runner.run_streamed(
            ["-c", "import sys; sys.stdout.write('hello stdout\\n')"],
            run_dir,
        )

        assert result.console_log.exists()
        assert "hello stdout" in result.console_log.read_text(encoding="utf-8")

    def test_captures_stderr_to_stderr_log(self, tmp_path: Path) -> None:
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        runner = _make_runner()

        result = runner.run_streamed(
            ["-c", "import sys; sys.stderr.write('hello stderr\\n')"],
            run_dir,
        )

        assert result.stderr_log.exists()
        assert "hello stderr" in result.stderr_log.read_text(encoding="utf-8")

    def test_captures_both_streams_concurrently(self, tmp_path: Path) -> None:
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        runner = _make_runner()

        script = (
            "import sys; "
            "sys.stdout.write('out1\\n'); sys.stdout.flush(); "
            "sys.stderr.write('err1\\n'); sys.stderr.flush(); "
            "sys.stdout.write('out2\\n'); sys.stdout.flush(); "
            "sys.stderr.write('err2\\n'); sys.stderr.flush()"
        )
        result = runner.run_streamed(["-c", script], run_dir)

        stdout_content = result.console_log.read_text(encoding="utf-8")
        stderr_content = result.stderr_log.read_text(encoding="utf-8")
        assert "out1" in stdout_content
        assert "out2" in stdout_content
        assert "err1" in stderr_content
        assert "err2" in stderr_content

    def test_returns_zero_exit_code_on_success(self, tmp_path: Path) -> None:
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        runner = _make_runner()

        result = runner.run_streamed(["-c", "pass"], run_dir)

        assert result.exit_code == 0

    def test_returns_nonzero_exit_code_on_failure(self, tmp_path: Path) -> None:
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        runner = _make_runner()

        result = runner.run_streamed(["-c", "raise SystemExit(2)"], run_dir)

        assert result.exit_code == 2

    def test_creates_empty_files_when_no_output(self, tmp_path: Path) -> None:
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        runner = _make_runner()

        result = runner.run_streamed(["-c", "pass"], run_dir)

        assert result.console_log.exists()
        assert result.stderr_log.exists()
        assert result.console_log.read_text(encoding="utf-8") == ""
        assert result.stderr_log.read_text(encoding="utf-8") == ""

    def test_xml_path_points_to_run_dir(self, tmp_path: Path) -> None:
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        runner = _make_runner()

        result = runner.run_streamed(["-c", "pass"], run_dir)

        assert result.xml_path == run_dir / "nmaprun.xml"

    def test_result_is_streamed_run_result(self, tmp_path: Path) -> None:
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        runner = _make_runner()

        result = runner.run_streamed(["-c", "pass"], run_dir)

        assert isinstance(result, StreamedRunResult)

    def test_multiline_output_preserved(self, tmp_path: Path) -> None:
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        runner = _make_runner()

        script = "for i in range(5): print(f'line {i}')"
        result = runner.run_streamed(["-c", script], run_dir)

        lines = result.console_log.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 5
        assert lines[0] == "line 0"
        assert lines[4] == "line 4"

    def test_existing_run_xml_method_still_works(self, tmp_path: Path) -> None:
        """Verify run_xml is unchanged and coexists with run_streamed."""
        runner = _make_runner()
        # run_xml expects actual nmap — just confirm the method exists and is callable
        assert callable(runner.run_xml)
        assert callable(runner.run_streamed)
