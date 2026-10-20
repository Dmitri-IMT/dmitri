#!/bin/sh
set -eu
exec python3 - "$@" <<'PY'
import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID, uuid4


def fail(message):
    raise SystemExit(f"publish-apt: {message}")


def run(args):
    try:
        return subprocess.run(args, check=True, capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError) as exc:
        fail(f"command failed: {args[0]} ({exc})")


def digest_file(path):
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def read_catalog(path):
    if not path.exists():
        return {"generation": 0, "releases": []}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"current release catalog is unreadable: {exc}")
    if not isinstance(value, dict) or type(value.get("generation")) is not int or not isinstance(value.get("releases"), list):
        fail("current release catalog has an invalid shape")
    return value


def read_updater_provenance(path):
    if not path.exists():
        return []
    try:
        entries = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"updater provenance is unreadable: {exc}")
    if not isinstance(entries, list):
        fail("updater provenance has an invalid shape")
    seen = set()
    for item in entries:
        if not isinstance(item, dict) or set(item) != {
            "package", "package_version", "architecture", "source_commit", "sha256", "size_bytes"
        }:
            fail("updater provenance has an invalid entry")
        identity = (item["package"], item["package_version"], item["architecture"])
        if (
            item["package"] != "hardware-agent-updater"
            or item["architecture"] != "all"
            or not isinstance(item["package_version"], str)
            or not re.fullmatch(r"[A-Za-z0-9.+:~_-]{1,128}", item["package_version"])
            or not isinstance(item["source_commit"], str)
            or not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", item["source_commit"])
            or not isinstance(item["sha256"], str)
            or not re.fullmatch(r"[0-9a-f]{64}", item["sha256"])
            or type(item["size_bytes"]) is not int
            or item["size_bytes"] < 0
            or identity in seen
        ):
            fail("updater provenance contains an invalid or duplicate identity")
        seen.add(identity)
    return entries


def package_control(path, package_name, version, architecture):
    control = run(["dpkg-deb", "--field", str(path)]).stdout.rstrip()
    fields = {}
    for line in control.splitlines():
        if line[:1].isspace() and fields:
            key = next(reversed(fields))
            fields[key] += "\n" + line
        elif ": " in line:
            key, value = line.split(": ", 1)
            fields[key] = value
    if (fields.get("Package"), fields.get("Version"), fields.get("Architecture")) != (
        package_name, version, architecture
    ):
        fail("package control fields do not match the release identity")
    return control


def package_stanzas(path):
    if path is None or not path.is_file():
        return []
    return [
        dict(line.split(": ", 1) for line in block.splitlines() if ": " in line)
        for block in path.read_text(encoding="utf-8").strip().split("\n\n")
        if block.strip()
    ]


def sha256_entries(suite_root):
    rows = []
    for path in sorted(p for p in suite_root.rglob("*") if p.is_file() and p.name not in {"Release", "Release.gpg", "InRelease"}):
        digest, size = digest_file(path)
        rows.append(f" {digest} {size} {path.relative_to(suite_root).as_posix()}")
    return rows


def validate_args(args):
    validate_suite(args.suite)
    if args.architecture != "arm64":
        fail("only the planned arm64 release platform is supported")
    if args.package:
        if not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", args.source_commit):
            fail("source commit must be a lowercase 40- or 64-character hash")
        if not re.fullmatch(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)", args.upstream_version):
            fail("upstream version must be numeric MAJOR.MINOR.PATCH")
        try:
            parsed = UUID(args.release_id)
        except ValueError:
            fail("release id must be a UUID")
        if str(parsed) != args.release_id.lower():
            fail("release id must be a canonical UUID")
    if args.updater_package and not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", args.updater_source_commit):
        fail("updater source commit must be a lowercase 40- or 64-character hash")
    if not args.origin or any(ord(char) < 32 or ord(char) == 127 for char in args.origin):
        fail("origin must be a non-empty single-line value")
    if len(args.release_notes) > 4000 or "\x00" in args.release_notes:
        fail("release notes must be at most 4000 characters and contain no NUL")
    if args.required_protocol_version < 1 or args.required_updater_version < 1:
        fail("required protocol and updater versions must be positive")
    if not 1 <= args.valid_days <= 30:
        fail("metadata validity must be between 1 and 30 days")


