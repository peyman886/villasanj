"""Convert a Pydantic JSON schema into OpenAI "strict" structured-output form.

Strict mode requires: every object has ``additionalProperties: false`` and lists all properties as
required; no ``default`` keywords; a ``$ref`` may not have sibling keywords.
"""

from __future__ import annotations

import copy
from collections.abc import Mapping
from typing import Any

_REF_PREFIX = "#/$defs/"


def to_strict_json_schema(schema: Mapping[str, Any]) -> dict[str, Any]:
    root = copy.deepcopy(dict(schema))
    definitions: dict[str, Any] = root.get("$defs", {})
    strict: dict[str, Any] = _strict(root, definitions)
    return strict


def _strict(node: Any, definitions: dict[str, Any]) -> Any:
    if isinstance(node, list):
        return [_strict(item, definitions) for item in node]
    if not isinstance(node, dict):
        return node
    node.pop("default", None)
    if "$ref" in node and len(node) > 1:
        ref = node.pop("$ref")
        resolved = copy.deepcopy(definitions[ref.removeprefix(_REF_PREFIX)])
        node = {**resolved, **node}
    if node.get("type") == "object" or "properties" in node:
        if isinstance(node.get("additionalProperties"), dict):
            raise ValueError("free-form mappings cannot be expressed in strict structured output")
        properties = node.get("properties", {})
        node["additionalProperties"] = False
        node["required"] = list(properties)
    return {key: _strict(value, definitions) for key, value in node.items()}
