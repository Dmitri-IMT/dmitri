from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET_TEST = "tests/test_alembic_single_head.py"
USAGE_MESSAGE = (
    b"DATABASE_URL_TEST must point at the dmitri_test database. "
    b"Run ./database.sh --test."
)


def _env_without_database() -> dict[str, str]:
    env = os.environ.copy()
    env.pop("DATABASE_URL_TEST", None)
    env.pop("DATABASE_URL_DIRECT", None)
    return env


def _run_pytest_without_database(
    *extra_args: str,
) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        [sys.executable, "-m", "pytest", TARGET_TEST, "-q", *extra_args],
        cwd=ROOT,
        env=_env_without_database(),
        capture_output=True,
    )


def test_database_url_test_required_aborts_collection() -> None:
    result = _run_pytest_without_database()
    output = result.stdout + result.stderr
    assert result.returncode == 4
    assert USAGE_MESSAGE in output


def test_database_url_test_required_cannot_be_silenced() -> None:
    result = _run_pytest_without_database("-p", "no:cacheprovider")
    output = result.stdout + result.stderr
    assert result.returncode == 4
    assert USAGE_MESSAGE in output
