from __future__ import annotations

import sys

from agent.tools.runner import ExternalToolRunner, ToolRunStatus


def test_external_tool_runner_captures_successful_output() -> None:
    result = ExternalToolRunner(timeout_seconds=5).run(
        sys.executable,
        ["-c", "print('web-ok')"],
    )

    assert result.status == ToolRunStatus.COMPLETED
    assert result.exit_code == 0
    assert result.stdout.strip() == "web-ok"


def test_external_tool_runner_reports_missing_binary_without_raising() -> None:
    result = ExternalToolRunner(timeout_seconds=5).run(
        "definitely-not-a-dmitri-tool",
        [],
    )

    assert result.status == ToolRunStatus.SKIPPED
    assert result.exit_code is None
    assert "not found" in result.error