def validate_suite(suite):
    if suite != "stable":
        fail("only the stable suite is supported by this publisher")


def inside(root, path):
    try:
        path.resolve(strict=True).relative_to(root)
    except (OSError, ValueError):
        fail("managed repository path escapes repository")


def managed_dir(root, relative, create=False):
    current = root
    for part in Path(relative).parts:
        current = current / part
        if current.is_symlink():
            fail("managed repository directory must not be a symlink")
        if current.exists():
            if not current.is_dir():
                fail("managed repository path is not a directory")
            inside(root, current)
        elif create:
            current.mkdir()
            if current.is_symlink() or not current.is_dir():
                fail("managed repository directory changed during creation")
            inside(root, current)
    return current


def safe_repo(path, create=False):
    repo = path.resolve()
    if create and not repo.exists():
        repo.mkdir(parents=True)
    if not repo.is_dir():
        fail("repository must be a directory")
    return repo


def validate_managed_parents(repo):
    for relative in (".staging", "pool", "pool/sha256", "snapshots", "dists"):
        managed_dir(repo, relative)


def safe_lock(repo):
    lock_path = repo / ".publish.lock"
    if lock_path.is_symlink():
        fail("publish lock must not be a symlink")
    if lock_path.exists() and not lock_path.is_file():
        fail("publish lock must be a regular file")
    return lock_path


