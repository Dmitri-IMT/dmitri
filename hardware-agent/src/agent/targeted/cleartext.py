from __future__ import annotations

import re
import socket
from collections.abc import Callable
from time import monotonic
from typing import Any

from agent.config import TARGETED_UNIT_TIMEOUT_S
from agent.targeted.executor import TargetedExecutor

# ruff: noqa: E501
from agent.targeted.models import (
    TargetedGapReason,
    TargetedIssue,
    TargetedOutcome,
    TargetedUnit,
    TargetedUnitResult,
)
from agent.targeted.report import sanitize_evidence

_BANNER_LIMIT = 4096


def _deadline(unit: TargetedUnit, **kwargs: Any) -> tuple[float, str]:
    values = [(monotonic() + TARGETED_UNIT_TIMEOUT_S[unit.tool.value], "unit")]
    for key in ("stage_deadline", "overall_deadline"):
        value = kwargs.get(key)
        if isinstance(value, (int, float)):
            values.append(
                (float(value), "stage" if key == "stage_deadline" else "overall")
            )
    return min(values, key=lambda value: value[0])


def _deadline_result(unit: TargetedUnit, scope: str) -> TargetedUnitResult:
    if scope == "stage":
        return TargetedUnitResult(
            unit, TargetedOutcome.SKIPPED, reason_code=TargetedGapReason.STAGE_BUDGET
        )
    if scope == "overall":
        return TargetedUnitResult(unit, TargetedOutcome.TIMED_OUT)
    return TargetedUnitResult(
        unit, TargetedOutcome.TIMED_OUT, reason_code=TargetedGapReason.UNIT_TIMEOUT
    )


def _cancelled(executor: TargetedExecutor, cancel_event: Any) -> bool:
    return bool(getattr(executor, "_cancelled", False)) or bool(
        cancel_event is not None and cancel_event.is_set()
    )


def _socket(
    executor: TargetedExecutor,
    unit: TargetedUnit,
    deadline: float,
    socket_factory: Callable[..., socket.socket] | None = None,
):
    if _cancelled(executor, None):
        return None
    active_socket = (socket_factory or socket.socket)(
        socket.AF_INET, socket.SOCK_STREAM
    )
    try:
        _refresh_socket_deadline(active_socket, deadline)
    except socket.timeout:
        active_socket.close()
        return None
    register = getattr(executor, "register_socket", None)
    if callable(register):
        register(active_socket)
    try:
        active_socket.connect((unit.ip, unit.port))
    except Exception:
        unregister = getattr(executor, "unregister_socket", None)
        if callable(unregister):
            unregister(active_socket)
        active_socket.close()
        raise
    return active_socket


def _refresh_socket_deadline(active_socket: socket.socket, deadline: float) -> None:
    remaining = deadline - monotonic()
    if remaining <= 0:
        raise socket.timeout
    active_socket.settimeout(remaining)


def _close(executor: TargetedExecutor, active_socket: socket.socket) -> None:
    unregister = getattr(executor, "unregister_socket", None)
    if callable(unregister):
        unregister(active_socket)
    try:
        active_socket.close()
    except OSError:
        pass


def _failed(
    unit: TargetedUnit, reason: TargetedGapReason, diagnostic: str | None = None
) -> TargetedUnitResult:
    return TargetedUnitResult(
        unit,
        TargetedOutcome.FAILED,
        reason_code=reason,
        diagnostic=sanitize_evidence(diagnostic or ""),
    )


