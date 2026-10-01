"""Deterministic token estimation, calibrated per model (no tokenizer downloads, works offline)."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from typing import Any

from villasanj.shared.application.llm.routing import ModelCatalog
from villasanj.shared.application.llm.types import Message

PER_MESSAGE_OVERHEAD_TOKENS = 4


class HeuristicTokenEstimator:
    """chars-per-token and per-image token costs come from ``config/llm.toml`` calibration.

    Calibration values are re-derived from ledger actuals (ROADMAP M9: dry-run within ±25%).
    """

    def __init__(self, catalog: ModelCatalog) -> None:
        self._catalog = catalog

    def input_tokens(
        self, model: str, messages: Sequence[Message], json_schema: Mapping[str, Any] | None
    ) -> int:
        profile = self._catalog.get(model)
        chars = sum(len(message.text) for message in messages)
        if json_schema is not None:
            chars += len(json.dumps(json_schema, separators=(",", ":")))
        images = sum(len(message.images) for message in messages)
        return (
            math.ceil(chars / profile.chars_per_token)
            + images * profile.image_tokens
            + PER_MESSAGE_OVERHEAD_TOKENS * len(messages)
        )

    def output_tokens(self, model: str, text: str) -> int:
        return math.ceil(len(text) / self._catalog.get(model).chars_per_token)
