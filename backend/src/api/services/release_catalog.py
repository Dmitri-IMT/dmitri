from __future__ import annotations

import hashlib
import json
import logging
import re
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx
from sqlmodel import Session, select

from api.core.config import Settings, get_settings
from api.models.agent_update import AgentRelease, AgentReleaseCatalogState

logger = logging.getLogger(__name__)
_MAX_METADATA = 16 * 1024 * 1024
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_UPSTREAM_VERSION = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
_COMMIT = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")


class CatalogError(ValueError):
    pass


def debian_version_compare(left: str, operator: str, right: str) -> bool:
    if operator not in {"lt", "le", "eq", "ge", "gt"}:
        raise ValueError("unsupported Debian version operator")
    for version in (left, right):
        validation = subprocess.run(
            ["dpkg", "--validate-version", version],
            check=False,
            capture_output=True,
            timeout=5,
            shell=False,
        )
        if validation.returncode != 0:
            raise ValueError("invalid Debian version")
    result = subprocess.run(
        ["dpkg", "--compare-versions", left, operator, right],
        check=False,
        capture_output=True,
        timeout=5,
        shell=False,
    )
    if result.returncode > 1:
        raise ValueError("invalid Debian version")
    return result.returncode == 0


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise CatalogError("duplicate JSON object key")
        result[key] = value
    return result


def _get(client: httpx.Client, base: str, path: str, limit: int = _MAX_METADATA) -> bytes:
    target = urljoin(base.rstrip("/") + "/", path)
    if urlparse(target).scheme != "https" or urlparse(target).netloc != urlparse(base).netloc:
        raise CatalogError("repository metadata URL is not same-origin HTTPS")
    chunks = bytearray()
    with client.stream("GET", target, follow_redirects=False) as response:
        if 300 <= response.status_code < 400:
            raise CatalogError("repository metadata redirects are not allowed")
        response.raise_for_status()
        content_length = response.headers.get("content-length")
        if content_length is not None:
            try:
                declared_length = int(content_length)
            except ValueError as exc:
                raise CatalogError("invalid repository metadata content length") from exc
            if declared_length > limit:
                raise CatalogError("repository metadata exceeds size limit")
        for chunk in response.iter_bytes():
            if len(chunks) + len(chunk) > limit:
                raise CatalogError("repository metadata exceeds size limit")
            chunks.extend(chunk)
    return bytes(chunks)


def _verify_metadata(settings: Settings, client: httpx.Client) -> tuple[bytes, str]:
    base = settings.agent_update_repository_url
    keyring = Path(settings.agent_update_keyring_path)
    if not base or urlparse(base).scheme != "https" or not keyring.is_file():
        raise CatalogError("repository URL or dedicated keyring is not configured")
    try:
        signed = _get(client, base, "dists/" + settings.agent_update_suite + "/InRelease")
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code != 404:
            raise
        release = _get(client, base, "dists/" + settings.agent_update_suite + "/Release")
        signature = _get(client, base, "dists/" + settings.agent_update_suite + "/Release.gpg")
        with tempfile.TemporaryDirectory() as directory:
            release_path = Path(directory) / "Release"
            signature_path = Path(directory) / "Release.gpg"
            release_path.write_bytes(release)
            signature_path.write_bytes(signature)
            result = subprocess.run(
                ["gpgv", "--keyring", str(keyring), str(signature_path), str(release_path)],
                capture_output=True,
                timeout=15,
                shell=False,
            )
        if result.returncode:
            raise CatalogError("Release signature verification failed")
        return release, hashlib.sha256(release).hexdigest()
    with tempfile.TemporaryDirectory() as directory:
        signed_path = Path(directory) / "InRelease"
        release_path = Path(directory) / "Release"
        signed_path.write_bytes(signed)
        result = subprocess.run(
            ["gpgv", "--keyring", str(keyring), "--output", str(release_path), str(signed_path)],
            capture_output=True,
            timeout=15,
            shell=False,
        )
        if result.returncode:
            raise CatalogError("InRelease signature verification failed")
        release = release_path.read_bytes()
    return release, hashlib.sha256(signed).hexdigest()


