from __future__ import annotations

import hashlib
import re
import time
from uuid import UUID

import pytest
from agent.transport import build_device_signature_headers
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

DEVICE_ID = UUID("6f1b2c3d-4e5f-4a6b-8c9d-0e1f2a3b4c5d")
PRIVATE_KEY = bytes.fromhex("ab" * 32)
PUBLIC_KEY = Ed25519PrivateKey.from_private_bytes(PRIVATE_KEY).public_key()

COMMAND_PATH = f"/api/v1/agents/{DEVICE_ID}/commands"
INGEST_PATH = "/api/v1/scans"


def verify(headers: dict[str, str], method: str, path: str) -> None:
    canonical = "\n".join(
        (
            method,
            path,
            headers["X-Device-Id"],
            headers["X-Timestamp"],
            headers["X-Nonce"],
            headers["X-Body-SHA256"],
        )
    )
    PUBLIC_KEY.verify(bytes.fromhex(headers["X-Signature"]), canonical.encode("utf-8"))


class TestCanonicalString:
    def test_get_upgrade_signature_verifies(self) -> None:
        headers = build_device_signature_headers(
            "GET", COMMAND_PATH, b"", str(DEVICE_ID), PRIVATE_KEY
        )

        assert set(headers) == {
            "X-Device-Id",
            "X-Timestamp",
            "X-Nonce",
            "X-Body-SHA256",
            "X-Signature",
        }
        assert headers["X-Device-Id"] == str(DEVICE_ID)
        assert re.fullmatch(r"[0-9a-f]{32}", headers["X-Nonce"])
        verify(headers, "GET", COMMAND_PATH)

    def test_post_ingest_signature_verifies(self) -> None:
        body = b'{"scan_id": "6f1b2c3d-4e5f-4a6b-8c9d-0e1f2a3b4c5d"}'
        headers = build_device_signature_headers(
            "POST", INGEST_PATH, body, str(DEVICE_ID), PRIVATE_KEY
        )

        assert headers["X-Body-SHA256"] == hashlib.sha256(body).hexdigest()
        verify(headers, "POST", INGEST_PATH)

    def test_signature_is_bound_to_method_and_path(self) -> None:
        headers = build_device_signature_headers(
            "GET", COMMAND_PATH, b"", str(DEVICE_ID), PRIVATE_KEY
        )

        with pytest.raises(InvalidSignature):
            verify(headers, "POST", COMMAND_PATH)
        with pytest.raises(InvalidSignature):
            verify(headers, "GET", INGEST_PATH)

    def test_empty_body_hashes_zero_bytes(self) -> None:
        headers = build_device_signature_headers(
            "GET", COMMAND_PATH, b"", str(DEVICE_ID), PRIVATE_KEY
        )

        assert headers["X-Body-SHA256"] == hashlib.sha256(b"").hexdigest()


class TestFreshness:
    def test_identical_arguments_produce_fresh_proof(self) -> None:
        first = build_device_signature_headers(
            "GET", COMMAND_PATH, b"", str(DEVICE_ID), PRIVATE_KEY
        )
        time.sleep(0.05)
        second = build_device_signature_headers(
            "GET", COMMAND_PATH, b"", str(DEVICE_ID), PRIVATE_KEY
        )

        assert first["X-Nonce"] != second["X-Nonce"]
        assert first["X-Timestamp"] != second["X-Timestamp"]
        assert first["X-Signature"] != second["X-Signature"]
        assert first["X-Body-SHA256"] == second["X-Body-SHA256"]
        verify(second, "GET", COMMAND_PATH)


class TestSecretSafety:
    def test_key_absent_from_headers(self) -> None:
        headers = build_device_signature_headers(
            "GET", COMMAND_PATH, PRIVATE_KEY, str(DEVICE_ID), PRIVATE_KEY
        )

        assert PRIVATE_KEY.hex() not in "".join(headers.values())

    @pytest.mark.parametrize(
        "bad_key", [bytes.fromhex("cd" * 31), PRIVATE_KEY + b"\x01"]
    )
    def test_invalid_key_error_leaks_nothing(self, bad_key: bytes) -> None:
        with pytest.raises(ValueError) as excinfo:
            build_device_signature_headers(
                "GET", COMMAND_PATH, b"", str(DEVICE_ID), bad_key
            )

        assert bad_key.hex() not in str(excinfo.value)
