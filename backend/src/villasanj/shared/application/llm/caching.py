"""Persistent response cache: an identical model call never costs twice."""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from typing import Any

import structlog
from pydantic import BaseModel, ValidationError

from villasanj.shared.application.clock import Clock
from villasanj.shared.application.llm.ports import (
    CachedCompletion,
    CallStatus,
    Invocation,
    LedgerEntry,
    LLMCacheStore,
    LLMLedger,
    ModelCall,
    ModelInvoker,
)
from villasanj.shared.application.llm.types import ImagePart, TextPart, TokenUsage

log = structlog.get_logger(__name__)


def cache_key(provider: str, call: ModelCall[Any]) -> str:
    """SHA-256 over everything that can change the output. Images enter by content hash."""
    request = call.request
    payload = {
        "provider": provider,
        "model": call.model,
        "prompt": f"{request.prompt_id}@{request.prompt_version}",
        "messages": [
            {
                "role": message.role.value,
                "parts": [
                    {"text": part.text}
                    if isinstance(part, TextPart)
                    else {"image": _image_digest(part)}
                    for part in message.parts
                ],
            }
            for message in request.messages
        ],
        "schema": request.output_schema.model_json_schema(),
        "params": {
            "max_output_tokens": call.max_output_tokens,
            "temperature": call.route.temperature,
            "reasoning_effort": call.route.reasoning_effort,
        },
    }
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _image_digest(part: ImagePart) -> str:
    return f"{part.media_type}:{part.sha256}"


class CachingInvoker:
    def __init__(
        self,
        inner: ModelInvoker,
        store: LLMCacheStore,
        ledger: LLMLedger,
        clock: Clock,
        provider_name: str,
    ) -> None:
        self._inner = inner
        self._store = store
        self._ledger = ledger
        self._clock = clock
        self._provider = provider_name

    async def invoke[T: BaseModel](self, call: ModelCall[T]) -> Invocation[T]:
        key = cache_key(self._provider, call)
        hit = await self._load(key, call)
        if hit is not None:
            await self._record_hit(call)
            return hit
        invocation = await self._inner.invoke(call)
        await self._store.put(
            key,
            CachedCompletion(
                text=invocation.raw_text, model=invocation.model, usage=invocation.usage
            ),
            call.request.task,
        )
        return invocation

    async def _load[T: BaseModel](self, key: str, call: ModelCall[T]) -> Invocation[T] | None:
        cached = await self._store.get(key)
        if cached is None:
            return None
        try:
            value = call.request.output_schema.model_validate_json(cached.text)
        except ValidationError:
            log.warning("llm.cache.stale_entry", key=key, prompt_id=call.request.prompt_id)
            return None
        return Invocation(
            value=value,
            raw_text=cached.text,
            model=cached.model,
            usage=cached.usage,
            cost_usd=Decimal(0),
            attempts=0,
            latency_ms=0,
            cache_hit=True,
        )

    async def _record_hit(self, call: ModelCall[Any]) -> None:
        await self._ledger.record(
            LedgerEntry(
                job_id=call.ctx.job_id,
                task=call.request.task,
                model=call.model,
                prompt_id=call.request.prompt_id,
                prompt_version=call.request.prompt_version,
                attempt=0,
                status=CallStatus.CACHE_HIT,
                usage=TokenUsage.zero(),
                cost_usd=Decimal(0),
                latency_ms=0,
                created_at=self._clock.now(),
            )
        )
