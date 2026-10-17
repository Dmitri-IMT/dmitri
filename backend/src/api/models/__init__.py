"""ORM models.

Import every model module so their tables register on the shared
``SQLModel.metadata`` that Alembic targets. ``identity`` pulls in
``persistence`` itself (it reuses ``utc_now``), so import order is irrelevant.
"""

from . import (  # noqa: F401
    activity,
    agent_update,
    command,
    identity,
    persistence,
    session,
)
