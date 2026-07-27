from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from api.services import device_sig

ROOT = Path(__file__).resolve().parents[1]


def test_canonical_string_is_byte_exact():
    result = device_sig.canonical_string(
        "POST",
        "/api/v1/scans",
        "device-1",
        "2026-07-24T00:00:00Z",
        "nonce-1",
        "abc123",
    )
    expected = "POST\n/api/v1/scans\ndevice-1\n2026-07-24T00:00:00Z\nnonce-1\nabc123"
    assert result == expected


def test_body_sha256_empty_body_pinned_constant():
    assert (
        device_sig.body_sha256(b"")
        == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    )


def test_generate_keypair_returns_32_byte_raw_keys():
    private_raw, public_raw = device_sig.generate_keypair()
    assert len(private_raw) == 32
    assert len(public_raw) == 32


def test_sign_then_verify_round_trips():
    private_raw, public_raw = device_sig.generate_keypair()
    canonical = "POST\n/api/v1/scans\ndevice-1\nts\nnonce\nhash"
    signature_hex = device_sig.sign(private_raw, canonical)
    device_sig.verify(public_raw, canonical, signature_hex)


def test_verify_raises_for_wrong_public_key():
    private_raw, _ = device_sig.generate_keypair()
    _, other_public_raw = device_sig.generate_keypair()
    canonical = "POST\n/api/v1/scans\ndevice-1\nts\nnonce\nhash"
    signature_hex = device_sig.sign(private_raw, canonical)
    with pytest.raises(device_sig.SignatureError):
        device_sig.verify(other_public_raw, canonical, signature_hex)


def test_verify_raises_for_mutated_canonical():
    private_raw, public_raw = device_sig.generate_keypair()
    canonical = "POST\n/api/v1/scans\ndevice-1\nts\nnonce\nhash"
    signature_hex = device_sig.sign(private_raw, canonical)
    with pytest.raises(device_sig.SignatureError):
        device_sig.verify(public_raw, canonical + "x", signature_hex)


def test_verify_raises_for_short_hex_signature():
    _, public_raw = device_sig.generate_keypair()
    with pytest.raises(device_sig.SignatureError):
        device_sig.verify(public_raw, "canonical", "ab" * 10)


def test_verify_raises_for_non_hex_signature():
    _, public_raw = device_sig.generate_keypair()
    with pytest.raises(device_sig.SignatureError):
        device_sig.verify(public_raw, "canonical", "z" * 128)


def _valid_headers() -> dict[str, str]:
    return {
        "X-Device-Id": str(uuid4()),
        "X-Timestamp": "2026-07-24T00:00:00Z",
        "X-Nonce": "n" * 16,
        "X-Body-SHA256": "a" * 64,
        "X-Signature": "b" * 128,
    }


def test_parse_headers_accepts_valid_headers():
    headers = _valid_headers()
    parsed = device_sig.parse_headers(headers)
    assert parsed.device_id == headers["X-Device-Id"]
    assert parsed.timestamp == headers["X-Timestamp"]
    assert parsed.nonce == headers["X-Nonce"]
    assert parsed.body_sha256 == headers["X-Body-SHA256"]
    assert parsed.signature == headers["X-Signature"]


@pytest.mark.parametrize(
    "missing",
    ["X-Device-Id", "X-Timestamp", "X-Nonce", "X-Body-SHA256", "X-Signature"],
)
def test_parse_headers_raises_for_each_missing_header(missing):
    headers = _valid_headers()
    del headers[missing]
    with pytest.raises(device_sig.MalformedSigHeaders):
        device_sig.parse_headers(headers)


def test_parse_headers_raises_for_non_hex_signature():
    headers = _valid_headers()
    headers["X-Signature"] = "z" * 128
    with pytest.raises(device_sig.MalformedSigHeaders):
        device_sig.parse_headers(headers)


def test_parse_headers_rejects_old_hmac_width_signature():
    headers = _valid_headers()
    headers["X-Signature"] = "a" * 64
    with pytest.raises(device_sig.MalformedSigHeaders):
        device_sig.parse_headers(headers)


def test_parse_headers_raises_for_non_hex_body_hash():
    headers = _valid_headers()
    headers["X-Body-SHA256"] = "z" * 64
    with pytest.raises(device_sig.MalformedSigHeaders):
        device_sig.parse_headers(headers)


def test_parse_headers_raises_for_non_uuid_device_id():
    headers = _valid_headers()
    headers["X-Device-Id"] = "not-a-uuid"
    with pytest.raises(device_sig.MalformedSigHeaders):
        device_sig.parse_headers(headers)


@pytest.mark.parametrize("nonce", ["n" * 15, "n" * 129])
def test_parse_headers_raises_for_out_of_range_nonce_length(nonce):
    headers = _valid_headers()
    headers["X-Nonce"] = nonce
    with pytest.raises(device_sig.MalformedSigHeaders):
        device_sig.parse_headers(headers)


def test_parse_timestamp_parses_iso8601():
    parsed = device_sig.parse_timestamp("2026-07-24T00:00:00+00:00")
    assert parsed.year == 2026


def test_parse_timestamp_raises_malformed_for_garbage():
    with pytest.raises(device_sig.MalformedSigHeaders):
        device_sig.parse_timestamp("not-a-timestamp")


def test_parse_timestamp_raises_malformed_for_naive_iso8601():
    with pytest.raises(device_sig.MalformedSigHeaders):
        device_sig.parse_timestamp("2026-07-24T00:00:00")


def test_no_backend_src_module_outside_device_sig_imports_cryptography():
    src_root = ROOT / "src"
    device_sig_path = (
        ROOT / "src" / "api" / "services" / "device_sig.py"
    ).resolve()
    offenders = [
        path
        for path in src_root.rglob("*.py")
        if path.resolve() != device_sig_path
        and "cryptography" in path.read_text(encoding="utf-8")
    ]
    assert offenders == []


def test_verify_wrong_key_error_omits_key_and_signature_material():
    private_raw, public_raw = device_sig.generate_keypair()
    _, other_public_raw = device_sig.generate_keypair()
    canonical = "POST\n/api/v1/scans\ndevice-1\nts\nnonce\nhash"
    signature_hex = device_sig.sign(private_raw, canonical)
    with pytest.raises(device_sig.SignatureError) as excinfo:
        device_sig.verify(other_public_raw, canonical, signature_hex)
    message = str(excinfo.value)
    assert signature_hex not in message
    assert public_raw.hex() not in message
    assert other_public_raw.hex() not in message
    assert private_raw.hex() not in message


def test_verify_short_hex_signature_error_omits_signature_material():
    _, public_raw = device_sig.generate_keypair()
    short_sig = "ab" * 10
    with pytest.raises(device_sig.SignatureError) as excinfo:
        device_sig.verify(public_raw, "canonical", short_sig)
    assert short_sig not in str(excinfo.value)


def test_verify_non_hex_signature_error_omits_signature_material():
    _, public_raw = device_sig.generate_keypair()
    garbage_sig = "z" * 128
    with pytest.raises(device_sig.SignatureError) as excinfo:
        device_sig.verify(public_raw, "canonical", garbage_sig)
    assert garbage_sig not in str(excinfo.value)


def test_parse_headers_signature_error_omits_signature_value():
    headers = _valid_headers()
    headers["X-Signature"] = "z" * 128
    with pytest.raises(device_sig.MalformedSigHeaders) as excinfo:
        device_sig.parse_headers(headers)
    assert headers["X-Signature"] not in str(excinfo.value)
