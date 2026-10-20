from __future__ import annotations

import hashlib
import json
import subprocess
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from api.core.config import Settings
from api.models.agent_update import AgentRelease, AgentReleaseCatalogState
from api.services.release_catalog import (
    CatalogError,
    _get,
    debian_version_compare,
    project_availability,
    refresh_release_catalog,
)
from sqlmodel import Session, select


class _Result:
    def __init__(self, rows):
        self.rows = rows

    def first(self):
        return self.rows[0] if self.rows else None

    def all(self):
        return list(self.rows)


class _Session:
    def __init__(self):
        self.rows = []
        self.state = None
        self.snapshot = ([], None)

    def get(self, model, key):
        return self.state if model is AgentReleaseCatalogState else None

    def exec(self, _statement):
        model = _statement.column_descriptions[0]["entity"]
        return _Result(
            [self.state]
            if model is AgentReleaseCatalogState and self.state
            else self.rows
        )

    def add(self, row):
        if isinstance(row, AgentReleaseCatalogState):
            self.state = row
        else:
            existing = next((item for item in self.rows if item.id == row.id), None)
            if existing is None:
                self.rows.append(row)

    def commit(self):
        self.snapshot = deepcopy((self.rows, self.state))

    def rollback(self):
        self.rows, self.state = deepcopy(self.snapshot)


def _run(args: list[str], **kwargs) -> bytes:
    result = subprocess.run(args, capture_output=True, check=True, timeout=30, **kwargs)
    return result.stdout


@pytest.fixture(scope="session")
def signing_material(tmp_path_factory):
    key_dir = tmp_path_factory.mktemp("release-signing-key")
    home = key_dir / "gnupg"
    home.mkdir(mode=0o700)
    _run(
        [
            "gpg",
            "--homedir",
            str(home),
            "--batch",
            "--passphrase",
            "",
            "--quick-generate-key",
            "Release Test <release@example.test>",
            "ed25519",
            "sign",
            "0",
        ]
    )
    fingerprint = next(
        line.split(":")[9]
        for line in _run(
            ["gpg", "--homedir", str(home), "--batch", "--with-colons", "--list-keys"]
        ).decode().splitlines()
        if line.startswith("fpr:")
    )
    keyring = key_dir / "trusted.gpg"
    keyring.write_bytes(_run(["gpg", "--homedir", str(home), "--export", fingerprint]))
    return home, keyring


@pytest.fixture
def repository(tmp_path, signing_material):
    home, keyring = signing_material
    files = {}
    package_bytes = b"test deb package"
    package_hash = hashlib.sha256(package_bytes).hexdigest()
    package_index = (
        "Package: hardware-agent\nVersion: 1.0.10-1\nArchitecture: arm64\n"
        f"Size: {len(package_bytes)}\nSHA256: {package_hash}\n"
        "Filename: pool/hardware-agent.deb\n\n"
    ).encode()
    catalog = {
        "generation": 1,
        "releases": [
            {
                "id": str(uuid4()),
                "source_commit": "a" * 40,
                "upstream_version": "1.0.10",
                "package_version": "1.0.10-1",
                "architecture": "arm64",
                "suite": "stable",
                "sha256": package_hash,
                "size_bytes": len(package_bytes),
                "required_protocol_version": 1,
                "required_updater_version": 1,
                "published_at": datetime.now(UTC).isoformat(),
                "release_notes": "Test release",
            }
        ],
    }
    catalog_bytes = json.dumps(catalog, separators=(",", ":")).encode()
    files["main/binary-arm64/Packages"] = package_index
    files["main/release-catalog.json"] = catalog_bytes

    def sign(
        *, valid_until=None, origin="Dmitri", suite="stable", change=b"", detached=False
    ):
        until = valid_until or datetime.now(UTC) + timedelta(days=1)
        entries = []
        for name, content in files.items():
            if change and name.endswith("Packages"):
                content = content + change
            entries.append(
                f" {hashlib.sha256(content).hexdigest()} {len(content)} {name}"
            )
        release_date = (datetime.now(UTC) - timedelta(minutes=1)).strftime(
            "%a, %d %b %Y %H:%M:%S UTC"
        )
        release = (
            f"Origin: {origin}\nSuite: {suite}\nDate: "
            f"{release_date}\n"
            f"Valid-Until: {until.strftime('%a, %d %b %Y %H:%M:%S UTC')}\nSHA256:\n"
            + "\n".join(entries) + "\n"
        ).encode()
        clear = tmp_path / "InRelease"
        clear.write_bytes(release)
        if detached:
            release_path = tmp_path / "Release"
            release_path.write_bytes(release)
            files["Release"] = release
            files["Release.gpg"] = _run(
                [
                    "gpg", "--homedir", str(home), "--batch", "--yes",
                    "--detach-sign", "--output", "-", str(release_path),
                ]
            )
            files.pop("InRelease", None)
        else:
            signed = _run(
                [
                    "gpg", "--homedir", str(home), "--batch", "--yes",
                    "--clearsign", "--output", "-", str(clear),
                ]
            )
            files["InRelease"] = signed

    sign()

    def client_for_current():
        def handler(request):
            name = request.url.path.split("/dists/stable/", 1)[-1]
            if name not in files:
                return httpx.Response(404)
            return httpx.Response(200, content=files[name])

        return httpx.Client(
            transport=httpx.MockTransport(handler), follow_redirects=False
        )

    settings = Settings.model_construct(
        agent_update_repository_url="https://repo.example.test",
        agent_update_keyring_path=str(keyring),
        agent_update_origin="Dmitri",
        agent_update_suite="stable",
        agent_update_catalog_max_bytes=1024 * 1024,
    )
    return files, catalog, settings, client_for_current, sign


