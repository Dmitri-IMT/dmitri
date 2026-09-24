"""Exercise the package shell entrypoints with real Linux flock."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.skipif(
    shutil.which("flock") is None, reason="Linux flock required"
)


@pytest.fixture
def appliance(tmp_path):
    lock = tmp_path / "scan.lock"
    lock.touch()
    contract = tmp_path / "packaging" / "scan-lock-path"
    contract.parent.mkdir()
    contract.write_text(str(lock) + "\n")
    commands = tmp_path / "bin"
    commands.mkdir()
    log = tmp_path / "apt.log"
    apt = commands / "apt-get"
    apt.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "$APT_LOG"\n')
    apt.chmod(0o755)
    identity = commands / "id"
    identity.write_text("#!/bin/sh\necho 0\n")
    identity.chmod(0o755)
    env = {
        **os.environ,
        "PATH": f"{commands}:{os.environ['PATH']}",
        "APT_LOG": str(log),
    }
    return tmp_path, lock, contract, log, env


@pytest.mark.parametrize("entrypoint", ["timer", "provision"])
def test_scan_blocks_every_install_entrypoint(appliance, entrypoint):
    import fcntl

    root, lock, contract, log, env = appliance
    if entrypoint == "timer":
        script = root / "update"
        script.write_text(
            (ROOT / "packaging/apt-upgrade-agent")
            .read_text()
            .replace("/usr/lib/dmitri/scan-lock-path", str(contract))
        )
    else:
        script = root / "scripts/provision-pi.sh"
        script.parent.mkdir()
        script.write_text((ROOT / "scripts/provision-pi.sh").read_text())
    with lock.open() as handle:
        fcntl.flock(handle, fcntl.LOCK_SH)
        result = subprocess.run(
            ["sh", str(script)], env=env, capture_output=True, text=True, timeout=5
        )
    assert result.returncode == (0 if entrypoint == "timer" else 1)
    assert "in progress" in result.stdout + result.stderr
    assert not log.exists()


def test_timer_holds_lock_for_install_and_releases_afterward(appliance):
    import fcntl

    root, lock, contract, log, env = appliance
    apt = root / "bin/apt-get"
    apt.write_text(
        "#!/bin/sh\n"
        'if flock -n -x "$SCAN_LOCK" true; then exit 42; fi\n'
        'printf "%s\\n" "$*" >> "$APT_LOG"\n'
    )
    script = root / "update"
    script.write_text(
        (ROOT / "packaging/apt-upgrade-agent")
        .read_text()
        .replace("/usr/lib/dmitri/scan-lock-path", str(contract))
    )
    subprocess.run(
        ["sh", str(script)], env={**env, "SCAN_LOCK": str(lock)}, check=True, timeout=5
    )
    assert log.read_text().splitlines() == [
        "update",
        "install -y --only-upgrade hardware-agent",
    ]
    with lock.open() as handle:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
