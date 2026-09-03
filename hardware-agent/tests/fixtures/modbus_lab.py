from __future__ import annotations

import asyncio
import socket
import threading
import time
from types import TracebackType

from pymodbus.constants import ExcCodes
from pymodbus.pdu.device import ModbusDeviceIdentification
from pymodbus.server import ModbusTcpServer
from pymodbus.simulator import DataType, SimData, SimDevice


async def _lab_action(
    function_code: int,
    start_address: int,
    address: int,
    count: int,
    current_registers: list[int],
    set_values: list[int] | list[bool] | None,
) -> None | ExcCodes:
    del function_code, start_address, count, current_registers, set_values
    if address == 800:
        return ExcCodes.DEVICE_FAILURE
    if address == 900:
        await asyncio.sleep(2.0)
    return None


class ModbusLabServer:
    """Local Modbus target with bounded reads and disposable write points."""

    host = "127.0.0.1"
    unit_id = 1

    def __init__(self) -> None:
        self.port = _free_tcp_port()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._server: ModbusTcpServer | None = None
        self._started = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def __enter__(self) -> ModbusLabServer:
        self._thread.start()
        if not self._started.wait(timeout=3.0):
            raise RuntimeError("Modbus laboratory server did not start")
        _wait_for_listener(self.host, self.port)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exc_type, exc, traceback
        if self._loop is not None and self._server is not None:
            future = asyncio.run_coroutine_threadsafe(
                self._server.shutdown(),
                self._loop,
            )
            future.result(timeout=3.0)
        self._thread.join(timeout=3.0)
        if self._thread.is_alive():
            raise RuntimeError("Modbus laboratory server did not stop")

    def _run(self) -> None:
        asyncio.run(self._serve())

    async def _serve(self) -> None:
        self._loop = asyncio.get_running_loop()
        self._server = ModbusTcpServer(
            _lab_device(),
            address=(self.host, self.port),
        )
        self._started.set()
        await self._server.serve_forever()


def _lab_device() -> SimDevice:
    identity = ModbusDeviceIdentification(
        info_name={
            "VendorName": "Dmitri Laboratory",
            "ProductCode": "MODBUS-TARGET",
            "MajorMinorRevision": "1.0",
            "ProductName": "NSPi deterministic fixture",
            "ModelName": "LAB-PLC",
        }
    )
    blocks = (
        [
            SimData(0, values=[False, True, False, True], datatype=DataType.BITS),
            SimData(100, values=[False], datatype=DataType.BITS),
        ],
        [
            SimData(
                0,
                values=[True, False, True, False],
                datatype=DataType.BITS,
                readonly=True,
            )
        ],
        [
            SimData(0, values=[0, 7, 42, 1450], datatype=DataType.REGISTERS),
            SimData(100, values=[0], datatype=DataType.REGISTERS),
            SimData(800, values=[8], datatype=DataType.REGISTERS),
            SimData(900, values=[9], datatype=DataType.REGISTERS),
        ],
        [
            SimData(
                0,
                values=[10, 20, 30, 40],
                datatype=DataType.REGISTERS,
                readonly=True,
            )
        ],
    )
    return SimDevice(
        id=1,
        simdata=blocks,
        identity=identity,
        action=_lab_action,
    )


def _free_tcp_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def _wait_for_listener(host: str, port: int) -> None:
    deadline = time.monotonic() + 3.0
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.1):
                return
        except OSError:
            time.sleep(0.02)
    raise RuntimeError("Modbus laboratory server did not listen in time")
