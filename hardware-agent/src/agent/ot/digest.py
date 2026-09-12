from __future__ import annotations

import hashlib
import hmac
import json
import os
import platform
from pathlib import Path, PureWindowsPath

DIGEST_PREFIX = "hmac-sha256:"
DIGEST_KEY_BYTES = 32


def default_digest_key_path() -> Path:
    if platform.system() == "Windows":
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        return Path(str(PureWindowsPath(base) / "Dmitri" / "ot-digest-key"))
    xdg_config = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return Path(xdg_config) / "dmitri" / "ot-digest-key"


def _parse_key_hex(value: str) -> bytes | None:
    cleaned = value.strip()
    if len(cleaned) != DIGEST_KEY_BYTES * 2:
        return None
    try:
        key = bytes.fromhex(cleaned)
    except ValueError:
        return None
    if len(key) != DIGEST_KEY_BYTES:
        return None
    return key


def load_digest_key() -> bytes | None:
    env = os.environ.get("DMITRI_OT_DIGEST_KEY")
    if env:
        return _parse_key_hex(env)
    path = default_digest_key_path()
    if not path.is_file():
        return None
    if platform.system() != "Windows":
        if path.stat().st_mode & 0o777 != 0o600:
            return None
    return _parse_key_hex(path.read_text(encoding="utf-8"))


def value_digest(
    key: bytes | None,
    address_space: str,
    start_address: int,
    count: int,
    values: list[int | bool],
) -> str | None:
    if key is None:
        return None
    canonical = json.dumps(
        [address_space, start_address, count, values],
        separators=(",", ":"),
        ensure_ascii=True,
    )
    digest = hmac.new(key, canonical.encode("ascii"), hashlib.sha256).hexdigest()
    return f"{DIGEST_PREFIX}{digest}"
