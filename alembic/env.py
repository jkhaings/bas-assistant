"""Alembic environment: DATABASE_URL from the environment, schema from bas_assistant.db."""

import os

from alembic import context
from sqlalchemy import Column, Index
from sqlalchemy.schema import SchemaItem

from bas_assistant.db import create_db_engine, metadata

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
    table = item.table.name if isinstance(item, Column | Index) else name
    return table not in CHECKPOINT_TABLES


def run_migrations_online() -> None:
    engine = create_db_engine(os.environ["DATABASE_URL"])
    with engine.connect() as connection:
        context.configure(
            connection=connection, target_metadata=metadata, include_object=include_object
        )
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


run_migrations_online()