def atomic_json(path, value):
    temporary = path.with_name(path.name + ".tmp-" + str(uuid4()))
    temporary.write_text(json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def write_by_hash(path, destination):
    digest, _ = digest_file(path)
    target = destination / "by-hash" / "SHA256" / digest
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(path, target)


def copy_old_by_hash(current, suite_root):
    if not current.exists():
        return
    for source in current.rglob("by-hash/SHA256/*"):
        if source.is_file():
            relative = source.relative_to(current)
            target = suite_root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists():
                shutil.copyfile(source, target)


def managed_repo(args):
    validate_suite(args.suite)
    repo = args.repo.resolve(strict=True)
    if not repo.is_dir():
        fail("repository must be a directory")
    validate_managed_parents(repo)
    return repo


def managed_candidate(repo, candidate):
    try:
        parsed = UUID(candidate)
    except ValueError:
        fail("candidate must be a canonical UUID")
    if str(parsed) != candidate.lower():
        fail("candidate must be a canonical UUID")
    staging = managed_dir(repo, ".staging")
    if not staging.is_dir():
        fail("managed staging directory is missing")
    stage = (staging / candidate).resolve(strict=True)
    if stage.parent != staging or not stage.is_dir():
        fail("candidate escapes managed staging directory")
    validate_managed_tree(stage)
    return stage


def validate_managed_tree(root):
    root = root.resolve(strict=True)
    for current, directories, files in os.walk(root, followlinks=False):
        current_path = Path(current)
        for name in directories + files:
            path = current_path / name
            if path.is_symlink():
                fail("managed tree contains a symlink")
            try:
                path.resolve(strict=True).relative_to(root)
            except (OSError, ValueError):
                fail("managed tree path escapes its root")


def managed_current_suite(repo, suite):
    validate_suite(suite)
    snapshots = managed_dir(repo, "snapshots")
    dists = managed_dir(repo, "dists")
    current = dists / suite
    if current.is_symlink():
        try:
            resolved = current.resolve(strict=True)
        except OSError:
            fail("current suite snapshot link is broken")
        try:
            resolved.relative_to(snapshots)
        except ValueError:
            fail("current suite link escapes managed snapshots")
        if resolved.name != suite or resolved.parent.name != "dists":
            fail("current suite link does not target this suite snapshot")
        validate_managed_tree(resolved)
    elif current.exists():
        fail("current suite is not a managed snapshot symlink")
    return current


def prepare(args):
    validate_args(args)
    repo = safe_repo(args.repo, create=True)
    validate_managed_parents(repo)
    staging_root = managed_dir(repo, ".staging", create=True)
    pool_root = managed_dir(repo, "pool/sha256", create=True)
    managed_dir(repo, "snapshots", create=True)
    managed_dir(repo, "dists", create=True)
    stage_id = str(uuid4())
    stage = staging_root / stage_id
    stage.mkdir()
    suite_root = stage / "dists" / args.suite
    index_dir = suite_root / "main" / "binary-arm64"
    updater_index_dir = suite_root / "main" / "binary-all"
    managed_dir(repo, f".staging/{stage_id}/dists/{args.suite}/main/binary-arm64", create=True)
    current = managed_current_suite(repo, args.suite)
    if current.is_symlink() and not current.exists():
        fail("current suite snapshot link is broken")
    old_catalog = read_catalog(current / "main" / "release-catalog.json") if current.exists() else {"generation": 0, "releases": []}
    catalog = {"generation": old_catalog["generation"] + 1, "releases": list(old_catalog["releases"])}
    package_lines = []
    copy_old_by_hash(current, suite_root)
    old_packages = current / "main" / "binary-arm64" / "Packages" if current.exists() else None
    if old_packages and old_packages.is_file():
        package_lines.extend(old_packages.read_text(encoding="utf-8").strip().split("\n\n"))
    if args.package:
        package = args.package.resolve(strict=True)
        package_hash, package_size = digest_file(package)
        deb_version = args.upstream_version + "-1"
        control = package_control(package, "hardware-agent", deb_version, args.architecture)
        filename = f"pool/sha256/{package_hash}.deb"
        target = pool_root / f"{package_hash}.deb"
        if target.exists():
            if target.is_symlink() or not target.is_file():
                fail("content-addressed package path is not a regular file")
            existing_hash, existing_size = digest_file(target)
            if (existing_hash, existing_size) != (package_hash, package_size):
                fail("content-addressed package path collision")
        else:
            temporary = target.with_name(target.name + ".tmp-" + stage_id)
            shutil.copyfile(package, temporary)
            temporary.chmod(0o444)
            os.replace(temporary, target)
        existing_release = next((item for item in catalog["releases"] if item.get("package_version") == deb_version and item.get("architecture") == args.architecture), None)
        release = {
            "id": args.release_id.lower(),
            "source_commit": args.source_commit,
            "upstream_version": args.upstream_version,
            "package_version": deb_version,
            "architecture": args.architecture,
            "suite": args.suite,
            "sha256": package_hash,
            "size_bytes": package_size,
            "required_protocol_version": args.required_protocol_version,
            "required_updater_version": args.required_updater_version,
            "published_at": datetime.now(timezone.utc).isoformat(),
            "release_notes": args.release_notes,
        }
        if existing_release:
            if existing_release != release and any(existing_release.get(key) != release.get(key) for key in ("sha256", "id", "source_commit", "upstream_version", "package_version", "architecture", "suite", "size_bytes", "required_protocol_version", "required_updater_version", "release_notes")):
                fail("release identity collision; published identities are immutable")
            fail("release identity already exists; create a new version and release UUID")
        if any(item.get("id") == release["id"] for item in catalog["releases"]):
            fail("release UUID is already assigned")
        catalog["releases"].append(release)
        package_lines.append(
            "\n".join([
                control,
                f"Filename: {filename}",
                f"Size: {package_size}",
                f"SHA256: {package_hash}",
            ])
        )
    updater_lines = []
    old_updater_packages = current / "main" / "binary-all" / "Packages" if current.exists() else None
    provenance_path = suite_root / "main" / "updater-provenance.json"
    old_provenance_path = current / "main" / "updater-provenance.json" if current.exists() else None
    provenance = read_updater_provenance(old_provenance_path) if old_provenance_path else []
    if old_updater_packages and old_updater_packages.is_file():
        updater_lines.extend(old_updater_packages.read_text(encoding="utf-8").strip().split("\n\n"))
    if args.updater_package:
        updater = args.updater_package.resolve(strict=True)
        updater_version = args.updater_version
        if not re.fullmatch(r"[A-Za-z0-9.+:~_-]{1,128}", updater_version):
            fail("updater version must be a valid Debian version")
        control = package_control(updater, "hardware-agent-updater", updater_version, "all")
        updater_hash, updater_size = digest_file(updater)
        existing_updater = [
            item for item in package_stanzas(old_updater_packages)
            if (item.get("Package"), item.get("Version"), item.get("Architecture"))
            == ("hardware-agent-updater", updater_version, "all")
        ]
        if len(existing_updater) > 1:
            fail("updater package index contains a duplicate identity")
        if existing_updater:
            existing = existing_updater[0]
            if (existing.get("SHA256"), existing.get("Size")) != (updater_hash, str(updater_size)):
                fail("updater package identity already exists with different immutable bytes")
        else:
            updater_lines.append("\n".join([
                control,
                f"Filename: pool/sha256/{updater_hash}.deb",
                f"Size: {updater_size}",
                f"SHA256: {updater_hash}",
            ]))
        filename = f"pool/sha256/{updater_hash}.deb"
        target = pool_root / f"{updater_hash}.deb"
        if target.exists():
            if target.is_symlink() or not target.is_file() or digest_file(target) != (updater_hash, updater_size):
                fail("content-addressed package path collision")
        else:
            temporary = target.with_name(target.name + ".tmp-" + stage_id)
            shutil.copyfile(updater, temporary)
            temporary.chmod(0o444)
            os.replace(temporary, target)
        existing_provenance = [
            item for item in provenance
            if (item["package_version"], item["architecture"])
            == (updater_version, "all")
        ]
        if len(existing_provenance) > 1:
            fail("updater provenance contains a duplicate identity")
        if existing_provenance:
            existing = existing_provenance[0]
            if (existing["sha256"], existing["size_bytes"]) != (updater_hash, updater_size):
                fail("updater provenance identity already exists with different immutable bytes")
        else:
            provenance.append({
                "package": "hardware-agent-updater",
                "package_version": updater_version,
                "architecture": "all",
                "source_commit": args.updater_source_commit,
                "sha256": updater_hash,
                "size_bytes": updater_size,
            })
        updater_index_dir.mkdir(parents=True, exist_ok=True)
    if not catalog["releases"]:
        fail("cannot prepare a repository without a release")
    package_text = "\n\n".join(line for line in package_lines if line) + "\n"
    (index_dir / "Packages").write_text(package_text, encoding="utf-8")
    write_by_hash(index_dir / "Packages", index_dir)
    if updater_lines:
        updater_index_dir.mkdir(parents=True, exist_ok=True)
        (updater_index_dir / "Packages").write_text("\n\n".join(updater_lines) + "\n", encoding="utf-8")
        write_by_hash(updater_index_dir / "Packages", updater_index_dir)
    if provenance:
        atomic_json(provenance_path, provenance)
        write_by_hash(provenance_path, suite_root / "main")
    (suite_root / "main").mkdir(exist_ok=True)
    catalog_path = suite_root / "main" / "release-catalog.json"
    catalog_bytes = json.dumps(catalog, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if len(catalog_bytes) > 1024 * 1024:
        fail("release catalog exceeds the backend's 1 MiB import limit")
    atomic_json(catalog_path, catalog)
    write_by_hash(catalog_path, suite_root / "main")
    now = datetime.now(timezone.utc).replace(microsecond=0)
    valid_until = now + timedelta(days=args.valid_days)
    base_digest = hashlib.sha256(
        (current / "main" / "release-catalog.json").read_bytes()
    ).hexdigest() if current.exists() else ""
    release_text = "\n".join([
        f"Origin: {args.origin}",
        f"Label: {args.origin}",
        f"Suite: {args.suite}",
        f"Codename: {args.suite}",
        "Architectures: arm64 all",
        "Components: main",
        "Acquire-By-Hash: yes",
        f"Date: {now.strftime('%a, %d %b %Y %H:%M:%S UTC')}",
        f"Valid-Until: {valid_until.strftime('%a, %d %b %Y %H:%M:%S UTC')}",
        f"X-Dmitri-Base-Generation: {old_catalog['generation']}",
        f"X-Dmitri-Base-Catalog-SHA256: {base_digest or 'none'}",
        "SHA256:",
        *sha256_entries(suite_root),
        "",
    ])
    (suite_root / "Release").write_text(release_text, encoding="utf-8")
    print(stage_id)


def sign(args):
    repo = managed_repo(args)
    stage = managed_candidate(repo, args.candidate)
    release = stage / "dists" / args.suite / "Release"
    if not release.is_file():
        fail("candidate Release metadata is missing")
    home = Path(args.gnupg_home).resolve(strict=True)
    passphrase_args = []
    if args.passphrase_file:
        passphrase_file = Path(args.passphrase_file)
        try:
            info = passphrase_file.lstat()
        except OSError as exc:
            fail(f"signing passphrase file is unavailable: {exc}")
        if (
            not stat.S_ISREG(info.st_mode)
            or stat.S_ISLNK(info.st_mode)
            or info.st_mode & 0o077
        ):
            fail("signing passphrase file must be a private regular file")
        passphrase_args = [
            "--pinentry-mode",
            "loopback",
            "--passphrase-file",
            str(passphrase_file.resolve(strict=True)),
        ]
    temp_signed = stage / "InRelease.tmp"
    temp_detached = stage / "Release.gpg.tmp"
    run(["gpg", "--homedir", str(home), "--batch", "--yes", *passphrase_args, "--local-user", args.key_id, "--clearsign", "--output", str(temp_signed), str(release)])
    run(["gpg", "--homedir", str(home), "--batch", "--yes", *passphrase_args, "--local-user", args.key_id, "--detach-sign", "--output", str(temp_detached), str(release)])
    os.replace(temp_signed, release.parent / "InRelease")
    os.replace(temp_detached, release.parent / "Release.gpg")


def verify_signed_suite(repo, suite_root, suite, keyring):
    release = suite_root / "Release"
    if not all(path.is_file() for path in (release, suite_root / "InRelease", suite_root / "Release.gpg")):
        fail("candidate metadata has not been signed")
    verified_release = suite_root / "Release.verified"
    run(["gpgv", "--output", str(verified_release), "--keyring", str(keyring.resolve(strict=True)), str(suite_root / "InRelease")])
    if verified_release.read_bytes() != release.read_bytes():
        fail("InRelease does not cover the candidate Release file")
    verified_release.unlink()
    run(["gpgv", "--keyring", str(keyring.resolve(strict=True)), str(suite_root / "Release.gpg"), str(release)])
    entries = {}
    lines = release.read_text(encoding="utf-8").splitlines()
    in_hashes = False
    for line in lines:
        if line == "SHA256:":
            in_hashes = True
        elif in_hashes and line.startswith(" "):
            digest, size, name = line.split()
            entries[name] = (digest, int(size))
        elif in_hashes:
            in_hashes = False
    for name, expected in entries.items():
        if name.startswith("/") or ".." in Path(name).parts:
            fail("Release contains an unsafe metadata path")
        path = suite_root / name
        if not path.is_file() or digest_file(path) != (expected[0], expected[1]):
            fail(f"metadata hash/size mismatch: {name}")
    catalog_path = suite_root / "main" / "release-catalog.json"
    packages_path = suite_root / "main" / "binary-arm64" / "Packages"
    if "main/release-catalog.json" not in entries or "main/binary-arm64/Packages" not in entries:
        fail("Release does not cover the catalog and Packages index")
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    packages = packages_path.read_text(encoding="utf-8")
    package_indexes = [packages_path]
    updater_packages_path = suite_root / "main" / "binary-all" / "Packages"
    if updater_packages_path.exists():
        package_indexes.append(updater_packages_path)
    if any(path.relative_to(suite_root).as_posix() not in entries for path in package_indexes):
        fail("Release does not authenticate every package index")
    identities = set()
    for package_index in package_indexes:
        for block in package_index.read_text(encoding="utf-8").split("\n\n"):
            fields = dict(line.split(": ", 1) for line in block.splitlines() if ": " in line)
            if not fields:
                continue
            identity = (fields.get("Package"), fields.get("Version"), fields.get("Architecture"))
            if identity in identities:
                fail("Packages contains a duplicate package/version/architecture identity")
            identities.add(identity)
            filename = fields.get("Filename", "")
            if not re.fullmatch(r"pool/sha256/[0-9a-f]{64}\.deb", filename):
                fail("Packages contains an unsafe package path")
            package_path = repo / filename
            digest = fields.get("SHA256", "")
            try:
                size = int(fields.get("Size", ""))
            except ValueError:
                fail("Packages contains an invalid package size")
            if package_path.is_symlink() or not package_path.is_file() or digest_file(package_path) != (digest, size):
                fail("Packages references a missing or changed package")
            package_control(package_path, *identity)
    provenance_path = suite_root / "main" / "updater-provenance.json"
    if provenance_path.exists():
        if "main/updater-provenance.json" not in entries:
            fail("Release does not authenticate updater provenance")
        provenance = read_updater_provenance(provenance_path)
        for item in provenance:
            identity = (item.get("package"), item.get("package_version"), item.get("architecture"))
            package_index = suite_root / "main" / f"binary-{identity[2]}" / "Packages"
            matching = [
                block for block in package_index.read_text(encoding="utf-8").split("\n\n")
                if f"Package: {identity[0]}\n" in block
                and f"Version: {identity[1]}\n" in block
                and f"Architecture: {identity[2]}\n" in block
            ] if package_index.is_file() else []
            if len(matching) != 1:
                fail("updater provenance does not map to one package index entry")
            fields = dict(line.split(": ", 1) for line in matching[0].splitlines() if ": " in line)
            if fields.get("SHA256") != item.get("sha256") or int(fields.get("Size", "0")) != item.get("size_bytes"):
                fail("updater provenance does not match its immutable package bytes")
    for item in catalog["releases"]:
        if item.get("suite") != suite or item.get("architecture") != "arm64":
            fail("catalog contains a release outside this suite/platform")
        matches = [block for block in packages.split("\n\n") if f"Package: hardware-agent\n" in block and f"Version: {item['package_version']}\n" in block and f"Architecture: {item['architecture']}\n" in block]
        if len(matches) != 1:
            fail("catalog release does not map to one Packages entry")
        fields = dict(line.split(": ", 1) for line in matches[0].splitlines() if ": " in line)
        if fields.get("Filename") != f"pool/sha256/{item['sha256']}.deb":
            fail("Packages contains an unsafe package path")
        package_path = repo / fields["Filename"]
        if (fields.get("SHA256"), int(fields.get("Size", "0"))) != (item["sha256"], item["size_bytes"]):
            fail("catalog release does not match Packages metadata")
        if package_path.is_symlink() or not package_path.is_file() or digest_file(package_path) != (item["sha256"], item["size_bytes"]):
            fail("catalog references a missing or changed package")


def verify_candidate(repo, stage, suite, keyring):
    verify_signed_suite(repo, stage / "dists" / suite, suite, keyring)


def verify_current(args):
    repo = managed_repo(args)
    current = managed_current_suite(repo, args.suite)
    if not current.exists():
        fail("current signed APT snapshot is missing")
    verify_signed_suite(repo, current, args.suite, args.keyring)


def promote(args):
    repo = managed_repo(args)
    stage = managed_candidate(repo, args.candidate)
    keyring = args.keyring
    verify_candidate(repo, stage, args.suite, keyring)
    signed_release = (stage / "dists" / args.suite / "Release").read_text(encoding="utf-8")
    release_fields = dict(
        line.split(": ", 1) for line in signed_release.splitlines() if ": " in line
    )
    target = managed_current_suite(repo, args.suite)
    current_catalog_path = target / "main" / "release-catalog.json"
    current_catalog = read_catalog(current_catalog_path) if target.exists() else {"generation": 0, "releases": []}
    current_digest = hashlib.sha256(current_catalog_path.read_bytes()).hexdigest() if target.exists() else ""
    base_digest = release_fields.get("X-Dmitri-Base-Catalog-SHA256")
    if base_digest == "none":
        base_digest = ""
    try:
        base_generation = int(release_fields["X-Dmitri-Base-Generation"])
    except (KeyError, ValueError):
        fail("candidate base generation is missing or invalid")
    if base_generation != current_catalog["generation"] or base_digest != current_digest:
        fail("candidate is stale; prepare it again from the current catalog")
    digest = hashlib.sha256()
    for path in sorted(p for p in stage.rglob("*") if p.is_file()):
        digest.update(path.relative_to(stage).as_posix().encode() + b"\0")
        digest.update(bytes.fromhex(digest_file(path)[0]))
    snapshot_id = digest.hexdigest()
    snapshot_root = managed_dir(repo, "snapshots", create=True)
    snapshot = snapshot_root / snapshot_id
    if snapshot.exists():
        fail("snapshot identity already exists")
    os.replace(stage, snapshot)
    dists = managed_dir(repo, "dists", create=True)
    target = dists / args.suite
    temporary = dists / (args.suite + ".tmp-" + str(uuid4()))
    relative = os.path.relpath(snapshot / "dists" / args.suite, dists)
    os.symlink(relative, temporary, target_is_directory=True)
    try:
        if os.environ.get("DIMITRI_PUBLISH_FAILPOINT") == "before_metadata_promote":
            fail("injected failure before atomic metadata promotion")
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
    print(snapshot_id)


def main():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare_parser = subparsers.add_parser("prepare")
    prepare_parser.add_argument("--repo", type=Path, required=True)
    prepare_parser.add_argument("--package", type=Path)
    prepare_parser.add_argument("--updater-package", type=Path)
    prepare_parser.add_argument("--updater-version", default="")
    prepare_parser.add_argument("--updater-source-commit", default="")
    prepare_parser.add_argument("--release-id", default=str(uuid4()))
    prepare_parser.add_argument("--source-commit", default="")
    prepare_parser.add_argument("--upstream-version", default="")
    prepare_parser.add_argument("--architecture", default="arm64")
    prepare_parser.add_argument("--suite", default="stable")
    prepare_parser.add_argument("--required-protocol-version", type=int, default=1)
    prepare_parser.add_argument("--required-updater-version", type=int, default=1)
    prepare_parser.add_argument("--release-notes", default="")
    prepare_parser.add_argument("--origin", default="Dmitri")
    prepare_parser.add_argument("--valid-days", type=int, default=7)
    prepare_parser.set_defaults(func=prepare)
    sign_parser = subparsers.add_parser("sign")
    sign_parser.add_argument("--repo", type=Path, required=True)
    sign_parser.add_argument("--candidate", required=True)
    sign_parser.add_argument("--suite", default="stable")
    sign_parser.add_argument("--gnupg-home", required=True)
    sign_parser.add_argument("--key-id", required=True)
    sign_parser.add_argument("--passphrase-file")
    sign_parser.set_defaults(func=sign)
    promote_parser = subparsers.add_parser("promote")
    promote_parser.add_argument("--repo", type=Path, required=True)
    promote_parser.add_argument("--candidate", required=True)
    promote_parser.add_argument("--suite", default="stable")
    promote_parser.add_argument("--keyring", type=Path, required=True)
    promote_parser.set_defaults(func=promote)
    verify_parser = subparsers.add_parser("verify-current")
    verify_parser.add_argument("--repo", type=Path, required=True)
    verify_parser.add_argument("--suite", default="stable")
    verify_parser.add_argument("--keyring", type=Path, required=True)
    verify_parser.set_defaults(func=verify_current)
    args = parser.parse_args()
    validate_suite(args.suite)
    repo = safe_repo(args.repo, create=True)
    validate_managed_parents(repo)
    lock_path = safe_lock(repo)
    flags = os.O_RDWR | os.O_CREAT
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        lock_fd = os.open(lock_path, flags, 0o600)
    except OSError as exc:
        fail(f"cannot safely open publish lock: {exc}")
    if not stat.S_ISREG(os.fstat(lock_fd).st_mode):
        os.close(lock_fd)
        fail("publish lock must be a regular file")
    with os.fdopen(lock_fd, "a+b") as lock:
        if os.name == "posix":
            import fcntl

            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        args.func(args)


if __name__ == "__main__":
    main()
PY
