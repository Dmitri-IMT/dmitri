from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from api.core.config import normalize_postgres_url
from api.models import command, identity, persistence  # noqa: F401
from sqlalchemy import engine_from_config, pool

config = context.config

if config.config_file_name is not None:
    # disable_existing_loggers defaults to True, which would silence every logger
    # already created at import time (e.g. api.services.*) for the rest of the
    # process — breaking log assertions in any test that runs after a migration.
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = persistence.SQLModel.metadata


def _migration_url() -> str:
    value = os.environ.get("DATABASE_URL_DIRECT")
    if not value:
        raise RuntimeError("DATABASE_URL_DIRECT is required for migrations.")

    try:
        return normalize_postgres_url(value, variable="DATABASE_URL_DIRECT")
    except ValueError as exc:
        raise RuntimeError(str(exc)) from exc


def run_migrations_offline() -> None:
    context.configure(
        url=_migration_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    config.set_main_option("sqlalchemy.url", _migration_url().replace("%", "%%"))
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
