from __future__ import annotations

import api.services.worker as worker_module
import api.worker_main as worker_main
import pytest
from api.db import session as session_module
from api.db.session import reset_db_state
from pydantic import ValidationError
from sqlmodel import Session


def test_run_worker_loop_fails_before_poll_or_engine_when_database_url_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reset_db_state()
    engine_calls: list[bool] = []
    sleep_calls: list[bool] = []

    def _fake_create_engine(*a: object, **k: object) -> object:
        engine_calls.append(True)
        return object()

    with monkeypatch.context() as ctx:
        ctx.delenv("DATABASE_URL", raising=False)
        ctx.setattr(session_module, "create_engine", _fake_create_engine)
        ctx.setattr(
            worker_module.time, "sleep", lambda *a, **k: sleep_calls.append(True)
        )
        with pytest.raises(ValidationError):
            worker_module.run_worker_loop()
    reset_db_state()
    assert engine_calls == []
    assert sleep_calls == []


def test_run_worker_once_fails_before_engine_construction_when_database_url_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reset_db_state()
    engine_calls: list[bool] = []

    def _fake_create_engine(*a: object, **k: object) -> object:
        engine_calls.append(True)
        return object()

    with monkeypatch.context() as ctx:
        ctx.delenv("DATABASE_URL", raising=False)
        ctx.setattr(session_module, "create_engine", _fake_create_engine)
        with pytest.raises(ValidationError):
            worker_module.run_worker_once()
    reset_db_state()
    assert engine_calls == []


def test_run_worker_loop_fails_before_poll_or_engine_when_database_url_invalid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reset_db_state()
    engine_calls: list[bool] = []
    sleep_calls: list[bool] = []

    def _fake_create_engine(*a: object, **k: object) -> object:
        engine_calls.append(True)
        return object()

    with monkeypatch.context() as ctx:
        ctx.setenv("DATABASE_URL", "sqlite:///./scanner.db")
        ctx.setattr(session_module, "create_engine", _fake_create_engine)
        ctx.setattr(
            worker_module.time, "sleep", lambda *a, **k: sleep_calls.append(True)
        )
        with pytest.raises(ValidationError):
            worker_module.run_worker_loop()
    reset_db_state()
    assert engine_calls == []
    assert sleep_calls == []


def test_run_worker_once_fails_before_engine_construction_when_database_url_invalid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reset_db_state()
    engine_calls: list[bool] = []

    def _fake_create_engine(*a: object, **k: object) -> object:
        engine_calls.append(True)
        return object()

    with monkeypatch.context() as ctx:
        ctx.setenv("DATABASE_URL", "sqlite:///./scanner.db")
        ctx.setattr(session_module, "create_engine", _fake_create_engine)
        with pytest.raises(ValidationError):
            worker_module.run_worker_once()
    reset_db_state()
    assert engine_calls == []


def test_run_worker_once_returns_zero_against_migrated_empty_database(
    monkeypatch: pytest.MonkeyPatch, runtime_session: Session
) -> None:
    def _fake_get_session():
        yield runtime_session

    monkeypatch.setattr(worker_module, "get_session", _fake_get_session)

    assert worker_module.run_worker_once() == 0


def test_main_is_wired_to_run_worker_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[bool] = []
    monkeypatch.setattr(worker_main, "run_worker_loop", lambda: calls.append(True))

    assert worker_main.main() == 0

    assert calls == [True]
