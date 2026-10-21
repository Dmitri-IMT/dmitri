from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable
from datetime import datetime, timezone
from uuid import UUID, uuid4

import httpx
import pytest
from agent.normalize.contracts import FindingPayload, HostPayload, ScanPayload
from agent.transport import (
    IngestConfig,
    ScanIngestClient,
    SubmissionResult,
    ingest,
)
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

DEVICE_ID = UUID("6f1b2c3d-4e5f-4a6b-8c9d-0e1f2a3b4c5d")
PRIVATE_KEY = bytes.fromhex("ab" * 32)
BACKEND_URL = "https://api.example.com"

CONFIG = IngestConfig(
    backend_url=BACKEND_URL, device_id=DEVICE_ID, private_key=PRIVATE_KEY
)
PUBLIC_KEY = Ed25519PrivateKey.from_private_bytes(PRIVATE_KEY).public_key()


def make_payload(scan_id: UUID | None = None) -> ScanPayload:
    return ScanPayload(
        scan_id=scan_id or uuid4(),
        timestamp=datetime(2026, 8, 5, 12, 0, tzinfo=timezone.utc),
        subnet="192.168.1.0/24",
        scan_mode="quick",
        hosts=[
            HostPayload(ip="192.168.1.10", hostname="alpha", vendor="Acme"),
            HostPayload(ip="192.168.1.11", hostname="beta", vendor="Acme"),
        ],
    )


def accepted_body(payload: ScanPayload, **overrides: object) -> dict[str, object]:
    return {
        "status": "accepted",
        "scan_id": str(payload.scan_id),
        "hosts_received": len(payload.hosts),
        **overrides,
    }


def build_client(
    handler: Callable[[httpx.Request], httpx.Response],
    requests: list[httpx.Request],
) -> tuple[ScanIngestClient, httpx.Client]:
    def capture(request: httpx.Request) -> httpx.Response:
        request.read()
        requests.append(request)
        return handler(request)

    http_client = httpx.Client(transport=httpx.MockTransport(capture))
    return ScanIngestClient(CONFIG, client=http_client), http_client


def respond(
    status: int, body: object = None, headers: dict[str, str] | None = None
) -> Callable[[httpx.Request], httpx.Response]:
    def handler(request: httpx.Request) -> httpx.Response:
        if body is None:
            return httpx.Response(status, headers=headers or {})
        return httpx.Response(status, json=body, headers=headers or {})

    return handler


def verify_signature(request: httpx.Request) -> None:
    canonical = (
        "POST\n/api/v1/scans\n"
        f"{request.headers['X-Device-Id']}\n"
        f"{request.headers['X-Timestamp']}\n"
        f"{request.headers['X-Nonce']}\n"
        f"{hashlib.sha256(request.content).hexdigest()}"
    )
    PUBLIC_KEY.verify(
        bytes.fromhex(request.headers["X-Signature"]), canonical.encode("utf-8")
    )


class TestRequestEnvelope:
    def test_target_headers_and_signature(self) -> None:
        payload = make_payload()
        requests: list[httpx.Request] = []
        client, _ = build_client(respond(202, accepted_body(payload)), requests)
        client.submit(payload)

        request = requests[0]
        assert request.method == "POST"
        assert str(request.url) == f"{BACKEND_URL}/api/v1/scans"
        assert request.headers["Content-Type"] == "application/json"

        body = request.content
        digest = hashlib.sha256(body).hexdigest()
        assert request.headers["X-Body-SHA256"] == digest
        assert request.headers["X-Device-Id"] == str(DEVICE_ID)

        canonical = (
            "POST\n/api/v1/scans\n"
            f"{request.headers['X-Device-Id']}\n"
            f"{request.headers['X-Timestamp']}\n"
            f"{request.headers['X-Nonce']}\n"
            f"{digest}"
        )
        PUBLIC_KEY.verify(
            bytes.fromhex(request.headers["X-Signature"]), canonical.encode("utf-8")
        )

    def test_signed_body_preserves_evidence_policy_and_issue_key(self) -> None:
        payload = make_payload().model_copy(
            update={
                "finding_evidence_policy_version": "1",
                "findings": [
                    FindingPayload(
                        ip="192.168.1.10",
                        issue_key="smb:signing",
                        severity="high",
                        title="SMB signing disabled",
                        description="The SMB service does not require signing.",
                        recommendation="Require SMB signing.",
                        evidence="The service reported signing as disabled.",
                    )
                ],
            }
        )
        requests: list[httpx.Request] = []
        client, _ = build_client(respond(202, accepted_body(payload)), requests)

        client.submit(payload)

        request = requests[0]
        body = json.loads(request.content)
        assert body["finding_evidence_policy_version"] == "1"
        assert body["findings"][0]["issue_key"] == "smb:signing"
        assert request.content == payload.model_dump_json().encode("utf-8")
        assert request.headers["X-Body-SHA256"] == hashlib.sha256(
            request.content
        ).hexdigest()
        verify_signature(request)

    def test_signature_rejects_trailing_newline_variant(self) -> None:
        payload = make_payload()
        requests: list[httpx.Request] = []
        client, _ = build_client(respond(202, accepted_body(payload)), requests)
        client.submit(payload)

        request = requests[0]
        canonical = (
            "POST\n/api/v1/scans\n"
            f"{request.headers['X-Device-Id']}\n"
            f"{request.headers['X-Timestamp']}\n"
            f"{request.headers['X-Nonce']}\n"
            f"{request.headers['X-Body-SHA256']}\n"
        )
        with pytest.raises(InvalidSignature):
            PUBLIC_KEY.verify(
                bytes.fromhex(request.headers["X-Signature"]), canonical.encode("utf-8")
            )

    def test_timestamp_and_nonce_shape(self) -> None:
        payload = make_payload()
        requests: list[httpx.Request] = []
        client, _ = build_client(respond(202, accepted_body(payload)), requests)
        client.submit(payload)

        headers = requests[0].headers
        parsed = datetime.fromisoformat(headers["X-Timestamp"])
        assert parsed.utcoffset() == timezone.utc.utcoffset(None)
        assert re.fullmatch(r"[0-9a-f]{32}", headers["X-Nonce"])
        assert re.fullmatch(r"[0-9a-f]{128}", headers["X-Signature"])


