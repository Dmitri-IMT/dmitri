from __future__ import annotations

import dataclasses
import typing
from uuid import UUID

import pytest
from agent.transport import (
    IngestConfig,
    IngestConfigError,
    ScanIngestClient,
    SubmissionOutcome,
    SubmissionResult,
    load_ingest_config,
)

DEVICE_ID = "6f1b2c3d-4e5f-4a6b-8c9d-0e1f2a3b4c5d"
PRIVATE_KEY = "ab" * 32

VALID_ENV = {
    "BACKEND_URL": "https://api.example.com",
    "DEVICE_ID": DEVICE_ID,
    "DEVICE_PRIVATE_KEY": PRIVATE_KEY,
}


class TestExports:
    def test_public_names_are_importable(self) -> None:
        assert all(
            obj is not None
            for obj in (
                IngestConfig,
                IngestConfigError,
                ScanIngestClient,
                SubmissionOutcome,
                SubmissionResult,
                load_ingest_config,
            )
        )


class TestLoadIngestConfig:
    def test_reads_supplied_mapping(self) -> None:
        config = load_ingest_config(VALID_ENV)
        assert config.backend_url == "https://api.example.com"
        assert config.device_id == UUID(DEVICE_ID)
        assert config.private_key == bytes.fromhex(PRIVATE_KEY)

    def test_reads_process_environment(self, monkeypatch: pytest.MonkeyPatch) -> None:
        for key, value in VALID_ENV.items():
            monkeypatch.setenv(key, value)
        assert load_ingest_config().device_id == UUID(DEVICE_ID)

    @pytest.mark.parametrize("name", sorted(VALID_ENV))
    def test_missing_variable_raises(self, name: str) -> None:
        env = {k: v for k, v in VALID_ENV.items() if k != name}
        with pytest.raises(IngestConfigError):
            load_ingest_config(env)

    @pytest.mark.parametrize("name", sorted(VALID_ENV))
    def test_blank_variable_raises(self, name: str) -> None:
        with pytest.raises(IngestConfigError):
            load_ingest_config({**VALID_ENV, name: "   "})


class TestBackendUrl:
    @pytest.mark.parametrize(
        "url",
        [
            "ftp://api.example.com",
            "file:///etc/passwd",
            "https://user:pass@api.example.com",  # pragma: allowlist secret
            "https://api.example.com?token=1",
            "https://api.example.com#frag",
            "https://api.example.com/api/v1",
            "http://example.com:bad",
            "http://example.com:65536",
            "http://[::1",
            "http://:8000",
            "api.example.com",
        ],
    )
    def test_rejected_forms(self, url: str) -> None:
        with pytest.raises(IngestConfigError):
            load_ingest_config({**VALID_ENV, "BACKEND_URL": url})

    @pytest.mark.parametrize(
        ("url", "expected"),
        [
            ("http://127.0.0.1:8000", "http://127.0.0.1:8000"),
            ("http://127.0.0.1:8000/", "http://127.0.0.1:8000"),
        ],
    )
    def test_accepted_forms(self, url: str, expected: str) -> None:
        config = load_ingest_config({**VALID_ENV, "BACKEND_URL": url})
        assert config.backend_url == expected


class TestDeviceId:
    @pytest.mark.parametrize("value", ["not-a-uuid", "12345", DEVICE_ID[:-1]])
    def test_non_uuid_raises(self, value: str) -> None:
        with pytest.raises(IngestConfigError):
            load_ingest_config({**VALID_ENV, "DEVICE_ID": value})


class TestPrivateKey:
    def test_sixty_four_hex_chars_decode_to_32_bytes(self) -> None:
        key = load_ingest_config(VALID_ENV).private_key
        assert isinstance(key, bytes)
        assert len(key) == 32

    @pytest.mark.parametrize(
        "value",
        ["ab" * 31, "ab" * 33, "zz" * 32, "ab" * 32 + "a", " " + "ab" * 32 + " x"],
    )
    def test_malformed_key_raises(self, value: str) -> None:
        with pytest.raises(IngestConfigError):
            load_ingest_config({**VALID_ENV, "DEVICE_PRIVATE_KEY": value})


class TestSecretSafety:
    def test_config_repr_and_str_hide_values(self) -> None:
        config = load_ingest_config(VALID_ENV)
        for text in (repr(config), str(config)):
            assert PRIVATE_KEY not in text
            assert str(bytes.fromhex(PRIVATE_KEY)) not in text
            assert DEVICE_ID not in text
            assert "api.example.com" not in text

    @pytest.mark.parametrize(
        ("name", "value"),
        [
            ("BACKEND_URL", "ftp://secret.example.com"),
            ("DEVICE_ID", "secret-not-a-uuid"),
            ("DEVICE_PRIVATE_KEY", "cd" * 40),
        ],
    )
    def test_error_text_hides_supplied_value(self, name: str, value: str) -> None:
        with pytest.raises(IngestConfigError) as excinfo:
            load_ingest_config({**VALID_ENV, name: value})
        for text in (str(excinfo.value), repr(excinfo.value)):
            assert value not in text
            assert name in text


class TestSubmissionTypes:
    def test_outcome_literal_values(self) -> None:
        assert typing.get_args(SubmissionOutcome) == (
            "accepted",
            "unauthorized",
            "forbidden",
            "invalid",
            "rejected",
            "unavailable",
            "protocol_error",
        )

    def test_result_is_frozen_slotted_with_fields(self) -> None:
        result = SubmissionResult(
            outcome="accepted",
            scan_id=UUID(DEVICE_ID),
            attempts=1,
            status_code=202,
            message="accepted",
        )
        assert [f.name for f in dataclasses.fields(result)] == [
            "outcome",
            "scan_id",
            "attempts",
            "status_code",
            "message",
        ]
        assert not hasattr(result, "__dict__")
        with pytest.raises(dataclasses.FrozenInstanceError):
            result.attempts = 2  # type: ignore[misc]