def test_imports_signed_release_and_checks_packages_chain(repository):
    _, _, settings, client, _ = repository
    session = _Session()

    assert refresh_release_catalog(session, settings, client=client()) == 1
    assert session.state.generation == 1
    assert session.rows[0].approved_at is not None
    assert session.rows[0].package_version == "1.0.10-1"


def test_railpack_runtime_includes_catalog_tools_and_approved_keyring():
    backend_root = Path(__file__).resolve().parents[1]
    deployment = json.loads((backend_root / "railpack.json").read_text())
    packages = set(deployment["deploy"]["aptPackages"])
    assert {"ca-certificates", "dpkg", "gpgv"}.issubset(packages)

    keyring = backend_root / "agent-release/public-keyring.gpg"
    assert keyring.is_file()
    assert not (backend_root.parent / "agent-release/public-keyring.gpg").exists()
    assert hashlib.sha256(keyring.read_bytes()).hexdigest() == (
        "e133d6975f2e5df775ce407ba902cb6bd40f19f5972c3bc61c991392d96346aa"
    )
    key_listing = subprocess.run(
        ["gpg", "--batch", "--show-keys", "--with-colons", str(keyring)],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )
    fingerprints = {
        fields[9]
        for line in key_listing.stdout.splitlines()
        if (fields := line.split(":"))[0] == "fpr"
    }
    assert "92BD91D03608EA3AFDB108AAB7EEC4E4E954DA7A" in fingerprints
    assert "49B97982F566B0FEF9F2412FDC0B27B955B74936" in fingerprints
    assert subprocess.run(
        ["gpgv", "--version"], capture_output=True, timeout=5
    ).returncode == 0
    assert subprocess.run(
        ["dpkg", "--compare-versions", "1.0", "lt", "1.1"],
        capture_output=True,
        timeout=5,
    ).returncode == 0


def test_approved_keyring_rejects_signature_from_another_key(repository):
    _, _, settings, client, _ = repository
    settings.agent_update_keyring_path = str(
        Path(__file__).resolve().parents[1] / "agent-release/public-keyring.gpg"
    )

    with pytest.raises(CatalogError, match="InRelease signature verification failed"):
        refresh_release_catalog(_Session(), settings, client=client())


