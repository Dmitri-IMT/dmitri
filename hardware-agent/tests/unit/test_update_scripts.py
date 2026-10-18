import hashlib
import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

import pytest

ROOT = Path(__file__).resolve().parents[2]


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
            ["sh", str(provision), str(agent_package), str(updater_package)],
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
        ["sh", str(provision), *(str(package) for package in packages)],
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
    assert 'cross_arm64=false' in builder
    assert 'DIMITRI_BUILD_ARM64_CROSS:-0' in builder
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
        "usage: provision-pi.sh HARDWARE_AGENT.deb HARDWARE_AGENT_UPDATER.deb"
        in provision
    )
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
