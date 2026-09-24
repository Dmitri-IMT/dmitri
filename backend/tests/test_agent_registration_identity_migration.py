from __future__ import annotations

import pytest
import sqlalchemy as sa
from api.models.command import Agent
from api.models.identity import Org
from conftest import _migrate
from sqlmodel import Session


def test_identity_constraint_round_trip(migrated_database):
    engine = migrated_database
    _migrate(engine, "20260922_34")
    assert "uq_agents_org_public_key" not in {
        c["name"] for c in sa.inspect(engine).get_unique_constraints("agents")
    }
    _migrate(engine, "head")
    with Session(engine) as session:
        org = Org(name="Test")
        session.add(org)
        session.commit()
        session.add(Agent(org_id=org.id, display_name="Pi", public_key=b"a" * 32))
        session.commit()
        session.add(Agent(org_id=org.id, display_name="Retry", public_key=b"a" * 32))
        with pytest.raises(sa.exc.IntegrityError):
            session.commit()
        session.rollback()
    _migrate(engine, "20260922_34")
    assert "uq_agents_org_public_key" not in {
        c["name"] for c in sa.inspect(engine).get_unique_constraints("agents")
    }
    _migrate(engine, "head")
