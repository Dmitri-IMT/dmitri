"""ORM models.

Import every model module so their tables register on the shared
``SQLModel.metadata`` that Alembic targets. ``identity`` pulls in
``persistence`` itself (it reuses ``utc_now``), so import order is irrelevant.
"""

from . import activity, command, identity, persistence, session  # noqa: F401