def test_refresh_lifecycle_with_real_sqlmodel_session(
    repository, administrative_session: Session
):
    files, catalog, settings, client, sign = repository
    first = catalog["releases"][0]
    second_bytes = b"second test package"
    second_hash = hashlib.sha256(second_bytes).hexdigest()
    second = deepcopy(first)
    second.update(
        id=str(uuid4()),
        source_commit="b" * 40,
        upstream_version="1.0.11",
        package_version="1.0.11-1",
        sha256=second_hash,
        size_bytes=len(second_bytes),
    )
    files["main/binary-arm64/Packages"] += (
        f"Package: hardware-agent\nVersion: 1.0.11-1\nArchitecture: arm64\n"
        f"Size: {len(second_bytes)}\nSHA256: {second_hash}\n"
        "Filename: pool/hardware-agent-1.0.11.deb\n\n"
    ).encode()
    catalog["releases"].append(second)
    files["main/release-catalog.json"] = json.dumps(catalog).encode()
    sign()

    assert (
        refresh_release_catalog(administrative_session, settings, client=client()) == 2
    )
    releases = administrative_session.exec(select(AgentRelease)).all()
    assert {release.package_version for release in releases} == {
        "1.0.10-1",
        "1.0.11-1",
    }

    # A same-generation refresh exercises lookups and immutable identity checks.
    assert (
        refresh_release_catalog(administrative_session, settings, client=client()) == 2
    )
    assert len(administrative_session.exec(select(AgentRelease)).all()) == 2

    # Removing a release from a newer signed catalog withdraws it, retaining history.
    catalog["generation"] = 2
    catalog["releases"] = [second]
    files["main/release-catalog.json"] = json.dumps(catalog).encode()
    sign()
    assert (
        refresh_release_catalog(administrative_session, settings, client=client()) == 1
    )
    releases = administrative_session.exec(select(AgentRelease)).all()
    first_row = next(
        release for release in releases if release.package_version == "1.0.10-1"
    )
    second_row = next(
        release for release in releases if release.package_version == "1.0.11-1"
    )
    assert first_row.withdrawn_at is not None
    assert second_row.withdrawn_at is None

    # A late invalid entry rolls back an earlier withdrawal mutation and generation.
    catalog["generation"] = 3
    withdrawn_second = deepcopy(second)
    withdrawn_second["withdrawn"] = True
    catalog["releases"] = [withdrawn_second, {"id": "invalid"}]
    files["main/release-catalog.json"] = json.dumps(catalog).encode()
    sign()
    with pytest.raises(CatalogError, match="invalid release entry"):
        refresh_release_catalog(administrative_session, settings, client=client())

    administrative_session.expire_all()
    state = administrative_session.exec(select(AgentReleaseCatalogState)).one()
    releases = administrative_session.exec(select(AgentRelease)).all()
    second_row = next(
        release for release in releases if release.package_version == "1.0.11-1"
    )
    assert state.generation == 2
    assert second_row.withdrawn_at is None


def test_imports_detached_release_signature(repository):
    _, _, settings, client, sign = repository
    sign(detached=True)
    session = _Session()

    assert refresh_release_catalog(session, settings, client=client()) == 1
    assert session.state.generation == 1
    assert session.rows[0].approved_at is not None


def test_rejects_invalid_detached_release_signature(repository):
    files, _, settings, client, sign = repository
    sign(detached=True)
    signature = bytearray(files["Release.gpg"])
    signature[0] = ord("A") if signature[0] != ord("A") else ord("B")
    files["Release.gpg"] = bytes(signature)

    with pytest.raises(CatalogError, match="Release signature verification failed"):
        refresh_release_catalog(_Session(), settings, client=client())


def test_rejects_bad_signature_hash_origin_and_expiry(repository):
    files, catalog, settings, client, sign = repository
    session = _Session()
    signed = files["InRelease"]
    marker = b"-----BEGIN PGP SIGNATURE-----\n"
    start = signed.index(marker) + len(marker)
    tampered = bytearray(signed)
    tampered[start] = ord("A") if tampered[start] != ord("A") else ord("B")
    files["InRelease"] = bytes(tampered)
    with pytest.raises(CatalogError, match="signature"):
        refresh_release_catalog(session, settings, client=client())
    files["InRelease"] = signed
    sign(origin="Other")
    with pytest.raises(CatalogError, match="origin or suite"):
        refresh_release_catalog(session, settings, client=client())
    sign(suite="testing")
    with pytest.raises(CatalogError, match="origin or suite"):
        refresh_release_catalog(session, settings, client=client())
    sign(valid_until=datetime.now(UTC) - timedelta(seconds=1))
    with pytest.raises(CatalogError, match="currently valid"):
        refresh_release_catalog(session, settings, client=client())
    catalog["releases"][0]["sha256"] = "f" * 64
    files["main/release-catalog.json"] = json.dumps(catalog).encode()
    sign()
    with pytest.raises(CatalogError, match="does not match signed Packages"):
        refresh_release_catalog(session, settings, client=client())


