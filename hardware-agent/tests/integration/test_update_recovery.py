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


@pytest.mark.skipif(
    sys.platform != "linux" or not shutil.which("docker"),
    reason="requires Docker to run a real dpkg update and rollback in isolation",
)
def test_companion_dpkg_transaction_rolls_back_snapshot_and_reports_evidence(
    tmp_path: Path,
):
    """Exercise the companion transaction with real dpkg in an isolated Linux container."""
    transaction = r'''import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

source = Path("/repo/hardware-agent/packaging/updater.py")
spec = importlib.util.spec_from_file_location("linux_update_transaction", source)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

root = Path("/tmp/dmitri-transaction")
state = root / "state"
runtime = root / "run"
cache = state / "cache"
root.mkdir(parents=True)
cache.mkdir(parents=True)
module.STATE_DIR = state
module.PACKAGE_CACHE = cache
module.RUNTIME_DIR = runtime
module.GATE_PATH = root / "gate.json"
module.AGENT_ROOT = Path("/opt/dmitri-agent")
module._systemctl = lambda *_args: None
module._verify_package = lambda *_args: None
module._preflight = lambda *_args: None
module._verify_apt_origin_suite = lambda *_args: None

def package_version():
    result = subprocess.run(
        ["dpkg-query", "-W", "-f=${Version}", "hardware-agent"],
        check=True, capture_output=True, text=True,
    )
    return result.stdout.strip()

old_package = Path("/tmp/1.0.1-1.deb")
target_package = Path("/tmp/1.0.2-1.deb")
shutil.copyfile(old_package, cache / "1.0.1-1.deb")
old_digest = hashlib.sha256(old_package.read_bytes()).hexdigest()
(cache / "1.0.1-1.sha256").write_text(old_digest + "\n", encoding="ascii")
target_digest = hashlib.sha256(target_package.read_bytes()).hexdigest()
shutil.copyfile(target_package, cache / f"{target_digest}.deb")

updater = module.Updater(
    state, runtime, module.GATE_PATH,
    package_version=package_version,
    app_version=lambda: "1.0.1",
)
updater.initialize()
updater._run_metadata_refresh = lambda: True
def verify_local_health(target):
    if target == "1.0.2-1":
        raise module.UpdateFailure("local_health_failed")
    return "rollback-invocation"
updater._verify_local_health = verify_local_health
events = []
deadline = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()
update_id, session_id, release_id = (str(uuid.uuid4()) for _ in range(3))
def backend(path, body):
    if path.endswith("/claim"):
        return {
            "update_id": update_id,
            "session_id": session_id,
            "release_id": release_id,
            "sha256": target_digest,
            "target_package_version": "1.0.2-1",
            "required_updater_version": 1,
            "authorization_deadline": deadline,
        }
    events.append(body)
    return {"ack_sequence": body["sequence"]}
updater._post_json = backend

result = updater._apply_claimed_update(
    update_id, session_id, release_id,
    "1.0.2-1", target_digest, datetime.fromisoformat(deadline),
)
assert result == {"ok": False, "error": "rolled_back"}, result
assert package_version() == "1.0.1-1"
assert (module.AGENT_ROOT / "current.txt").read_text() == "old-runtime\n"
assert [event["phase"] for event in events] == [
    "preparing", "installing", "verifying", "recovering", "rolled_back"
]
terminal = events[-1]
assert terminal["local_outcome"] == "rolled_back"
assert terminal["package_version"] == "1.0.1-1"
assert terminal["evidence"] == {
    "package_status": "configured",
    "service_active": True,
    "health_check": "passed",
}
assert not module.GATE_PATH.exists()
print("real dpkg install, snapshot restore, rollback, and durable evidence passed")
'''
    (tmp_path / "transaction.py").write_text(transaction, encoding="utf-8")
    harness = r'''set -eu
make_deb() {
  version="$1"; content="$2"; root="/tmp/pkg-$version"
  mkdir -p "$root/DEBIAN" "$root/opt/dmitri-agent"
  cat >"$root/DEBIAN/control" <<EOF
Package: hardware-agent
Version: $version
Architecture: all
Maintainer: Test <test@example.test>
Description: isolated update transaction fixture
EOF
  printf '%s\n' "$content" >"$root/opt/dmitri-agent/current.txt"
  dpkg-deb --build "$root" "/tmp/$version.deb" >/dev/null
}
make_deb 1.0.1-1 old-runtime
make_deb 1.0.2-1 new-runtime
dpkg -i /tmp/1.0.1-1.deb >/dev/null
python /fixtures/transaction.py
'''
    (tmp_path / "run.sh").write_text(harness, encoding="utf-8", newline="\n")
    mount = f"type=bind,source={tmp_path},target=/fixtures,readonly"
    result = subprocess.run(
        [
            "docker", "run", "--rm", "--network", "none",
            "--mount", mount,
            "--mount", f"type=bind,source={ROOT.parent},target=/repo,readonly",
            "--entrypoint", "sh", "python:3.12-slim", "/fixtures/run.sh",
        ],
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "real dpkg install, snapshot restore, rollback, and durable evidence passed" in result.stdout

@pytest.mark.skipif(
    sys.platform != "linux" or not shutil.which("docker"),
    reason="requires Docker for a signed HTTPS APT repository fixture",
)
def test_signed_https_apt_metadata_is_revalidated_on_cache_hit(tmp_path: Path):
    """Use real apt/gpgv verification against an ephemeral signed HTTPS repository."""
    probe = subprocess.run(
        ["docker", "image", "inspect", "dmitri-main-test-agent:latest"],
        capture_output=True,
        text=True,
    )
    if probe.returncode:
        pytest.skip("requires local disposable agent image with Python, apt, and gpgv")

    prepare = r"""set -eu
repo=/fixtures/repo
mkdir -p "$repo/pool/main/h/hardware-agent" "$repo/dists/stable/main/binary-arm64" \
  "$repo/pool/competing/h/hardware-agent" "$repo/dists/unstable/main/binary-arm64"
for version in 1.2.2-1 1.2.3-1; do
  root="/tmp/pkg-$version"
  mkdir -p "$root/DEBIAN" "$root/opt/dmitri-agent"
  cat >"$root/DEBIAN/control" <<EOF
Package: hardware-agent
Version: $version
Architecture: arm64
Maintainer: Test <test@example.invalid>
Description: isolated APT trust fixture
EOF
  printf '%s\n' "$version" >"$root/opt/dmitri-agent/version.txt"
  deb="$repo/pool/main/h/hardware-agent_${version}_arm64.deb"
  dpkg-deb --build --root-owner-group "$root" "$deb" >/dev/null
done
root=/tmp/pkg-competing
mkdir -p "$root/DEBIAN" "$root/opt/dmitri-agent"
cat >"$root/DEBIAN/control" <<'EOF'
Package: hardware-agent
Version: 1.2.3-1
Architecture: arm64
Maintainer: Competing <competing@example.invalid>
Description: same-version collision from another signed suite
EOF
printf 'different package bytes\n' >"$root/opt/dmitri-agent/version.txt"
dpkg-deb --build --root-owner-group "$root" \
  "$repo/pool/competing/h/hardware-agent_1.2.3-1_arm64.deb" >/dev/null
packages="$repo/dists/stable/main/binary-arm64/Packages"
: >"$packages"
for deb in "$repo"/pool/main/h/hardware-agent_*.deb; do
  version=$(dpkg-deb -f "$deb" Version)
  filename="pool/main/h/$(basename "$deb")"
  size=$(stat -c '%s' "$deb")
  digest=$(sha256sum "$deb" | cut -d' ' -f1)
  cat >>"$packages" <<EOF
Package: hardware-agent
Version: $version
Architecture: arm64
Maintainer: Test <test@example.invalid>
Filename: $filename
Size: $size
SHA256: $digest
Description: isolated APT trust fixture

EOF
done
gzip -n -9 -kf "$packages"
competing_packages="$repo/dists/unstable/main/binary-arm64/Packages"
competing_deb="$repo/pool/competing/h/hardware-agent_1.2.3-1_arm64.deb"
competing_digest=$(sha256sum "$competing_deb" | cut -d' ' -f1)
competing_size=$(stat -c '%s' "$competing_deb")
cat >"$competing_packages" <<EOF
Package: hardware-agent
Version: 1.2.3-1
Architecture: arm64
Maintainer: Competing <competing@example.invalid>
Filename: pool/competing/h/hardware-agent_1.2.3-1_arm64.deb
Size: $competing_size
SHA256: $competing_digest
Description: same-version collision from another signed suite

EOF
gzip -n -9 -kf "$competing_packages"
cd "$repo/dists/stable"
date=$(date -u '+%a, %d %b %Y %H:%M:%S UTC')
expiry=$(date -u -d '+2 days' '+%a, %d %b %Y %H:%M:%S UTC')
write_release() {
  out="$1"; release_date="$2"; release_expiry="$3"
  cat >"$out" <<EOF
Origin: Dmitri
Label: Dmitri
Suite: stable
Codename: stable
Date: $release_date
Valid-Until: $release_expiry
Architectures: arm64
Components: main
SHA256:
 $(sha256sum main/binary-arm64/Packages | cut -d' ' -f1) $(stat -c '%s' main/binary-arm64/Packages) main/binary-arm64/Packages
 $(sha256sum main/binary-arm64/Packages.gz | cut -d' ' -f1) $(stat -c '%s' main/binary-arm64/Packages.gz) main/binary-arm64/Packages.gz
EOF
}
mkdir -m 700 /fixtures/gnupg
export GNUPGHOME=/fixtures/gnupg
gpg --batch --passphrase '' --quick-generate-key \
  'Task 11 APT Test <task11@example.invalid>' rsa2048 sign 2y >/dev/null 2>&1
write_release Release "$date" "$expiry"
gpg --batch --yes --clearsign --output InRelease Release
cat >"$repo/dists/unstable/Release" <<EOF
Origin: Dmitri
Label: Dmitri
Suite: unstable
Codename: unstable
Date: $date
Valid-Until: $expiry
Architectures: arm64
Components: main
SHA256:
 $(sha256sum "$competing_packages" | cut -d' ' -f1) $(stat -c '%s' "$competing_packages") main/binary-arm64/Packages
 $(sha256sum "$competing_packages.gz" | cut -d' ' -f1) $(stat -c '%s' "$competing_packages.gz") main/binary-arm64/Packages.gz
EOF
gpg --batch --yes --clearsign --output "$repo/dists/unstable/InRelease" \
  "$repo/dists/unstable/Release"
expired=$(date -u -d '-2 days' '+%a, %d %b %Y %H:%M:%S UTC')
expired_until=$(date -u -d '-1 days' '+%a, %d %b %Y %H:%M:%S UTC')
write_release /fixtures/expired.Release "$expired" "$expired_until"
gpg --batch --yes --clearsign --output /fixtures/expired.InRelease /fixtures/expired.Release
gpg --export > /fixtures/dmitri.gpg
openssl req -x509 -nodes -days 3 -newkey rsa:2048 \
  -keyout /fixtures/ca.key -out /fixtures/ca.crt \
  -subj '/CN=Task 11 local APT CA' >/dev/null 2>&1
openssl req -newkey rsa:2048 -nodes -keyout /fixtures/server.key \
  -out /fixtures/server.csr -subj '/CN=apt.task11.test' >/dev/null 2>&1
printf 'subjectAltName=DNS:apt.task11.test\nextendedKeyUsage=serverAuth\n' >/fixtures/server.ext
openssl x509 -req -days 2 -in /fixtures/server.csr \
  -CA /fixtures/ca.crt -CAkey /fixtures/ca.key -CAcreateserial \
  -out /fixtures/server.crt -extfile /fixtures/server.ext >/dev/null 2>&1
"""
    (tmp_path / "prepare-apt.sh").write_text(prepare, encoding="utf-8", newline="\n")
    bind = f"type=bind,source={tmp_path},target=/fixtures"
    signed = subprocess.run(
        [
            "docker", "run", "--rm", "--network", "none", "--mount", bind,
            "--entrypoint", "sh", "postgres:17", "/fixtures/prepare-apt.sh",
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert signed.returncode == 0, signed.stdout + signed.stderr

    verify = r"""import hashlib
import importlib.util
import os
import shutil
import ssl
import subprocess
import threading
from datetime import datetime, timedelta, timezone
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

repo = Path("/fixtures/repo")
for source in Path("/etc/apt/sources.list.d").glob("*"):
    source.unlink()
Path("/etc/apt/sources.list").unlink(missing_ok=True)
Path("/etc/apt/keyrings").mkdir(parents=True, exist_ok=True)
shutil.copyfile("/fixtures/dmitri.gpg", "/etc/apt/keyrings/dmitri.gpg")
os.chmod("/etc/apt/keyrings/dmitri.gpg", 0o644)
source = Path("/etc/apt/sources.list.d/dmitri.sources")
source.write_text(
    "Types: deb\nURIs: https://apt.task11.test:8443\nSuites: stable\n"
    "Components: main\nArchitectures: arm64\n"
    "Signed-By: /etc/apt/keyrings/dmitri.gpg\n",
    encoding="utf-8",
)
competing_source = Path("/etc/apt/sources.list.d/competing.list")
competing_source.write_text(
    "deb [arch=arm64 signed-by=/etc/apt/keyrings/dmitri.gpg] "
    "https://apt.task11.test:8443 unstable main\n",
    encoding="utf-8",
)
os.chmod(source, 0o644)
hosts = Path("/etc/hosts")
hosts.write_text(hosts.read_text(encoding="utf-8") + "\n127.0.0.1 apt.task11.test\n", encoding="utf-8")
Path("/usr/local/share/ca-certificates/task11-apt-test.crt").write_bytes(
    Path("/fixtures/ca.crt").read_bytes()
)
subprocess.run(["/usr/sbin/update-ca-certificates"], check=True, capture_output=True)
subprocess.run(["/usr/bin/dpkg", "--add-architecture", "arm64"], check=True)

requests = []
class LoggingHandler(SimpleHTTPRequestHandler):
    def log_message(self, _format, *args):
        requests.append(args[0] if args else "")

server = ThreadingHTTPServer(
    ("127.0.0.1", 8443), partial(LoggingHandler, directory=str(repo))
)
tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
tls.load_cert_chain("/fixtures/server.crt", "/fixtures/server.key")
server.socket = tls.wrap_socket(server.socket, server_side=True)
threading.Thread(target=server.serve_forever, daemon=True).start()
subprocess.run(
    ["/usr/bin/apt-get", "update"],
    check=True,
    capture_output=True,
    text=True,
    timeout=60,
    env={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C.UTF-8"},
)

spec = importlib.util.spec_from_file_location(
    "task11_updater", "/repo/hardware-agent/packaging/updater.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
state = Path("/tmp/task11-apt-state")
cache = state / "cache"
cache.mkdir(parents=True)
module.STATE_DIR = state
module.PACKAGE_CACHE = cache
module.RUNTIME_DIR = state / "run"
module.GATE_PATH = state / "gate.json"
target = "1.2.3-1"
prior = "1.2.2-1"
target_path = repo / "pool/main/h/hardware-agent_1.2.3-1_arm64.deb"
prior_path = repo / "pool/main/h/hardware-agent_1.2.2-1_arm64.deb"
target_digest = hashlib.sha256(target_path.read_bytes()).hexdigest()
competing_digest = hashlib.sha256(
    (repo / "pool/competing/h/hardware-agent_1.2.3-1_arm64.deb").read_bytes()
).hexdigest()
cached_target = cache / f"{target_digest}.deb"
shutil.copyfile(target_path, cached_target)
cached_prior = cache / f"{prior}.deb"
shutil.copyfile(prior_path, cached_prior)
(cache / f"{prior}.sha256").write_text(
    hashlib.sha256(prior_path.read_bytes()).hexdigest() + "\n", encoding="ascii"
)
updater = module.Updater(
    state, module.RUNTIME_DIR, module.GATE_PATH,
    package_version=lambda: prior, app_version=lambda: "1.2.2",
)
updater.initialize()
module._verify_apt_origin_suite(target, hashlib.sha256(target_path.read_bytes()).hexdigest())
try:
    module._verify_apt_origin_suite(target, competing_digest)
except module.UpdateFailure as exc:
    assert "artifact_mismatch" in str(exc)
else:
    raise AssertionError("a same-version hash from a competing signed suite was accepted")
result = updater._apply_claimed_update(
    "10000000-0000-0000-0000-000000000001",
    "20000000-0000-0000-0000-000000000002",
    "30000000-0000-0000-0000-000000000003",
    target,
    target_digest,
    datetime.now(timezone.utc) + timedelta(minutes=5),
)
assert result == {"ok": False, "error": "unsupported_platform"}, result
assert cached_target.read_bytes() == target_path.read_bytes()
assert not any("hardware-agent_1.2.3-1_arm64.deb" in request for request in requests)

inrelease = next(Path("/var/lib/apt/lists").glob("*apt.task11.test*stable*InRelease"))
inrelease.write_bytes(Path("/fixtures/expired.InRelease").read_bytes())
try:
    module._verify_apt_metadata_dates("https://apt.task11.test:8443")
except module.UpdateFailure as exc:
    assert "metadata_expired" in str(exc)
else:
    raise AssertionError("expired signed Release metadata was accepted")

keyring = Path("/etc/apt/keyrings/dmitri.gpg")
keyring.unlink()
try:
    module._verify_dedicated_apt_source()
except module.UpdateFailure as exc:
    assert "apt_keyring" in str(exc)
else:
    raise AssertionError("missing Signed-By keyring was accepted")
source.unlink()
competing_source.unlink()
try:
    module._verify_dedicated_apt_source()
except module.UpdateFailure as exc:
    assert "apt_source" in str(exc)
else:
    raise AssertionError("missing HTTPS source was accepted")
server.shutdown()
print("signed HTTPS APT cache-hit and source/keyring/expiry checks passed")
"""
    (tmp_path / "verify-apt.py").write_text(verify, encoding="utf-8", newline="\n")
    mount = f"type=bind,source={tmp_path},target=/fixtures,readonly"
    result = subprocess.run(
        [
            "docker", "run", "--rm", "--network", "none", "--mount", mount,
            "--mount", f"type=bind,source={ROOT.parent},target=/repo,readonly",
            "--entrypoint", "sh", "dmitri-main-test-agent:latest", "-c",
            "/root/.local/share/uv/python/cpython-3.12.12-linux-x86_64-gnu/bin/python3.12 /fixtures/verify-apt.py",
        ],
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "signed HTTPS APT cache-hit and source/keyring/expiry checks passed" in result.stdout