class TestScanIdOverride:
    def test_without_override_body_uses_payload_scan_id(self) -> None:
        payload = make_payload()
        requests: list[httpx.Request] = []
        client, _ = build_client(respond(202, accepted_body(payload)), requests)
        result = client.submit(payload)

        assert json.loads(requests[0].content)["scan_id"] == str(payload.scan_id)
        assert result.scan_id == payload.scan_id

    def test_override_used_without_mutating_caller_payload(self) -> None:
        payload = make_payload()
        assigned = uuid4()
        requests: list[httpx.Request] = []
        client, _ = build_client(
            respond(202, accepted_body(payload, scan_id=str(assigned))), requests
        )
        original = payload.scan_id
        result = client.submit(payload, scan_id=assigned)

        assert json.loads(requests[0].content)["scan_id"] == str(assigned)
        assert payload.scan_id == original
        assert result.outcome == "accepted"
        assert result.scan_id == assigned


class TestResponseHandling:
    def test_valid_202_is_accepted(self) -> None:
        payload = make_payload()
        requests: list[httpx.Request] = []
        client, _ = build_client(respond(202, accepted_body(payload)), requests)
        result = client.submit(payload)

        assert result.outcome == "accepted"
        assert result.scan_id == payload.scan_id
        assert result.attempts == 1
        assert result.status_code == 202
        assert len(requests) == 1

    @pytest.mark.parametrize(
        "overrides",
        [
            {"status": "queued"},
            {"scan_id": str(uuid4())},
            {"hosts_received": 99},
            {"scan_id": "not-a-uuid"},
        ],
    )
    def test_contradictory_202_is_protocol_error(
        self, overrides: dict[str, object]
    ) -> None:
        payload = make_payload()
        requests: list[httpx.Request] = []
        client, _ = build_client(
            respond(202, accepted_body(payload, **overrides)), requests
        )
        result = client.submit(payload)

        assert result.outcome == "protocol_error"
        assert result.status_code == 202
        assert len(requests) == 1

    def test_malformed_202_body_is_protocol_error(self) -> None:
        payload = make_payload()
        requests: list[httpx.Request] = []
        client, _ = build_client(
            lambda _r: httpx.Response(202, content=b"not json"), requests
        )
        result = client.submit(payload)

        assert result.outcome == "protocol_error"
        assert len(requests) == 1

    def test_redirect_is_not_followed(self) -> None:
        payload = make_payload()
        requests: list[httpx.Request] = []
        client, _ = build_client(
            respond(307, headers={"Location": f"{BACKEND_URL}/api/v1/scans/"}),
            requests,
        )
        result = client.submit(payload)

        assert result.outcome == "protocol_error"
        assert result.status_code == 307
        assert len(requests) == 1


