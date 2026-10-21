from __future__ import annotations

import asyncio
import copy
import socket
import threading
import time
from types import TracebackType

from asyncua import ua
from asyncua.common.utils import ServiceError
from asyncua.server import Server
from asyncua.server.internal_session import InternalSession
from asyncua.server.uaprocessor import UaProcessor
from asyncua.ua.ua_binary import nodeid_from_binary

_REQUEST_LOCK = threading.Lock()
_RECEIVED_REQUESTS: list[int] = []
_PATCH_LOCK = threading.Lock()
_ORIGINAL_PROCESS_MESSAGE = UaProcessor.process_message
_ORIGINAL_ACTIVATE_SESSION = InternalSession.activate_session
_ORIGINAL_BROWSE = InternalSession.browse
_LAB_DELAY_GET_ENDPOINTS = 0.0
_LAB_DENY_ANONYMOUS = False
_LAB_DENY_BROWSE = False
_LAB_DENY_BROWSE_AFTER_FIRST = False
_LAB_BROWSE_ERROR_AFTER_FIRST = False
_LAB_DELAY_SECOND_BROWSE = 0.0
_LAB_BROWSE_COUNT = 0


class OpcUaLabServer:
    """Disposable OPC UA server bound only to loopback and an ephemeral port."""

    host = "127.0.0.1"

    def __init__(
        self, *, oversized: bool = False, delay_get_endpoints: float = 0,
        deny_anonymous: bool = False,
        deny_browse: bool = False,
        deny_browse_after_first: bool = False,
        browse_error_after_first: bool = False,
        delay_second_browse: float = 0,
        bulk_variables: int = 0,
        long_identifiers: bool = False,
        opaque_sentinel: str | None = None,
        opaque_metadata_sentinel: str | None = None,
    ) -> None:
        self.port = _free_tcp_port()
        self._oversized = oversized
        self._delay_get_endpoints = delay_get_endpoints
        self._deny_anonymous = deny_anonymous
        self._deny_browse = deny_browse
        self._deny_browse_after_first = deny_browse_after_first
        self._browse_error_after_first = browse_error_after_first
        self._delay_second_browse = delay_second_browse
        self._bulk_variables = max(0, bulk_variables)
        self._long_identifiers = long_identifiers
        self._opaque_sentinel = opaque_sentinel
        self._opaque_metadata_sentinel = opaque_metadata_sentinel
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
            InternalSession.activate_session = _ORIGINAL_ACTIVATE_SESSION
            InternalSession.browse = _ORIGINAL_BROWSE
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
        InternalSession.activate_session = _ORIGINAL_ACTIVATE_SESSION
        InternalSession.browse = _ORIGINAL_BROWSE
        if self._thread.is_alive():
            raise RuntimeError("OPC UA laboratory server did not stop")

    def _install_observer(self) -> None:
        global _LAB_DELAY_GET_ENDPOINTS
        global _LAB_DENY_ANONYMOUS
        global _LAB_DENY_BROWSE
        global _LAB_DENY_BROWSE_AFTER_FIRST
        global _LAB_BROWSE_ERROR_AFTER_FIRST
        global _LAB_DELAY_SECOND_BROWSE, _LAB_BROWSE_COUNT
        _LAB_DELAY_GET_ENDPOINTS = self._delay_get_endpoints
        _LAB_DENY_ANONYMOUS = self._deny_anonymous
        _LAB_DENY_BROWSE = self._deny_browse
        _LAB_DENY_BROWSE_AFTER_FIRST = self._deny_browse_after_first
        _LAB_BROWSE_ERROR_AFTER_FIRST = self._browse_error_after_first
        _LAB_DELAY_SECOND_BROWSE = self._delay_second_browse
        _LAB_BROWSE_COUNT = 0

        def activate_session(self, params, peer_certificate):
            if _LAB_DENY_ANONYMOUS:
                raise ServiceError(ua.StatusCodes.BadUserAccessDenied)
            return _ORIGINAL_ACTIVATE_SESSION(self, params, peer_certificate)

        async def browse(self, params):
            if _LAB_BROWSE_ERROR_AFTER_FIRST and _LAB_BROWSE_COUNT >= 2:
                raise ServiceError(ua.StatusCodes.BadEncodingLimitsExceeded)
            if _LAB_DENY_BROWSE or (
                _LAB_DENY_BROWSE_AFTER_FIRST and _LAB_BROWSE_COUNT >= 2
            ):
                raise ServiceError(ua.StatusCodes.BadUserAccessDenied)
            return await _ORIGINAL_BROWSE(self, params)

        async def observed(
            self: UaProcessor, seqhdr: ua.SequenceHeader, body: ua.utils.Buffer
        ) -> bool:
            type_id = nodeid_from_binary(body.copy()).Identifier
            with _REQUEST_LOCK:
                _RECEIVED_REQUESTS.append(int(type_id))
                if type_id == ua.ObjectIds.BrowseRequest_Encoding_DefaultBinary:
                    global _LAB_BROWSE_COUNT
                    _LAB_BROWSE_COUNT += 1
                    browse_count = _LAB_BROWSE_COUNT
                else:
                    browse_count = 0
            if (
                _LAB_DELAY_SECOND_BROWSE
                and type_id == ua.ObjectIds.BrowseRequest_Encoding_DefaultBinary
                and browse_count == 2
            ):
                await asyncio.sleep(_LAB_DELAY_SECOND_BROWSE)
            if (
                _LAB_DELAY_GET_ENDPOINTS
                and type_id == ua.ObjectIds.GetEndpointsRequest_Encoding_DefaultBinary
            ):
                await asyncio.sleep(_LAB_DELAY_GET_ENDPOINTS)
            return await _ORIGINAL_PROCESS_MESSAGE(self, seqhdr, body)

        with _PATCH_LOCK:
            InternalSession.activate_session = activate_session
            InternalSession.browse = browse
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
        if self._deny_anonymous:
            self._server.iserver.user_manager = _DenyAnonymousUserManager()
        namespace = await self._server.register_namespace("urn:dmitri:opcua-lab")
        device = await self._server.nodes.objects.add_object(namespace, "LabDevice")
        await device.add_variable(namespace, "ProcessValue", "PROCESS_VALUE_SENTINEL")
        for index in range(self._bulk_variables):
            if self._long_identifiers:
                node_id = ua.NodeId(
                    f"N{index:03d}" + "n" * 124,
                    namespace,
                    ua.NodeIdType.String,
                )
                await self._server.nodes.objects.add_variable(
                    node_id, "B" * 128, index
                )
            else:
                await self._server.nodes.objects.add_variable(
                    namespace, f"Bulk_{index}", index
                )
        if self._opaque_sentinel is not None:
            opaque_node_id = ua.NodeId(
                self._opaque_sentinel.encode(), namespace, ua.NodeIdType.ByteString
            )
            await device.add_variable(opaque_node_id, "OpaqueSentinel", 1)
        if self._opaque_metadata_sentinel is not None:
            datatype_id = ua.NodeId(
                (self._opaque_metadata_sentinel + "_DATA").encode(),
                namespace,
                ua.NodeIdType.ByteString,
            )
            reference_type_id = ua.NodeId(
                (self._opaque_metadata_sentinel + "_REF").encode(),
                namespace,
                ua.NodeIdType.ByteString,
            )
            opaque_typed = await device.add_variable(
                namespace, "OpaqueDataType", 7, datatype=datatype_id
            )
            references_node = self._server.get_node(ua.ObjectIds.References)
            await references_node.add_reference_type(
                reference_type_id, "OpaqueReferenceType", symmetric=False
            )
            hierarchical = self._server.get_node(
                ua.ObjectIds.HierarchicalReferences
            )
            await hierarchical.add_reference(
                reference_type_id,
                ua.ObjectIds.HasSubtype,
                forward=True,
                bidirectional=False,
            )
            await device.add_reference(
                opaque_typed, reference_type_id, forward=True, bidirectional=False
            )
        await device.add_reference(
            self._server.nodes.objects,
            ua.ObjectIds.HierarchicalReferences,
            forward=True,
            bidirectional=False,
        )
        external_reference = ua.AddReferencesItem(
            SourceNodeId=device.nodeid,
            ReferenceTypeId=ua.NodeId(ua.ObjectIds.HierarchicalReferences),
            IsForward=True,
            TargetServerUri="opc.tcp://192.0.2.99:4840/",
            TargetNodeId=ua.ExpandedNodeId(Identifier=99, ServerIndex=1),
            TargetNodeClass=ua.NodeClass.Object,
        )
        await device.session.add_references([external_reference])
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


class _DenyAnonymousUserManager:
    def get_user(self, _iserver, *, username=None, password=None, certificate=None):
        del password
        if username is None and certificate is None:
            return None
        from asyncua.crypto.permission_rules import User, UserRole

        return User(role=UserRole.User, name=username)


def _wait_for_listener(host: str, port: int) -> None:
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.1):
                return
        except OSError:
            time.sleep(0.02)
    raise RuntimeError("OPC UA laboratory server did not listen in time")
