from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from agent.normalize.contracts import ScanPayload
from agent.transport.client import BackendClient, BackendSubmissionError


class _FakeResponse:
    def __init__(
        self,
        status_code: int,
        payload: dict | None = None,
        text: str = "",
    ) -> None:
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    def json(self) -> dict:
        return self._payload


def test_submit_scan_posts_to_api_v1_scans(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = ScanPayload(
        scan_id=uuid4(),
        timestamp=datetime.now(timezone.utc),
        subnet="192.168.0.0/24",
        scan_mode="quick",
        devices=[],
        findings=[],
        metadata=None,
    )
    posted: dict[str, object] = {}

    def fake_post(url: str, *, json: dict, timeout: float) -> _FakeResponse:
        posted["url"] = url
        posted["json"] = json
        posted["timeout"] = timeout
        return _FakeResponse(202, {"status": "accepted"})

    monkeypatch.setattr("agent.transport.client.requests.post", fake_post)

    client = BackendClient("http://127.0.0.1:8000/api/v1")
    result = client.submit_scan(payload)

    assert posted["url"] == "http://127.0.0.1:8000/api/v1/scans"
    assert result.status_code == 202
    assert result.body == {"status": "accepted"}


def test_submit_scan_raises_on_error_status(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = ScanPayload(
        scan_id=uuid4(),
        timestamp=datetime.now(timezone.utc),
        subnet="192.168.0.0/24",
        scan_mode="quick",
        devices=[],
        findings=[],
        metadata=None,
    )

    monkeypatch.setattr(
        "agent.transport.client.requests.post",
        lambda *args, **kwargs: _FakeResponse(500, text="boom"),
    )

    client = BackendClient("http://127.0.0.1:8000/api/v1")
    with pytest.raises(BackendSubmissionError):
        client.submit_scan(payload)
