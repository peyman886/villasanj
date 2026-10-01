from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from villasanj.shared.infrastructure.settings import DatabaseSettings


def create_engine(settings: DatabaseSettings) -> AsyncEngine:
    return create_async_engine(settings.url, pool_size=settings.pool_size, pool_pre_ping=True)