def run_ftp_check(
    unit: TargetedUnit,
    executor: TargetedExecutor,
    *,
    socket_factory: Callable[..., socket.socket] | None = None,
    cancel_event: Any = None,
    **deadline: Any,
) -> TargetedUnitResult:
    end, scope = _deadline(unit, **deadline)
    if _cancelled(executor, cancel_event):
        return TargetedUnitResult(
            unit, TargetedOutcome.SKIPPED, reason_code=TargetedGapReason.STAGE_BUDGET
        )
    active_socket = None
    try:
        active_socket = _socket(executor, unit, end, socket_factory)
        if active_socket is None:
            return _deadline_result(unit, scope)
        _refresh_socket_deadline(active_socket, end)
        greeting = active_socket.recv(_BANNER_LIMIT)
        if _cancelled(executor, cancel_event):
            return TargetedUnitResult(
                unit,
                TargetedOutcome.SKIPPED,
                reason_code=TargetedGapReason.STAGE_BUDGET,
            )
        if not greeting:
            return TargetedUnitResult(unit, TargetedOutcome.COMPLETED)
        greeting_match = re.match(rb"\s*(\d{3})", greeting)
        greeting_code = int(greeting_match.group(1)) if greeting_match else None
        if greeting_code is None or not 100 <= greeting_code <= 399:
            return TargetedUnitResult(unit, TargetedOutcome.COMPLETED)
        if _cancelled(executor, cancel_event):
            return TargetedUnitResult(
                unit,
                TargetedOutcome.SKIPPED,
                reason_code=TargetedGapReason.STAGE_BUDGET,
            )
        _refresh_socket_deadline(active_socket, end)
        active_socket.sendall(b"FEAT\r\n")
        _refresh_socket_deadline(active_socket, end)
        feat = active_socket.recv(_BANNER_LIMIT)
        if _cancelled(executor, cancel_event):
            return TargetedUnitResult(
                unit,
                TargetedOutcome.SKIPPED,
                reason_code=TargetedGapReason.STAGE_BUDGET,
            )
        _refresh_socket_deadline(active_socket, end)
        if _cancelled(executor, cancel_event):
            return TargetedUnitResult(
                unit,
                TargetedOutcome.SKIPPED,
                reason_code=TargetedGapReason.STAGE_BUDGET,
            )
        active_socket.sendall(b"USER anonymous\r\n")
        _refresh_socket_deadline(active_socket, end)
        user_reply = active_socket.recv(_BANNER_LIMIT)
        if _cancelled(executor, cancel_event):
            return TargetedUnitResult(
                unit,
                TargetedOutcome.SKIPPED,
                reason_code=TargetedGapReason.STAGE_BUDGET,
            )
        _refresh_socket_deadline(active_socket, end)
        if _cancelled(executor, cancel_event):
            return TargetedUnitResult(
                unit,
                TargetedOutcome.SKIPPED,
                reason_code=TargetedGapReason.STAGE_BUDGET,
            )
        active_socket.sendall(b"PASS dmitri@localhost\r\n")
        _refresh_socket_deadline(active_socket, end)
        pass_reply = active_socket.recv(_BANNER_LIMIT)
        if _cancelled(executor, cancel_event):
            return TargetedUnitResult(
                unit,
                TargetedOutcome.SKIPPED,
                reason_code=TargetedGapReason.STAGE_BUDGET,
            )
        issues = [
            TargetedIssue(
                "ftp:cleartext",
                "FTP exposes a plaintext control channel",
                "The FTP greeting and control channel were reachable without TLS negotiation.",
                "medium",
                "Disable plaintext FTP or require an encrypted transport before authentication.",
                sanitize_evidence(
                    f"ftp-check: greeting={greeting_code}; auth_tls={'advertised' if b'AUTH TLS' in feat.upper() else 'not-advertised'}"
                ),
                method="configuration_observation",
                result="positive",
                rule_id="targeted:ftp-check-cleartext-control",
                facts={"auth_tls_advertised": b"AUTH TLS" in feat.upper()},
            )
        ]
        if re.match(rb"\s*230\b", pass_reply):
            issues.append(
                TargetedIssue(
                    "ftp:anonymous-login",
                    "FTP permits anonymous login",
                    "The FTP service accepted the standardized anonymous login check.",
                    "high",
                    "Disable anonymous FTP access or isolate the service and remove sensitive content.",
                    "ftp-check: anonymous login accepted",
                    method="specific_check",
                    result="positive",
                    rule_id="targeted:ftp-check-anonymous",
                    facts={"anonymous_login_accepted": True},
                )
            )
        _ = user_reply
        return TargetedUnitResult(unit, TargetedOutcome.COMPLETED, issues=issues)
    except socket.timeout:
        if _cancelled(executor, cancel_event):
            return TargetedUnitResult(
                unit,
                TargetedOutcome.SKIPPED,
                reason_code=TargetedGapReason.STAGE_BUDGET,
            )
        return _deadline_result(unit, scope)
    except OSError as exc:
        if _cancelled(executor, cancel_event):
            return TargetedUnitResult(
                unit,
                TargetedOutcome.SKIPPED,
                reason_code=TargetedGapReason.STAGE_BUDGET,
            )
        return _failed(unit, TargetedGapReason.EXECUTION_ERROR, str(exc))
    finally:
        if active_socket is not None:
            _close(executor, active_socket)


def run_telnet_check(
    unit: TargetedUnit,
    executor: TargetedExecutor,
    *,
    socket_factory: Callable[..., socket.socket] | None = None,
    cancel_event: Any = None,
    **deadline: Any,
) -> TargetedUnitResult:
    end, scope = _deadline(unit, **deadline)
    if _cancelled(executor, cancel_event):
        return TargetedUnitResult(
            unit, TargetedOutcome.SKIPPED, reason_code=TargetedGapReason.STAGE_BUDGET
        )
    active_socket = None
    try:
        active_socket = _socket(executor, unit, end, socket_factory)
        if active_socket is None:
            return _deadline_result(unit, scope)
        try:
            _refresh_socket_deadline(active_socket, end)
            banner = active_socket.recv(_BANNER_LIMIT)
        except (OSError, socket.timeout):
            banner = b""
        if _cancelled(executor, cancel_event):
            return TargetedUnitResult(
                unit,
                TargetedOutcome.SKIPPED,
                reason_code=TargetedGapReason.STAGE_BUDGET,
            )
        evidence = sanitize_evidence(banner[:_BANNER_LIMIT])
        return TargetedUnitResult(
            unit,
            TargetedOutcome.COMPLETED,
            issues=[
                TargetedIssue(
                    "telnet:cleartext",
                    "Telnet remote access is reachable in cleartext",
                    "A Telnet control channel accepted a TCP connection.",
                    "high",
                    "Disable Telnet and use an encrypted remote-access protocol.",
                    f"telnet-check: reachable; banner={evidence or '[empty]'}",
                    method="specific_check",
                    result="positive",
                    rule_id="targeted:telnet-check-reachable",
                    facts={"tcp_connection_accepted": True},
                )
            ],
        )
    except socket.timeout:
        if _cancelled(executor, cancel_event):
            return TargetedUnitResult(
                unit,
                TargetedOutcome.SKIPPED,
                reason_code=TargetedGapReason.STAGE_BUDGET,
            )
        return _deadline_result(unit, scope)
    except OSError as exc:
        if _cancelled(executor, cancel_event):
            return TargetedUnitResult(
                unit,
                TargetedOutcome.SKIPPED,
                reason_code=TargetedGapReason.STAGE_BUDGET,
            )
        return _failed(unit, TargetedGapReason.EXECUTION_ERROR, str(exc))
    finally:
        if active_socket is not None:
            _close(executor, active_socket)
