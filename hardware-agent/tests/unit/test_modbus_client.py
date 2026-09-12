from __future__ import annotations

import threading

from agent.ot.modbus.client import (
    ModbusClientController,
    ModbusReadSession,
    _decode_device_information,
    probe_device_identification,
)
from agent.ot.untrusted import MAX_DEVICE_STRING_CHARS
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
    assert forbidden.isdisjoint(vars(ModbusReadSession))


class _ReadResponse:
    def __init__(self, *, bits=None, registers=None, exception_code=None) -> None:
        self.bits = bits or []
        self.registers = registers or []
        self.exception_code = exception_code

    def isError(self) -> bool:
        return self.exception_code is not None


class _ReadClient:
    def __init__(self, response) -> None:
        self.response = response
        self.calls = []
        self.closed = False

    def connect(self) -> bool:
        return True

    def close(self) -> None:
        self.closed = True

    def _read(self, name, address, **kwargs):
        self.calls.append((name, address, kwargs))
        return self.response

    def read_coils(self, address, **kwargs):
        return self._read("coil", address, **kwargs)

    def read_discrete_inputs(self, address, **kwargs):
        return self._read("discrete_input", address, **kwargs)

    def read_holding_registers(self, address, **kwargs):
        return self._read("holding_register", address, **kwargs)

    def read_input_registers(self, address, **kwargs):
        return self._read("input_register", address, **kwargs)


def test_mapping_adapter_dispatches_all_four_typed_reads() -> None:
    clients = []

    def factory(*args, **kwargs):
        del args, kwargs
        client = _ReadClient(_ReadResponse(bits=[True, False], registers=[7, 8]))
        clients.append(client)
        return client

    for address_space in (
        "coil",
        "discrete_input",
        "holding_register",
        "input_register",
    ):
        with ModbusReadSession(
            "192.168.10.30", 502, timeout=1.0, client_factory=factory
        ) as session:
            result = session.read(address_space, 10, 2, 7)

        assert result.status == "readable"
        assert result.values == (
            [True, False]
            if address_space in {"coil", "discrete_input"}
            else [7, 8]
        )
        assert clients[-1].calls == [
            (address_space, 10, {"count": 2, "device_id": 7})
        ]
        assert clients[-1].closed is True


def test_mapping_adapter_normalises_exception_and_returned_timeout() -> None:
    exception_client = _ReadClient(_ReadResponse(exception_code=2))
    with ModbusReadSession(
        "192.168.10.30",
        502,
        timeout=1.0,
        client_factory=lambda *args, **kwargs: exception_client,
    ) as session:
        exception = session.read("holding_register", 0, 1, 1)

    timeout_client = _ReadClient(ModbusIOException("No response received"))
    with ModbusReadSession(
        "192.168.10.30",
        502,
        timeout=1.0,
        client_factory=lambda *args, **kwargs: timeout_client,
    ) as session:
        timeout = session.read("holding_register", 0, 1, 1)

    assert exception.status == "illegal_address"
    assert exception.exception_code == 2
    assert timeout.status == "timeout"
    assert timeout.request_sent is True


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


def test_fc43_bounds_oversized_identification_and_sets_truncated() -> None:
    long_vendor = "V" * (MAX_DEVICE_STRING_CHARS + 10)
    identification = _decode_device_information({0: long_vendor.encode("utf-8")})

    assert identification is not None
    assert len(identification.vendor_name or "") == MAX_DEVICE_STRING_CHARS
    assert identification.truncated is True


def test_fc43_probe_keeps_unit_on_bounded_oversized_identification() -> None:
    long_vendor = "V" * (MAX_DEVICE_STRING_CHARS + 10)
    client = _Client(_Response(information={0: long_vendor.encode("utf-8")}))

    unit = probe_device_identification(
        "192.168.10.30",
        502,
        3,
        timeout=1.0,
        client_factory=lambda *args, **kwargs: client,
    )

    assert unit.status == "responding"
    assert unit.device_identification is not None
    assert unit.device_identification.truncated is True
    assert len(unit.device_identification.vendor_name or "") == MAX_DEVICE_STRING_CHARS