@pytest.fixture
def no_sleep(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    delays: list[float] = []
    monkeypatch.setattr(ingest.time, "sleep", delays.append)
    return delays


def sequence(*responses):
    remaining = list(responses)

    def handler(request: httpx.Request) -> httpx.Response:
        item = remaining.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    return handler


class TestErrorMapping:
    @pytest.mark.parametrize(
        ("status", "outcome"),
        [
            (401, "unauthorized"),
            (403, "forbidden"),
            (400, "rejected"),
            (413, "invalid"),
            (422, "invalid"),
            (404, "rejected"),
            (409, "rejected"),
        ],
    )
    def test_status_maps_to_outcome_in_one_request(
        self, status: int, outcome: str
    ) -> None:
        payload = make_payload()
        requests: list[httpx.Request] = []
        client, _ = build_client(respond(status, {"detail": "leak me"}), requests)
        result = client.submit(payload)

        assert result.outcome == outcome
        assert result.status_code == status
        assert result.attempts == 1
        assert len(requests) == 1

    def test_transport_failure_returns_result_without_raising(
        self, no_sleep: list[float]
    ) -> None:
        payload = make_payload()
        requests: list[httpx.Request] = []
        client, _ = build_client(
            lambda _r: (_ for _ in ()).throw(httpx.ConnectError("boom")), requests
        )
        result = client.submit(payload)

        assert isinstance(result, SubmissionResult)
        assert result.outcome == "unavailable"
        assert result.status_code is None


class TestRetry:
    @pytest.mark.parametrize(
        "first",
        [httpx.ConnectError("boom"), httpx.Response(500, json={"detail": "oops"})],
    )
    def test_transient_failure_then_accepted(
        self, first: object, no_sleep: list[float]
    ) -> None:
        payload = make_payload()
        requests: list[httpx.Request] = []
        client, _ = build_client(
            sequence(first, httpx.Response(202, json=accepted_body(payload))), requests
        )
        result = client.submit(payload)

        assert result.outcome == "accepted"
        assert result.attempts == 2
        assert result.status_code == 202
        assert no_sleep == [0.25]

        first_headers, second_headers = (r.headers for r in requests)
        assert first_headers["X-Nonce"] != second_headers["X-Nonce"]
        assert first_headers["X-Signature"] != second_headers["X-Signature"]
        assert requests[0].content == requests[1].content
        for request in requests:
            verify_signature(request)

    @pytest.mark.parametrize(
        "failure",
        [httpx.ConnectError("boom"), httpx.Response(503)],
    )
    def test_three_transient_failures_exhaust(
        self, failure: object, no_sleep: list[float]
    ) -> None:
        payload = make_payload()
        requests: list[httpx.Request] = []
        client, _ = build_client(sequence(failure, failure, failure), requests)
        result = client.submit(payload)

        assert result.outcome == "unavailable"
        assert result.attempts == 3
        assert len(requests) == 3
        assert no_sleep == [0.25, 1.0]


class TestRepeatedSubmission:
    def test_same_payload_twice_builds_fresh_envelopes(self) -> None:
        payload = make_payload()
        requests: list[httpx.Request] = []
        client, _ = build_client(respond(202, accepted_body(payload)), requests)
        first = client.submit(payload)
        second = client.submit(payload)

        assert first.outcome == second.outcome == "accepted"
        assert requests[0].content == requests[1].content
        assert requests[0].headers["X-Nonce"] != requests[1].headers["X-Nonce"]
        assert requests[0].headers["X-Signature"] != requests[1].headers["X-Signature"]
        assert payload == make_payload(payload.scan_id)


class TestMessageSafety:
    def test_message_leaks_nothing(self, no_sleep: list[float]) -> None:
        payload = make_payload()
        messages = []
        for handler in (
            respond(401, {"detail": "bad signature ab" * 4}),
            respond(422, {"detail": "invalid"}),
            respond(400, {"detail": "nope"}),
            sequence(*[httpx.Response(500)] * 3),
            respond(202, accepted_body(payload)),
        ):
            requests: list[httpx.Request] = []
            client, _ = build_client(handler, requests)
            result = client.submit(payload)
            messages.append(result.message)
            assert PRIVATE_KEY.hex() not in result.message
            assert BACKEND_URL not in result.message
            assert str(DEVICE_ID) not in result.message
            assert "detail" not in result.message
            assert requests[0].headers["X-Signature"] not in result.message

        assert messages[1] != messages[2]
        assert len(set(messages)) == 5


class TestLifecycle:
    def test_injected_client_is_not_closed(self) -> None:
        http_client = httpx.Client(
            transport=httpx.MockTransport(lambda _r: httpx.Response(202))
        )
        with ScanIngestClient(CONFIG, client=http_client):
            pass
        assert not http_client.is_closed

    def test_owned_client_is_closed(self) -> None:
        client = ScanIngestClient(CONFIG)
        owned = client._client
        client.close()
        assert owned.is_closed
