#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import shutil
import subprocess
from pathlib import Path

MAX_PAGES_BYTES = 1_000_000_000


def fail(message: str) -> None:
    raise SystemExit(f"prepare-pages: {message}")


def safe_tree(root: Path) -> None:
    for path in root.rglob("*"):
        if path.is_symlink():
            fail("APT suite contains an unexpected symlink")
        if not path.is_dir() and not path.is_file():
            fail("APT suite contains a non-regular file")


def digest_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run(args: list[str]) -> None:
    try:
        subprocess.run(args, check=True, capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError) as exc:
        fail(f"signature verification failed ({exc})")


def prepare(repo: Path, output: Path, keyring: Path) -> int:
    repo = repo.resolve(strict=True)
    keyring = keyring.resolve(strict=True)
    output = output.resolve()
    if output == repo or repo in output.parents:
        fail("output must be outside the authoritative APT state")
    if output.exists() and any(output.iterdir()):
        fail("output directory must be empty")

    pool = repo / "pool"
    pool_sha = pool / "sha256"
    dists = repo / "dists"
    suite_link = dists / "stable"
    snapshots = repo / "snapshots"
    if any(
        path.is_symlink() or not path.is_dir()
        for path in (pool, pool_sha, dists, snapshots)
    ):
        fail("authoritative APT state has an unsafe directory")
    if not suite_link.is_symlink():
        fail("managed stable suite link is missing")
    suite = suite_link.resolve(strict=True)
    try:
        suite.relative_to(snapshots.resolve(strict=True))
    except ValueError:
        fail("stable suite link escapes retained snapshots")
    if suite.name != "stable" or suite.parent.name != "dists":
        fail("stable suite link has an unexpected target")
    safe_tree(suite)
    for name in ("Release", "Release.gpg", "InRelease"):
        if not (suite / name).is_file():
            fail(f"signed suite is missing {name}")
    run(
        [
            "gpgv",
            "--keyring",
            str(keyring),
            str(suite / "Release.gpg"),
            str(suite / "Release"),
        ]
    )
    verified_release = output.with_name(output.name + ".verified-release")
    run(
        [
            "gpgv",
            "--keyring",
            str(keyring),
            "--output",
            str(verified_release),
            str(suite / "InRelease"),
        ]
    )
    try:
        if verified_release.read_bytes() != (suite / "Release").read_bytes():
            fail("InRelease does not cover the published Release bytes")
    finally:
        verified_release.unlink(missing_ok=True)

    output.mkdir(parents=True, exist_ok=True)
    (output / "dists").mkdir()
    shutil.copytree(suite, output / "dists" / "stable", symlinks=False)
    (output / "pool" / "sha256").mkdir(parents=True)
    total = 0
    for package in pool_sha.iterdir():
        if (
            package.is_symlink()
            or not package.is_file()
            or package.name != f"{package.stem}.deb"
        ):
            fail("package pool contains an unsafe path")
        if len(package.stem) != 64 or any(
            char not in "0123456789abcdef" for char in package.stem
        ):
            fail("package pool has a non-content-addressed package")
        if digest_file(package) != package.stem:
            fail("package pool content does not match its immutable filename")
        total += package.stat().st_size
        shutil.copyfile(package, output / "pool" / "sha256" / package.name)
    total += sum(
        path.stat().st_size for path in (output / "dists").rglob("*") if path.is_file()
    )
    if total > MAX_PAGES_BYTES:
        fail("flattened APT site exceeds the GitHub Pages 1 GB limit")
    if any(path.is_symlink() for path in output.rglob("*")):
        fail("flattened Pages artifact contains a symlink")
    return total


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--keyring", type=Path, required=True)
    args = parser.parse_args()
    size = prepare(args.repo, args.output, args.keyring)
    print(size)


if __name__ == "__main__":
    main()
