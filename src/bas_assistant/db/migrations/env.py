"""Alembic environment: builds the connection URL from Settings, not alembic.ini."""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import Column, Index, engine_from_config, pool
from sqlalchemy.schema import SchemaItem

from bas_assistant.db import activity, corpus  # noqa: F401 — register models on Base.metadata
from bas_assistant.db.engine import Base
from bas_assistant.settings import Settings

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# Created and migrated by LangGraph's PostgresSaver.setup(); autogenerate must never drop them.
CHECKPOINT_TABLES = {
    "checkpoints",
    "checkpoint_blobs",
    "checkpoint_writes",
    "checkpoint_migrations",
}


def include_object(
    item: SchemaItem, name: str | None, _type: str, _reflected: bool, _compare_to: object
) -> bool:
    parent = item.table if isinstance(item, Column | Index) else None
    table = parent.name if parent is not None else name
    return table not in CHECKPOINT_TABLES


def run_migrations_online() -> None:
    """Run migrations against a live Postgres connection."""
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = Settings().database_url
    connectable = engine_from_config(configuration, prefix="sqlalchemy.", poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata, include_object=include_object
        )
        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()
