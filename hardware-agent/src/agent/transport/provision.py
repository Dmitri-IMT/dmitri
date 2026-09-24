"""Register this Pi with the backend and write /etc/dmitri/agent.env.

hardware-agent/scripts/provision-pi.sh runs this as `dmitri provision`. The
private key is created here and never leaves the Pi; only the public key is
sent. The admin password is read from the terminal and sent once, over HTTPS.
"""

from __future__ import annotations

import getpass
import os
import sys
from pathlib import Path
from uuid import UUID

import httpx
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from agent.transport.ingest import (
    IngestConfigError,
    parse_backend_url,
    parse_private_key,
)

ENV_FILE = Path("/etc/dmitri/agent.env")
_TIMEOUT = httpx.Timeout(30.0)


class ProvisionError(Exception):
    pass


def _env_value(env_file: Path, name: str) -> str | None:
    if not env_file.is_file():
        return None
    for line in env_file.read_text().splitlines():
        if line.startswith(f"{name}="):
            return line.split("=", 1)[1].strip()
    return None


def _write_env(env_file: Path, lines: list[str]) -> None:
    env_file.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    tmp = env_file.with_suffix(".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as handle:
        handle.write("".join(f"{line}\n" for line in lines))
    os.replace(tmp, env_file)


def is_provisioned(env_file: Path = ENV_FILE) -> bool:
    return _env_value(env_file, "DEVICE_ID") is not None


def load_or_create_key(env_file: Path = ENV_FILE) -> bytes:
    """Return the device private key, creating and saving it on first use.

    A rerun after a failed registration keeps the same key.
    """
    existing = _env_value(env_file, "DEVICE_PRIVATE_KEY")
    if existing is not None:
        return parse_private_key(existing)
    private_key = Ed25519PrivateKey.generate().private_bytes(
        serialization.Encoding.Raw,
        serialization.PrivateFormat.Raw,
        serialization.NoEncryption(),
    )
    _write_env(env_file, [f"DEVICE_PRIVATE_KEY={private_key.hex()}"])
    return private_key


def public_key_hex(private_key: bytes) -> str:
    public = Ed25519PrivateKey.from_private_bytes(private_key).public_key()
    return public.public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    ).hex()


def parse_https_url(raw: str) -> str:
    # The admin password goes to this URL. Never send it without TLS.
    if not raw.strip().startswith("https://"):
        raise ProvisionError("Backend URL must start with https://")
    try:
        return parse_backend_url(raw.strip())
    except IngestConfigError as exc:
        raise ProvisionError(str(exc)) from exc


def register(
    client: httpx.Client,
    *,
    email: str,
    password: str,
    display_name: str,
    public_key: str,
) -> UUID:
    """Log in as an org admin and register the public key in that org."""
    login = client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    if login.status_code != 200:
        raise ProvisionError(f"login failed: HTTP {login.status_code}")
    token = login.json()["access_token"]
    response = client.post(
        "/api/v1/agents",
        json={"display_name": display_name, "public_key": public_key},
        headers={"Authorization": f"Bearer {token}"},
    )
    if response.status_code != 201:
        raise ProvisionError(
            f"register failed: HTTP {response.status_code} {response.text}"
        )
    return UUID(response.json()["agent_id"])


def provision(env_file: Path = ENV_FILE) -> None:
    backend_url = parse_https_url(input("Backend URL (https://...): "))
    email = input("Admin email for that backend: ").strip()
    password = getpass.getpass("Admin password: ")
    display_name = input("Name for this Pi: ").strip()
    if not (email and password and display_name):
        raise ProvisionError("email, password, and name are required")
    print("The Pi joins the org of that admin account.")

    private_key = load_or_create_key(env_file)
    with httpx.Client(base_url=backend_url, timeout=_TIMEOUT) as client:
        device_id = register(
            client,
            email=email,
            password=password,
            display_name=display_name,
            public_key=public_key_hex(private_key),
        )
    _write_env(
        env_file,
        [
            f"BACKEND_URL={backend_url}",
            f"DEVICE_ID={device_id}",
            f"DEVICE_PRIVATE_KEY={private_key.hex()}",
        ],
    )
    print(f"Registered as {device_id}.")


def main() -> None:
    if is_provisioned():
        print("This Pi is already provisioned.")
        return
    try:
        provision()
    except (ProvisionError, httpx.HTTPError, EOFError) as exc:
        print(f"provision: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
