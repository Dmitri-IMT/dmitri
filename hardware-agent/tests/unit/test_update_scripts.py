import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _bootstrap_staging_code(parent: Path):
    script = (ROOT / "scripts/provision-pi.sh").read_text()
    function = script.split("stage_bootstrap_inputs() {\n", 1)[1]
    code = function.split("<<'PY'\n", 1)[1].split("\nPY\n}", 1)[0]
    return (
        code.replace("(Path('/'), Path('/run'))", f"(Path({str(parent)!r}),)")
        .replace("dir='/run'", f"dir={str(parent)!r}")
        .replace("info.st_uid != 0", "info.st_uid != os.getuid()")
    )


@pytest.mark.skipif(os.name != "posix", reason="POSIX file permissions required")
@pytest.mark.parametrize("unsafe_parent", ["symlink", "writable"])
def test_bootstrap_staging_rejects_unsafe_parent_before_mutation(
    tmp_path, unsafe_parent
):
    target = tmp_path / "target"
    target.mkdir(mode=0o700)
    sentinel = target / "sentinel"
    sentinel.write_bytes(b"preserve")
    parent = tmp_path / "run"
    if unsafe_parent == "symlink":
        parent.symlink_to(target, target_is_directory=True)
    else:
        parent = target
        parent.chmod(0o777)
    before = target.stat().st_mode
    result = subprocess.run(
        [sys.executable, "-c", _bootstrap_staging_code(parent)],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode != 0
    assert "untrusted staging parent" in result.stderr
    assert target.stat().st_mode == before
    assert list(target.iterdir()) == [sentinel]
    assert sentinel.read_bytes() == b"preserve"


@pytest.mark.skipif(os.name != "posix", reason="POSIX shell required")
def test_bootstrap_consumes_staged_bytes_after_original_inputs_are_replaced(
    tmp_path, apt_test_signer
):
    script = (ROOT / "scripts/provision-pi.sh").read_text()
    parent = tmp_path / "run"
    parent.mkdir(mode=0o700)
    _, fingerprint, keyring = apt_test_signer
    originals = [tmp_path / name for name in ("key.gpg", "agent.deb", "updater.deb")]
    originals[0].write_bytes(keyring.read_bytes())
    agent = _artificial_deb(tmp_path, "staged-agent", "1.2.3", b"agent payload")
    originals[1].write_bytes(agent.read_bytes())
    control = tmp_path / "updater-root" / "DEBIAN"
    control.mkdir(parents=True)
    (control / "control").write_text(
        "Package: hardware-agent-updater\nVersion: 1.2.3-1\nArchitecture: all\n"
        "Maintainer: Test <test@example.test>\nDescription: staged updater\n"
    )
    subprocess.run(
        ["dpkg-deb", "--build", str(control.parent), str(originals[2])],
        check=True,
        capture_output=True,
        timeout=30,
    )
    expected = [path.read_bytes() for path in originals]
    result = subprocess.run(
        [sys.executable, "-c", _bootstrap_staging_code(parent), *map(str, originals)],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )
    stage = Path(result.stdout.strip())
    staged = [
        stage / name
        for name in ("public-key", "hardware-agent.deb", "hardware-agent-updater.deb")
    ]
    assert stage.stat().st_mode & 0o777 == 0o700
    assert all(path.stat().st_mode & 0o777 == 0o600 for path in staged)
    # The validation boundary observes only private copies.
    key_info = subprocess.run(
        ["gpg", "--batch", "--show-keys", "--with-colons", str(staged[0])],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    ).stdout
    assert any(
        line.startswith("fpr:") and line.split(":")[9] == fingerprint
        for line in key_info.splitlines()
    )
    assert [path.read_bytes() for path in staged] == expected
    helper_spec = importlib.util.spec_from_file_location(
        "staged_bootstrap_verifier", ROOT / "packaging/verify-bootstrap-packages.py"
    )
    assert helper_spec is not None and helper_spec.loader is not None
    helper = importlib.util.module_from_spec(helper_spec)
    helper_spec.loader.exec_module(helper)
    records = {}
    for name, architecture, contents in zip(
        ("hardware-agent", "hardware-agent-updater"), ("arm64", "all"), expected[1:]
    ):
        records[name] = (
            f"Package: {name}\nVersion: 1.2.3-1\nArchitecture: {architecture}\n"
            f"SHA256: {hashlib.sha256(contents).hexdigest()}\nSize: {len(contents)}\n"
        )

    class SignedApt:
        def _verify_dedicated_apt_source(self):
            return "https://apt.example.test", "/etc/apt/keyrings/dmitri.gpg"

        def _verify_apt_metadata_dates(self, uri):
            assert uri == "https://apt.example.test"

        def _trusted_apt_package_record(self, version, uri, package_name, architecture):
            return records[package_name]

        def _apt_record_matches(
            self, record, version, digest, package_name, architecture
        ):
            return f"SHA256: {digest}\n" in record

    helper.verify_packages(staged[1:], "https://apt.example.test", SignedApt())
    for original in originals:
        replacement = original.with_suffix(".replacement")
        replacement.write_bytes(b"attacker replacement")
        replacement.replace(original)

    # Run the actual keyring, installation and cache consumers with isolated paths.
    trust = tmp_path / "trust"
    trust.mkdir()
    cache = tmp_path / "cache"
    cache.mkdir(mode=0o700)
    key_install = script.split("keyring_tmp=$(mktemp", 1)[1].split("printf 'deb ", 1)[0]
    key_install = "keyring_tmp=$(mktemp" + key_install
    install_lines = [
        line for line in script.splitlines() if line.startswith('apt-get install -y "')
    ]
    assert len(install_lines) == 2
    cache_code = script.split("<<'PY'\nimport hashlib, os, shutil, sys, tempfile\n", 1)[
        1
    ].split("\nPY\n", 1)[0]
    cache_code = "import hashlib, os, shutil, sys, tempfile\n" + cache_code
    cache_code = cache_code.replace(
        "Path('/var/lib/dmitri/updates/cache')", f"Path({str(cache)!r})"
    )
    commands_dir = tmp_path / "bin"
    commands_dir.mkdir()
    apt = commands_dir / "apt-get"
    apt.write_text(
        '#!/bin/sh\ncp -- "$3" "$installed_packages/installed-$(basename "$3")"\n'
    )
    apt.chmod(0o755)
    environment = {
        **os.environ,
        "PATH": f"{commands_dir}{os.pathsep}{os.environ['PATH']}",
        "input_stage": str(stage),
        "keyring_directory": str(trust),
        "keyring": str(trust / "installed.gpg"),
        "installed_packages": str(tmp_path),
    }
    assignments = script.split("public_key=$input_stage/public-key\n", 1)[1].split(
        '[ -f "$agent_deb" ]', 1
    )[0]
    commands = (
        "set -eu\nexec 9>/dev/null\npublic_key=$input_stage/public-key\n"
        + assignments
        + '\ndie() { echo "$*" >&2; exit 1; }\n'
        + key_install
        + "\n"
        + "\n".join(install_lines)
    )
    consumed = subprocess.run(
        ["sh", "-c", commands],
        env=environment,
        capture_output=True,
        timeout=10,
    )
    assert consumed.returncode == 0, consumed.stderr.decode()
    subprocess.run(
        [sys.executable, "-c", cache_code, str(staged[1]), "1.2.3-1"],
        check=True,
        capture_output=True,
        timeout=10,
    )
    assert (trust / "installed.gpg").read_bytes() == expected[0]
    assert (tmp_path / "installed-hardware-agent.deb").read_bytes() == expected[1]
    assert (tmp_path / "installed-hardware-agent-updater.deb").read_bytes() == expected[
        2
    ]
    assert (cache / "1.2.3-1.deb").read_bytes() == expected[1]
    assert (cache / "1.2.3-1.sha256").read_text().strip() == hashlib.sha256(
        expected[1]
    ).hexdigest()
    assert script.index("input_stage=$(stage_bootstrap_inputs)") < script.index(
        "actual_fingerprint=$(gpg"
    )
    assert '--repository "$repository" "$agent_deb" "$updater_deb"' in script


def test_default_helper_only_requests_metadata_check():
    helper = (ROOT / "packaging/apt-upgrade-agent").read_text()
    assert "updater.py --check" in helper
    assert "apt-get install" not in helper
    assert "apt-get update" not in helper
    assert "source " not in helper
    assert " . /" not in helper


def test_timer_targets_check_only_unit():
    timer = (ROOT / "packaging/dmitri-agent-update.timer").read_text()
    check = (ROOT / "packaging/dmitri-agent-update-check.service").read_text()
    supervisor = (ROOT / "packaging/dmitri-agent-update.service").read_text()
    assert "Unit=dmitri-agent-update-check.service" in timer
    assert "apt-upgrade-agent --check" in check
    assert "Type=notify" in supervisor
    assert "KillMode=control-group" in supervisor
    assert "apt-get install" not in check + supervisor


def test_agent_waits_for_supervisor_without_supervisor_waiting_for_agent():
    agent = (ROOT / "dmitri-agent.service").read_text()
    supervisor = (ROOT / "packaging/dmitri-agent-update.service").read_text()
    assert "After=network-online.target dmitri-agent-update.service" in agent
    assert "Requires=dmitri-agent-update.service" in agent
    assert "Before=dmitri-agent.service" in supervisor
    assert "dmitri-agent.service" not in supervisor.split("[Service]", 1)[1]


@pytest.mark.skipif(
    os.name != "posix" or shutil.which("flock") is None,
    reason="POSIX shell and flock required",
)
def test_provision_refuses_to_mutate_while_scan_holds_lock(tmp_path: Path):
    import fcntl

    checkout = tmp_path / "checkout" / "hardware-agent"
    scripts = checkout / "scripts"
    packaging = checkout / "packaging"
    scripts.mkdir(parents=True)
    packaging.mkdir()
    lock = tmp_path / "scan.lock"
    lock.touch()
    (packaging / "scan-lock-path").write_text(f"{lock}\n")
    provision = scripts / "provision-pi.sh"
    provision_text = (ROOT / "scripts/provision-pi.sh").read_text()
    provision_text = provision_text.replace(
        "lock_expected=/var/lib/dmitri/scan.lock", f"lock_expected={lock}"
    ).replace("lock_directory=/var/lib/dmitri", f"lock_directory={lock.parent}")
    provision.write_text(provision_text)
    agent_package = tmp_path / "hardware-agent.deb"
    updater_package = tmp_path / "hardware-agent-updater.deb"
    agent_package.touch()
    updater_package.touch()

    commands = tmp_path / "bin"
    commands.mkdir()
    apt_log = tmp_path / "apt.log"
    apt = commands / "apt-get"
    apt.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "$APT_LOG"\n')
    apt.chmod(0o755)
    identity = commands / "id"
    identity.write_text("#!/bin/sh\necho 0\n")
    identity.chmod(0o755)
    environment = {
        **os.environ,
        "PATH": f"{commands}{os.pathsep}{os.environ['PATH']}",
        "APT_LOG": str(apt_log),
    }

    with lock.open() as handle:
        fcntl.flock(handle, fcntl.LOCK_SH)
        result = subprocess.run(
            [
                "sh",
                str(provision),
                "--repository",
                "https://apt.example.test",
                "--fingerprint",
                "A" * 40,
                "--public-key",
                str(tmp_path / "key.gpg"),
                "--",
                str(agent_package),
                str(updater_package),
            ],
            env=environment,
            capture_output=True,
            text=True,
            timeout=5,
        )

    assert result.returncode == 1
    assert "scan or update in progress" in result.stdout + result.stderr
    assert not apt_log.exists()


@pytest.mark.skipif(os.name != "posix", reason="POSIX shell required")
def test_provision_rejects_traversal_lock_path_even_inside_data_directory(tmp_path):
    checkout = tmp_path / "checkout" / "hardware-agent"
    scripts = checkout / "scripts"
    packaging = checkout / "packaging"
    scripts.mkdir(parents=True)
    packaging.mkdir()
    (packaging / "scan-lock-path").write_text("/var/lib/dmitri/../dmitri/scan.lock\n")
    provision = scripts / "provision-pi.sh"
    provision.write_text((ROOT / "scripts/provision-pi.sh").read_text())
    packages = [tmp_path / "hardware-agent.deb", tmp_path / "updater.deb"]
    for package in packages:
        package.touch()
    commands = tmp_path / "bin"
    commands.mkdir()
    identity = commands / "id"
    identity.write_text("#!/bin/sh\necho 0\n")
    identity.chmod(0o755)
    result = subprocess.run(
        [
            "sh",
            str(provision),
            "--repository",
            "https://apt.example.test",
            "--fingerprint",
            "A" * 40,
            "--public-key",
            str(tmp_path / "key.gpg"),
            "--",
            *(str(package) for package in packages),
        ],
        env={**os.environ, "PATH": f"{commands}{os.pathsep}{os.environ['PATH']}"},
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert result.returncode == 1
    assert "unsafe or non-canonical scan lock path" in result.stdout + result.stderr


@pytest.mark.skipif(os.name != "posix", reason="POSIX shell and proc fixture required")
def test_provision_idle_check_detects_controlled_scan_process(tmp_path):
    script = (ROOT / "scripts/provision-pi.sh").read_text()
    start = script.index("assert_legacy_idle() {")
    end = script.index("\nassert_legacy_idle\n", start)
    function = script[start:end]
    python = shutil.which("python3") or shutil.which("python")
    assert python is not None
    function = function.replace("/usr/bin/python3", python)
    proc_root = tmp_path / "proc"
    process = proc_root / "4242"
    process.mkdir(parents=True)
    (process / "cmdline").write_bytes(b"nmap\0-sV\0" + b"192.0.2.10\0")
    function = function.replace(
        "os.scandir('/proc')", f"os.scandir({str(proc_root)!r})"
    )
    commands = tmp_path / "bin"
    commands.mkdir()
    systemctl = commands / "systemctl"
    systemctl.write_text("#!/bin/sh\nexit 1\n")
    systemctl.chmod(0o755)
    result = subprocess.run(
        [
            "sh",
            "-c",
            'die() { echo "$*" >&2; exit 1; }\n' + function + "\nassert_legacy_idle",
        ],
        env={**os.environ, "PATH": f"{commands}{os.pathsep}{os.environ['PATH']}"},
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert result.returncode == 1
    assert "active scan-related process: nmap" in result.stderr


def test_bootstrap_baseline_lists_existing_units_and_helpers_as_separate_paths():
    provision = (ROOT / "scripts/provision-pi.sh").read_text()
    required_paths = {
        "lib/systemd/system/dmitri-agent.service",
        "lib/systemd/system/dmitri-agent-update.service",
        "lib/systemd/system/dmitri-agent-update.timer",
        "lib/systemd/system/dmitri-agent-update-check.service",
        "usr/lib/dmitri/apt-upgrade-agent",
        "usr/lib/dmitri/scan-lock-path",
    }
    for path in required_paths:
        assert path in provision
    assert 'printf \'%s\\n\' "$path" >>"$baseline/system-paths.txt"' in provision
    assert (
        'tar -C / -cpf "$baseline/system-files.tar" -T "$baseline/system-paths.txt"'
        in provision
    )


def test_build_script_creates_separate_offline_arm64_and_companion_packages():
    builder = (ROOT / "packaging/build-deb.sh").read_text()
    assert "cross_arm64=false" in builder
    assert "DIMITRI_BUILD_ARM64_CROSS:-0" in builder
    assert "Architecture: arm64" in builder
    assert "Package: hardware-agent-updater" in builder
    assert 'cp "$1" "$agent_root/opt/dmitri-agent/"' in builder
    assert "hardware_agent-*.whl" in builder
    assert "runtime-requirements.txt" in builder
    assert "tr -d '\\r' < \"$root/packaging/scan-lock-path\"" in builder
    assert "pip3 download --require-hashes --only-binary=:all:" in builder
    assert "--platform manylinux2014_aarch64" in builder
    assert "device_signing.py" in builder
    assert "apt-get install" not in builder


def test_agent_package_postinst_is_offline_and_does_not_start_services():
    builder = (ROOT / "packaging/build-deb.sh").read_text()
    postinst = builder.split("cat >\"$agent_root/DEBIAN/postinst\" <<'EOF'\n", 1)[1]
    postinst = postinst.split("\nEOF", 1)[0]
    assert "UV_OFFLINE=1" in postinst
    assert "--no-index" in postinst
    assert "--require-hashes" in postinst
    assert "exec 9>&- 9<&-" in postinst
    assert '"$uv" venv --offline --python "$python" "$agent/.venv"' in postinst
    assert '"$agent/.venv.next"' not in postinst
    assert '"$agent/.venv/bin/dmitri"' in postinst
    assert "Unknown command" in postinst
    assert "UV_PYTHON_DOWNLOADS=never" in postinst
    assert "systemctl start" not in postinst
    assert "apt-get install" not in postinst


def test_companion_owns_supervisor_contract_without_enabling_or_starting_units():
    builder = (ROOT / "packaging/build-deb.sh").read_text()
    postinst = builder.split("cat >\"$updater_root/DEBIAN/postinst\" <<'EOF'\n", 1)[1]
    postinst = postinst.split("\nEOF", 1)[0]
    assert "scan-lock-path" in builder
    assert "dmitri-agent-update-check.service" in builder
    assert "apt-upgrade-agent" in builder
    assert 'chmod 644 "$lock"' in postinst
    assert "lock_expected=/var/lib/dmitri/scan.lock" in postinst
    assert 'readlink -f "$lock_directory"' in postinst
    assert '[ ! -L "$lock_expected" ]' in postinst
    assert 'case "$lock" in /var/lib/dmitri/*)' not in postinst
    assert "systemctl enable" not in postinst
    assert "systemctl start" not in postinst


def test_companion_declares_offline_install_prerequisites():
    builder = (ROOT / "packaging/build-deb.sh").read_text()
    assert "Depends: apt, ca-certificates," in builder
    assert "python3-cryptography" in builder


def test_companion_ownership_transfer_cutoff_is_independent_of_agent_version():
    builder = (ROOT / "packaging/build-deb.sh").read_text()
    updater_control = builder.split('cat >"$updater_root/DEBIAN/control" <<EOF\n', 1)[1]
    updater_control = updater_control.split("\nEOF", 1)[0]
    assert "updater_transfer_cutoff=1.0.5-1" in builder
    assert "Breaks: hardware-agent (<< $updater_transfer_cutoff)" in updater_control
    assert "Replaces: hardware-agent (<< $updater_transfer_cutoff)" in updater_control
    assert "$agent_deb_version" not in updater_control


def test_bootstrap_requires_prebuilt_packages_and_retains_recovery_baseline():
    provision = (ROOT / "scripts/provision-pi.sh").read_text()
    assert (
        "usage: provision-pi.sh --repository HTTPS_URL --fingerprint "
        "FINGERPRINT --public-key KEYFILE" in provision
    )
    assert "verify-bootstrap-packages.py" in provision
    assert "bootstrap packages do not match authenticated signed metadata" in provision
    assert "--fingerprint" in provision
    assert "--public-key" in provision
    assert 'apt-get install -y "$updater_deb" 9>&-' in provision
    assert 'apt-get install -y "$agent_deb" 9>&-' in provision
    assert "packaging/build-deb.sh" not in provision
    assert 'tar -C / -cpf "$baseline/agent-tree.tar" opt/dmitri-agent' in provision
    assert "bootstrap-baselines" in provision
    assert "cannot prove the agent is idle" in provision
    assert "control.sock" in provision
    assert "state.sqlite3" in provision
    assert "update-gate.json" in provision
    assert "lock_expected=/var/lib/dmitri/scan.lock" in provision
    assert 'readlink -f "$lock_directory"' in provision
    assert 'case "$lock" in /var/lib/dmitri/*)' not in provision
    assert "flock -u 9" in provision
    assert "systemctl start dmitri-agent-update.service 9>&-" in provision
    assert "systemctl enable --now dmitri-agent-update.timer" in provision
    assert "systemctl show -p Unit --value dmitri-agent-update.timer" in provision
    assert "dmitri-agent-update-check.service" in provision
    assert "${installed_version}.sha256" not in provision
    assert "hashlib.sha256(source.read_bytes())" not in provision


@pytest.fixture
def apt_test_signer(tmp_path):
    required = ("sh", "python3", "gpg", "gpgv", "dpkg-deb")
    if os.name != "posix" or not all(shutil.which(tool) for tool in required):
        pytest.skip("POSIX shell, Python 3, GnuPG, gpgv and dpkg-deb required")
    home = tmp_path / "gnupg"
    home.mkdir(mode=0o700)
    generated = subprocess.run(
        [
            "gpg",
            "--homedir",
            str(home),
            "--batch",
            "--pinentry-mode",
            "loopback",
            "--passphrase",
            "",
            "--quick-generate-key",
            "APT Test <apt@example.test>",
            "ed25519",
            "sign",
            "0",
        ],
        capture_output=True,
        timeout=30,
    )
    assert generated.returncode == 0, generated.stderr.decode(errors="replace")
    fingerprint = next(
        line.split(":")[9]
        for line in subprocess.run(
            ["gpg", "--homedir", str(home), "--batch", "--with-colons", "--list-keys"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.splitlines()
        if line.startswith("fpr:")
    )
    keyring = tmp_path / "trusted.gpg"
    keyring.write_bytes(
        subprocess.run(
            ["gpg", "--homedir", str(home), "--batch", "--export", fingerprint],
            check=True,
            capture_output=True,
        ).stdout
    )
    return home, fingerprint, keyring


def _artificial_deb(tmp_path, name, version, payload, extra_control=()):
    package_root = tmp_path / f"{name}-root"
    control = package_root / "DEBIAN"
    content = package_root / "usr/share/hardware-agent"
    control.mkdir(parents=True)
    content.mkdir(parents=True)
    (control / "control").write_text(
        "\n".join(
            [
                "Package: hardware-agent",
                f"Version: {version}-1",
                "Architecture: arm64",
                "Maintainer: Test <test@example.test>",
                *extra_control,
                "Description: Artificial test package",
                "",
            ]
        )
    )
    (content / "payload").write_bytes(payload)
    package = tmp_path / f"{name}.deb"
    subprocess.run(
        ["dpkg-deb", "--build", str(package_root), str(package)],
        check=True,
        capture_output=True,
        timeout=30,
    )
    return package


def _apt_publish(
    tmp_path,
    signer,
    repo,
    package=None,
    version="1.0.1",
    notes="Test release",
    failpoint=None,
    release_id=None,
    valid_days=7,
    updater_package=None,
    updater_version=None,
):
    home, fingerprint, keyring = signer
    script = ROOT / "packaging/publish-apt.sh"
    command = ["sh", str(script), "prepare", "--repo", str(repo)]
    if package is not None:
        command.extend(
            [
                "--package",
                str(package),
                "--release-id",
                str(release_id or uuid4()),
                "--source-commit",
                "a" * 40,
                "--upstream-version",
                version,
                "--required-protocol-version",
                "1",
                "--required-updater-version",
                "1",
                "--release-notes",
                notes,
            ]
        )
    if updater_package is not None:
        command.extend(
            [
                "--updater-package",
                str(updater_package),
                "--updater-version",
                updater_version,
                "--updater-source-commit",
                "b" * 40,
            ]
        )
    command.extend(["--valid-days", str(valid_days)])
    prepared = subprocess.run(command, capture_output=True, text=True, timeout=30)
    assert prepared.returncode == 0, prepared.stdout + prepared.stderr
    candidate = prepared.stdout.strip().splitlines()[-1]
    signed = subprocess.run(
        [
            "sh",
            str(script),
            "sign",
            "--repo",
            str(repo),
            "--candidate",
            candidate,
            "--gnupg-home",
            str(home),
            "--key-id",
            fingerprint,
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert signed.returncode == 0, signed.stdout + signed.stderr
    environment = os.environ.copy()
    if failpoint:
        environment["DIMITRI_PUBLISH_FAILPOINT"] = failpoint
    promoted = subprocess.run(
        [
            "sh",
            str(script),
            "promote",
            "--repo",
            str(repo),
            "--candidate",
            candidate,
            "--keyring",
            str(keyring),
        ],
        capture_output=True,
        text=True,
        env=environment,
        timeout=30,
    )
    return promoted


def _apt_verify_current(signer, repo):
    _, _, keyring = signer
    return subprocess.run(
        [
            "sh",
            str(ROOT / "packaging/publish-apt.sh"),
            "verify-current",
            "--repo",
            str(repo),
            "--suite",
            "stable",
            "--keyring",
            str(keyring),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_apt_publisher_indexes_independently_versioned_updater_package(
    tmp_path: Path, apt_test_signer
):
    repo = tmp_path / "repo"
    agent = _artificial_deb(tmp_path, "agent", "1.2.3", b"agent")
    updater_root = tmp_path / "updater-root"
    control = updater_root / "DEBIAN"
    control.mkdir(parents=True)
    (control / "control").write_text(
        "Package: hardware-agent-updater\nVersion: 1.2.3-1\nArchitecture: all\n"
        "Maintainer: Test <test@example.test>\nDescription: updater fixture\n",
        encoding="utf-8",
    )
    updater_package = tmp_path / "hardware-agent-updater.deb"
    subprocess.run(
        ["dpkg-deb", "--build", str(updater_root), str(updater_package)],
        check=True,
        capture_output=True,
        timeout=30,
    )

    result = _apt_publish(
        tmp_path,
        apt_test_signer,
        repo,
        agent,
        version="1.2.3",
        updater_package=updater_package,
        updater_version="1.2.3-1",
    )

    assert result.returncode == 0, result.stdout + result.stderr
    snapshot = (repo / "dists/stable").resolve()
    arm64 = (snapshot / "main/binary-arm64/Packages").read_text(encoding="utf-8")
    all_arch = (snapshot / "main/binary-all/Packages").read_text(encoding="utf-8")
    assert "Package: hardware-agent\nVersion: 1.2.3-1\nArchitecture: arm64" in arm64
    assert (
        "Package: hardware-agent-updater\nVersion: 1.2.3-1\nArchitecture: all"
        in all_arch
    )
    catalog = json.loads(
        (snapshot / "main/release-catalog.json").read_text(encoding="utf-8")
    )
    assert len(catalog["releases"]) == 1
    provenance = json.loads(
        (snapshot / "main/updater-provenance.json").read_text(encoding="utf-8")
    )
    assert provenance == [
        {
            "package": "hardware-agent-updater",
            "package_version": "1.2.3-1",
            "architecture": "all",
            "source_commit": "b" * 40,
            "sha256": hashlib.sha256(updater_package.read_bytes()).hexdigest(),
            "size_bytes": updater_package.stat().st_size,
        }
    ]


@pytest.mark.parametrize(
    "relative_path",
    [
        "main/release-catalog.json",
        "main/binary-arm64/Packages",
    ],
)
def test_apt_publisher_rejects_tampered_previous_signed_index(
    tmp_path: Path, apt_test_signer, relative_path: str
):
    repo = tmp_path / "repo"
    agent = _artificial_deb(tmp_path, "agent", "1.2.3", b"agent")
    published = _apt_publish(tmp_path, apt_test_signer, repo, agent, version="1.2.3")
    assert published.returncode == 0, published.stdout + published.stderr

    current = (repo / "dists/stable").resolve()
    previous_index = current / relative_path
    previous_index.write_bytes(previous_index.read_bytes() + b" ")

    verified = _apt_verify_current(apt_test_signer, repo)
    assert verified.returncode != 0
    assert "metadata hash/size mismatch" in verified.stderr


def test_apt_publisher_reuses_identical_updater_for_next_agent_release(
    tmp_path: Path, apt_test_signer
):
    repo = tmp_path / "repo"
    agent_one = _artificial_deb(tmp_path, "agent-one", "1.2.3", b"agent-one")
    agent_two = _artificial_deb(tmp_path, "agent-two", "1.2.4", b"agent-two")
    updater_root = tmp_path / "updater-root"
    control = updater_root / "DEBIAN"
    control.mkdir(parents=True)
    (control / "control").write_text(
        "Package: hardware-agent-updater\nVersion: 1.2.3-1\nArchitecture: all\n"
        "Maintainer: Test <test@example.test>\nDescription: updater fixture\n",
        encoding="utf-8",
    )
    updater_package = tmp_path / "hardware-agent-updater.deb"
    subprocess.run(
        ["dpkg-deb", "--build", str(updater_root), str(updater_package)],
        check=True,
        capture_output=True,
        timeout=30,
    )

    first = _apt_publish(
        tmp_path,
        apt_test_signer,
        repo,
        agent_one,
        version="1.2.3",
        updater_package=updater_package,
        updater_version="1.2.3-1",
    )
    assert first.returncode == 0, first.stdout + first.stderr
    second = _apt_publish(
        tmp_path,
        apt_test_signer,
        repo,
        agent_two,
        version="1.2.4",
        updater_package=updater_package,
        updater_version="1.2.3-1",
    )
    assert second.returncode == 0, second.stdout + second.stderr

    current = (repo / "dists/stable").resolve()
    updater_index = (current / "main/binary-all/Packages").read_text(encoding="utf-8")
    provenance = json.loads(
        (current / "main/updater-provenance.json").read_text(encoding="utf-8")
    )
    assert updater_index.count("Package: hardware-agent-updater") == 1
    assert len(provenance) == 1


def test_apt_publisher_rejects_changed_bytes_for_existing_updater_identity(
    tmp_path: Path, apt_test_signer
):
    repo = tmp_path / "repo"
    agent_one = _artificial_deb(tmp_path, "agent-one", "1.2.3", b"agent-one")
    agent_two = _artificial_deb(tmp_path, "agent-two", "1.2.4", b"agent-two")

    def updater(payload: bytes, name: str) -> Path:
        root = tmp_path / name
        control = root / "DEBIAN"
        control.mkdir(parents=True)
        (control / "control").write_text(
            "Package: hardware-agent-updater\nVersion: 1.2.3-1\nArchitecture: all\n"
            "Maintainer: Test <test@example.test>\nDescription: updater fixture\n",
            encoding="utf-8",
        )
        (root / "usr/share/fixture").parent.mkdir(parents=True)
        (root / "usr/share/fixture").write_bytes(payload)
        package = tmp_path / f"{name}.deb"
        subprocess.run(
            ["dpkg-deb", "--build", str(root), str(package)],
            check=True,
            capture_output=True,
            timeout=30,
        )
        return package

    first_updater = updater(b"same identity, first bytes", "updater-first")
    changed_updater = updater(b"same identity, changed bytes", "updater-changed")
    first = _apt_publish(
        tmp_path,
        apt_test_signer,
        repo,
        agent_one,
        version="1.2.3",
        updater_package=first_updater,
        updater_version="1.2.3-1",
    )
    assert first.returncode == 0, first.stdout + first.stderr

    rejected = subprocess.run(
        [
            "sh",
            str(ROOT / "packaging/publish-apt.sh"),
            "prepare",
            "--repo",
            str(repo),
            "--package",
            str(agent_two),
            "--release-id",
            str(uuid4()),
            "--source-commit",
            "a" * 40,
            "--upstream-version",
            "1.2.4",
            "--updater-package",
            str(changed_updater),
            "--updater-version",
            "1.2.3-1",
            "--updater-source-commit",
            "b" * 40,
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert rejected.returncode != 0
    assert "different immutable bytes" in rejected.stderr


@pytest.mark.skipif(
    os.name != "posix" or shutil.which("dpkg-deb") is None,
    reason="POSIX dpkg-deb required",
)
def test_bootstrap_verifier_binds_local_bytes_to_package_identity_and_signed_record(
    tmp_path: Path,
):
    helper_path = ROOT / "packaging/verify-bootstrap-packages.py"
    spec = importlib.util.spec_from_file_location("bootstrap_verifier", helper_path)
    assert spec is not None and spec.loader is not None
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    packages = []
    records = {}
    for package_name, architecture in (
        ("hardware-agent", "arm64"),
        ("hardware-agent-updater", "all"),
    ):
        package_root = tmp_path / package_name
        control = package_root / "DEBIAN"
        control.mkdir(parents=True)
        (control / "control").write_text(
            f"Package: {package_name}\nVersion: 1.2.3-1\n"
            f"Architecture: {architecture}\nMaintainer: Test <test@example.test>\n"
            "Description: bootstrap verification fixture\n",
            encoding="utf-8",
        )
        payload = package_root / "usr/share/dmitri/fixture"
        payload.parent.mkdir(parents=True)
        payload.write_text(package_name, encoding="utf-8")
        package = tmp_path / f"{package_name}.deb"
        subprocess.run(
            ["dpkg-deb", "--build", str(package_root), str(package)],
            check=True,
            capture_output=True,
            timeout=30,
        )
        digest = hashlib.sha256(package.read_bytes()).hexdigest()
        records[(package_name, architecture)] = {
            "Package": package_name,
            "Version": "1.2.3-1",
            "Architecture": architecture,
            "SHA256": digest,
            "Size": str(package.stat().st_size),
        }
        packages.append(package)

    class SignedApt:
        def _verify_dedicated_apt_source(self):
            return "https://apt.example.test", "/etc/apt/keyrings/dmitri.gpg"

        def _verify_apt_metadata_dates(self, uri):
            assert uri == "https://apt.example.test"

        def _trusted_apt_package_record(self, version, uri, package_name, architecture):
            assert version == "1.2.3-1"
            assert uri == "https://apt.example.test"
            return "\n".join(
                f"{key}: {value}"
                for key, value in records[(package_name, architecture)].items()
            )

        def _apt_record_matches(
            self, record, version, digest, package_name, architecture
        ):
            return (
                f"Package: {package_name}" in record
                and f"Version: {version}" in record
                and f"Architecture: {architecture}" in record
                and f"SHA256: {digest}" in record
            )

    result = helper.verify_packages(packages, "https://apt.example.test/", SignedApt())

    assert result == [
        (
            "hardware-agent",
            "1.2.3-1",
            "arm64",
            records[("hardware-agent", "arm64")]["SHA256"],
        ),
        (
            "hardware-agent-updater",
            "1.2.3-1",
            "all",
            records[("hardware-agent-updater", "all")]["SHA256"],
        ),
    ]
    (tmp_path / "hardware-agent/usr/share/dmitri/fixture").write_text(
        "changed after authentication", encoding="utf-8"
    )
    changed_package = tmp_path / "hardware-agent-changed.deb"
    subprocess.run(
        ["dpkg-deb", "--build", str(tmp_path / "hardware-agent"), str(changed_package)],
        check=True,
        capture_output=True,
        timeout=30,
    )
    changed_package.replace(packages[0])
    with pytest.raises(ValueError, match="not authenticated"):
        helper.verify_packages(packages, "https://apt.example.test", SignedApt())


def _prepare_only(tmp_path, signer, repo, package, version):
    command = [
        "sh",
        str(ROOT / "packaging/publish-apt.sh"),
        "prepare",
        "--repo",
        str(repo),
        "--package",
        str(package),
        "--release-id",
        str(uuid4()),
        "--source-commit",
        "b" * 40,
        "--upstream-version",
        version,
        "--release-notes",
        "interleaved",
    ]
    result = subprocess.run(command, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout.strip().splitlines()[-1]


def _sign_promote(repo, signer, candidate, *, promote=True):
    home, fingerprint, keyring = signer
    script = ROOT / "packaging/publish-apt.sh"
    signed = subprocess.run(
        [
            "sh",
            str(script),
            "sign",
            "--repo",
            str(repo),
            "--candidate",
            candidate,
            "--gnupg-home",
            str(home),
            "--key-id",
            fingerprint,
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert signed.returncode == 0, signed.stdout + signed.stderr
    if not promote:
        return signed
    return subprocess.run(
        [
            "sh",
            str(script),
            "promote",
            "--repo",
            str(repo),
            "--candidate",
            candidate,
            "--keyring",
            str(keyring),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )


@pytest.mark.skipif(os.name != "posix", reason="APT repository symlinks require POSIX")
def test_apt_publisher_creates_signed_catalog_and_immutable_package(
    tmp_path, apt_test_signer
):
    repo = tmp_path / "repo"
    package = _artificial_deb(
        tmp_path, "artificial-hardware-agent", "1.0.1", b"disposable payload 1"
    )
    result = _apt_publish(tmp_path, apt_test_signer, repo, package)
    assert result.returncode == 0, result.stdout + result.stderr

    suite = repo / "dists/stable"
    catalog = json.loads((suite / "main/release-catalog.json").read_text())
    release = catalog["releases"][0]
    assert catalog["generation"] == 1
    assert release["source_commit"] == "a" * 40
    assert release["upstream_version"] == "1.0.1"
    assert release["package_version"] == "1.0.1-1"
    assert release["architecture"] == "arm64"
    assert release["suite"] == "stable"
    assert release["required_protocol_version"] == 1
    assert release["required_updater_version"] == 1
    assert release["release_notes"] == "Test release"
    assert str(UUID(release["id"])) == release["id"]
    assert datetime.fromisoformat(release["published_at"].replace("Z", "+00:00")).tzinfo
    package_path = repo / "pool/sha256" / f"{release['sha256']}.deb"
    assert package_path.read_bytes() == package.read_bytes()
    assert hashlib.sha256(package_path.read_bytes()).hexdigest() == release["sha256"]
    assert package_path.stat().st_size == release["size_bytes"]
    assert package_path.stat().st_mode & 0o222 == 0
    assert (suite / "InRelease").is_file()
    assert (suite / "Release.gpg").is_file()
    packages = (suite / "main/binary-arm64/Packages").read_text()
    assert f"SHA256: {release['sha256']}" in packages
    assert f"Size: {release['size_bytes']}" in packages
    assert "Filename: pool/sha256/" in packages
    index_hash = hashlib.sha256(packages.encode()).hexdigest()
    assert (
        suite / "main/binary-arm64/by-hash/SHA256" / index_hash
    ).read_text() == packages
    assert "Acquire-By-Hash: yes" in (suite / "Release").read_text()
    catalog_hash = hashlib.sha256(
        (suite / "main/release-catalog.json").read_bytes()
    ).hexdigest()
    assert (suite / "main/by-hash/SHA256" / catalog_hash).read_bytes() == (
        suite / "main/release-catalog.json"
    ).read_bytes()


@pytest.mark.skipif(os.name != "posix", reason="APT repository symlinks require POSIX")
def test_apt_publisher_refuses_different_bytes_for_existing_release_identity(
    tmp_path, apt_test_signer
):
    repo = tmp_path / "repo"
    first = _artificial_deb(tmp_path, "first", "1.0.1", b"original")
    second = _artificial_deb(tmp_path, "second", "1.0.1", b"replaced")
    identity = uuid4()
    initial = _apt_publish(tmp_path, apt_test_signer, repo, first, release_id=identity)
    assert initial.returncode == 0, initial.stdout + initial.stderr
    release_before = json.loads(
        (repo / "dists/stable/main/release-catalog.json").read_text()
    )["releases"][0]
    script = ROOT / "packaging/publish-apt.sh"
    collision = subprocess.run(
        [
            "sh",
            str(script),
            "prepare",
            "--repo",
            str(repo),
            "--package",
            str(second),
            "--release-id",
            str(identity),
            "--source-commit",
            "a" * 40,
            "--upstream-version",
            "1.0.1",
            "--required-protocol-version",
            "1",
            "--required-updater-version",
            "1",
            "--release-notes",
            "Test release",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert collision.returncode != 0
    assert "release identity collision" in collision.stdout + collision.stderr
    release_after = json.loads(
        (repo / "dists/stable/main/release-catalog.json").read_text()
    )["releases"][0]
    assert release_after == release_before
    assert (
        repo / "pool/sha256" / f"{release_before['sha256']}.deb"
    ).read_bytes() == first.read_bytes()


@pytest.mark.skipif(os.name != "posix", reason="APT repository symlinks require POSIX")
def test_apt_publisher_retains_releases_and_packages_after_new_version(
    tmp_path, apt_test_signer
):
    repo = tmp_path / "repo"
    first = _artificial_deb(tmp_path, "first", "1.0.1", b"retained release")
    second = _artificial_deb(tmp_path, "second", "1.0.2", b"new release")
    first_result = _apt_publish(tmp_path, apt_test_signer, repo, first)
    assert first_result.returncode == 0, first_result.stdout + first_result.stderr
    first_snapshot = (repo / "dists/stable").resolve()
    first_catalog = json.loads(
        (first_snapshot / "main/release-catalog.json").read_text()
    )
    first_entry = first_catalog["releases"][0]
    first_hash = first_entry["sha256"]

    second_result = _apt_publish(
        tmp_path, apt_test_signer, repo, second, version="1.0.2"
    )
    assert second_result.returncode == 0, second_result.stdout + second_result.stderr

    current = repo / "dists/stable"
    catalog = json.loads((current / "main/release-catalog.json").read_text())
    assert [entry["package_version"] for entry in catalog["releases"]] == [
        "1.0.1-1",
        "1.0.2-1",
    ]
    retained_first = repo / "pool/sha256" / f"{first_hash}.deb"
    retained_second = repo / "pool/sha256" / f"{catalog['releases'][1]['sha256']}.deb"
    assert retained_first.read_bytes() == first.read_bytes()
    assert retained_second.read_bytes() == second.read_bytes()
    assert first_snapshot.is_dir()
    packages = (current / "main/binary-arm64/Packages").read_text()
    assert "Version: 1.0.1-1" in packages
    assert "Version: 1.0.2-1" in packages


@pytest.mark.skipif(os.name != "posix", reason="APT repository symlinks require POSIX")
def test_apt_publisher_preserves_old_by_hash_objects_at_stable_suite_urls(
    tmp_path, apt_test_signer
):
    repo = tmp_path / "repo"
    first = _artificial_deb(tmp_path, "byhash-first", "1.0.1", b"first")
    second = _artificial_deb(tmp_path, "byhash-second", "1.0.2", b"second")
    assert _apt_publish(tmp_path, apt_test_signer, repo, first).returncode == 0
    old_suite = repo / "dists/stable"
    old_release = (old_suite / "Release").read_text()
    old_entries = {}
    hashing = False
    for line in old_release.splitlines():
        if line == "SHA256:":
            hashing = True
        elif hashing and line.startswith(" "):
            digest, size, name = line.split()
            if "/by-hash/SHA256/" in name:
                old_entries[name] = (digest, int(size))
        elif hashing:
            hashing = False
    assert old_entries
    second_result = _apt_publish(
        tmp_path, apt_test_signer, repo, second, version="1.0.2"
    )
    assert second_result.returncode == 0, second_result.stdout + second_result.stderr
    current = repo / "dists/stable"
    for name, (digest, size) in old_entries.items():
        content = (current / name).read_bytes()
        assert len(content) == size
        assert hashlib.sha256(content).hexdigest() == digest


@pytest.mark.skipif(os.name != "posix", reason="APT repository symlinks require POSIX")
def test_apt_publisher_rejects_stale_candidate_after_newer_generation_promoted(
    tmp_path, apt_test_signer
):
    repo = tmp_path / "repo"
    first = _artificial_deb(tmp_path, "stale-first", "1.0.1", b"first")
    older = _artificial_deb(tmp_path, "stale-older", "1.0.2", b"older")
    newer = _artificial_deb(tmp_path, "stale-newer", "1.0.3", b"newer")
    first_result = _apt_publish(tmp_path, apt_test_signer, repo, first)
    assert first_result.returncode == 0, first_result.stdout + first_result.stderr
    stale_candidate = _prepare_only(tmp_path, apt_test_signer, repo, older, "1.0.2")
    newer_result = _apt_publish(tmp_path, apt_test_signer, repo, newer, version="1.0.3")
    assert newer_result.returncode == 0, newer_result.stdout + newer_result.stderr
    current_before = (repo / "dists/stable").resolve()
    result = _sign_promote(repo, apt_test_signer, stale_candidate)
    assert result.returncode != 0
    assert "candidate is stale" in result.stdout + result.stderr
    assert (repo / "dists/stable").resolve() == current_before
    catalog = json.loads((repo / "dists/stable/main/release-catalog.json").read_text())
    assert catalog["generation"] == 2
    assert catalog["releases"][-1]["package_version"] == "1.0.3-1"


@pytest.mark.skipif(os.name != "posix", reason="APT repository symlinks require POSIX")
def test_packages_index_includes_full_control_dependencies_and_conflicts(
    tmp_path, apt_test_signer
):
    repo = tmp_path / "repo"
    package = _artificial_deb(
        tmp_path,
        "deps",
        "1.0.1",
        b"payload",
        (
            "Depends: libc6 (>= 2.31)",
            "Pre-Depends: adduser",
            "Conflicts: legacy-agent (<< 1.0)",
            "Breaks: old-agent (<< 2.0)",
        ),
    )
    result = _apt_publish(tmp_path, apt_test_signer, repo, package)
    assert result.returncode == 0, result.stdout + result.stderr
    packages = (repo / "dists/stable/main/binary-arm64/Packages").read_text()
    for field in (
        "Depends: libc6 (>= 2.31)",
        "Pre-Depends: adduser",
        "Conflicts: legacy-agent (<< 1.0)",
        "Breaks: old-agent (<< 2.0)",
    ):
        assert field in packages
    assert "Filename: pool/sha256/" in packages
    assert "Size: " in packages and "SHA256: " in packages


@pytest.mark.skipif(os.name != "posix", reason="APT repository symlinks require POSIX")
def test_refreshed_release_date_is_not_artificially_advanced_into_future(
    tmp_path, apt_test_signer
):
    repo = tmp_path / "repo"
    package = _artificial_deb(tmp_path, "date", "1.0.1", b"payload")
    assert _apt_publish(tmp_path, apt_test_signer, repo, package).returncode == 0
    before = datetime.now(timezone.utc).replace(microsecond=0)
    result = _apt_publish(tmp_path, apt_test_signer, repo)
    after = datetime.now(timezone.utc).replace(microsecond=0)
    assert result.returncode == 0, result.stdout + result.stderr
    release_text = (repo / "dists/stable/Release").read_text()
    published = datetime.strptime(
        next(
            line.removeprefix("Date: ")
            for line in release_text.splitlines()
            if line.startswith("Date: ")
        ),
        "%a, %d %b %Y %H:%M:%S UTC",
    ).replace(tzinfo=timezone.utc)
    assert before <= published <= after


@pytest.mark.skipif(os.name != "posix", reason="APT repository symlinks require POSIX")
def test_sign_and_promote_reject_unsafe_candidate_and_suite_paths(
    tmp_path, apt_test_signer
):
    repo = tmp_path / "repo"
    repo.mkdir()
    script = ROOT / "packaging/publish-apt.sh"
    home, fingerprint, keyring = apt_test_signer
    for candidate in (str(tmp_path / "outside"), "../outside"):
        for command, extra in (
            ("sign", ["--gnupg-home", str(home), "--key-id", fingerprint]),
            ("promote", ["--keyring", str(keyring)]),
        ):
            result = subprocess.run(
                [
                    "sh",
                    str(script),
                    command,
                    "--repo",
                    str(repo),
                    "--candidate",
                    candidate,
                    *extra,
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )
            assert result.returncode != 0
            assert "canonical UUID" in result.stdout + result.stderr
    stage_root = repo / ".staging"
    stage_root.mkdir()
    outside = tmp_path / "outside-stage"
    outside.mkdir()
    candidate = str(uuid4())
    (stage_root / candidate).symlink_to(outside, target_is_directory=True)
    for command, extra in (
        ("sign", ["--gnupg-home", str(home), "--key-id", fingerprint]),
        ("promote", ["--keyring", str(keyring)]),
    ):
        escaped = subprocess.run(
            [
                "sh",
                str(script),
                command,
                "--repo",
                str(repo),
                "--candidate",
                candidate,
                *extra,
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert escaped.returncode != 0
        assert "candidate escapes" in escaped.stdout + escaped.stderr
    unsafe_suite = subprocess.run(
        [
            "sh",
            str(script),
            "sign",
            "--repo",
            str(repo),
            "--candidate",
            candidate,
            "--suite",
            "../outside",
            "--gnupg-home",
            str(home),
            "--key-id",
            fingerprint,
        ],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert unsafe_suite.returncode != 0
    assert "only the stable suite" in unsafe_suite.stdout + unsafe_suite.stderr
    unsafe_promote_suite = subprocess.run(
        [
            "sh",
            str(script),
            "promote",
            "--repo",
            str(repo),
            "--candidate",
            candidate,
            "--suite",
            "../outside",
            "--keyring",
            str(keyring),
        ],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert unsafe_promote_suite.returncode != 0
    assert "only the stable suite" in (
        unsafe_promote_suite.stdout + unsafe_promote_suite.stderr
    )


@pytest.mark.skipif(os.name != "posix", reason="APT repository symlinks require POSIX")
def test_apt_publisher_rejects_non_stable_suite_for_every_command(
    tmp_path, apt_test_signer
):
    repo = tmp_path / "repo"
    package = _artificial_deb(tmp_path, "other-suite", "1.0.1", b"payload")
    script = ROOT / "packaging/publish-apt.sh"
    prepare = subprocess.run(
        [
            "sh",
            str(script),
            "prepare",
            "--repo",
            str(repo),
            "--package",
            str(package),
            "--release-id",
            str(uuid4()),
            "--source-commit",
            "a" * 40,
            "--upstream-version",
            "1.0.1",
            "--suite",
            "testing",
        ],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert prepare.returncode != 0
    assert "only the stable suite" in prepare.stdout + prepare.stderr
    home, fingerprint, keyring = apt_test_signer
    for command, extra in (
        ("sign", ["--gnupg-home", str(home), "--key-id", fingerprint]),
        ("promote", ["--keyring", str(keyring)]),
    ):
        result = subprocess.run(
            [
                "sh",
                str(script),
                command,
                "--repo",
                str(repo),
                "--candidate",
                str(uuid4()),
                "--suite",
                "testing",
                *extra,
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode != 0
        assert "only the stable suite" in result.stdout + result.stderr


@pytest.mark.skipif(os.name != "posix", reason="APT repository symlinks require POSIX")
def test_apt_publisher_rejects_nested_candidate_symlink_before_sign_or_promote(
    tmp_path, apt_test_signer
):
    repo = tmp_path / "repo"
    package = _artificial_deb(tmp_path, "nested-link", "1.0.1", b"payload")
    script = ROOT / "packaging/publish-apt.sh"
    home, fingerprint, keyring = apt_test_signer
    outside = tmp_path / "outside-suite"
    outside.mkdir()
    sentinel = outside / "Release"
    sentinel.write_text("external evidence must remain untouched", encoding="utf-8")

    for command, extra in (
        ("sign", ["--gnupg-home", str(home), "--key-id", fingerprint]),
        ("promote", ["--keyring", str(keyring)]),
    ):
        candidate = _prepare_only(tmp_path, apt_test_signer, repo, package, "1.0.1")
        staged_suite = repo / ".staging" / candidate / "dists/stable"
        shutil.rmtree(staged_suite)
        staged_suite.symlink_to(outside, target_is_directory=True)
        result = subprocess.run(
            [
                "sh",
                str(script),
                command,
                "--repo",
                str(repo),
                "--candidate",
                candidate,
                *extra,
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode != 0
        assert "managed tree contains a symlink" in result.stdout + result.stderr
        assert sentinel.read_text(encoding="utf-8") == (
            "external evidence must remain untouched"
        )
        assert sorted(path.name for path in outside.iterdir()) == ["Release"]


@pytest.mark.skipif(os.name != "posix", reason="APT repository symlinks require POSIX")
def test_apt_promotion_failure_keeps_previous_snapshot_and_catalog_references_valid(
    tmp_path, apt_test_signer
):
    repo = tmp_path / "repo"
    first = _artificial_deb(tmp_path, "first", "1.0.1", b"one")
    second = _artificial_deb(tmp_path, "second", "1.0.2", b"two")
    initial = _apt_publish(tmp_path, apt_test_signer, repo, first)
    assert initial.returncode == 0, initial.stdout + initial.stderr
    previous_snapshot = (repo / "dists/stable").resolve()
    previous_catalog = (repo / "dists/stable/main/release-catalog.json").read_bytes()
    failed = _apt_publish(
        tmp_path,
        apt_test_signer,
        repo,
        second,
        version="1.0.2",
        failpoint="before_metadata_promote",
    )
    assert failed.returncode != 0
    assert "injected failure" in failed.stdout + failed.stderr
    assert (repo / "dists/stable").resolve() == previous_snapshot
    assert (
        repo / "dists/stable/main/release-catalog.json"
    ).read_bytes() == previous_catalog
    assert not list((repo / "dists").glob("stable.tmp-*"))


@pytest.mark.skipif(os.name != "posix", reason="APT repository symlinks require POSIX")
def test_apt_refresh_extends_metadata_validity_and_retains_package_bytes(
    tmp_path, apt_test_signer
):
    repo = tmp_path / "repo"
    package = _artificial_deb(
        tmp_path,
        "artificial",
        "1.0.1",
        b"artificial package stays byte-for-byte stable",
    )
    initial = _apt_publish(tmp_path, apt_test_signer, repo, package, valid_days=1)
    assert initial.returncode == 0, initial.stdout + initial.stderr
    first_suite = repo / "dists/stable"
    first_catalog = json.loads((first_suite / "main/release-catalog.json").read_text())
    first_release = (first_suite / "Release").read_text()
    entry = first_catalog["releases"][0]
    package_path = repo / "pool/sha256" / f"{entry['sha256']}.deb"
    original_bytes = package_path.read_bytes()
    refreshed = _apt_publish(tmp_path, apt_test_signer, repo, valid_days=7)
    assert refreshed.returncode == 0, refreshed.stdout + refreshed.stderr
    second_suite = repo / "dists/stable"
    second_catalog = json.loads(
        (second_suite / "main/release-catalog.json").read_text()
    )
    second_release = (second_suite / "Release").read_text()
    assert second_catalog["generation"] == first_catalog["generation"] + 1
    assert second_catalog["releases"] == first_catalog["releases"]

    def validity(text):
        value = next(
            line.removeprefix("Valid-Until: ")
            for line in text.splitlines()
            if line.startswith("Valid-Until: ")
        )
        return datetime.strptime(value, "%a, %d %b %Y %H:%M:%S UTC").replace(
            tzinfo=timezone.utc
        )

    assert validity(second_release) > validity(first_release)
    assert package_path.read_bytes() == original_bytes
    assert len(list((repo / "snapshots").iterdir())) == 2


@pytest.mark.skipif(os.name != "posix", reason="APT repository symlinks require POSIX")
@pytest.mark.parametrize(
    "managed_path", [".staging", "pool/sha256", "snapshots", "dists", ".publish.lock"]
)
def test_prepare_rejects_managed_parent_symlink_without_touching_external_tree(
    tmp_path, managed_path
):
    repo = tmp_path / "repo"
    repo.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = outside / "sentinel"
    sentinel.write_text("preserve", encoding="utf-8")
    link = repo / managed_path
    link.parent.mkdir(parents=True, exist_ok=True)
    if managed_path == ".publish.lock":
        link.symlink_to(sentinel)
    else:
        link.symlink_to(outside, target_is_directory=True)

    result = subprocess.run(
        ["sh", str(ROOT / "packaging/publish-apt.sh"), "prepare", "--repo", str(repo)],
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode != 0
    assert "symlink" in result.stdout + result.stderr
    assert sentinel.read_text(encoding="utf-8") == "preserve"
    assert sorted(path.name for path in outside.iterdir()) == ["sentinel"]
    assert not (outside / "stable").exists()


@pytest.mark.skipif(os.name != "posix", reason="APT repository symlinks require POSIX")
@pytest.mark.parametrize("escape_parent", ["snapshots", "dists", "current"])
def test_promote_rejects_snapshot_parent_escape_without_external_writes(
    tmp_path, apt_test_signer, escape_parent
):
    repo = tmp_path / "repo"
    package = _artificial_deb(tmp_path, "promotion-parent", "1.0.1", b"payload")
    candidate = _prepare_only(tmp_path, apt_test_signer, repo, package, "1.0.1")
    home, fingerprint, keyring = apt_test_signer
    signed = subprocess.run(
        [
            "sh",
            str(ROOT / "packaging/publish-apt.sh"),
            "sign",
            "--repo",
            str(repo),
            "--candidate",
            candidate,
            "--gnupg-home",
            str(home),
            "--key-id",
            fingerprint,
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert signed.returncode == 0, signed.stdout + signed.stderr

    outside = tmp_path / "outside-publish"
    outside.mkdir()
    sentinel = outside / "sentinel"
    sentinel.write_text("preserve", encoding="utf-8")
    if escape_parent == "snapshots":
        shutil.rmtree(repo / "snapshots")
        (repo / "snapshots").symlink_to(outside, target_is_directory=True)
    elif escape_parent == "dists":
        shutil.rmtree(repo / "dists")
        (repo / "dists").symlink_to(outside, target_is_directory=True)
    else:
        (repo / "dists/stable").symlink_to(outside / "stable", target_is_directory=True)

    result = subprocess.run(
        [
            "sh",
            str(ROOT / "packaging/publish-apt.sh"),
            "promote",
            "--repo",
            str(repo),
            "--candidate",
            candidate,
            "--keyring",
            str(keyring),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode != 0
    assert sentinel.read_text(encoding="utf-8") == "preserve"
    assert sorted(path.name for path in outside.iterdir()) == ["sentinel"]


def test_apt_signer_uses_private_passphrase_file_and_rejects_broad_permissions(
    tmp_path, apt_test_signer
):
    home, fingerprint, keyring = apt_test_signer
    package = _artificial_deb(tmp_path, "passphrase-file", "1.0.1", b"fixture")
    repo = tmp_path / "repo"
    candidate = _prepare_only(tmp_path, apt_test_signer, repo, package, "1.0.1")
    passphrase = tmp_path / "signing-passphrase"
    passphrase.write_text("", encoding="ascii")
    passphrase.chmod(0o600)
    command = [
        "sh",
        str(ROOT / "packaging/publish-apt.sh"),
        "sign",
        "--repo",
        str(repo),
        "--candidate",
        candidate,
        "--gnupg-home",
        str(home),
        "--key-id",
        fingerprint,
        "--passphrase-file",
        str(passphrase),
    ]
    signed = subprocess.run(command, capture_output=True, text=True, timeout=30)
    assert signed.returncode == 0, signed.stdout + signed.stderr

    passphrase.chmod(0o644)
    rejected = subprocess.run(command, capture_output=True, text=True, timeout=30)
    assert rejected.returncode != 0
    assert "private regular file" in rejected.stderr

    promoted = subprocess.run(
        [
            "sh",
            str(ROOT / "packaging/publish-apt.sh"),
            "promote",
            "--repo",
            str(repo),
            "--candidate",
            candidate,
            "--keyring",
            str(keyring),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert promoted.returncode == 0, promoted.stdout + promoted.stderr


def test_pages_export_flattens_signed_suite_and_retains_content_addressed_pool(
    tmp_path, apt_test_signer
):
    package = _artificial_deb(tmp_path, "pages-export", "1.0.1", b"pages fixture")
    repo = tmp_path / "repo"
    result = _apt_publish(tmp_path, apt_test_signer, repo, package, version="1.0.1")
    assert result.returncode == 0, result.stdout + result.stderr

    helper_path = ROOT / "packaging/prepare-pages.py"
    spec = importlib.util.spec_from_file_location("prepare_pages", helper_path)
    assert spec is not None and spec.loader is not None
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    output = tmp_path / "pages"
    size = helper.prepare(repo, output, apt_test_signer[2])

    digest = hashlib.sha256(package.read_bytes()).hexdigest()
    assert size > 0
    assert (output / "dists/stable/Release").is_file()
    assert not (output / "dists/stable").is_symlink()
    assert (
        output / "pool/sha256" / f"{digest}.deb"
    ).read_bytes() == package.read_bytes()
    assert not (output / ".staging").exists()
    assert not (output / ".publish.lock").exists()


def test_pages_export_rejects_a_suite_link_outside_retained_snapshots(tmp_path):
    helper_path = ROOT / "packaging/prepare-pages.py"
    spec = importlib.util.spec_from_file_location("prepare_pages", helper_path)
    assert spec is not None and spec.loader is not None
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    repo = tmp_path / "repo"
    for directory in (repo / "pool/sha256", repo / "dists", repo / "snapshots"):
        directory.mkdir(parents=True, exist_ok=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    (repo / "dists/stable").symlink_to(outside, target_is_directory=True)
    keyring = tmp_path / "public.gpg"
    keyring.write_bytes(b"unused")

    with pytest.raises(SystemExit, match="escapes retained snapshots"):
        helper.prepare(repo, tmp_path / "pages", keyring)
