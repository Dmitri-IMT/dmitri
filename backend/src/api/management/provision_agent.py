from __future__ import annotations

import argparse
import sys
from uuid import UUID

from api.db.session import get_session
from api.models.command import Agent
from api.models.identity import Org
from api.services import device_sig


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="backend-provision-agent")
    parser.add_argument("--org-id", required=True)
    parser.add_argument("--display-name", required=True)
    parser.add_argument("--public-key")
    parser.add_argument("--generate", action="store_true")
    return parser.parse_args(argv)


def _decode_public_key(hex_value: str) -> bytes | None:
    try:
        raw = bytes.fromhex(hex_value)
    except ValueError:
        return None
    if len(raw) != 32:
        return None
    return raw


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    try:
        org_id = UUID(args.org_id)
    except ValueError:
        print(f"invalid --org-id: {args.org_id}", file=sys.stderr)
        return 1

    if args.generate:
        private_key, public_key = device_sig.generate_keypair()
        print("WARNING: --generate is for local testing only, not production")
        print(f"private_key={private_key.hex()}")
    else:
        if not args.public_key:
            print(
                "--public-key is required unless --generate is passed",
                file=sys.stderr,
            )
            return 1
        public_key = _decode_public_key(args.public_key)
        if public_key is None:
            print("--public-key must be 64 hex characters (32 bytes)", file=sys.stderr)
            return 1

    for session in get_session():
        org = session.get(Org, org_id)
        if org is None:
            print(f"unknown org: {org_id}", file=sys.stderr)
            return 1

        agent = Agent(
            org_id=org_id,
            display_name=args.display_name,
            public_key=public_key,
        )
        session.add(agent)
        session.commit()
        session.refresh(agent)

        print(f"agent_id={agent.id}")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
