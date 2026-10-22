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
        self.request_count = 0
        self._instrument_send()

    def _instrument_send(self) -> None:
        """Count bytes accepted by pymodbus' raw transport send method.

        Some test and integration factories expose only the public read API. Keep
        those clients usable, but do not infer a sent request when no transport
        boundary can be observed.
        """
        # Pymodbus binds ``client.send`` into transaction.low_level_send when
        # constructing the transaction manager, so instrument that actual
        # transport callback when present. Lightweight factories often expose
        # only ``send`` and are handled through the same fallback.
        owner = getattr(self._client, "transaction", None)
        send_name = "low_level_send"
        if owner is None or not callable(getattr(owner, send_name, None)):
            owner = self._client
            send_name = "send"
        try:
            send = getattr(owner, send_name)
        except (AttributeError, TypeError):
            return
        if not callable(send):
            return

        def counted_send(*args: Any, **kwargs: Any) -> Any:
            sent = send(*args, **kwargs)
            if isinstance(sent, int) and not isinstance(sent, bool) and sent > 0:
                self.request_count += 1
            return sent

        try:
            setattr(owner, send_name, counted_send)
        except (AttributeError, TypeError):
            # Immutable/slots-only adapters remain compatible and report no
            # observable sends rather than guessing based on method invocation.
            return

    def __getattr__(self, name: str) -> Any:
        if name in READ_ONLY_METHODS:
            return getattr(self._client, name)
        self.write_attempts += 1
        raise WriteAttemptError(f"Modbus write method '{name}' is not permitted")
