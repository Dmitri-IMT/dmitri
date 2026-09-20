from __future__ import annotations

import agent.targeted.executor as executor_module
import pytest
from agent.targeted.executor import TargetedExecutor, ToolCommand
from agent.targeted.models import TargetedGapReason, TargetedOutcome, TargetedTool


def test_windows_targeted_execution_is_an_explicit_gap_without_spawn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Simulate an unsupported host so this guard is covered on Linux and
    # Windows development machines alike.  The executor checks both
    # ``os.name`` and ``sys.platform``; changing the latter is sufficient on
    # the POSIX test host, while the real Windows host already has ``nt``.
    monkeypatch.setattr(executor_module.sys, "platform", "win32")

    def fail_if_spawned(*args, **kwargs):
        raise AssertionError("targeted subprocess must not spawn on Windows")

    monkeypatch.setattr(executor_module.subprocess, "Popen", fail_if_spawned)
    result = TargetedExecutor().execute(
        ToolCommand(
            tool=TargetedTool.SSH_AUDIT,
            argv=("ssh-audit", "-j", "192.0.2.1"),
            report_mode="stdout",
        )
    )

    assert result.outcome is TargetedOutcome.SKIPPED
    assert result.reason_code is TargetedGapReason.INCOMPATIBLE_TOOL
    assert result.diagnostic and "Raspberry Pi Linux" in result.diagnostic
