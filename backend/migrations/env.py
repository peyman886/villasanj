"""Alembic environment (async). The URL comes from Settings unless a caller injects one."""

import asyncio

from alembic import context
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

from villasanj.catalog.infrastructure.tables import metadata as catalog_metadata
from villasanj.entity_resolution.infrastructure.tables import metadata as er_metadata
from villasanj.ingestion.infrastructure.tables import metadata as ingestion_metadata
from villasanj.shared.infrastructure.db.tables import metadata as ops_metadata
from villasanj.shared.infrastructure.settings import Settings

config = context.config
target_metadata = [ops_metadata, ingestion_metadata, catalog_metadata, er_metadata]


def _database_url() -> str:
    injected = config.attributes.get("database_url")
    return str(injected) if injected else Settings().database.url


def run_migrations_offline() -> None:
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        include_schemas=True,
        literal_binds=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def _run_sync(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, include_schemas=True)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    engine = create_async_engine(_database_url())
    async with engine.connect() as connection:
        await connection.run_sync(_run_sync)
    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
