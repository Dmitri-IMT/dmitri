from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from api.models import persistence
from sqlalchemy import engine_from_config, pool

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = persistence.SQLModel.metadata


def _migration_url() -> str:
    value = os.environ.get("DATABASE_URL_DIRECT")
    if not value:
        raise RuntimeError("DATABASE_URL_DIRECT is required for migrations.")

    prefixes = (
        "postgres://",
        "postgresql://",
        "postgresql+psycopg://",
        "postgresql+asyncpg://",
    )
    if not value.startswith(prefixes):
        raise RuntimeError("DATABASE_URL_DIRECT must be a PostgreSQL connection URL.")

    return "postgresql+psycopg://" + value.split("://", 1)[1]


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