def _release_fields(raw: bytes, settings: Settings) -> tuple[datetime, datetime, dict[str, tuple[str, int]]]:
    fields: dict[str, str] = {}
    current = None
    for line in raw.decode("utf-8").splitlines():
        if line.startswith((" ", "\t")) and current:
            fields[current] += "\n" + line.strip()
        elif ":" in line:
            current, value = line.split(":", 1)
            fields[current] = value.strip()
    if fields.get("Origin") != settings.agent_update_origin or fields.get("Suite") != settings.agent_update_suite:
        raise CatalogError("repository origin or suite mismatch")
    now = datetime.now(UTC)
    date = datetime.strptime(fields["Date"], "%a, %d %b %Y %H:%M:%S %Z").replace(tzinfo=UTC)
    valid = datetime.strptime(fields["Valid-Until"], "%a, %d %b %Y %H:%M:%S %Z").replace(tzinfo=UTC)
    if date > now or valid <= now:
        raise CatalogError("repository metadata is not currently valid")
    indexes: dict[str, tuple[str, int]] = {}
    for row in fields.get("SHA256", "").splitlines():
        parts = row.split()
        if len(parts) == 3 and _SHA256.fullmatch(parts[0]):
            indexes[parts[2]] = (parts[0], int(parts[1]))
    return date, valid, indexes


def _verify_index(client: httpx.Client, base: str, suite: str, name: str, expected: tuple[str, int]) -> bytes:
    digest, size = expected
    if size > _MAX_METADATA:
        raise CatalogError("APT index exceeds size limit")
    content = _get(client, base, f"dists/{suite}/{name}", size)
    if len(content) != size or hashlib.sha256(content).hexdigest() != digest:
        raise CatalogError("APT index hash or size mismatch")
    return content


