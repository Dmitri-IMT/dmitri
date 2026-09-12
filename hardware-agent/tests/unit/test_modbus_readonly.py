from __future__ import annotations

import pytest

from agent.ot.modbus.client import ModbusReadSession
from agent.ot.modbus.readonly import (
    READ_ONLY_METHODS,
    ReadOnlyModbusClient,
    WriteAttemptError,
)


class _BareClient:
    def connect(self) -> bool:
        return True

    def close(self) -> None:
        return None

    def is_socket_open(self) -> bool:
        return True

    def read_coils(self, *args, **kwargs):
        return None

    def write_register(self, *args, **kwargs):
        raise AssertionError("bare client write should not run")


def test_read_only_methods_cover_expected_surface() -> None:
    assert READ_ONLY_METHODS == frozenset(
        {
            "connect",
            "close",
            "is_socket_open",
            "read_coils",
            "read_discrete_inputs",
            "read_holding_registers",
            "read_input_registers",
            "read_device_information",
        }
    )


def test_write_register_raises_write_attempt_error() -> None:
    wrapped = ReadOnlyModbusClient(_BareClient())

    with pytest.raises(WriteAttemptError):
        wrapped.write_register(0, 1)

    assert wrapped.write_attempts == 1


def test_modbus_read_session_client_blocks_writes() -> None:
    with ModbusReadSession(
        "192.168.10.30",
        502,
        timeout=1.0,
        client_factory=lambda *args, **kwargs: _BareClient(),
    ) as session:
        with pytest.raises(WriteAttemptError):
            session._client.write_register(0, 1)

        assert session._client.write_attempts == 1
