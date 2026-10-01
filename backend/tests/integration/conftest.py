"""Integration fixtures: a throwaway Postgres built from our own image, migrated with Alembic."""

from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from testcontainers.community.postgres import PostgresContainer
from testcontainers.core.image import DockerImage

BACKEND = Path(__file__).resolve().parents[2]
POSTGRES_IMAGE_CONTEXT = BACKEND.parent / "infra" / "docker" / "postgres"


def alembic_config(database_url: str) -> Config:
    config = Config(str(BACKEND / "alembic.ini"))
    config.attributes["database_url"] = database_url
    return config


@pytest.fixture(scope="session")
def database_url() -> Iterator[str]:
    with (
        DockerImage(path=POSTGRES_IMAGE_CONTEXT, tag="villasanj-db:test", clean_up=False) as image,
        PostgresContainer(
            str(image), username="villasanj", password="villasanj", dbname="villasanj"
        ) as postgres,
    ):
        url = postgres.get_connection_url(driver="psycopg")
        command.upgrade(alembic_config(url), "head")
        yield url


@pytest.fixture
async def engine(database_url: str) -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(database_url)
    yield engine
    await engine.dispose()
