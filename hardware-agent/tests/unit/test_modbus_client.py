from __future__ import annotations

import threading

from agent.ot.modbus.client import (
    ModbusClientController,
    probe_device_identification,
)
from pymodbus.exceptions import ModbusIOException


class _Response:
    def __init__(
        self,
        *,
        information=None,
        is_error: bool = False,
        exception_code: int | None = None,
    ) -> None:
        self.information = information
        self._is_error = is_error
        self.exception_code = exception_code

    def isError(self) -> bool:
        return self._is_error


class _Client:
    def __init__(self, response: _Response, *, connects: bool = True) -> None:
        self.response = response
        self.connects = connects
        self.closed = False
        self.calls: list[dict[str, int]] = []

    def connect(self) -> bool:
        return self.connects

    def read_device_information(self, **kwargs):
        self.calls.append(kwargs)
        return self.response

    def close(self) -> None:
        self.closed = True


def test_fc43_decodes_standard_objects_and_closes_connection() -> None:
    client = _Client(
        _Response(
            information={
                0: b"Schneider Electric",
                1: b"BMX P34",
                2: b"2.60",
                5: b"M340",
            }
        )
    )
    factory_calls = []

    def factory(*args, **kwargs):
        factory_calls.append((args, kwargs))
        return client

    unit = probe_device_identification(
        "192.168.10.30",
        502,
        7,
        timeout=1.25,
        client_factory=factory,
    )

    assert factory_calls == [
        (("192.168.10.30",), {"port": 502, "timeout": 1.25, "retries": 0})
    ]
    assert client.calls == [{"read_code": 2, "object_id": 0, "device_id": 7}]
    assert client.closed is True
    assert unit.status == "responding"
    assert unit.device_identification is not None
    assert unit.device_identification.vendor_name == "Schneider Electric"
    assert unit.device_identification.product_code == "BMX P34"
    assert unit.device_identification.major_minor_revision == "2.60"
    assert unit.device_identification.model_name == "M340"


def test_protocol_exception_is_normalised_and_connection_is_closed() -> None:
    client = _Client(_Response(is_error=True, exception_code=2))

    unit = probe_device_identification(
        "192.168.10.30",
        502,
        1,
        timeout=1.0,
        client_factory=lambda *args, **kwargs: client,
    )

    assert client.closed is True
    assert unit.status == "exception"
    assert unit.exception_code == 2


def test_connection_failure_sends_no_request() -> None:
    client = _Client(_Response(), connects=False)

    unit = probe_device_identification(
        "192.168.10.30",
        502,
        1,
        timeout=1.0,
        client_factory=lambda *args, **kwargs: client,
    )

    assert client.calls == []
    assert client.closed is True
    assert unit.status == "error"


def test_pymodbus_io_error_is_normalised_as_timeout() -> None:
    class TimeoutClient(_Client):
        def read_device_information(self, **kwargs):
            raise ModbusIOException("No response received")

    client = TimeoutClient(_Response())

    unit = probe_device_identification(
        "192.168.10.30",
        502,
        1,
        timeout=1.0,
        client_factory=lambda *args, **kwargs: client,
    )

    assert client.closed is True
    assert unit.status == "timeout"
    assert "No response received" in (unit.error or "")


def test_read_only_adapter_has_no_write_or_raw_pdu_surface() -> None:
    import agent.ot.modbus.client as client_module

    forbidden = {
        "write_coil",
        "write_coils",
        "write_register",
        "write_registers",
        "execute",
    }
    assert forbidden.isdisjoint(vars(client_module))


def test_cancellation_closes_an_active_client() -> None:
    read_started = threading.Event()

    class BlockingClient(_Client):
        def read_device_information(self, **kwargs):
            self.calls.append(kwargs)
            read_started.set()
            assert threading.Event().wait(0.01) is False
            while not self.closed:
                threading.Event().wait(0.01)
            raise OSError("socket closed")

    client = BlockingClient(_Response())
    controller = ModbusClientController()
    result = []
    thread = threading.Thread(
        target=lambda: result.append(
            probe_device_identification(
                "192.168.10.30",
                502,
                1,
                timeout=5.0,
                client_factory=lambda *args, **kwargs: client,
                controller=controller,
            )
        )
    )
    thread.start()
    assert read_started.wait(timeout=1.0)

    controller.cancel()
    thread.join(timeout=1.0)

    assert thread.is_alive() is False
    assert client.closed is True
    assert result[0].status == "error"


def test_cancelled_controller_prevents_connect_and_request() -> None:
    client = _Client(_Response())
    controller = ModbusClientController()
    controller.cancel()

    unit = probe_device_identification(
        "192.168.10.30",
        502,
        1,
        timeout=1.0,
        client_factory=lambda *args, **kwargs: client,
        controller=controller,
    )

    assert client.calls == []
    assert client.closed is True
    assert unit.status == "skipped"
