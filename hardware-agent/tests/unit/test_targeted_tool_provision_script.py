"""Check release-specific package verification without installing tools."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/provision-targeted-tools.sh"
pytestmark = pytest.mark.skipif(os.name != "posix" or not shutil.which("bash"), reason="Bash required")


@pytest.mark.parametrize(
    ("codename", "version"),
    [("bookworm", "3.0.8+dfsg-1"), ("trixie", "3.2.1+dfsg-1")],
)
def test_verifier_uses_release_package_version(tmp_path: Path, codename: str, version: str) -> None:
    os_release = tmp_path / "os-release"
    os_release.write_text(f"VERSION_CODENAME={codename}\n")
    script = tmp_path / "provision-targeted-tools.sh"
    script.write_text(SCRIPT.read_text().replace("/etc/os-release", str(os_release)))

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name, body in {
        "dpkg": "printf 'arm64\\n'",
        "dpkg-query": f"printf '{version}\\n'",
        "testssl": "exit 0",
    }.items():
        binary = bin_dir / name
        binary.write_text(f"#!/bin/sh\n{body}\n")
        binary.chmod(0o755)

    result = subprocess.run(
        ["bash", str(script), "--verify-only"],
        env={**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}"},
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 1  # Other targeted tools are absent in the fixture.
    assert f"PASS  testssl {version}" in result.stdout


def test_production_checkout_skips_development_smoke_tests(tmp_path: Path) -> None:
    script = tmp_path / "provision-targeted-tools.sh"
    script.write_text(SCRIPT.read_text().split('ARCH="$(require_arm_arch)"')[0] + "run_local_smoke_tests\n")
    result = subprocess.run(
        ["bash", str(script)], capture_output=True, text=True, timeout=10
    )
    assert result.returncode == 0
    assert "Development smoke tests unavailable" in result.stdout
