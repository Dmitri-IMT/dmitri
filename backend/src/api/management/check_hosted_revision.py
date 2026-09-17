from __future__ import annotations

import argparse
import ast
import os
import sys
from pathlib import Path

from sqlalchemy import create_engine, text

from api.core.config import normalize_postgres_url

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


class UnknownHostedRevisionError(RuntimeError):
    """The hosted database is at a revision this checkout does not contain."""

    def __init__(self, unknown: set[str]) -> None:
        super().__init__(", ".join(sorted(unknown)))
        self.unknown = unknown


class MigrationParseError(RuntimeError):
    """A migration file does not declare a revision the way Alembic expects."""


def _literal(module: ast.Module, name: str) -> object:
    """The module-level literal assigned to `name`, or None if absent.

    Deliberately `ast.literal_eval`, never `eval` or an import: this parses
    migration files from an untrusted branch, so nothing in them may run.
    """
    for node in module.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == name:
                try:
                    return ast.literal_eval(node.value)
                except ValueError:
                    # A computed value. Alembic's own template never emits one,
                    # and guessing at it would corrupt the graph.
                    raise MigrationParseError(
                        f"{name} is not a literal"
                    ) from None
    return None


def _down_revisions(value: object) -> set[str]:
    if value is None:
        return set()
    if isinstance(value, str):
        return {value}
    if isinstance(value, (tuple, list)):
        # Merge revisions declare several parents.
        return {str(item) for item in value}
    raise MigrationParseError(f"unsupported down_revision: {value!r}")


def read_revision_graph(versions_dir: Path) -> dict[str, set[str]]:
    """Map every revision in `versions_dir` to its parents.

    Alembic imports migration files to read this, which executes them. This
    check runs against branches before review, so it parses instead.
    """
    graph: dict[str, set[str]] = {}
    for path in sorted(versions_dir.glob("*.py")):
        if path.name == "__init__.py":
            continue
        module = ast.parse(path.read_text(), filename=str(path))
        revision = _literal(module, "revision")
        if revision is None:
            continue
        if not isinstance(revision, str):
            raise MigrationParseError(f"{path.name}: revision is not a string")
        if revision in graph:
            raise MigrationParseError(f"duplicate revision {revision}")
        graph[revision] = _down_revisions(_literal(module, "down_revision"))
    if not graph:
        raise MigrationParseError(f"no migrations found in {versions_dir}")
    return graph


def heads(graph: dict[str, set[str]]) -> set[str]:
    """Revisions nothing else descends from."""
    parents = {parent for parents in graph.values() for parent in parents}
    return set(graph) - parents


def missing_heads(
    graph: dict[str, set[str]], expected: set[str], hosted: set[str]
) -> set[str]:
    """Which of `expected` the hosted database has not run.

    `alembic_version` stores only current head(s), so a revision counts as
    applied exactly when it is one of those heads or an ancestor of one.

    The hosted database is shared by every open pull request, so it may sit
    ahead of this branch on a revision another branch already landed. Being
    ahead is fine; only being behind breaks the deploy. Hence containment
    rather than equality.
    """
    unknown = hosted - set(graph)
    if unknown:
        # Ancestry through a revision we do not have is unresolvable, so we
        # cannot prove `expected` is applied. Say that rather than guess.
        raise UnknownHostedRevisionError(unknown)

    applied: set[str] = set()
    pending = list(hosted)
    while pending:
        revision = pending.pop()
        if revision in applied:
            continue
        applied.add(revision)
        pending.extend(graph[revision])
    return expected - applied


def hosted_revisions(database_url: str) -> set[str]:
    engine = create_engine(
        normalize_postgres_url(database_url),
        connect_args={"prepare_threshold": None, "connect_timeout": 10},
    )
    try:
        with engine.connect() as connection:
            rows = connection.execute(
                text("SELECT version_num FROM public.alembic_version")
            ).all()
    finally:
        engine.dispose()
    return {row[0] for row in rows}


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="backend-check-hosted-revision",
        description=(
            "Fail when the hosted database is missing a migration the given "
            "migration directory expects. Reads DATABASE_URL; needs only "
            "SELECT on alembic_version."
        ),
    )
    parser.add_argument(
        "--versions",
        type=Path,
        default=Path("alembic/versions"),
        help=(
            "Alembic versions directory to check (default: alembic/versions, "
            "i.e. run from backend/). Parsed, never imported, so it may come "
            "from an unreviewed branch."
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url:
        print("DATABASE_URL is required.", file=sys.stderr)
        return 1

    try:
        graph = read_revision_graph(args.versions)
    except (MigrationParseError, OSError) as exc:
        print(f"cannot read migrations: {exc}", file=sys.stderr)
        return 1

    expected = heads(graph)
    hosted = hosted_revisions(database_url)
    if not hosted:
        print(
            "hosted database reports no Alembic revision; it has never been "
            "migrated",
            file=sys.stderr,
        )
        return 1

    try:
        missing = missing_heads(graph, expected, hosted)
    except UnknownHostedRevisionError as exc:
        print(
            "cannot verify the hosted schema: it is at a revision this "
            f"checkout does not contain ({exc}).\n"
            "That happens when a migration was applied from a branch which is "
            "not merged yet. Merge or rebase onto it, then re-run this check.",
            file=sys.stderr,
        )
        return 1

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
