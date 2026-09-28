from __future__ import annotations

import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from os import environ as process_environ
from typing import Literal
from urllib.parse import urlsplit
from uuid import UUID

import httpx

from agent.normalize.contracts import ScanPayload
from agent.transport.signing import build_device_signature_headers

_INGEST_PATH = "/api/v1/scans"
_TIMEOUT = httpx.Timeout(connect=10.0, write=60.0, read=120.0, pool=10.0)
_RETRY_DELAYS = (0.0, 0.25, 1.0)

SubmissionOutcome = Literal[
    "accepted",
    "unauthorized",
    "forbidden",
    "invalid",
    "rejected",
    "unavailable",
    "protocol_error",
]


class IngestConfigError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class IngestConfig:
    backend_url: str = field(repr=False)
    device_id: UUID = field(repr=False)
    private_key: bytes = field(repr=False)


@dataclass(frozen=True, slots=True)
class SubmissionResult:
    outcome: SubmissionOutcome
    scan_id: UUID
    attempts: int
    status_code: int | None
    message: str


_MESSAGES: dict[SubmissionOutcome, str] = {
    "accepted": "scan accepted by the backend",
    "unauthorized": "backend rejected the device authentication proof",
    "forbidden": "device is not permitted to submit this scan",
    "invalid": "backend rejected the scan payload as invalid",
    "rejected": "backend rejected the submission",
    "unavailable": "backend was unreachable after three attempts",
    "protocol_error": "unexpected response from the backend",
}


_STATUS_OUTCOMES: dict[int, SubmissionOutcome] = {
    401: "unauthorized",
    403: "forbidden",
    413: "invalid",
    422: "invalid",
}


def _message(outcome: SubmissionOutcome, status_code: int | None) -> str:
    return f"{_MESSAGES[outcome]} (status {status_code})"


def _require(environ: Mapping[str, str], name: str) -> str:
    value = environ.get(name)
    if value is None or not value.strip():
        raise IngestConfigError(f"{name} is required")
    return value.strip()


def parse_backend_url(raw: str) -> str:
    try:
        parts = urlsplit(raw)
        _ = parts.port
        parsed_url = httpx.URL(raw)
    except (ValueError, httpx.InvalidURL):
        raise IngestConfigError(
            "BACKEND_URL must be an http or https origin with no credentials, "
            "query, fragment, or path"
        ) from None
    if (
        parts.scheme not in ("http", "https")
        or not parts.netloc
        or not parsed_url.host
        or parts.username is not None
        or parts.password is not None
        or parts.query
        or parts.fragment
        or parts.path not in ("", "/")
    ):
        raise IngestConfigError(
            "BACKEND_URL must be an http or https origin with no credentials, "
            "query, fragment, or path"
        )
    return raw.rstrip("/")


def _parse_device_id(raw: str) -> UUID:
    try:
        return UUID(raw)
    except ValueError:
        raise IngestConfigError("DEVICE_ID must be a UUID") from None


def parse_private_key(raw: str) -> bytes:
    try:
        key = bytes.fromhex(raw)
    except ValueError:
        raise IngestConfigError(
            "DEVICE_PRIVATE_KEY must be 64 hexadecimal characters"
        ) from None
    if len(raw) != 64 or len(key) != 32:
        raise IngestConfigError("DEVICE_PRIVATE_KEY must be 64 hexadecimal characters")
    return key


def load_ingest_config(environ: Mapping[str, str] | None = None) -> IngestConfig:
    source = process_environ if environ is None else environ
    return IngestConfig(
        backend_url=parse_backend_url(_require(source, "BACKEND_URL")),
        device_id=_parse_device_id(_require(source, "DEVICE_ID")),
        private_key=parse_private_key(_require(source, "DEVICE_PRIVATE_KEY")),
    )


class ScanIngestClient:
    def __init__(self, config: IngestConfig, *, client: httpx.Client | None = None):
        self._config = config
        self._owns_client = client is None
        self._client = client if client is not None else httpx.Client()

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> ScanIngestClient:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def submit(
        self, payload: ScanPayload, *, scan_id: UUID | None = None
    ) -> SubmissionResult:
        effective = (
            payload
            if scan_id is None
            else payload.model_copy(update={"scan_id": scan_id})
        )
        body = effective.model_dump_json().encode("utf-8")
        status_code: int | None = None
        for attempt, delay in enumerate(_RETRY_DELAYS, start=1):
            if delay:
                time.sleep(delay)
            try:
                response = self._client.post(
                    f"{self._config.backend_url}{_INGEST_PATH}",
                    content=body,
                    headers=self._build_headers(body),
                    timeout=_TIMEOUT,
                    follow_redirects=False,
                )
            except httpx.TransportError:
                status_code = None
            else:
                if response.status_code < 500:
                    return self._map_response(response, effective, attempts=attempt)
                status_code = response.status_code
        return self._result("unavailable", effective, len(_RETRY_DELAYS), status_code)

    def _build_headers(self, body: bytes) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            **build_device_signature_headers(
                "POST",
                _INGEST_PATH,
                body,
                str(self._config.device_id),
                self._config.private_key,
            ),
        }

    def _map_response(
        self, response: httpx.Response, effective: ScanPayload, *, attempts: int
    ) -> SubmissionResult:
        status = response.status_code
        if status == 202:
            outcome: SubmissionOutcome = (
                "accepted"
                if self._acknowledgement_matches(response, effective)
                else "protocol_error"
            )
        elif 400 <= status < 500:
            outcome = _STATUS_OUTCOMES.get(status, "rejected")
        else:
            outcome = "protocol_error"
        return self._result(outcome, effective, attempts, status)

    @staticmethod
    def _result(
        outcome: SubmissionOutcome,
        effective: ScanPayload,
        attempts: int,
        status_code: int | None,
    ) -> SubmissionResult:
        return SubmissionResult(
            outcome=outcome,
            scan_id=effective.scan_id,
            attempts=attempts,
            status_code=status_code,
            message=_message(outcome, status_code),
        )

    @staticmethod
    def _acknowledgement_matches(
        response: httpx.Response, effective: ScanPayload
    ) -> bool:
        try:
            body = response.json()
        except ValueError:
            return False
        if not isinstance(body, dict):
            return False
        try:
            acknowledged = UUID(str(body.get("scan_id")))
        except ValueError:
            return False
        return (
            body.get("status") == "accepted"
            and acknowledged == effective.scan_id
            and body.get("hosts_received") == len(effective.hosts)
        )
