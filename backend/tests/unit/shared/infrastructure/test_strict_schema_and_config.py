from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import BaseModel

from villasanj.shared.application.errors import ConfigurationError
from villasanj.shared.application.llm.types import LLMTask
from villasanj.shared.infrastructure.llm.config import load_catalog, load_routing
from villasanj.shared.infrastructure.llm.strict_schema import to_strict_json_schema

CONFIG = Path(__file__).resolve().parents[5] / "config"


class Inner(BaseModel):
    note: str = "n/a"


class Outer(BaseModel):
    name: str
    count: int | None = None
    inner: Inner
    tags: list[Inner] = []


def test_strict_schema_requires_everything_and_forbids_extras() -> None:
    schema = to_strict_json_schema(Outer.model_json_schema())
    assert schema["additionalProperties"] is False
    assert schema["required"] == ["name", "count", "inner", "tags"]
    assert "default" not in str(schema)
    inner = schema["$defs"]["Inner"]
    assert inner["additionalProperties"] is False
    assert inner["required"] == ["note"]


def test_strict_schema_rejects_free_form_mappings() -> None:
    class Loose(BaseModel):
        data: dict[str, int]

    with pytest.raises(ValueError, match="free-form"):
        to_strict_json_schema(Loose.model_json_schema())


def test_repository_config_is_valid() -> None:
    routing = load_routing(CONFIG / "llm.toml", Decimal(30))
    catalog = load_catalog(CONFIG / "llm-models.json", CONFIG / "llm.toml")
    routing.validate_against(catalog)
    assert set(routing.routes) == set(LLMTask)
    assert routing.project_budget_usd == Decimal(30)
    flash_lite = catalog.get("gemini-3.1-flash-lite")
    assert flash_lite.image_tokens == 1090
    assert flash_lite.pricing.input_per_mtok == Decimal("0.25")


def test_broken_routing_file_is_a_configuration_error(tmp_path: Path) -> None:
    bad = tmp_path / "llm.toml"
    bad.write_text("[budget]\ndefault_job_usd = -1\n")
    with pytest.raises(ConfigurationError, match="invalid routing file"):
        load_routing(bad, Decimal(30))
