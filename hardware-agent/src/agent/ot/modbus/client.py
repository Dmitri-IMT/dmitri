from __future__ import annotations

import contextlib
import threading
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ModbusException, ModbusIOException

from agent.ot.modbus.models import ModbusDeviceIdentification, ModbusUnit
from agent.ot.policy import AddressSpace
from agent.ot.untrusted import bound_objects, bound_text

_DEVICE_ID_FIELDS = {
    0: "vendor_name",
    1: "product_code",
    2: "major_minor_revision",
    3: "vendor_url",
    4: "product_name",
    5: "model_name",
    6: "user_application_name",
}


class ModbusClientController:
    """Closes the current sync client when the scan is cancelled."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._active_client: Any = None
        self._cancelled = False

    def register(self, client: Any) -> bool:
        with self._lock:
            if self._cancelled:
                with contextlib.suppress(Exception):
                    client.close()
                return False
            self._active_client = client
            return True

    def release(self, client: Any) -> None:
        with self._lock:
            if self._active_client is client:
                self._active_client = None

    def cancel(self) -> None:
        with self._lock:
            self._cancelled = True
            client = self._active_client
        if client is not None:
            with contextlib.suppress(Exception):
                client.close()


@dataclass(slots=True)
class ModbusReadResult:
    status: str
    values: list[int | bool] | None = None
    exception_code: int | None = None
    error: str | None = None
    request_sent: bool = False


class ModbusReadSession:
    """One-connection, FC01-FC04-only adapter for bounded mapping."""

    def __init__(
        self,
        host: str,
        port: int,
        *,
        timeout: float,
        client_factory: Callable[..., Any] = ModbusTcpClient,
        controller: ModbusClientController | None = None,
    ) -> None:
        self._client = client_factory(host, port=port, timeout=timeout, retries=0)
        self._controller = controller
        self._registered = False
        self._connected: bool | None = None

    def __enter__(self) -> ModbusReadSession:
        if self._controller is not None:
            self._registered = self._controller.register(self._client)
            if not self._registered:
                self._connected = False
        return self

    def __exit__(self, *args: object) -> None:
        del args
        self.close()

    def close(self) -> None:
        if self._registered and self._controller is not None:
            self._controller.release(self._client)
            self._registered = False
        with contextlib.suppress(Exception):
            self._client.close()

    def read(
        self,
        address_space: AddressSpace,
        start_address: int,
        count: int,
        unit_id: int,
    ) -> ModbusReadResult:
        if self._connected is None:
            try:
                self._connected = bool(self._client.connect())
            except (ModbusException, OSError, RuntimeError, ValueError) as exc:
                self._connected = False
                return ModbusReadResult(status="error", error=str(exc) or None)
        if not self._connected:
            return ModbusReadResult(
                status="error",
                error="Modbus TCP connection failed or scan was cancelled",
            )
        methods = {
            "coil": self._client.read_coils,
            "discrete_input": self._client.read_discrete_inputs,
            "holding_register": self._client.read_holding_registers,
            "input_register": self._client.read_input_registers,
        }
        try:
            response = methods[address_space](
                start_address,
                count=count,
                device_id=unit_id,
            )
            if isinstance(response, ModbusIOException):
                return ModbusReadResult(
                    status="timeout",
                    error=str(response) or None,
                    request_sent=True,
                )
            if response.isError():
                exception_code = getattr(response, "exception_code", None)
                code = exception_code if isinstance(exception_code, int) else None
                status = {1: "illegal_function", 2: "illegal_address"}.get(
                    code, "error"
                )
                return ModbusReadResult(
                    status=status,
                    exception_code=code,
                    error=str(response),
                    request_sent=True,
                )
            raw_values = (
                getattr(response, "bits", [])[:count]
                if address_space in {"coil", "discrete_input"}
                else getattr(response, "registers", [])[:count]
            )
            values = [
                (
                    bool(value)
                    if address_space in {"coil", "discrete_input"}
                    else int(value)
                )
                for value in raw_values
            ]
            if len(values) != count:
                return ModbusReadResult(
                    status="error",
                    error=f"Expected {count} values, received {len(values)}",
                    request_sent=True,
                )
            return ModbusReadResult(status="readable", values=values, request_sent=True)
        except (TimeoutError, ModbusIOException) as exc:
            return ModbusReadResult(
                status="timeout", error=str(exc) or None, request_sent=True
            )
        except (ModbusException, OSError, RuntimeError, ValueError) as exc:
            return ModbusReadResult(
                status="error", error=str(exc) or None, request_sent=True
            )


def probe_device_identification(
    host: str,
    port: int,
    unit_id: int,
    *,
    timeout: float,
    client_factory: Callable[..., Any] = ModbusTcpClient,
    controller: ModbusClientController | None = None,
) -> ModbusUnit:
    """Read FC43/MEI 14 identification through a deliberately narrow API."""

    client = client_factory(host, port=port, timeout=timeout, retries=0)
    if controller is not None and not controller.register(client):
        return ModbusUnit(
            unit_id=unit_id,
            status="skipped",
            error="Scan cancelled before Modbus request",
        )
    try:
        if not client.connect():
            return ModbusUnit(
                unit_id=unit_id,
                status="error",
                error="Modbus TCP connection failed",
            )
        response = client.read_device_information(
            read_code=0x02,
            object_id=0,
            device_id=unit_id,
        )
        if isinstance(response, ModbusIOException):
            return ModbusUnit(
                unit_id=unit_id,
                status="timeout",
                error=str(response) or None,
            )
        if response.isError():
            exception_code = getattr(response, "exception_code", None)
            return ModbusUnit(
                unit_id=unit_id,
                status="exception",
                exception_code=(
                    exception_code
                    if isinstance(exception_code, int) and 1 <= exception_code <= 255
                    else None
                ),
                error=str(response),
            )
        try:
            identification = _decode_device_information(
                getattr(response, "information", {})
            )
        except Exception as exc:
            return ModbusUnit(
                unit_id=unit_id,
                status="error",
                error=type(exc).__name__,
            )
        return ModbusUnit(
            unit_id=unit_id,
            status="responding",
            device_identification=identification,
            identification_sources=(
                ["pymodbus-fc43"] if identification is not None else []
            ),
        )
    except (TimeoutError, ModbusIOException) as exc:
        return ModbusUnit(unit_id=unit_id, status="timeout", error=str(exc) or None)
    except (ModbusException, OSError, RuntimeError, ValueError) as exc:
        return ModbusUnit(unit_id=unit_id, status="error", error=str(exc) or None)
    finally:
        if controller is not None:
            controller.release(client)
        with contextlib.suppress(Exception):
            client.close()


def _decode_device_information(
    information: Any,
) -> ModbusDeviceIdentification | None:
    if not isinstance(information, dict):
        return None
    identification = ModbusDeviceIdentification()
    truncated = False
    raw_objects: dict[str, str] = {}
    for object_id, raw_value in information.items():
        try:
            numeric_id = int(object_id)
        except (TypeError, ValueError):
            continue
        value = _decode_value(raw_value)
        bounded_value, cut = bound_text(value)
        truncated = truncated or cut
        raw_objects[str(numeric_id)] = bounded_value or ""
        field_name = _DEVICE_ID_FIELDS.get(numeric_id)
        if field_name is not None:
            setattr(identification, field_name, bounded_value)
    bounded_objs, dropped = bound_objects(raw_objects)
    identification.objects = bounded_objs
    identification.truncated = truncated or dropped
    if identification.has_structured_fields or identification.objects:
        return identification
    return None


def _decode_value(value: Any) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace").strip("\x00 ")
    return str(value).strip()
