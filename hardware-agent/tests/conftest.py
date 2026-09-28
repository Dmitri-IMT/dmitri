from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


@pytest.fixture(autouse=True)
def _isolated_data_home(
    tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Keep default results out of the developer's home. The
    # directory name must not carry the test name (see test_not_downloads).
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path_factory.mktemp("xdg-data")))


@pytest.fixture(autouse=True)
def _appliance_lock(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    from agent.scanner import scan_lock

    lock = tmp_path / "scan.lock"
    lock.touch()
    contract = tmp_path / "scan-lock-path"
    contract.write_text(str(lock))
    monkeypatch.setattr(scan_lock, "LOCK_PATH_FILE", contract)
