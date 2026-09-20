# ruff: noqa: E501
from __future__ import annotations

import socket
import threading
from contextlib import contextmanager

from agent.targeted.cleartext import run_ftp_check, run_telnet_check
from agent.targeted.models import (
    TargetedGapReason,
    TargetedOutcome,
    TargetedTool,
    TargetedUnit,
)


class FakeSocket:
    def __init__(self, replies: list[bytes]) -> None:
        self.replies = iter(replies)
        self.sent: list[bytes] = []
        self.recv_sizes: list[int] = []
        self.closed = False

    def settimeout(self, _value: float) -> None:
        pass

    def connect(self, _address) -> None:
        pass

    def recv(self, _size: int) -> bytes:
        self.recv_sizes.append(_size)
        return next(self.replies, b"")

    def sendall(self, value: bytes) -> None:
        self.sent.append(value)

    def close(self) -> None:
        self.closed = True


class FakeExecutor:
    def __init__(self) -> None:
        self.sockets = []

    def register_socket(self, value) -> None:
        self.sockets.append(value)

    def unregister_socket(self, _value) -> None:
        pass


@contextmanager
def ftp_listener(expected: list[bytes]):
    received: list[bytes] = []
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    port = server.getsockname()[1]

    def serve() -> None:
        with server:
            connection, _ = server.accept()
            with connection:
                connection.sendall(b"220 FTP ready\r\n")
                replies = [b"211 AUTH TLS\r\n", b"331 password\r\n", b"230 logged in\r\n"]
                for reply in replies:
                    received.append(connection.recv(128))
                    connection.sendall(reply)

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    try:
        yield port, received
    finally:
        thread.join(timeout=2)
        assert received == expected


def _ftp_unit(port: int) -> TargetedUnit:
    return TargetedUnit("127.0.0.1", port, "tcp", "ftp", TargetedTool.FTP_CHECK)


def test_ftp_checks_only_feature_and_standard_anonymous_login() -> None:
    active = FakeSocket([b"220 FTP ready\r\n", b"211 AUTH TLS\r\n", b"331 password\r\n", b"230 logged in\r\n"])
    result = run_ftp_check(TargetedUnit("192.0.2.10", 21, "tcp", "ftp", TargetedTool.FTP_CHECK), FakeExecutor(), socket_factory=lambda *_args: active)
    assert {issue.issue_key for issue in result.issues} == {"ftp:cleartext", "ftp:anonymous-login"}
    assert active.sent == [b"FEAT\r\n", b"USER anonymous\r\n", b"PASS dmitri@localhost\r\n"]


def test_telnet_reads_banner_without_sending_credentials() -> None:
    active = FakeSocket([b"\xff\xfb\x01login:"])
    result = run_telnet_check(TargetedUnit("192.0.2.10", 23, "tcp", "telnet", TargetedTool.TELNET_CHECK), FakeExecutor(), socket_factory=lambda *_args: active)
    assert result.issues[0].issue_key == "telnet:cleartext"
    assert active.sent == []


def test_ftp_listener_receives_only_bounded_safe_commands() -> None:
    expected = [b"FEAT\r\n", b"USER anonymous\r\n", b"PASS dmitri@localhost\r\n"]
    with ftp_listener(expected) as (port, _received):
        result = run_ftp_check(_ftp_unit(port), FakeExecutor())
    assert result.outcome == TargetedOutcome.COMPLETED
    assert {issue.issue_key for issue in result.issues} == {"ftp:cleartext", "ftp:anonymous-login"}


def test_telnet_banner_read_is_bounded_and_never_sends_credentials() -> None:
    active = FakeSocket([b"banner=" + b"x" * 10000])
    result = run_telnet_check(
        TargetedUnit("192.0.2.10", 23, "tcp", "telnet", TargetedTool.TELNET_CHECK),
        FakeExecutor(),
        socket_factory=lambda *_args: active,
    )
    assert result.outcome == TargetedOutcome.COMPLETED
    assert active.recv_sizes == [4096]
    assert active.sent == []
    assert len(result.issues[0].evidence) <= 4096 + len("telnet-check: reachable; banner=")


def test_ftp_cancellation_after_greeting_does_not_attempt_login() -> None:
    cancel = threading.Event()

    class CancellingSocket(FakeSocket):
        def recv(self, size: int) -> bytes:
            value = super().recv(size)
            cancel.set()
            return value

    active = CancellingSocket([b"220 FTP ready\r\n"])
    result = run_ftp_check(
        _ftp_unit(21),
        FakeExecutor(),
        socket_factory=lambda *_args: active,
        cancel_event=cancel,
    )
    assert result.outcome == TargetedOutcome.SKIPPED
    assert result.reason_code == TargetedGapReason.STAGE_BUDGET
    assert active.sent == []


def test_ftp_cancellation_after_feat_does_not_attempt_user_or_pass() -> None:
    cancel = threading.Event()

    class CancellingSocket(FakeSocket):
        def sendall(self, value: bytes) -> None:
            super().sendall(value)
            if value == b"FEAT\r\n":
                cancel.set()

    active = CancellingSocket([b"220 FTP ready\r\n", b"211 AUTH TLS\r\n"])
    result = run_ftp_check(
        _ftp_unit(21),
        FakeExecutor(),
        socket_factory=lambda *_args: active,
        cancel_event=cancel,
    )
    assert result.outcome == TargetedOutcome.SKIPPED
    assert result.reason_code == TargetedGapReason.STAGE_BUDGET
    assert active.sent == [b"FEAT\r\n"]


def test_cleartext_refreshes_socket_timeout_for_each_operation() -> None:
    class TrackingSocket(FakeSocket):
        def __init__(self, replies: list[bytes]) -> None:
            super().__init__(replies)
            self.timeouts: list[float] = []

        def settimeout(self, value: float) -> None:
            self.timeouts.append(value)

    active = TrackingSocket([b"220 FTP ready\r\n", b"211 AUTH TLS\r\n", b"331 password\r\n", b"530 denied\r\n"])
    result = run_ftp_check(
        _ftp_unit(21), FakeExecutor(), socket_factory=lambda *_args: active
    )
    assert result.outcome == TargetedOutcome.COMPLETED
    assert len(active.timeouts) >= 8
    assert all(left >= right for left, right in zip(active.timeouts, active.timeouts[1:]))


def test_cleartext_pre_cancellation_skips_before_connect() -> None:
    cancel = threading.Event()
    cancel.set()
    called = False

    def socket_factory(*_args):
        nonlocal called
        called = True
        return FakeSocket([])

    result = run_telnet_check(
        TargetedUnit("192.0.2.10", 23, "tcp", "telnet", TargetedTool.TELNET_CHECK),
        FakeExecutor(),
        socket_factory=socket_factory,
        cancel_event=cancel,
    )
    assert result.outcome == TargetedOutcome.SKIPPED
    assert called is False
