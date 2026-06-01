from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from api.db.session import get_engine, reset_db_state  # noqa: E402

TEST_DB = ROOT / "test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB.as_posix()}"


def _cleanup_test_db() -> None:
    try:
        get_engine().dispose()
    except Exception:
        pass
    reset_db_state()
    if TEST_DB.exists():
        try:
            TEST_DB.unlink()
        except PermissionError:
            pass


@pytest.fixture(autouse=True)
def reset_test_database() -> None:
    _cleanup_test_db()
    yield
    _cleanup_test_db()


def pytest_sessionstart(session) -> None:  # type: ignore[no-untyped-def]
    _cleanup_test_db()


def pytest_sessionfinish(session, exitstatus) -> None:  # type: ignore[no-untyped-def]
    _cleanup_test_db()
