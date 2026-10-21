from __future__ import annotations

import asyncio
import copy
import socket
import threading
import time
from types import TracebackType

from asyncua import ua
from asyncua.server import Server
from asyncua.server.uaprocessor import UaProcessor
from asyncua.ua.ua_binary import nodeid_from_binary

_REQUEST_LOCK = threading.Lock()
_RECEIVED_REQUESTS: list[int] = []
_PATCH_LOCK = threading.Lock()
_ORIGINAL_PROCESS_MESSAGE = UaProcessor.process_message
_LAB_DELAY_GET_ENDPOINTS = 0.0


class OpcUaLabServer:
    """Disposable OPC UA server bound only to loopback and an ephemeral port."""

    host = "127.0.0.1"

    def __init__(
        self, *, oversized: bool = False, delay_get_endpoints: float = 0
    ) -> None:
        self.port = _free_tcp_port()
        self._oversized = oversized
        self._delay_get_endpoints = delay_get_endpoints
        self._loop: asyncio.AbstractEventLoop | None = None
        self._server: Server | None = None
        self._started = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._error: BaseException | None = None

    @property
    def received_request_type_ids(self) -> tuple[int, ...]:
        with _REQUEST_LOCK:
            return tuple(_RECEIVED_REQUESTS)

    def __enter__(self) -> OpcUaLabServer:
        with _REQUEST_LOCK:
            _RECEIVED_REQUESTS.clear()
        self._install_observer()
        self._thread.start()
        if not self._started.wait(timeout=5):
            raise RuntimeError("OPC UA laboratory server did not start")
        if self._error is not None:
            UaProcessor.process_message = _ORIGINAL_PROCESS_MESSAGE
            raise RuntimeError("OPC UA laboratory server failed") from self._error
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
            future = asyncio.run_coroutine_threadsafe(self._server.stop(), self._loop)
            future.result(timeout=5)
            self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(timeout=5)
        UaProcessor.process_message = _ORIGINAL_PROCESS_MESSAGE
        if self._thread.is_alive():
            raise RuntimeError("OPC UA laboratory server did not stop")

    def _install_observer(self) -> None:
        global _LAB_DELAY_GET_ENDPOINTS
        _LAB_DELAY_GET_ENDPOINTS = self._delay_get_endpoints

        async def observed(
            self: UaProcessor, seqhdr: ua.SequenceHeader, body: ua.utils.Buffer
        ) -> bool:
            type_id = nodeid_from_binary(body.copy()).Identifier
            with _REQUEST_LOCK:
                _RECEIVED_REQUESTS.append(int(type_id))
            if (
                _LAB_DELAY_GET_ENDPOINTS
                and type_id == ua.ObjectIds.GetEndpointsRequest_Encoding_DefaultBinary
            ):
                await asyncio.sleep(_LAB_DELAY_GET_ENDPOINTS)
            return await _ORIGINAL_PROCESS_MESSAGE(self, seqhdr, body)

        with _PATCH_LOCK:
            if not getattr(UaProcessor.process_message, "_dmitri_lab_observer", False):
                observed._dmitri_lab_observer = True  # type: ignore[attr-defined]
                UaProcessor.process_message = observed

    def _run(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop
        try:
            loop.run_until_complete(self._serve())
            loop.run_forever()
        except BaseException as exc:
            self._error = exc
            self._started.set()
        finally:
            loop.close()

    async def _serve(self) -> None:
        self._server = Server()
        await self._server.init()
        self._server.set_endpoint(f"opc.tcp://{self.host}:{self.port}/")
        await self._server.start()
        if self._oversized:
            template = self._server.iserver.endpoints[0]
            self._server.iserver.endpoints.extend(
                copy.copy(template) for _ in range(768)
            )
        self._started.set()


def _free_tcp_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def _wait_for_listener(host: str, port: int) -> None:
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.1):
                return
        except OSError:
            time.sleep(0.02)
    raise RuntimeError("OPC UA laboratory server did not listen in time")