def test_rejects_packages_index_size_mismatch(repository):
    files, catalog, settings, client, sign = repository
    catalog["releases"][0]["size_bytes"] += 1
    files["main/release-catalog.json"] = json.dumps(catalog).encode()
    sign()

    with pytest.raises(CatalogError, match="does not match signed Packages"):
        refresh_release_catalog(_Session(), settings, client=client())


def test_rejects_packages_index_hash_or_size_tampering(repository):
    files, _, settings, client, sign = repository
    sign(change=b"tampered")

    with pytest.raises(CatalogError, match="APT index hash or size mismatch"):
        refresh_release_catalog(_Session(), settings, client=client())


def test_metadata_size_limit_stops_streaming_before_full_download():
    consumed = []

    class Chunks(httpx.SyncByteStream):
        def __iter__(self):
            for chunk in (b"1234", b"56", b"ignored"):
                consumed.append(chunk)
                yield chunk

    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(200, stream=Chunks())
        )
    )
    try:
        with pytest.raises(CatalogError, match="exceeds size limit"):
            _get(client, "https://repo.example.test", "metadata", limit=5)
    finally:
        client.close()

    assert consumed == [b"1234", b"56"]


def test_metadata_declared_size_limit_has_specific_error():
    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(
                200,
                headers={"content-length": "6"},
                content=b"123456",
            )
        )
    )
    try:
        with pytest.raises(CatalogError, match="exceeds size limit"):
            _get(client, "https://repo.example.test", "metadata", limit=5)
    finally:
        client.close()


def test_rejects_replay_and_same_generation_conflict(repository):
    files, catalog, settings, client, sign = repository
    session = _Session()
    refresh_release_catalog(session, settings, client=client())
    catalog["generation"] = 0
    files["main/release-catalog.json"] = json.dumps(catalog).encode()
    sign()
    with pytest.raises(CatalogError, match="replay or generation conflict"):
        refresh_release_catalog(session, settings, client=client())
    catalog["generation"] = 1
    catalog["extra"] = True
    files["main/release-catalog.json"] = json.dumps(catalog).encode()
    sign()
    with pytest.raises(CatalogError, match="replay or generation conflict"):
        refresh_release_catalog(session, settings, client=client())


def test_refresh_failure_preserves_previous_evidence_and_withdrawal_keeps_row(
    repository,
):
    files, catalog, settings, client, sign = repository
    session = _Session()
    refresh_release_catalog(session, settings, client=client())
    original = session.rows[0]
    files["InRelease"] = b"invalid signature"
    with pytest.raises(CatalogError):
        refresh_release_catalog(session, settings, client=client())
    assert len(session.rows) == 1
    assert session.rows[0].id == original.id
    assert session.state.generation == 1
    catalog["generation"] = 2
    catalog["releases"] = []
    files["main/release-catalog.json"] = json.dumps(catalog).encode()
    sign()
    refresh_release_catalog(session, settings, client=client())
    assert len(session.rows) == 1
    assert session.rows[0].id == original.id
    assert session.rows[0].withdrawn_at is not None


def test_mid_refresh_failure_rolls_back_changed_release_evidence(repository):
    files, catalog, settings, client, sign = repository
    session = _Session()
    refresh_release_catalog(session, settings, client=client())
    catalog["generation"] = 2
    catalog["releases"][0]["withdrawn"] = True
    catalog["releases"].append({"id": "invalid"})
    files["main/release-catalog.json"] = json.dumps(catalog).encode()
    sign()

    with pytest.raises(CatalogError, match="invalid release entry"):
        refresh_release_catalog(session, settings, client=client())

    assert session.state.generation == 1
    assert session.rows[0].withdrawn_at is None