def refresh_release_catalog(session: Session, settings: Settings | None = None, *, client: httpx.Client | None = None) -> int:
    settings = settings or get_settings()
    own_client = client is None
    client = client or httpx.Client(timeout=15, follow_redirects=False, trust_env=False)
    try:
        release, _ = _verify_metadata(settings, client)
        published, valid_until, indexes = _release_fields(release, settings)
        suite = settings.agent_update_suite
        catalog_name = next((name for name in indexes if name.endswith("release-catalog.json")), None)
        if not catalog_name:
            raise CatalogError("signed Release does not index a release catalog")
        catalog_bytes = _verify_index(client, settings.agent_update_repository_url, suite, catalog_name, indexes[catalog_name])
        if len(catalog_bytes) > settings.agent_update_catalog_max_bytes:
            raise CatalogError("release catalog exceeds size limit")
        catalog = json.loads(catalog_bytes, object_pairs_hook=_unique_object)
        generation = catalog["generation"]
        releases = catalog["releases"]
        if type(generation) is not int or not isinstance(releases, list):
            raise CatalogError("invalid release catalog structure")
        digest = hashlib.sha256(catalog_bytes).hexdigest()
        state = session.exec(
            select(AgentReleaseCatalogState)
            .where(AgentReleaseCatalogState.singleton_id == 1)
            .with_for_update()
        ).first()
        if state and state.generation:
            if generation < state.generation or (generation == state.generation and digest != state.digest):
                raise CatalogError("catalog replay or generation conflict")
        if generation < 1:
            raise CatalogError("invalid release catalog generation")
        packages: dict[tuple[str, str], dict[str, str]] = {}
        for index_name in indexes:
            if index_name.endswith("Packages"):
                content = _verify_index(client, settings.agent_update_repository_url, suite, index_name, indexes[index_name])
                for paragraph in content.decode("utf-8").split("\n\n"):
                    fields = dict(line.split(": ", 1) for line in paragraph.splitlines() if ": " in line and not line.startswith(" "))
                    if fields.get("Package") == "hardware-agent":
                        packages[(fields.get("Version", ""), fields.get("Architecture", ""))] = fields
        seen: set[tuple[str, str, str]] = set()
        for item in releases:
            required = {"id", "source_commit", "upstream_version", "package_version", "architecture", "suite", "sha256", "size_bytes", "required_protocol_version", "required_updater_version", "published_at"}
            if not isinstance(item, dict) or not required.issubset(item):
                raise CatalogError("invalid release entry")
            if (
                item["suite"] != suite
                or not isinstance(item["upstream_version"], str)
                or not _UPSTREAM_VERSION.fullmatch(item["upstream_version"])
                or item["package_version"] != item["upstream_version"] + "-1"
                or not isinstance(item["source_commit"], str)
                or not _COMMIT.fullmatch(item["source_commit"])
                or not isinstance(item["sha256"], str)
                or item["sha256"] != item["sha256"].lower()
                or not _SHA256.fullmatch(item["sha256"])
                or not isinstance(item["size_bytes"], int)
                or item["size_bytes"] <= 0
                or not isinstance(item.get("release_notes", ""), str)
            ):
                raise CatalogError("release suite or digest is invalid")
            key = ("hardware-agent", item["package_version"], item["architecture"])
            if key in seen:
                raise CatalogError("duplicate release identity")
            seen.add(key)
            package = packages.get((item["package_version"], item["architecture"]))
            if not package or int(package.get("Size", "0")) != item["size_bytes"] or package.get("SHA256") != item["sha256"]:
                raise CatalogError("release does not match signed Packages index")
            existing = session.exec(select(AgentRelease).where(AgentRelease.package_version == item["package_version"], AgentRelease.architecture == item["architecture"])).first()
            if existing:
                published_at = datetime.fromisoformat(item["published_at"].replace("Z", "+00:00"))
                immutable = (
                    existing.sha256 == item["sha256"]
                    and str(existing.id) == item["id"]
                    and existing.source_commit == item["source_commit"]
                    and existing.upstream_version == item["upstream_version"]
                    and existing.suite == item["suite"]
                    and existing.size_bytes == item["size_bytes"]
                    and existing.required_protocol_version == item["required_protocol_version"]
                    and existing.required_updater_version == item["required_updater_version"]
                    and existing.release_notes == item.get("release_notes", "")[:4000]
                    and existing.published_at == published_at
                )
                if not immutable:
                    raise CatalogError("published release identity collision")
                existing.withdrawn_at = datetime.now(UTC) if item.get("withdrawn", False) else None
                if not item.get("withdrawn", False):
                    existing.approved_at = existing.approved_at or datetime.now(UTC)
                session.add(existing)
            else:
                session.add(AgentRelease(id=item["id"], source_commit=item["source_commit"], upstream_version=item["upstream_version"], package="hardware-agent", package_version=item["package_version"], architecture=item["architecture"], suite=item["suite"], sha256=item["sha256"], size_bytes=item["size_bytes"], required_protocol_version=item["required_protocol_version"], required_updater_version=item["required_updater_version"], release_notes=item.get("release_notes", "")[:4000], published_at=datetime.fromisoformat(item["published_at"].replace("Z", "+00:00")), approved_at=None if item.get("withdrawn", False) else datetime.now(UTC), withdrawn_at=datetime.now(UTC) if item.get("withdrawn", False) else None))
        for previous in session.exec(select(AgentRelease)).all():
            if ("hardware-agent", previous.package_version, previous.architecture) not in seen and previous.withdrawn_at is None:
                previous.withdrawn_at = datetime.now(UTC)
                session.add(previous)
        if state is None:
            state = AgentReleaseCatalogState(singleton_id=1)
        state.generation = generation
        state.digest = digest
        state.validated_at = datetime.now(UTC)
        state.valid_until = valid_until
        session.add(state)
        session.commit()
        return len(releases)
    except Exception:
        session.rollback()
        raise
    finally:
        if own_client:
            client.close()


def project_availability(
    releases: list[AgentRelease],
    *,
    installed_version: str | None,
    architecture: str,
    protocol_version: int | None,
    updater_version: int | None,
    catalog_valid_until: datetime | None,
    now: datetime | None = None,
) -> tuple[str, AgentRelease | None]:
    now = now or datetime.now(UTC)
    if catalog_valid_until is None or catalog_valid_until <= now:
        return "unavailable", None
    if installed_version is None:
        return "unknown", None
    candidates = [
        release
        for release in releases
        if release.approved_at is not None
        and release.withdrawn_at is None
        and release.architecture == architecture
        and protocol_version is not None
        and updater_version is not None
        and protocol_version >= release.required_protocol_version
        and updater_version >= release.required_updater_version
    ]
    if not candidates:
        return "unavailable", None
    latest = candidates[0]
    for candidate in candidates[1:]:
        if debian_version_compare(candidate.package_version, "gt", latest.package_version):
            latest = candidate
    try:
        if debian_version_compare(installed_version, "ge", latest.package_version):
            return "up_to_date", None
    except ValueError:
        return "unknown", None
    return "available", latest
