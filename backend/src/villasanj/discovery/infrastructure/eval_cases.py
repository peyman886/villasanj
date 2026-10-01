"""Load query-understanding eval cases: JSON lines of ``{"query": ..., "expected": {...}}``."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from villasanj.discovery.application.intent import SearchIntent
from villasanj.discovery.application.understanding_eval import EvalCase
from villasanj.shared.application.errors import ConfigurationError


def load_cases(path: Path) -> list[EvalCase]:
    cases = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise ConfigurationError(f"cannot read eval cases {path}: {error}") from None
    for number, line in enumerate(lines, start=1):
        if not line.strip() or line.lstrip().startswith("//"):
            continue
        try:
            item = json.loads(line)
            cases.append(EvalCase(item["query"], SearchIntent.model_validate(item["expected"])))
        except (json.JSONDecodeError, KeyError, TypeError, ValidationError) as error:
            raise ConfigurationError(f"{path}:{number}: invalid case: {error}") from None
    return cases
