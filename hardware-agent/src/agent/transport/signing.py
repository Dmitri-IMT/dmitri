from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timezone

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


def build_device_signature_headers(
    method: str,
    path: str,
    body: bytes,
    device_id: str,
    private_key_bytes: bytes,
) -> dict[str, str]:
    timestamp = datetime.now(timezone.utc).isoformat()
    nonce = secrets.token_hex(16)
    body_sha256 = hashlib.sha256(body).hexdigest()
    canonical = "\n".join((method, path, device_id, timestamp, nonce, body_sha256))
    signature = Ed25519PrivateKey.from_private_bytes(private_key_bytes).sign(
        canonical.encode("utf-8")
    )
    return {
        "X-Device-Id": device_id,
        "X-Timestamp": timestamp,
        "X-Nonce": nonce,
        "X-Body-SHA256": body_sha256,
        "X-Signature": signature.hex(),
    }
