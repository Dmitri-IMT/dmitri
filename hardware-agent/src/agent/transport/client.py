"""HTTP transport for submitting scan payloads to the backend API."""

from __future__ import annotations

from dataclasses import dataclass

import requests

from agent.normalize.contracts import ScanPayload


class BackendSubmissionError(RuntimeError):
    """Raised when the backend submission fails."""


@dataclass(slots=True)
class SubmissionResult:
    """Successful backend submission summary."""

    status_code: int
    body: dict


class BackendClient:
    """Simple synchronous HTTP client for scan ingestion."""

    def __init__(self, base_url: str, timeout_seconds: float = 30.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def submit_scan(self, payload: ScanPayload) -> SubmissionResult:
        """POST the normalized scan payload to the backend ingestion endpoint."""

        endpoint = self._resolve_scans_endpoint()
        response = requests.post(
            endpoint,
            json=payload.model_dump(mode="json"),
            timeout=self.timeout_seconds,
        )
        if response.status_code >= 400:
            raise BackendSubmissionError(
                f"Backend submission failed with status {response.status_code}: "
                f"{response.text.strip()}"
            )

        try:
            body = response.json()
        except ValueError as exc:
            raise BackendSubmissionError(
                "Backend response was not valid JSON."
            ) from exc

        return SubmissionResult(status_code=response.status_code, body=body)

    def _resolve_scans_endpoint(self) -> str:
        if self.base_url.endswith("/api/v1"):
            return f"{self.base_url}/scans"
        if self.base_url.endswith("/scans"):
            return self.base_url
        return f"{self.base_url}/scans"
