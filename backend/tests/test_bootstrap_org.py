from __future__ import annotations

import ast
import hashlib
import tomllib
from pathlib import Path

import pytest
from api.management import bootstrap_org
from api.models.identity import Invite, Org, User
from api.services.invites import accept_invite
from sqlmodel import Session, select

ROOT = Path(__file__).resolve().parents[1]
VALID_PASSWORD = "Xk9$mQvL2pTz"


@pytest.fixture(autouse=True)
def _disable_hibp(monkeypatch: pytest.MonkeyPatch) -> None:
    from api.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("HIBP_ENABLED", "false")
    yield
    get_settings.cache_clear()


def test_bootstrap_creates_org_and_admin_invite(
    migrated_database, administrative_session: Session
) -> None:
    exit_code = bootstrap_org.main(
        ["--org-name", "Acme", "--email", "a@acme.test"]
    )

    assert exit_code == 0

    orgs = administrative_session.exec(select(Org)).all()
    assert len(orgs) == 1

    invites = administrative_session.exec(select(Invite)).all()
    assert len(invites) == 1
    assert invites[0].role == "admin"
    assert invites[0].org_id == orgs[0].id


def test_bootstrap_prints_token_matching_stored_hash_and_accept_succeeds(
    migrated_database, administrative_session: Session, capsys: pytest.CaptureFixture
) -> None:
    exit_code = bootstrap_org.main(
        ["--org-name", "Acme", "--email", "a@acme.test"]
    )
    assert exit_code == 0

    output = capsys.readouterr().out
    token = None
    for line in output.splitlines():
        if line.startswith("invite_token="):
            token = line.split("=", 1)[1]
    assert token is not None

    invite = administrative_session.exec(select(Invite)).one()
    assert invite.token_hash == hashlib.sha256(token.encode("utf-8")).hexdigest()

    access_token, refresh_token, expires_in = accept_invite(
        administrative_session,
        token=token,
        password=VALID_PASSWORD,
    )
    assert access_token
    assert refresh_token
    assert expires_in > 0

    user = administrative_session.exec(
        select(User).where(User.email == "a@acme.test")
    ).one()
    assert user.role == "admin"
    assert user.org_id == invite.org_id


def test_bootstrap_refuses_duplicate_org_name(
    migrated_database, administrative_session: Session, capsys: pytest.CaptureFixture
) -> None:
    first = bootstrap_org.main(["--org-name", "Acme", "--email", "a@acme.test"])
    assert first == 0

    second = bootstrap_org.main(["--org-name", "Acme", "--email", "b@acme.test"])
    assert second == 1
    assert capsys.readouterr().err

    orgs = administrative_session.exec(select(Org)).all()
    assert len(orgs) == 1
    invites = administrative_session.exec(select(Invite)).all()
    assert len(invites) == 1


def test_bootstrap_refuses_duplicate_org_name_case_and_whitespace_insensitive(
    migrated_database, administrative_session: Session, capsys: pytest.CaptureFixture
) -> None:
    first = bootstrap_org.main(["--org-name", "Acme", "--email", "a@acme.test"])
    assert first == 0

    second = bootstrap_org.main(
        ["--org-name", "  acme  ", "--email", "b@acme.test"]
    )
    assert second == 1
    assert capsys.readouterr().err

    orgs = administrative_session.exec(select(Org)).all()
    assert len(orgs) == 1
    invites = administrative_session.exec(select(Invite)).all()
    assert len(invites) == 1


def test_bootstrap_refusal_precedes_any_insert(
    migrated_database,
    administrative_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = bootstrap_org.main(["--org-name", "Acme", "--email", "a@acme.test"])
    assert first == 0

    add_calls: list[object] = []
    original_add = Session.add

    def _tracking_add(self: Session, instance: object, *a: object, **k: object) -> None:
        add_calls.append(instance)
        return original_add(self, instance, *a, **k)

    monkeypatch.setattr(Session, "add", _tracking_add)

    second = bootstrap_org.main(["--org-name", "  acme  ", "--email", "b@acme.test"])
    assert second == 1
    assert add_calls == []


def test_bootstrap_org_module_never_references_logging() -> None:
    source = Path(bootstrap_org.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    referenced_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                referenced_names.add((alias.asname or alias.name).split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            referenced_names.add(node.module.split(".")[0])
            for alias in node.names:
                referenced_names.add(alias.asname or alias.name)
        elif isinstance(node, ast.Name):
            referenced_names.add(node.id)
    assert "logging" not in referenced_names
    assert "logger" not in referenced_names


def test_bootstrap_org_never_logs_the_invite_token(
    migrated_database,
    administrative_session: Session,
    capsys: pytest.CaptureFixture,
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level("DEBUG"):
        exit_code = bootstrap_org.main(
            ["--org-name", "Acme", "--email", "a@acme.test"]
        )
    assert exit_code == 0

    output = capsys.readouterr().out
    token = None
    for line in output.splitlines():
        if line.startswith("invite_token="):
            token = line.split("=", 1)[1]
    assert token is not None

    for record in caplog.records:
        assert token not in record.getMessage()


def test_console_scripts_registered() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    scripts = project["project"]["scripts"]
    assert scripts["backend-bootstrap-org"] == "api.management.bootstrap_org:main"
    assert (
        scripts["backend-provision-agent"] == "api.management.provision_agent:main"
    )
