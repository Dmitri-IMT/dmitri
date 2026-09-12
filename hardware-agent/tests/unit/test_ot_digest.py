from __future__ import annotations

import os
import stat

import pytest

from agent.ot.digest import (
    DIGEST_KEY_BYTES,
    DIGEST_PREFIX,
    load_digest_key,
    value_digest,
)

_TEST_KEY_HEX = "a" * (DIGEST_KEY_BYTES * 2)
_TEST_KEY = bytes.fromhex(_TEST_KEY_HEX)


def test_value_digest_is_keyed_stable_and_address_specific(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DMITRI_OT_DIGEST_KEY", raising=False)

    first = value_digest(_TEST_KEY, "coil", 0, 4, [False, True, False, True])
    second = value_digest(_TEST_KEY, "coil", 0, 4, [False, True, False, True])
    different_address = value_digest(_TEST_KEY, "coil", 4, 4, [False, True, False, True])
    different_values = value_digest(_TEST_KEY, "coil", 0, 4, [True, False, True, False])

    assert first == second
    assert first is not None
    assert first.startswith(DIGEST_PREFIX)
    assert len(first) == len(DIGEST_PREFIX) + 64
    assert first != different_address
    assert first != different_values


def test_value_digest_without_key_returns_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DMITRI_OT_DIGEST_KEY", raising=False)

    assert value_digest(None, "coil", 0, 4, [False, True, False, True]) is None


def test_load_digest_key_reads_env_hex(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DMITRI_OT_DIGEST_KEY", _TEST_KEY_HEX)

    assert load_digest_key() == _TEST_KEY


def test_load_digest_key_reads_mode_0600_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    monkeypatch.delenv("DMITRI_OT_DIGEST_KEY", raising=False)
    key_path = tmp_path / "ot-digest-key"
    key_path.write_text(_TEST_KEY_HEX, encoding="utf-8")
    key_path.chmod(stat.S_IRUSR | stat.S_IWUSR)
    monkeypatch.setattr("agent.ot.digest.default_digest_key_path", lambda: key_path)

    assert load_digest_key() == _TEST_KEY
