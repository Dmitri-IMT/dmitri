from __future__ import annotations

from typing import Any

READ_ONLY_METHODS = frozenset(
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


class WriteAttemptError(AttributeError):
    """Raised when code attempts a Modbus write through ReadOnlyModbusClient."""


class ReadOnlyModbusClient:
    """Forwards only read-safe ModbusTcpClient methods."""

    def __init__(self, client: Any) -> None:
        self._client = client
        self.write_attempts = 0

    def __getattr__(self, name: str) -> Any:
        if name in READ_ONLY_METHODS:
            return getattr(self._client, name)
        self.write_attempts += 1
        raise WriteAttemptError(f"Modbus write method '{name}' is not permitted")
