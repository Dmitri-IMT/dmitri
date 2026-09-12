from __future__ import annotations

import api.services.nvd as nvd_module
import sqlalchemy as sa
from api.core.config import get_settings
from api.models.persistence import NvdCacheRecord
from api.services.nvd import NvdClient, NvdTemporaryError
from sqlmodel import Session, select


class _FakeResponse:
    def __init__(
        self,
        status_code: int,
        *,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.status_code = status_code
        self.headers = nvd_module.httpx.Headers(headers)

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise nvd_module.httpx.HTTPStatusError(
                "request failed",
                request=nvd_module.httpx.Request("GET", "https://nvd.test"),
                response=nvd_module.httpx.Response(self.status_code),
            )

    def json(self) -> dict[str, object]:
        return {"vulnerabilities": []}


class _FakeClient:
    responses: list[_FakeResponse] = []

    def __init__(self, *args: object, **kwargs: object) -> None:
        pass

    def __enter__(self) -> "_FakeClient":
        return self

    def __exit__(self, *exc_info: object) -> bool:
        return False

    def get(self, url: str, params: dict | None = None) -> _FakeResponse:
        return self.responses.pop(0)


def _session() -> Session:
    engine = sa.create_engine("sqlite://")
    NvdCacheRecord.metadata.create_all(engine, tables=[NvdCacheRecord.__table__])
    return Session(engine)


def test_nvd_429_exposes_retry_after_without_caching(monkeypatch) -> None:
    monkeypatch.setenv("NVD_MIN_REQUEST_INTERVAL_SECONDS", "0")
    get_settings.cache_clear()
    _FakeClient.responses = [_FakeResponse(429, headers={"Retry-After": "17"})]
    monkeypatch.setattr(nvd_module.httpx, "Client", _FakeClient)

    with _session() as session:
        try:
            NvdClient().query_by_cve(session, "CVE-2024-0001")
        except NvdTemporaryError as exc:
            assert exc.code == "nvd_rate_limited"
            assert exc.retry_after_seconds == 17
        else:
            raise AssertionError("expected NvdTemporaryError")
        assert session.exec(select(NvdCacheRecord)).all() == []
    get_settings.cache_clear()


def test_nvd_client_spaces_uncached_requests(monkeypatch) -> None:
    monkeypatch.setenv("NVD_MIN_REQUEST_INTERVAL_SECONDS", "6")
    get_settings.cache_clear()
    _FakeClient.responses = [_FakeResponse(200), _FakeResponse(200)]
    monkeypatch.setattr(nvd_module.httpx, "Client", _FakeClient)
    clock = iter([100.0, 100.0, 101.0, 107.0])
    sleeps: list[float] = []
    monkeypatch.setattr(nvd_module.time, "monotonic", lambda: next(clock))
    monkeypatch.setattr(nvd_module.time, "sleep", sleeps.append)

    with _session() as session:
        client = NvdClient()
        client.query_by_cve(session, "CVE-2024-0001")
        client.query_by_cve(session, "CVE-2024-0002")

    assert sleeps == [5.0]
    get_settings.cache_clear()
