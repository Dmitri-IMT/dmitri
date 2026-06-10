"""Targeted external security tools for service-specific scan stages."""

from agent.tools.runner import ExternalToolRunner, ToolRunResult, ToolRunStatus
from agent.tools.targeted import (
    TargetedToolSummary,
    run_targeted_security_tools,
    select_smb_targets,
    select_tls_targets,
)
from agent.tools.web import (
    WebDirectoryHit,
    WebTarget,
    WebToolSummary,
    run_web_security_tools,
    select_web_targets,
)

__all__ = [
    "ExternalToolRunner",
    "ToolRunResult",
    "ToolRunStatus",
    "TargetedToolSummary",
    "WebDirectoryHit",
    "WebTarget",
    "WebToolSummary",
    "run_targeted_security_tools",
    "run_web_security_tools",
    "select_smb_targets",
    "select_tls_targets",
    "select_web_targets",
]
