from __future__ import annotations

from pathlib import Path

import pytest
from api.management.check_hosted_revision import (
    MigrationParseError,
    UnknownHostedRevisionError,
    heads,
    missing_heads,
    read_revision_graph,
)

ROOT = Path(__file__).resolve().parents[1]
VERSIONS = ROOT / "alembic" / "versions"

# A linear stretch of this repository's real graph, newest last.
OLDER = "20260912_24"
PREVIOUS = "20260912_26"
HEAD = "20260917_27"


@pytest.fixture(name="graph")
def _graph() -> dict[str, set[str]]:
    return read_revision_graph(VERSIONS)


def test_graph_matches_the_shipped_migrations(graph: dict[str, set[str]]) -> None:
    assert heads(graph) == {HEAD}
    assert graph[HEAD] == {PREVIOUS}
    # A merge revision declares several parents.
    assert graph["20260912_23"] == {"20260912_21", "20260912_22"}


def test_parser_agrees_with_alembic_on_the_real_graph(
    graph: dict[str, set[str]],
) -> None:
    """The gate's own parser must not drift from Alembic's reading.

    `read_revision_graph` exists only because Alembic imports migration files,
    which the gate cannot do. That means a second implementation of Alembic's
    revision conventions, and a silently wrong graph here is worse than a
    failing check. This pins the two together on every real migration.
    """
    from alembic.script import ScriptDirectory
    from conftest import _alembic_config

    scripts = ScriptDirectory.from_config(_alembic_config())
    alembic_graph = {
        revision.revision: set(revision._all_down_revisions)
        for revision in scripts.walk_revisions()
    }

    assert graph == alembic_graph
    assert heads(graph) == set(scripts.get_heads())


def test_up_to_date_database_is_missing_nothing(graph: dict[str, set[str]]) -> None:
    assert missing_heads(graph, {HEAD}, {HEAD}) == set()


def test_database_one_revision_behind_reports_the_head(
    graph: dict[str, set[str]],
) -> None:
    # The 2026-09-16 outage: code expected a revision the database lacked.
    assert missing_heads(graph, {HEAD}, {PREVIOUS}) == {HEAD}


def test_database_several_revisions_behind_reports_the_head(
    graph: dict[str, set[str]],
) -> None:
    assert missing_heads(graph, {HEAD}, {OLDER}) == {HEAD}


def test_ancestor_of_hosted_head_counts_as_applied(
    graph: dict[str, set[str]],
) -> None:
    # A branch that adds no migration of its own must pass while the shared
    # database sits ahead of it.
    assert missing_heads(graph, {PREVIOUS}, {HEAD}) == set()
    assert missing_heads(graph, {OLDER}, {HEAD}) == set()


def test_ancestry_through_a_merge_revision_is_applied(
    graph: dict[str, set[str]],
) -> None:
    assert missing_heads(graph, {"20260912_21"}, {HEAD}) == set()
    assert missing_heads(graph, {"20260912_22"}, {HEAD}) == set()


def test_unknown_hosted_revision_is_not_silently_passed(
    graph: dict[str, set[str]],
) -> None:
    # Applied from a branch this checkout does not have. Ancestry through it is
    # unresolvable, so the check must refuse to reach a verdict.
    with pytest.raises(UnknownHostedRevisionError) as caught:
        missing_heads(graph, {HEAD}, {"20270101_99"})
    assert caught.value.unknown == {"20270101_99"}


def test_unknown_revision_alongside_a_known_one_still_refuses(
    graph: dict[str, set[str]],
) -> None:
    with pytest.raises(UnknownHostedRevisionError):
        missing_heads(graph, {HEAD}, {HEAD, "20270101_99"})


def test_migration_files_are_parsed_never_executed(tmp_path: Path) -> None:
    # The gate reads migrations from an unreviewed branch while a database
    # credential is in the environment, so importing them would hand that
    # credential to anyone who can push. Alembic's ScriptDirectory imports;
    # this must not.
    (tmp_path / "20270101_98_hostile.py").write_text(
        "raise AssertionError('migration file was executed')\n"
        'revision = "20270101_98"\n'
        "down_revision = None\n"
    )
    graph = read_revision_graph(tmp_path)
    assert graph == {"20270101_98": set()}


def test_tuple_and_list_parents_are_both_accepted(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text('revision = "a"\ndown_revision = None\n')
    (tmp_path / "b.py").write_text('revision = "b"\ndown_revision = "a"\n')
    (tmp_path / "c.py").write_text('revision = "c"\ndown_revision = ["a", "b"]\n')
    graph = read_revision_graph(tmp_path)
    assert graph["c"] == {"a", "b"}
    assert heads(graph) == {"c"}


def test_computed_revision_is_refused_rather_than_guessed(tmp_path: Path) -> None:
    (tmp_path / "x.py").write_text(
        'revision = "pre" + "fix"\ndown_revision = None\n'
    )
    with pytest.raises(MigrationParseError):
        read_revision_graph(tmp_path)


def test_duplicate_revision_ids_are_refused(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text('revision = "dup"\ndown_revision = None\n')
    (tmp_path / "b.py").write_text('revision = "dup"\ndown_revision = None\n')
    with pytest.raises(MigrationParseError):
        read_revision_graph(tmp_path)


def test_empty_directory_is_refused(tmp_path: Path) -> None:
    with pytest.raises(MigrationParseError):
        read_revision_graph(tmp_path)
