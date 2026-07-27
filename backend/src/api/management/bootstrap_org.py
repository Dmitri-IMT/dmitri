from __future__ import annotations

import argparse
import sys

from sqlalchemy import func
from sqlmodel import select

from api.db.session import get_session
from api.models.identity import Org
from api.services.invites import create_invite


class _SilentMailer:
    def send_reset_link(self, email: str, token: str) -> None:
        pass

    def send_invite_link(self, email: str, token: str) -> None:
        pass


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="backend-bootstrap-org")
    parser.add_argument("--org-name", required=True)
    parser.add_argument("--email", required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    for session in get_session():
        existing = session.exec(
            select(Org).where(
                func.lower(func.trim(Org.name)) == args.org_name.strip().lower()
            )
        ).first()
        if existing is not None:
            print(
                f"org already exists: {existing.id} ({existing.name})",
                file=sys.stderr,
            )
            return 1

        org = Org(name=args.org_name)
        session.add(org)
        session.commit()
        session.refresh(org)

        raw_token, expires_at = create_invite(
            session,
            org_id=org.id,
            email=args.email,
            role="admin",
            mailer=_SilentMailer(),
        )

        print(f"org_id={org.id}")
        print(f"invite_token={raw_token}")
        print(f"expires_at={expires_at.isoformat()}")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
