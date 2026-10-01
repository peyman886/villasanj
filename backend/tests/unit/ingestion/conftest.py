import pytest

from tests.fakes.ingestion import World


@pytest.fixture
def world() -> World:
    return World()
