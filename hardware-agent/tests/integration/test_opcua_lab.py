from __future__ import annotations

import asyncio

from agent.config import AgentSettings
from agent.ot.opcua.client import OpcUaClient
from agent.ot.opcua.inventory import inventory_opcua_service
from agent.ot.opcua.mapper import map_opcua_service
from agent.scanner.models import HostInfo, PortInfo, ServiceInfo
from agent.scanner.stages import build_host_payload, run_ot_inspection_stage
from asyncua import ua

from tests.fixtures.modbus_lab import ModbusLabServer
from tests.fixtures.opcua_lab import OpcUaLabServer

READ_ONLY_REQUESTS = {
    ua.ObjectIds.GetEndpointsRequest_Encoding_DefaultBinary,
    ua.ObjectIds.CreateSessionRequest_Encoding_DefaultBinary,
    ua.ObjectIds.ActivateSessionRequest_Encoding_DefaultBinary,
    ua.ObjectIds.BrowseRequest_Encoding_DefaultBinary,
    ua.ObjectIds.BrowseNextRequest_Encoding_DefaultBinary,
    ua.ObjectIds.ReadRequest_Encoding_DefaultBinary,
    ua.ObjectIds.CloseSessionRequest_Encoding_DefaultBinary,
    ua.ObjectIds.CloseSecureChannelRequest_Encoding_DefaultBinary,
}


def test_loopback_success_wire_counts_privacy_and_read_only_boundary() -> None:
    async def run(server: OpcUaLabServer) -> None:
        client = OpcUaClient()
        inventory = await inventory_opcua_service(
            client, server.host, server.port, timeout=2, pacing_ms=100
        )
        result = await client.map_anonymous(
            server.host,
            server.port,
            inventory.client_endpoints[0],
            timeout=2,
            pacing_ms=100,
        )
        assert result.mapping is not None
        # An external reference in the fixture makes this a bounded partial result.
        assert result.mapping.status == "partial"
        assert "external_reference" in result.mapping.reason_codes
        assert result.mapping.value_reads_attempted > 0
        assert "PROCESS_VALUE_SENTINEL" not in repr((inventory, result))
        # HEL, OpenSecureChannel, GetEndpoints, and CloseSecureChannel.
        assert inventory.requests_sent == 4
        assert result.stats.requests_total == sum(result.stats.requests.values())
        observed = server.received_request_type_ids
        assert observed
        assert set(observed) <= READ_ONLY_REQUESTS
        assert observed.count(
            ua.ObjectIds.GetEndpointsRequest_Encoding_DefaultBinary
        ) == 2
        assert observed.count(ua.ObjectIds.BrowseRequest_Encoding_DefaultBinary) == (
            result.stats.requests.get("Browse", 0)
        )
        assert observed.count(
            ua.ObjectIds.BrowseNextRequest_Encoding_DefaultBinary
        ) == result.stats.requests.get("BrowseNext", 0)
        assert observed.count(ua.ObjectIds.ReadRequest_Encoding_DefaultBinary) == (
            result.stats.requests.get("Read", 0)
        )
        assert observed.count(
            ua.ObjectIds.CloseSessionRequest_Encoding_DefaultBinary
        ) == result.stats.requests.get("CloseSession", 0)

    with OpcUaLabServer() as server:
        assert server.host == "127.0.0.1"
        asyncio.run(run(server))


def test_loopback_denial_and_hostile_server_keep_partial_facts_bounded() -> None:
    async def inspect(server: OpcUaLabServer) -> tuple[str, int, int]:
        client = OpcUaClient()
        inventory = await inventory_opcua_service(client, server.host, server.port)
        endpoint = next(
            item
            for item in inventory.client_endpoints
            if "Anonymous" in item.user_token_types
        )
        result = await map_opcua_service(
            client, server.host, server.port, inventory.client_endpoints
        )
        assert result.status in {"denied", "partial"}
        assert result.requests_sent <= 32
        assert len(result.nodes) <= 128
        assert len(result.references) <= 512
        assert "PROCESS_VALUE_SENTINEL" not in repr((inventory, result))
        assert endpoint.endpoint_url == f"opc.tcp://{server.host}:{server.port}/"
        return (
            result.status,
            result.requests_sent,
            len(server.received_request_type_ids),
        )

    with OpcUaLabServer(deny_anonymous=True) as denied:
        status, requests, wire = asyncio.run(inspect(denied))
        assert status == "denied"
        assert requests > 0 and wire > 0
        assert (
            ua.ObjectIds.BrowseRequest_Encoding_DefaultBinary
            not in denied.received_request_type_ids
        )

    with OpcUaLabServer(
        bulk_variables=180,
        long_identifiers=True,
        opaque_sentinel="HOSTILE_NODE_SENTINEL",
    ) as hostile:
        _status, requests, wire = asyncio.run(inspect(hostile))
        assert requests <= 32
        assert wire > 0
        assert set(hostile.received_request_type_ids) <= READ_ONLY_REQUESTS


def test_loopback_cancellation_sends_no_session_cleanup_after_cancel() -> None:
    async def run(server: OpcUaLabServer) -> None:
        client = OpcUaClient()
        inventory = await inventory_opcua_service(client, server.host, server.port)
        start = len(server.received_request_type_ids)
        task = asyncio.create_task(
            client.map_anonymous(
                server.host,
                server.port,
                inventory.client_endpoints[0],
                timeout=5,
            )
        )
        loop = asyncio.get_running_loop()
        deadline = loop.time() + 3
        while loop.time() < deadline:
            observed = server.received_request_type_ids[start:]
            if ua.ObjectIds.BrowseRequest_Encoding_DefaultBinary in observed:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                else:
                    raise AssertionError("cancelled mapping returned normally")
                observed = server.received_request_type_ids[start:]
                assert (
                    ua.ObjectIds.CreateSessionRequest_Encoding_DefaultBinary
                    in observed
                )
                assert (
                    ua.ObjectIds.CloseSessionRequest_Encoding_DefaultBinary
                    not in observed
                )
                return
            await asyncio.sleep(0.02)
        task.cancel()
        raise AssertionError("mapping did not reach a real loopback Browse request")

    with OpcUaLabServer(delay_second_browse=2.5) as server:
        asyncio.run(run(server))


def test_same_host_dual_protocol_inventory_preserves_modbus_and_opcua() -> None:
    with ModbusLabServer() as modbus, OpcUaLabServer() as opcua:
        host = HostInfo(
            ip="127.0.0.1",
            hostname="dual-protocol-lab",
            ports=[
                PortInfo(port=modbus.port, service=ServiceInfo(name="modbus")),
                PortInfo(port=opcua.port, service=ServiceInfo(name="opcua")),
            ],
        )
        run_ot_inspection_stage(AgentSettings(scan_mode="nspi"), [host])
        industrial = build_host_payload(host).industrial_services

        assert [service.protocol for service in industrial] == [
            "modbus_tcp",
            "opcua_tcp",
        ]
        assert industrial[0].units[0].status == "responding"
        assert industrial[0].units[0].device_identification is not None
        assert industrial[1].confidence == "confirmed"
        assert industrial[1].observation is not None
        assert industrial[1].observation.mapping is None
        assert "PROCESS_VALUE_SENTINEL" not in repr(industrial)
        assert set(opcua.received_request_type_ids) <= READ_ONLY_REQUESTS
