# ruff: noqa: E501
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _smoke_wheel(path: Path) -> None:
    files = {
        "dmitri_smoke.py": "import sys\ndef main():\n    print('Unknown command', file=sys.stderr)\n    return 2\n",
        "hardware_agent-0.1.dist-info/METADATA": "Metadata-Version: 2.1\nName: hardware-agent\nVersion: 0.1\n",
        "hardware_agent-0.1.dist-info/WHEEL": "Wheel-Version: 1.0\nGenerator: test\nRoot-Is-Purelib: true\nTag: py3-none-any\n",
        "hardware_agent-0.1.dist-info/entry_points.txt": "[console_scripts]\ndmitri = dmitri_smoke:main\n",
        "hardware_agent-0.1.dist-info/RECORD": "",
    }
    with zipfile.ZipFile(path, "w") as wheel:
        for name, contents in files.items():
            wheel.writestr(name, contents)


@pytest.mark.skipif(
    sys.platform != "linux" or not shutil.which("docker"),
    reason="requires Docker to run dpkg in a disposable Linux container",
)
def test_agent_package_postinst_runs_offline_and_recovers_failed_install(tmp_path):
    """Run the actual postinst under dpkg in a network-isolated disposable container."""
    builder = (ROOT / "packaging/build-deb.sh").read_text(encoding="utf-8")
    postinst = builder.split("cat >\"$agent_root/DEBIAN/postinst\" <<'EOF'\n", 1)[1]
    postinst = postinst.split("\nEOF", 1)[0]
    (tmp_path / "postinst").write_text(postinst + "\n", encoding="utf-8", newline="\n")
    updater_postinst = builder.split(
        "cat >\"$updater_root/DEBIAN/postinst\" <<'EOF'\n", 1
    )[1].split("\nEOF", 1)[0]
    (tmp_path / "updater-postinst").write_text(
        updater_postinst + "\n", encoding="utf-8", newline="\n"
    )
    _smoke_wheel(tmp_path / "valid.whl")
    (tmp_path / "invalid.whl").write_bytes(b"not a wheel")

    harness = r"""set -eu
mkdir -p /opt/uv-python/bin /usr/local/bin /tmp/pkgroot/DEBIAN /tmp/pkgroot/opt/dmitri-agent/wheelhouse /etc/dmitri /var/lib/dmitri/results
mkdir -p /usr/lib/dmitri
cp /fixtures/updater-postinst /usr/lib/dmitri/postinst
printf '%s' '/var/lib/dmitri/../dmitri/scan.lock' >/usr/lib/dmitri/scan-lock-path
set +e; sh /usr/lib/dmitri/postinst >/tmp/updater-postinst.log 2>&1; updater_status=$?; set -e
test "$updater_status" -ne 0
grep -q 'unsafe or non-canonical lock path' /tmp/updater-postinst.log
test ! -e /var/lib/dmitri/scan.lock
printf '%s' '/var/lib/dmitri/scan.lock' >/usr/lib/dmitri/scan-lock-path
sh /usr/lib/dmitri/postinst
test -f /var/lib/dmitri/scan.lock
ln -s /usr/local/bin/python3 /opt/uv-python/bin/python
printf 'DEVICE_ID=stable-device\\nAPI_KEY=identity\\n' >/etc/dmitri/agent.env
printf 'previous result\\n' >/var/lib/dmitri/results/result.json
mkdir -p /opt/dmitri-agent/.venv/bin
printf '#!/bin/sh\\necho old-runtime\\n' >/opt/dmitri-agent/.venv/bin/dmitri
chmod 755 /opt/dmitri-agent/.venv/bin/dmitri
set +e; sh /fixtures/postinst >/tmp/prerequisite.log 2>&1; prerequisite_status=$?; set -e
test "$prerequisite_status" -ne 0
grep -q 'prepared uv is required' /tmp/prerequisite.log
grep -q 'old-runtime' /opt/dmitri-agent/.venv/bin/dmitri
grep -q 'DEVICE_ID=stable-device' /etc/dmitri/agent.env
cat >/usr/local/bin/uv <<'PY'
#!/usr/local/bin/python3
import subprocess, sys
a=sys.argv[1:]
if a == ['--version']:
 print('uv 0.11.20'); raise SystemExit(0)
if a and a[0] == 'venv':
 python=a[a.index('--python')+1]; raise SystemExit(subprocess.call([python,'-m','venv',a[-1]]))
if len(a)>2 and a[:2]==['pip','install']:
 if '-r' in a: raise SystemExit(0)
 python=a[a.index('--python')+1]; raise SystemExit(subprocess.call([python,'-m','pip','install','--no-index','--no-deps',a[-1]]))
raise SystemExit('unsupported fake uv invocation: '+repr(a))
PY
chmod 755 /usr/local/bin/uv
cp /fixtures/valid.whl /tmp/pkgroot/opt/dmitri-agent/hardware_agent-0.1-py3-none-any.whl
printf '# fixture has no runtime dependencies\n' >/tmp/pkgroot/opt/dmitri-agent/runtime-requirements.txt
cp /fixtures/postinst /tmp/pkgroot/DEBIAN/postinst; chmod 755 /tmp/pkgroot/DEBIAN/postinst
cat >/tmp/pkgroot/DEBIAN/control <<'EOF'
Package: hardware-agent
Version: 1.0.5-1
Architecture: all
Maintainer: Test <test@example.test>
Description: isolated package test
EOF
dpkg-deb --build /tmp/pkgroot /tmp/valid.deb >/dev/null
printf 'DEVICE_ID=stable-device\nAPI_KEY=identity\n' >/etc/dmitri/agent.env
printf 'previous result\n' >/var/lib/dmitri/results/result.json
mkdir -p /opt/dmitri-agent/.venv/bin
printf '#!/bin/sh\necho old-runtime\n' >/opt/dmitri-agent/.venv/bin/dmitri; chmod 755 /opt/dmitri-agent/.venv/bin/dmitri
dpkg --force-depends -i /tmp/valid.deb >/tmp/dpkg-success.log 2>&1
test -x /opt/dmitri-agent/.venv/bin/dmitri
head -n1 /opt/dmitri-agent/.venv/bin/dmitri | grep -F '#!/opt/dmitri-agent/.venv/bin/python' >/dev/null
set +e; /opt/dmitri-agent/.venv/bin/dmitri __dmitri_install_smoke_check__ >/tmp/cli.log 2>&1; cli_status=$?; set -e
test "$cli_status" -eq 2; grep -q 'Unknown command' /tmp/cli.log
cp /fixtures/invalid.whl /tmp/pkgroot/opt/dmitri-agent/hardware_agent-0.2-py3-none-any.whl
rm -f /tmp/pkgroot/opt/dmitri-agent/hardware_agent-0.1-py3-none-any.whl
sed -i 's/1.0.5-1/1.0.6-1/' /tmp/pkgroot/DEBIAN/control
dpkg-deb --build /tmp/pkgroot /tmp/invalid.deb >/dev/null
set +e; dpkg --force-depends -i /tmp/invalid.deb >/tmp/dpkg-failure.log 2>&1; failed_status=$?; set -e
test "$failed_status" -ne 0; test -x /opt/dmitri-agent/.venv/bin/dmitri
head -n1 /opt/dmitri-agent/.venv/bin/dmitri | grep -F '#!/opt/dmitri-agent/.venv/bin/python' >/dev/null
grep -q 'DEVICE_ID=stable-device' /etc/dmitri/agent.env; grep -q 'API_KEY=identity' /etc/dmitri/agent.env
grep -q 'previous result' /var/lib/dmitri/results/result.json; test ! -e /opt/dmitri-agent/.venv.previous
echo 'dpkg offline install, CLI smoke, and failed-install recovery passed'
"""
    (tmp_path / "run.sh").write_text(harness, encoding="utf-8", newline="\n")
    mount = f"type=bind,source={tmp_path},target=/fixtures,readonly"
    result = subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "--network",
            "none",
            "--mount",
            mount,
            "--entrypoint",
            "sh",
            "python:3.12-slim",
            "/fixtures/run.sh",
        ],
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert (
        "dpkg offline install, CLI smoke, and failed-install recovery passed"
        in result.stdout
    ), result.stdout + result.stderr
