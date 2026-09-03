from __future__ import annotations

import contextlib
import threading
from collections.abc import Callable
from typing import Any

from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ModbusException, ModbusIOException

from agent.ot.modbus.models import ModbusDeviceIdentification, ModbusUnit

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
        return ModbusUnit(
            unit_id=unit_id,
            status="responding",
            device_identification=_decode_device_information(
                getattr(response, "information", {})
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
    for object_id, raw_value in information.items():
        try:
            numeric_id = int(object_id)
        except (TypeError, ValueError):
            continue
        value = _decode_value(raw_value)
        identification.objects[str(numeric_id)] = value
        field_name = _DEVICE_ID_FIELDS.get(numeric_id)
        if field_name is not None:
            setattr(identification, field_name, value)
    if identification.has_structured_fields or identification.objects:
        return identification
    return None


def _decode_value(value: Any) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace").strip("\x00 ")
    return str(value).strip()
