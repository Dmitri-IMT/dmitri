from __future__ import annotations

from alembic.script import ScriptDirectory
from conftest import _alembic_config


def test_alembic_has_single_head() -> None:
    script = ScriptDirectory.from_config(_alembic_config())
    heads = script.get_heads()
    assert len(heads) == 1
    assert heads[0] == "20261012_40"
