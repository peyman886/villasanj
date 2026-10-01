"""The frontend's committed OpenAPI schema (and the TS types made from it) match the API."""

import json
from pathlib import Path
from typing import cast

from villasanj.entrypoints.api.app import create_app
from villasanj.entrypoints.container import Container

COMMITTED = (
    Path(__file__).resolve().parents[3] / "frontend" / "src" / "lib" / "api" / "openapi.json"
)


def test_committed_schema_is_current() -> None:
    live = create_app(lambda: cast(Container, None)).openapi()
    committed = json.loads(COMMITTED.read_text("utf-8"))
    assert committed == json.loads(json.dumps(live)), "run `make openapi` and commit the result"
