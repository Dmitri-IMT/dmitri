import asyncio
import json
import os
import subprocess
import sys

import pytest

from tests.fixtures.opcua_lab import OpcUaLabServer


def test_worker_get_endpoints_uses_raw_guarded_transport() -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(("hardware-agent/src", "hardware-agent/tests"))
    with OpcUaLabServer() as server:
        result = subprocess.run(
            [sys.executable, "-m", "agent.ot.opcua.worker"],
            input=json.dumps(
                {
                    "operation": "get_endpoints",
                    "host": server.host,
                    "port": server.port,
                    "request_budget": 8,
                    "timeout_ms": 2000,
                    "pacing_ms": 100,
                    "deadline_ms": 10000,
                }
            ),
            capture_output=True,
            text=True,
            env=env,
            timeout=15,
            check=False,
        )
        received = server.received_request_type_ids
    assert result.returncode == 0, result.stderr
    response = json.loads(result.stdout)
    assert response["status"] == "ok", (json.dumps(response), received)
    assert response["endpoints"]
    assert response["hello_limits"] == [65536, 65536, 131072, 16]
    assert response["requests_total"] == sum(response["requests"].values())
    assert response["request_attempts"] >= response["requests_total"]
    assert response["write_requests_sent"] == 0
    assert response["request_count_known"] is True


def test_worker_response_is_json_bounded_and_does_not_echo_command_values() -> None:
    response = {"status": "error", "code": "invalid_request"}
    payload = json.dumps(response, separators=(",", ":")).encode()
    assert len(payload) <= 128 * 1024
    assert b"secret" not in payload


@pytest.mark.asyncio
async def test_timeout_result_includes_send_ambiguity_after_writer_cleanup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from agent.ot.opcua import worker

    async def suspended_send(_sock: object, _data: bytes) -> None:
        await asyncio.Event().wait()

    with OpcUaLabServer() as server:
        monkeypatch.setattr(asyncio.get_running_loop(), "sock_sendall", suspended_send)
        result = await worker.execute(
            {
                "operation": "get_endpoints",
                "host": server.host,
                "port": server.port,
                "request_budget": 8,
                "timeout_ms": 50,
                "pacing_ms": 100,
                "deadline_ms": 50,
            }
        )
    assert result["status"] == "error"
    assert result["code"] == "timeout"
    assert result["request_count_known"] is False


@pytest.mark.asyncio
@pytest.mark.parametrize("cleanup_failure", ["error", "timeout"])
async def test_close_channel_failure_keeps_mapping_and_final_stats(
    monkeypatch: pytest.MonkeyPatch, cleanup_failure: str
) -> None:
    from agent.ot.opcua import worker
    from asyncua import ua

    with OpcUaLabServer() as server:
        command = {
            "operation": "get_endpoints",
            "host": server.host,
            "port": server.port,
            "request_budget": 24,
            "timeout_ms": 2000,
            "pacing_ms": 100,
            "deadline_ms": 15000,
        }
        discovery = await worker.execute(command)
        endpoint = next(
            item
            for item in discovery["endpoints"]
            if "Anonymous" in item["user_token_types"]
        )

        received_before_map = len(server.received_request_type_ids)
        close_secure_channel = worker.GuardedProtocol.close_secure_channel

        async def fail_close(self: object) -> None:
            await close_secure_channel(self)
            if cleanup_failure == "timeout":
                await asyncio.sleep(1.2)
                return
            raise ConnectionError("injected close failure")

        monkeypatch.setattr(worker.GuardedProtocol, "close_secure_channel", fail_close)
        result = await worker.execute(
            {
                **command,
                "operation": "map_anonymous",
                "endpoint_url": endpoint["endpoint_url"],
            }
        )
        mapping_requests = server.received_request_type_ids[received_before_map:]

    assert result["status"] == "ok"
    assert result["mapping"]["nodes"]
    assert result["mapping"]["phase"]["status"] == "partial"
    expected_reason = "timeout" if cleanup_failure == "timeout" else "service_error"
    assert expected_reason in result["mapping"]["phase"]["reason_codes"]
    assert "external_reference" in result["mapping"]["phase"]["reason_codes"]
    assert result["requests"]["CloseSession"] == 1
    assert result["requests"]["CloseSecureChannel"] == 1
    assert result["requests_total"] == sum(result["requests"].values())
    assert result["request_count_known"] is True
    assert ua.ObjectIds.CloseSessionRequest_Encoding_DefaultBinary in mapping_requests
