from __future__ import annotations

import asyncio
import base64
import importlib.util
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest
from agent.ot.opcua.client import OpcUaClient, _helper_command
from asyncua import ua

ROOT = Path(__file__).resolve().parents[2]
HELPER = ROOT / "src/agent/ot/opcua/helper/opcua-bridge.csproj"
_fixture_spec = importlib.util.spec_from_file_location(
    "opcua_lab", ROOT / "tests/fixtures/opcua_lab.py"
)
assert _fixture_spec is not None and _fixture_spec.loader is not None
_fixture_module = importlib.util.module_from_spec(_fixture_spec)
_fixture_spec.loader.exec_module(_fixture_module)
OpcUaLabServer = _fixture_module.OpcUaLabServer


async def _raw_mapping_stdout(host: str, port: int) -> bytes:
    request = json.dumps(
        {
            "operation": "map_anonymous",
            "host": host,
            "port": port,
            "endpoint_url": f"opc.tcp://{host}:{port}/",
            "request_budget": 32,
            "timeout_ms": 2000,
            "deadline_ms": 90000,
        },
        separators=(",", ":"),
    ).encode("utf-8")
    process = await asyncio.create_subprocess_exec(
        *_helper_command(),
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )
    stdout, _ = await process.communicate(request)
    assert process.returncode == 0
    return stdout


@pytest.fixture(scope="module", autouse=True)
def _built_helper() -> None:
    dotnet = shutil.which("dotnet")
    if dotnet is None:
        pytest.skip(
            ".NET SDK is not installed; helper installation is validated in Task 9"
        )
    env = os.environ.copy()
    env["DOTNET_HOST_PATH"] = dotnet
    env["DOTNET_ROOT"] = str(Path(dotnet).parent)
    subprocess.run(
        [dotnet, "build", str(HELPER), "--nologo", "--verbosity", "quiet"],
        cwd=ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )


