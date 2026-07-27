from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from typing import Mapping
from uuid import UUID

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

_HEADER_NAMES = (
    "X-Device-Id",
    "X-Timestamp",
    "X-Nonce",
    "X-Body-SHA256",
    "X-Signature",
)


class SignatureError(ValueError):
    pass


class MalformedSigHeaders(ValueError):
    pass


@dataclass(frozen=True)
class DeviceSigHeaders:
    device_id: str
    timestamp: str
    nonce: str
    body_sha256: str
    signature: str


def canonical_string(
    method: str,
    path: str,
    device_id: str,
    timestamp: str,
    nonce: str,
    body_sha256: str,
) -> str:
    return "\n".join((method, path, device_id, timestamp, nonce, body_sha256))


def body_sha256(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def parse_timestamp(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise MalformedSigHeaders(f"invalid X-Timestamp: {exc}") from exc
    if parsed.tzinfo is None:
        raise MalformedSigHeaders("X-Timestamp missing UTC offset")
    return parsed


def parse_headers(headers: Mapping[str, str]) -> DeviceSigHeaders:
    values: dict[str, str] = {}
    for name in _HEADER_NAMES:
        value = headers.get(name)
        if not value:
            raise MalformedSigHeaders(f"missing header {name}")
        values[name] = value

    device_id = values["X-Device-Id"]
    try:
        UUID(device_id)
    except ValueError as exc:
        raise MalformedSigHeaders("X-Device-Id is not a UUID") from exc

    nonce = values["X-Nonce"]
    if not (16 <= len(nonce) <= 128):
        raise MalformedSigHeaders("X-Nonce length out of range")

    body_hash = values["X-Body-SHA256"]
    if len(body_hash) != 64 or not _is_hex(body_hash):
        raise MalformedSigHeaders("X-Body-SHA256 is not 64 hex characters")

    signature = values["X-Signature"]
    if len(signature) != 128 or not _is_hex(signature):
        raise MalformedSigHeaders("X-Signature is not 128 hex characters")

    return DeviceSigHeaders(
        device_id=device_id,
        timestamp=values["X-Timestamp"],
        nonce=nonce,
        body_sha256=body_hash,
        signature=signature,
    )


def _is_hex(value: str) -> bool:
    try:
        int(value, 16)
    except ValueError:
        return False
    return True


def verify(public_key: bytes, canonical: str, signature_hex: str) -> None:
    try:
        signature = bytes.fromhex(signature_hex)
    except ValueError as exc:
        raise SignatureError("signature is not valid hex") from exc
    if len(signature) != 64:
        raise SignatureError("signature has invalid length")
    try:
        Ed25519PublicKey.from_public_bytes(public_key).verify(
            signature, canonical.encode("utf-8")
        )
    except InvalidSignature as exc:
        raise SignatureError("signature verification failed") from exc
    except ValueError as exc:
        raise SignatureError("public key is invalid") from exc


def generate_keypair() -> tuple[bytes, bytes]:
    private_key = Ed25519PrivateKey.generate()
    private_raw = private_key.private_bytes_raw()
    public_raw = private_key.public_key().public_bytes_raw()
    return private_raw, public_raw


def sign(private_key: bytes, canonical: str) -> str:
    key = Ed25519PrivateKey.from_private_bytes(private_key)
    signature = key.sign(canonical.encode("utf-8"))
    return signature.hex()
