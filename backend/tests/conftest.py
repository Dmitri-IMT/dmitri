from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

TEST_DB = ROOT / "test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB.as_posix()}"
os.environ["PROCESS_ENRICHMENT_INLINE"] = "true"


def pytest_sessionstart(session) -> None:  # type: ignore[no-untyped-def]
    if TEST_DB.exists():
        TEST_DB.unlink()


def pytest_sessionfinish(session, exitstatus) -> None:  # type: ignore[no-untyped-def]
    if TEST_DB.exists():
        try:
            TEST_DB.unlink()
        except PermissionError:
            pass