@pytest.mark.asyncio
async def test_discovery_observes_real_get_endpoints_and_closes_channel(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dotnet = shutil.which("dotnet")
    assert dotnet is not None
    monkeypatch.setenv("DOTNET_HOST_PATH", dotnet)
    monkeypatch.setenv("DOTNET_ROOT", str(Path(dotnet).parent))

    with OpcUaLabServer() as server:
        result = await OpcUaClient().discover_endpoints(server.host, server.port)

        assert result.status == "ok"
        assert result.endpoints
        assert (
            result.endpoints[0].endpoint_url
            == f"opc.tcp://{server.host}:{server.port}/"
        )
        assert result.endpoints[0].security_policy_uri
        assert result.endpoints[0].security_mode == "None"
        assert result.stats.requests["GetEndpoints"] == 1
        assert result.stats.requests["CloseSecureChannel"] == 1
        assert result.stats.hello_limits == (64 * 1024, 64 * 1024, 128 * 1024, 16)
        assert server.received_request_type_ids == (
            ua.ObjectIds.GetEndpointsRequest_Encoding_DefaultBinary,
        )


@pytest.mark.asyncio
async def test_probe_sends_only_allowlisted_metadata_services(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dotnet = shutil.which("dotnet")
    assert dotnet is not None
    monkeypatch.setenv("DOTNET_HOST_PATH", dotnet)
    monkeypatch.setenv("DOTNET_ROOT", str(Path(dotnet).parent))

    with OpcUaLabServer() as server:
        result = await OpcUaClient().probe_read_only_services(server.host, server.port)

        assert result.status == "ok"
        assert result.endpoints == ()
        assert result.stats.requests == {
            "HEL": 1,
            "OpenSecureChannel": 1,
            "GetEndpoints": 1,
            "Browse": 1,
            "BrowseNext": 1,
            "Read": 1,
            "CloseSecureChannel": 1,
        }
        assert server.received_request_type_ids == (
            ua.ObjectIds.GetEndpointsRequest_Encoding_DefaultBinary,
            ua.ObjectIds.BrowseRequest_Encoding_DefaultBinary,
            ua.ObjectIds.BrowseNextRequest_Encoding_DefaultBinary,
            ua.ObjectIds.ReadRequest_Encoding_DefaultBinary,
        )


@pytest.mark.asyncio
async def test_anonymous_mapping_uses_one_session_and_read_only_services(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dotnet = shutil.which("dotnet")
    assert dotnet is not None
    monkeypatch.setenv("DOTNET_HOST_PATH", dotnet)
    monkeypatch.setenv("DOTNET_ROOT", str(Path(dotnet).parent))

    with OpcUaLabServer() as server:
        client = OpcUaClient()
        discovery = await client.discover_endpoints(server.host, server.port)
        endpoint = next(
            item for item in discovery.endpoints if "Anonymous" in item.user_token_types
        )
        before = len(server.received_request_type_ids)
        result = await client.map_anonymous(server.host, server.port, endpoint)

        assert result.status == "ok", result.error
        assert result.mapping is not None, result
        assert result.stats.requests_total <= 32
        assert result.mapping.value_reads_attempted >= 1
        assert len(result.mapping.references) <= 512
        assert result.mapping.references
        assert "PROCESS_VALUE_SENTINEL" not in repr(result)
        assert result.mapping.references
        assert any(
            edge.target_node_id in {"i=85", "ns=0;i=85"}
            for edge in result.mapping.references
        )
        node_ids = [node.node_id for node in result.mapping.nodes]
        assert len(node_ids) == len(set(node_ids))
        assert "external_reference" in result.mapping.reason_codes
        sent = server.received_request_type_ids[before:]
        assert ua.ObjectIds.CreateSessionRequest_Encoding_DefaultBinary in sent
        assert ua.ObjectIds.ActivateSessionRequest_Encoding_DefaultBinary in sent
        assert ua.ObjectIds.BrowseRequest_Encoding_DefaultBinary in sent
        assert ua.ObjectIds.ReadRequest_Encoding_DefaultBinary in sent
        assert ua.ObjectIds.CloseSessionRequest_Encoding_DefaultBinary in sent
        assert ua.ObjectIds.WriteRequest_Encoding_DefaultBinary not in sent


@pytest.mark.asyncio
async def test_live_mapping_caps_large_browse_results_before_ipc(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dotnet = shutil.which("dotnet")
    assert dotnet is not None
    monkeypatch.setenv("DOTNET_HOST_PATH", dotnet)
    monkeypatch.setenv("DOTNET_ROOT", str(Path(dotnet).parent))

    with OpcUaLabServer(bulk_variables=180, long_identifiers=True) as server:
        raw_stdout = await _raw_mapping_stdout(server.host, server.port)
        assert len(raw_stdout) <= 131072
        assert len(raw_stdout.decode("utf-8").encode("utf-8")) == len(raw_stdout)
        client = OpcUaClient()
        discovery = await client.discover_endpoints(server.host, server.port)
        endpoint = next(
            item for item in discovery.endpoints if "Anonymous" in item.user_token_types
        )
        before = len(server.received_request_type_ids)
        result = await client.map_anonymous(server.host, server.port, endpoint)

        assert result.mapping is not None
        assert 0 < len(result.mapping.nodes) <= 128
        assert (
            "node_limit" in result.mapping.reason_codes
            or len(result.mapping.nodes) < 128
        )
        assert len(result.mapping.nodes) <= 128
        assert len(result.mapping.references) <= 512
        sent = server.received_request_type_ids[before:]
        assert sent.count(ua.ObjectIds.BrowseNextRequest_Encoding_DefaultBinary) <= 16
        assert result.stats.requests_total <= 32


@pytest.mark.asyncio
async def test_opaque_node_sentinel_is_absent_from_raw_helper_stdout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dotnet = shutil.which("dotnet")
    assert dotnet is not None
    monkeypatch.setenv("DOTNET_HOST_PATH", dotnet)
    monkeypatch.setenv("DOTNET_ROOT", str(Path(dotnet).parent))
    sentinel = "OPAQUE_NODE_SENTINEL_REVIEW"

    with OpcUaLabServer(
        opaque_sentinel=sentinel,
        opaque_metadata_sentinel=sentinel + "_METADATA",
    ) as server:
        raw_stdout = await _raw_mapping_stdout(server.host, server.port)

        assert len(raw_stdout) <= 131072
        for secret in (
            sentinel,
            sentinel + "_METADATA_DATA",
            sentinel + "_METADATA_REF",
        ):
            secret_bytes = secret.encode()
            assert secret_bytes not in raw_stdout
            assert base64.b64encode(secret_bytes) not in raw_stdout
        response = json.loads(raw_stdout)
        assert "opaque_node_id_omitted" in response["mapping"]["phase"]["reason_codes"]
        opaque_data_node = next(
            node
            for node in response["mapping"]["nodes"]
            if node["browse_name"] == "OpaqueDataType"
        )
        assert opaque_data_node["data_type"] is None
        discovery = await OpcUaClient().discover_endpoints(server.host, server.port)
        endpoint = next(
            item for item in discovery.endpoints if "Anonymous" in item.user_token_types
        )
        mapping = await OpcUaClient().map_anonymous(server.host, server.port, endpoint)
        assert mapping.mapping is not None
        assert "opaque_node_id_omitted" in mapping.mapping.reason_codes


@pytest.mark.asyncio
async def test_anonymous_denial_is_explicit_on_real_loopback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dotnet = shutil.which("dotnet")
    assert dotnet is not None
    monkeypatch.setenv("DOTNET_HOST_PATH", dotnet)
    monkeypatch.setenv("DOTNET_ROOT", str(Path(dotnet).parent))

    with OpcUaLabServer(deny_anonymous=True) as server:
        client = OpcUaClient()
        discovery = await client.discover_endpoints(server.host, server.port)
        endpoint = next(
            item for item in discovery.endpoints if "Anonymous" in item.user_token_types
        )
        result = await client.map_anonymous(server.host, server.port, endpoint)

        assert result.mapping is not None, result
        assert result.mapping.status == "denied", result.mapping
        assert "anonymous_denied" in result.mapping.reason_codes
        assert result.mapping.anonymous_session_activated is False
        assert result.mapping.browse_succeeded is None
        assert (
            server.received_request_type_ids.count(
                ua.ObjectIds.CloseSessionRequest_Encoding_DefaultBinary
            )
            == 1
        )
        assert result.mapping.nodes == ()
        assert (
            ua.ObjectIds.BrowseRequest_Encoding_DefaultBinary
            not in server.received_request_type_ids
        )


@pytest.mark.asyncio
async def test_browse_denial_keeps_prior_loopback_references(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dotnet = shutil.which("dotnet")
    assert dotnet is not None
    monkeypatch.setenv("DOTNET_HOST_PATH", dotnet)
    monkeypatch.setenv("DOTNET_ROOT", str(Path(dotnet).parent))

    with OpcUaLabServer(deny_browse_after_first=True) as server:
        client = OpcUaClient()
        discovery = await client.discover_endpoints(server.host, server.port)
        endpoint = next(
            item for item in discovery.endpoints if "Anonymous" in item.user_token_types
        )
        result = await client.map_anonymous(server.host, server.port, endpoint)

        assert result.mapping is not None
        assert result.mapping.status == "partial"
        assert "anonymous_denied" in result.mapping.reason_codes
        assert result.mapping.anonymous_session_activated is True
        assert result.mapping.browse_succeeded is False
        assert result.mapping.references_observed > 0
        assert result.mapping.nodes
        assert "PROCESS_VALUE_SENTINEL" not in repr(result)
        assert (
            server.received_request_type_ids.count(
                ua.ObjectIds.BrowseRequest_Encoding_DefaultBinary
            )
            == 2
        )


@pytest.mark.asyncio
async def test_browse_decoder_limit_keeps_prior_loopback_nodes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dotnet = shutil.which("dotnet")
    assert dotnet is not None
    monkeypatch.setenv("DOTNET_HOST_PATH", dotnet)
    monkeypatch.setenv("DOTNET_ROOT", str(Path(dotnet).parent))

    with OpcUaLabServer(browse_error_after_first=True) as server:
        client = OpcUaClient()
        discovery = await client.discover_endpoints(server.host, server.port)
        endpoint = next(
            item for item in discovery.endpoints if "Anonymous" in item.user_token_types
        )
        result = await client.map_anonymous(server.host, server.port, endpoint)

        assert result.mapping is not None
        assert result.mapping.status == "partial"
        assert result.mapping.truncated is True
        assert "message_size_limit" in result.mapping.reason_codes
        assert result.mapping.nodes
        assert result.mapping.references_observed > 0
        assert "PROCESS_VALUE_SENTINEL" not in repr(result)


@pytest.mark.asyncio
async def test_budget_exhaustion_keeps_observed_mapping_nodes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dotnet = shutil.which("dotnet")
    assert dotnet is not None
    monkeypatch.setenv("DOTNET_HOST_PATH", dotnet)
    monkeypatch.setenv("DOTNET_ROOT", str(Path(dotnet).parent))

    with OpcUaLabServer() as server:
        client = OpcUaClient()
        discovery = await client.discover_endpoints(server.host, server.port)
        endpoint = next(
            item for item in discovery.endpoints if "Anonymous" in item.user_token_types
        )
        result = await client.map_anonymous(
            server.host, server.port, endpoint, request_budget=12
        )

        assert result.mapping is not None
        assert result.mapping.status in {"partial", "timed_out"}
        assert result.mapping.nodes
        assert result.mapping.references_observed > 0
        assert "request_budget_exhausted" in result.mapping.reason_codes
        assert result.stats.requests_total <= 12


@pytest.mark.asyncio
async def test_timeout_on_second_browse_keeps_first_browse_nodes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dotnet = shutil.which("dotnet")
    assert dotnet is not None
    monkeypatch.setenv("DOTNET_HOST_PATH", dotnet)
    monkeypatch.setenv("DOTNET_ROOT", str(Path(dotnet).parent))

    with OpcUaLabServer(delay_second_browse=2.5) as server:
        client = OpcUaClient()
        discovery = await client.discover_endpoints(server.host, server.port)
        endpoint = next(
            item for item in discovery.endpoints if "Anonymous" in item.user_token_types
        )
        result = await client.map_anonymous(
            server.host, server.port, endpoint, timeout=1.8
        )

        assert result.mapping is not None
        assert result.mapping.status in {"partial", "timed_out"}
        assert result.mapping.nodes
        assert result.mapping.references_observed > 0
        assert result.mapping.reason_codes
        assert result.mapping.application_value_read_succeeded is None
        sent = server.received_request_type_ids
        assert sent.count(ua.ObjectIds.BrowseRequest_Encoding_DefaultBinary) == 2


@pytest.mark.asyncio
async def test_mapping_cancellation_after_create_session_sends_no_cleanup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dotnet = shutil.which("dotnet")
    assert dotnet is not None
    monkeypatch.setenv("DOTNET_HOST_PATH", dotnet)
    monkeypatch.setenv("DOTNET_ROOT", str(Path(dotnet).parent))

    with OpcUaLabServer(delay_second_browse=2.5) as server:
        client = OpcUaClient()
        discovery = await client.discover_endpoints(server.host, server.port)
        endpoint = next(
            item for item in discovery.endpoints if "Anonymous" in item.user_token_types
        )
        start = len(server.received_request_type_ids)
        task = asyncio.create_task(
            client.map_anonymous(server.host, server.port, endpoint, timeout=5.0)
        )
        deadline = asyncio.get_running_loop().time() + 3.0
        while True:
            sent = server.received_request_type_ids[start:]
            if sent.count(ua.ObjectIds.BrowseRequest_Encoding_DefaultBinary) >= 2:
                break
            if asyncio.get_running_loop().time() >= deadline:
                pytest.fail("mapping did not reach its delayed Browse request")
            await asyncio.sleep(0.02)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

        sent = server.received_request_type_ids[start:]
        assert ua.ObjectIds.CreateSessionRequest_Encoding_DefaultBinary in sent
        assert ua.ObjectIds.CloseSessionRequest_Encoding_DefaultBinary not in sent


@pytest.mark.asyncio
async def test_timeout_aborts_delayed_service_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dotnet = shutil.which("dotnet")
    assert dotnet is not None
    monkeypatch.setenv("DOTNET_HOST_PATH", dotnet)
    monkeypatch.setenv("DOTNET_ROOT", str(Path(dotnet).parent))

    with OpcUaLabServer(delay_get_endpoints=1.8) as server:
        result = await OpcUaClient().discover_endpoints(
            server.host, server.port, timeout=1.5
        )

        assert result.status == "error"
        assert result.error == "timeout"
        assert server.received_request_type_ids == (
            ua.ObjectIds.GetEndpointsRequest_Encoding_DefaultBinary,
        )


@pytest.mark.asyncio
async def test_external_cancellation_kills_inflight_helper_without_cleanup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dotnet = shutil.which("dotnet")
    assert dotnet is not None
    monkeypatch.setenv("DOTNET_HOST_PATH", dotnet)
    monkeypatch.setenv("DOTNET_ROOT", str(Path(dotnet).parent))

    with OpcUaLabServer(delay_get_endpoints=2.0) as server:
        task = asyncio.create_task(
            OpcUaClient().discover_endpoints(server.host, server.port, timeout=2.0)
        )
        deadline = asyncio.get_running_loop().time() + 1.8
        while not server.received_request_type_ids:
            if asyncio.get_running_loop().time() >= deadline:
                pytest.fail("helper did not send GetEndpoints before cancellation")
            await asyncio.sleep(0.02)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

        assert server.received_request_type_ids == (
            ua.ObjectIds.GetEndpointsRequest_Encoding_DefaultBinary,
        )


@pytest.mark.asyncio
async def test_oversized_get_endpoints_returns_bounded_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dotnet = shutil.which("dotnet")
    assert dotnet is not None
    monkeypatch.setenv("DOTNET_HOST_PATH", dotnet)
    monkeypatch.setenv("DOTNET_ROOT", str(Path(dotnet).parent))

    with OpcUaLabServer(oversized=True) as server:
        result = await OpcUaClient().discover_endpoints(server.host, server.port)
        assert result.status == "error"
        assert result.error == "message_size_limit"
        assert result.stats.bytes_received > 128 * 1024
        assert server.received_request_type_ids == (
            ua.ObjectIds.GetEndpointsRequest_Encoding_DefaultBinary,
        )


def test_helper_rejects_non_literal_or_non_ipv4_targets() -> None:
    async def check() -> None:
        client = OpcUaClient()
        assert (
            await client.discover_endpoints("localhost", 4840)
        ).error == "invalid_target"
        assert (await client.discover_endpoints("::1", 4840)).error == "invalid_target"
        assert (
            await client.discover_endpoints("127.0.0.1", 65536)
        ).error == "invalid_target"

    asyncio.run(check())
