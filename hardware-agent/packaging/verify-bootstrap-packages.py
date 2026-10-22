#!/usr/bin/python3
import argparse
import hashlib
import importlib.util
import subprocess
import sys
from pathlib import Path


def run(args):
    try:
        return subprocess.run(
            args,
            check=True,
            capture_output=True,
            text=True,
            timeout=60,
            env={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C.UTF-8"},
        ).stdout
    except subprocess.CalledProcessError as exc:
        raise ValueError(
            exc.stderr.strip() or "package metadata command failed"
        ) from exc


def package_fields(package):
    fields = run(["/usr/bin/dpkg-deb", "--field", str(package)]).splitlines()
    result = {}
    for line in fields:
        key, separator, value = line.partition(": ")
        if separator:
            result[key] = value
    return result


def verify_packages(packages, repository, updater):
    source_uri, _keyring = updater._verify_dedicated_apt_source()
    if source_uri.rstrip("/") != repository.rstrip("/"):
        raise ValueError("configured repository does not match the approved repository")
    updater._verify_apt_metadata_dates(source_uri)
    verified = []
    for package in packages:
        fields = package_fields(package)
        identity = (
            fields.get("Package"),
            fields.get("Version"),
            fields.get("Architecture"),
        )
        digest = hashlib.sha256()
        with package.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        package_digest = digest.hexdigest()
        record = updater._trusted_apt_package_record(
            identity[1], source_uri, identity[0], identity[2]
        )
        record_fields = (
            {
                key.strip(): value.strip()
                for line in record.splitlines()
                for key, separator, value in [line.partition(":")]
                if separator and not line[:1].isspace()
            }
            if record
            else {}
        )
        matches = (
            [record]
            if record
            and record_fields.get("Size") == str(package.stat().st_size)
            and updater._apt_record_matches(
                record, identity[1], package_digest, identity[0], identity[2]
            )
            else []
        )
        if len(matches) != 1:
            raise ValueError(
                "package is not authenticated by the approved signed repository: "
                f"{package.name}"
            )
        expected = {
            ("hardware-agent", "arm64"),
            ("hardware-agent-updater", "all"),
        }
        if (identity[0], identity[2]) not in expected:
            raise ValueError(f"unsupported bootstrap package identity: {identity}")
        verified.append((*identity, package_digest))
    return verified


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", required=True)
    parser.add_argument("packages", nargs=2, type=Path)
    args = parser.parse_args()
    updater_path = Path(__file__).with_name("updater.py")
    spec = importlib.util.spec_from_file_location(
        "dmitri_bootstrap_updater", updater_path
    )
    if spec is None or spec.loader is None:
        raise ValueError("updater verification module is unavailable")
    updater = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(updater)
    for package, identity in zip(
        args.packages, verify_packages(args.packages, args.repository, updater)
    ):
        print(f"verified {identity[0]} {identity[1]} {identity[2]} {identity[3]}")


if __name__ == "__main__":
    try:
        main()
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        print(f"verify-bootstrap-packages: {exc}", file=sys.stderr)
        raise SystemExit(1)
