from __future__ import annotations

import ast
from pathlib import Path
from uuid import uuid4

import pytest
from api.management import provision_agent
from api.models.command import Agent
from api.models.identity import Org
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from sqlmodel import Session, select


def test_provision_agent_inserts_agent_with_given_public_key(
    migrated_database, administrative_session: Session, seeded_org: Org
) -> None:
    public_key_hex = "11" * 32

    exit_code = provision_agent.main(
        [
            "--org-id",
            str(seeded_org.id),
            "--display-name",
            "NSPi lab",
            "--public-key",
            public_key_hex,
        ]
    )

    assert exit_code == 0

    agents = administrative_session.exec(select(Agent)).all()
    assert len(agents) == 1
    assert agents[0].org_id == seeded_org.id
    assert agents[0].public_key == bytes.fromhex(public_key_hex)


def test_provision_agent_prints_agent_id(
    migrated_database,
    administrative_session: Session,
    seeded_org: Org,
    capsys: pytest.CaptureFixture,
) -> None:
    public_key_hex = "22" * 32

    exit_code = provision_agent.main(
        [
            "--org-id",
            str(seeded_org.id),
            "--display-name",
            "NSPi lab",
            "--public-key",
            public_key_hex,
        ]
    )
    assert exit_code == 0

    agent = administrative_session.exec(select(Agent)).one()
    output = capsys.readouterr().out
    assert f"agent_id={agent.id}" in output


def test_provision_agent_rejects_bad_length_hex_key(
    migrated_database,
    administrative_session: Session,
    seeded_org: Org,
    capsys: pytest.CaptureFixture,
) -> None:
    exit_code = provision_agent.main(
        [
            "--org-id",
            str(seeded_org.id),
            "--display-name",
            "NSPi lab",
            "--public-key",
            "abcd",
        ]
    )

    assert exit_code == 1
    assert capsys.readouterr().err
    assert administrative_session.exec(select(Agent)).all() == []


def test_provision_agent_rejects_unknown_org(
    migrated_database, administrative_session: Session, capsys: pytest.CaptureFixture
) -> None:
    exit_code = provision_agent.main(
        [
            "--org-id",
            str(uuid4()),
            "--display-name",
            "NSPi lab",
            "--public-key",
            "33" * 32,
        ]
    )

    assert exit_code == 1
    assert capsys.readouterr().err
    assert administrative_session.exec(select(Agent)).all() == []


def test_provision_agent_generate_prints_private_key_once_with_banner(
    migrated_database,
    administrative_session: Session,
    seeded_org: Org,
    capsys: pytest.CaptureFixture,
) -> None:
    exit_code = provision_agent.main(
        [
            "--org-id",
            str(seeded_org.id),
            "--display-name",
            "NSPi lab",
            "--generate",
        ]
    )

    assert exit_code == 0

    output = capsys.readouterr().out.lower()
    assert "not production" in output
    assert "private_key=" in output

    agent = administrative_session.exec(select(Agent)).one()
    assert len(agent.public_key) == 32


def test_provision_agent_never_stores_a_private_key(
    migrated_database,
    administrative_session: Session,
    seeded_org: Org,
    capsys: pytest.CaptureFixture,
) -> None:
    exit_code = provision_agent.main(
        [
            "--org-id",
            str(seeded_org.id),
            "--display-name",
            "NSPi lab",
            "--generate",
        ]
    )
    assert exit_code == 0

    output = capsys.readouterr().out
    private_hex = None
    for line in output.splitlines():
        if line.startswith("private_key="):
            private_hex = line.split("=", 1)[1]
    assert private_hex is not None

    expected_public_key = (
        Ed25519PrivateKey.from_private_bytes(bytes.fromhex(private_hex))
        .public_key()
        .public_bytes_raw()
    )

    agent = administrative_session.exec(select(Agent)).one()
    assert agent.public_key == expected_public_key
    assert agent.public_key.hex() != private_hex
    assert "private_key" not in Agent.model_fields


def test_provision_agent_module_never_references_logging() -> None:
    source = Path(provision_agent.__file__).read_text(encoding="utf-8")
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
