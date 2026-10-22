"""Check installed OPC UA runtime against a disposable loopback server."""

from __future__ import annotations

import asyncio
import socket

import agent.ot.opcua.client as opcua_client_module
from agent.ot.opcua.client import OpcUaClient
from agent.ot.opcua.inventory import inventory_opcua_service
from agent.ot.opcua.mapper import map_opcua_service
from asyncua import Server


async def _run() -> None:
    # QEMU's first cold subprocess import can be far slower than an installed
    # Raspberry Pi. Give only this post-install harness up to 30 seconds for
    # helper startup/IPC; the actual OPC UA operation timeout remains capped at
    # two seconds in both client and worker.
    opcua_client_module.HELPER_STARTUP_GRACE_SECONDS = 28.0

    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]

    server = Server()
    await server.init()
    server.set_endpoint(f"opc.tcp://127.0.0.1:{port}/")
    namespace = await server.register_namespace("urn:dmitri:task9-loopback")
    device = await server.nodes.objects.add_object(namespace, "LabDevice")
    await device.add_variable(namespace, "LabValue", 7)

    async with server:
        client = OpcUaClient()
        inventory = await inventory_opcua_service(
            client, "127.0.0.1", port, timeout=2, pacing_ms=0
        )
        assert inventory.confidence == "confirmed", inventory
        assert inventory.request_count_known, inventory
        assert inventory.requests_sent > 0, inventory
        mapping = await map_opcua_service(
            client,
            "127.0.0.1",
            port,
            inventory.client_endpoints,
            timeout=2,
            deadline=90,
            pacing_ms=0,
        )
        assert mapping.status in {"complete", "partial"}, mapping
        assert mapping.nodes
        assert any(node.browse_name == "LabValue" for node in mapping.nodes), mapping


if __name__ == "__main__":
    asyncio.run(_run())
    print("Loopback OPC UA inventory and bounded mapping passed")
