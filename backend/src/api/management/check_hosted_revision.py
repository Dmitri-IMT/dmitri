from __future__ import annotations

import argparse
import sys

from alembic.config import Config
from alembic.script import ScriptDirectory
from alembic.util.exc import CommandError
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError

from api.db.session import get_session

RUNBOOK = (
    "Apply them before merging. Railway runs no migrations, so merging now "
    "ships code that reads columns which do not exist yet:\n\n"
    "    cd backend\n"
    "    export DATABASE_URL_DIRECT=...   # from your local .env, never on Railway\n"
    "    uv run alembic upgrade head\n"
    "    unset DATABASE_URL_DIRECT\n\n"
    "Then re-run this check. See docs/cloud/railway/SETUP.md, "
    "'Deploying a schema change'."
)


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="backend-check-hosted-revision",
        description=(
            "Fail when the hosted database is missing a migration this "
            "checkout expects. Reads DATABASE_URL; needs only SELECT on "
            "alembic_version."
        ),
    )
    parser.add_argument(
        "--config",
        default="alembic.ini",
        help="path to alembic.ini (default: alembic.ini, i.e. run from backend/)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    scripts = ScriptDirectory.from_config(Config(args.config))

    expected = set(scripts.get_heads())
    if not expected:
        print("no migrations in this checkout", file=sys.stderr)
        return 1

    try:
        for session in get_session():
            rows = session.execute(
                text("SELECT version_num FROM public.alembic_version")
            ).all()
    except ProgrammingError as exc:
        # Guaranteed on the first run: 20260917_27 is what grants dmitri_runtime
        # this read, and until it is applied the check cannot see anything.
        if "alembic_version" not in str(exc):
            raise
        print(
            "cannot read alembic_version with this credential. Apply "
            "20260917_27, which grants dmitri_runtime SELECT on it:\n\n" + RUNBOOK,
            file=sys.stderr,
        )
        return 1
    hosted = {row[0] for row in rows}

    if not hosted:
        print(
            "hosted database reports no Alembic revision; it has never been "
            "migrated",
            file=sys.stderr,
        )
        return 1

    # The hosted database is shared by every open pull request, so it may sit
    # ahead of this branch on a revision another branch already landed. Only
    # being *behind* breaks the deploy, so assert containment, not equality.
    try:
        applied = {
            script.revision
            for script in scripts.iterate_revisions(tuple(hosted), "base")
        }
    except CommandError:
        # A hosted revision this checkout has never seen. That is drift, not a
        # verdict this check can reach, so say so instead of guessing.
        print(
            "hosted database is at a revision this checkout does not contain: "
            f"{', '.join(sorted(hosted))}.\n"
            "Rebase onto the branch that introduced it, or investigate the "
            "hosted database before merging.",
            file=sys.stderr,
        )
        return 1

    missing = expected - applied
    if missing:
        print(
            "hosted database is behind this branch.\n"
            f"  hosted:   {', '.join(sorted(hosted))}\n"
            f"  expected: {', '.join(sorted(expected))}\n"
            f"  missing:  {', '.join(sorted(missing))}\n\n" + RUNBOOK,
            file=sys.stderr,
        )
        return 1

    print(f"hosted database is at or ahead of {', '.join(sorted(expected))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
