from __future__ import annotations

import json
import os
import socket
import subprocess
from pathlib import Path
from typing import Any

SOCKET_PATH = Path("/run/dmitri-agent-updater/control.sock")
MAX_MESSAGE_BYTES = 4096


def readiness_handshake(
    app_version: str,
    *,
    socket_path: Path = SOCKET_PATH,
    package_version: str | None = None,
) -> dict[str, Any]:
    version = package_version or _dpkg_version()
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
        connection.settimeout(3)
        connection.connect(str(socket_path))
        connection.sendall(
            json.dumps(
                {
                    "command": "readiness",
                    "app_version": app_version,
                    "package_version": version,
                },
                separators=(",", ":"),
            ).encode()
            + b"\n"
        )
        challenge = _read_line(connection)
        if set(challenge) != {"nonce", "main_pid", "invocation_id"}:
            raise OSError("invalid local readiness challenge")
        connection.sendall(
            json.dumps(
                {
                    **challenge,
                    "app_version": app_version,
                    "package_version": version,
                },
                separators=(",", ":"),
            ).encode()
            + b"\n"
        )
        response = _read_json(connection)
    if (
        not response.get("ok")
        or response.get("nonce") != challenge["nonce"]
        or response.get("main_pid") != os.getpid()
        or response.get("invocation_id") != challenge["invocation_id"]
        or response.get("app_version") != app_version
        or response.get("package_version") != version
    ):
        raise OSError("local readiness was rejected")
    return response


def _dpkg_version() -> str:
    result = subprocess.run(
        ["dpkg-query", "-W", "-f=${Version}", "hardware-agent"],
        check=True,
        capture_output=True,
        text=True,
        timeout=3,
    )
    value = result.stdout.strip()
    if not value:
        raise OSError("agent package version unavailable")
    return value


def _read_line(connection: socket.socket) -> dict[str, Any]:
    data = bytearray()
    while len(data) <= MAX_MESSAGE_BYTES:
        chunk = connection.recv(min(1024, MAX_MESSAGE_BYTES + 1 - len(data)))
        if not chunk:
            raise OSError("local readiness connection closed")
        if b"\n" in chunk:
            line, _, trailing = chunk.partition(b"\n")
            if trailing:
                raise OSError("invalid local readiness response")
            data.extend(line)
            return _parse(data)
        data.extend(chunk)
    raise OSError("local readiness response too large")


def _read_json(connection: socket.socket) -> dict[str, Any]:
    data = bytearray()
    while len(data) <= MAX_MESSAGE_BYTES:
        chunk = connection.recv(min(1024, MAX_MESSAGE_BYTES + 1 - len(data)))
        if not chunk:
            break
        data.extend(chunk)
    return _parse(data)


def _parse(data: bytearray) -> dict[str, Any]:
    try:
        parsed = json.loads(data)
    except (ValueError, TypeError) as exc:
        raise OSError("invalid local readiness response") from exc
    if not isinstance(parsed, dict):
        raise OSError("invalid local readiness response")
    return parsed
