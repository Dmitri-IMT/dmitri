from __future__ import annotations

import argparse
import sys
from pathlib import Path
from uuid import UUID

from pydantic import ValidationError
from sqlmodel import Session, select

from api.db.session import get_session
from api.dependencies.agent_auth import AgentIdentity
from api.models.command import Agent
from api.models.identity import Org
from api.models.persistence import utc_now
from api.schemas.scan import ScanIngestRequest
from api.services.device_sig import generate_keypair
from api.services.persistence import ScanClosedError, ScanOwnershipError, ingest_scan

IMPORT_AGENT_NAME = "Local JSON importer"


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="backend-import-scan")
    parser.add_argument("--file", required=True, type=Path)
    owner = parser.add_mutually_exclusive_group(required=True)
    owner.add_argument("--agent-id")
    owner.add_argument("--org-id")
    return parser.parse_args(argv)


def _load_scan(path: Path) -> ScanIngestRequest | None:
    try:
        payload = path.read_text(encoding="utf-8")
        return ScanIngestRequest.model_validate_json(payload)
    except OSError as exc:
        print(f"could not read scan file: {exc}", file=sys.stderr)
    except ValidationError:
        print("scan file does not match ScanIngestRequest", file=sys.stderr)
    return None


def _parse_uuid(raw: str, option: str) -> UUID | None:
    try:
        return UUID(raw)
    except ValueError:
        print(f"{option} must be a UUID", file=sys.stderr)
        return None


def _resolve_agent(session: Session, args: argparse.Namespace) -> Agent | None:
    if args.agent_id is not None:
        agent_id = _parse_uuid(args.agent_id, "--agent-id")
        if agent_id is None:
            return None
        agent = session.get(Agent, agent_id)
        if agent is None:
            print(f"unknown agent: {agent_id}", file=sys.stderr)
            return None
        if agent.revoked_at is not None:
            print(f"agent is revoked: {agent_id}", file=sys.stderr)
            return None
        return agent

    org_id = _parse_uuid(args.org_id, "--org-id")
    if org_id is None:
        return None
    if session.get(Org, org_id) is None:
        print(f"unknown organization: {org_id}", file=sys.stderr)
        return None
    agent = session.exec(
        select(Agent).where(
            Agent.org_id == org_id,
            Agent.display_name == IMPORT_AGENT_NAME,
            Agent.revoked_at.is_(None),
        )
    ).first()
    if agent is not None:
        return agent

    _, public_key = generate_keypair()
    agent = Agent(
        org_id=org_id,
        display_name=IMPORT_AGENT_NAME,
        public_key=public_key,
    )
    session.add(agent)
    session.commit()
    session.refresh(agent)
    return agent


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    scan = _load_scan(args.file)
    if scan is None:
        return 1

    for session in get_session():
        agent = _resolve_agent(session, args)
        if agent is None:
            return 1

        try:
            ingest_scan(
                session,
                scan,
                identity=AgentIdentity(agent_id=agent.id, org_id=agent.org_id),
                now=utc_now(),
            )
        except ScanOwnershipError:
            print("scan belongs to another agent or organization", file=sys.stderr)
            return 1
        except ScanClosedError:
            print("scan is no longer accepting results", file=sys.stderr)
            return 1

        print("status=imported")
        print(f"scan_id={scan.scan_id}")
        print(f"agent_id={agent.id}")
        print(f"hosts_received={len(scan.hosts)}")
        print(f"findings_received={len(scan.findings)}")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