def test_rejects_immutable_release_identity_collision(repository):
    files, catalog, settings, client, sign = repository
    session = _Session()
    refresh_release_catalog(session, settings, client=client())
    entry = catalog["releases"][0]
    entry["sha256"] = "f" * 64
    catalog["generation"] = 2
    files["main/release-catalog.json"] = json.dumps(catalog).encode()
    package_fields = files["main/binary-arm64/Packages"].decode().splitlines()
    package_fields = [
        "SHA256: " + "f" * 64 if line.startswith("SHA256:") else line
        for line in package_fields
    ]
    files["main/binary-arm64/Packages"] = "\n".join(package_fields).encode()
    sign()

    with pytest.raises(CatalogError, match="identity collision"):
        refresh_release_catalog(session, settings, client=client())


def test_debian_order_and_compatibility_projection():
    release = AgentRelease(
        source_commit="a" * 40,
        upstream_version="1.0.10",
        package_version="1.0.10-1",
        architecture="arm64",
        suite="stable",
        sha256="b" * 64,
        size_bytes=10,
        required_protocol_version=1,
        required_updater_version=1,
        published_at=datetime.now(UTC),
        approved_at=datetime.now(UTC),
    )
    assert debian_version_compare("1.0.10-1", "gt", "1.0.9-1")
    for invalid_version in ("garbage", "", "1:garbage"):
        with pytest.raises(ValueError, match="invalid Debian version"):
            debian_version_compare(invalid_version, "ge", "1.0.9-1")
    assert project_availability(
        [release],
        installed_version="1.0.9-1",
        architecture="arm64",
        protocol_version=1,
        updater_version=1,
        catalog_valid_until=datetime.now(UTC) + timedelta(days=1),
    ) == ("available", release)
    assert project_availability(
        [release],
        installed_version=None,
        architecture="arm64",
        protocol_version=1,
        updater_version=1,
        catalog_valid_until=datetime.now(UTC) + timedelta(days=1),
    ) == ("unknown", None)
    for invalid_version in ("garbage", "", "1:garbage"):
        assert project_availability(
            [release],
            installed_version=invalid_version,
            architecture="arm64",
            protocol_version=1,
            updater_version=1,
            catalog_valid_until=datetime.now(UTC) + timedelta(days=1),
        ) == ("unknown", None)
    for architecture, protocol_version, updater_version in (
        ("amd64", 1, 1),
        ("arm64", 0, 1),
        ("arm64", 1, 0),
        ("arm64", None, 1),
        ("arm64", 1, None),
    ):
        assert project_availability(
            [release],
            installed_version="1.0.9-1",
            architecture=architecture,
            protocol_version=protocol_version,
            updater_version=updater_version,
            catalog_valid_until=datetime.now(UTC) + timedelta(days=1),
        ) == ("unavailable", None)
    assert project_availability(
        [release],
        installed_version="1.0.10-1",
        architecture="arm64",
        protocol_version=1,
        updater_version=1,
        catalog_valid_until=datetime.now(UTC) - timedelta(seconds=1),
    ) == ("unavailable", None)


def test_worker_refreshes_only_the_configured_repository(monkeypatch):
    from api.services import worker

    session = _Session()
    settings = Settings.model_construct(
        agent_update_repository_url="https://repo.example.test",
        agent_update_refresh_interval_seconds=300,
        enrichment_batch_size=5,
    )
    calls = []
    monkeypatch.setattr(worker, "get_settings", lambda: settings)
    monkeypatch.setattr(worker, "get_session", lambda: iter([session]))
    monkeypatch.setattr(
        worker, "refresh_release_catalog",
        lambda current, configured: calls.append((current, configured)) or 0,
    )
    monkeypatch.setattr(worker, "sweep_stale_commands", lambda *_args, **_kwargs: 0)
    monkeypatch.setattr(
        worker, "process_pending_enrichment_jobs", lambda *_args, **_kwargs: 0
    )
    # GitHub-hosted runners can have a monotonic clock value below the refresh
    # interval shortly after boot. Use a definitely stale timestamp so this
    # test does not depend on runner uptime.
    stale_refresh_time = -settings.agent_update_refresh_interval_seconds
    monkeypatch.setattr(worker, "_last_catalog_refresh", stale_refresh_time)

    worker.run_worker_once()
    worker.run_worker_once()

    assert calls == [(session, settings)]

    settings.agent_update_repository_url = ""
    monkeypatch.setattr(worker, "_last_catalog_refresh", stale_refresh_time)
    worker.run_worker_once()
    assert calls == [(session, settings)]
