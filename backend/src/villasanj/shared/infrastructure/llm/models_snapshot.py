"""Refresh ``config/llm-models.json`` from AvalAI ``/v1/models`` (a free call)."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
from pydantic import SecretStr

SNAPSHOT_MODES = frozenset({"chat", "embedding"})
REQUEST_TIMEOUT_SECONDS = 30.0


async def fetch_models(api_key: SecretStr, base_url: str) -> list[dict[str, Any]]:
    headers = {"Authorization": f"Bearer {api_key.get_secret_value()}"}
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
        response = await client.get(f"{base_url.rstrip('/')}/models", headers=headers)
    response.raise_for_status()
    data: list[dict[str, Any]] = response.json()["data"]
    return data


def compact_snapshot(raw_models: list[dict[str, Any]], fetched_at: datetime, source: str) -> str:
    models = []
    for model in raw_models:
        pricing = model.get("pricing") or {}
        if model.get("mode") not in SNAPSHOT_MODES or pricing.get("input") is None:
            continue
        models.append(
            {
                "id": model["id"],
                "owned_by": model.get("owned_by"),
                "mode": model.get("mode"),
                "input_usd_per_mtok": pricing.get("input"),
                "output_usd_per_mtok": pricing.get("output") or 0,
                "cached_input_usd_per_mtok": pricing.get("cached_input"),
                "supports_vision": bool(model.get("supports_vision")),
                "supports_response_schema": bool(model.get("supports_response_schema")),
                "supports_reasoning": bool(model.get("supports_reasoning")),
                "min_tier": model.get("min_tier"),
                "max_input_tokens": model.get("max_input_tokens"),
                "max_output_tokens": model.get("max_output_tokens"),
                "deprecation_date": model.get("deprecation_date"),
            }
        )
    models.sort(key=lambda entry: str(entry["id"]))
    document = {
        "source": source,
        "fetched_at": fetched_at.isoformat(),
        "unit": "USD per 1M tokens",
        "models": models,
    }
    return json.dumps(document, indent=1, ensure_ascii=False) + "\n"


def write_snapshot(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
