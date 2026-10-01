"""Value types of the LLM port: tasks, multimodal messages, requests and responses."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel


class LLMTask(StrEnum):
    """Every LLM use in the system. Each task is routed to models in ``config/llm.toml``."""

    QUERY_UNDERSTANDING = "query_understanding"
    ER_JUDGE = "er_judge"
    CLAIM_EXTRACTION = "claim_extraction"
    TEXT_NORMALIZATION = "text_normalization"
    VISION_TAGGING = "vision_tagging"
    REVIEW_SUMMARY = "review_summary"
    EXPLANATION = "explanation"


VISION_TASKS = frozenset({LLMTask.ER_JUDGE, LLMTask.VISION_TAGGING})


class Role(StrEnum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


@dataclass(frozen=True, slots=True)
class TextPart:
    text: str


@dataclass(frozen=True, slots=True)
class ImagePart:
    data: bytes
    media_type: str

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.data).hexdigest()


type Part = TextPart | ImagePart


@dataclass(frozen=True, slots=True)
class Message:
    role: Role
    parts: tuple[Part, ...]

    @classmethod
    def system(cls, text: str) -> Message:
        return cls(Role.SYSTEM, (TextPart(text),))

    @classmethod
    def user(cls, *parts: Part | str) -> Message:
        return cls(Role.USER, tuple(TextPart(p) if isinstance(p, str) else p for p in parts))

    @property
    def text(self) -> str:
        return "".join(part.text for part in self.parts if isinstance(part, TextPart))

    @property
    def images(self) -> tuple[ImagePart, ...]:
        return tuple(part for part in self.parts if isinstance(part, ImagePart))


@dataclass(frozen=True, slots=True)
class LLMRequest[T: BaseModel]:
    """A structured-output request. The model is chosen by routing, never by the caller."""

    task: LLMTask
    prompt_id: str
    prompt_version: str
    messages: tuple[Message, ...]
    output_schema: type[T]
    max_output_tokens: int | None = None


class UsageSource(StrEnum):
    REPORTED = "reported"
    ESTIMATED = "estimated"


@dataclass(frozen=True, slots=True)
class TokenUsage:
    """Token counts. ``output_tokens`` includes reasoning tokens (OpenAI convention)."""

    input_tokens: int
    output_tokens: int
    cached_input_tokens: int = 0
    reasoning_tokens: int = 0
    source: UsageSource = UsageSource.REPORTED

    @classmethod
    def zero(cls) -> TokenUsage:
        return cls(0, 0)


@dataclass(frozen=True, slots=True)
class JobContext:
    """The job an LLM call is charged to."""

    job_id: str
    budget_usd: Decimal


@dataclass(frozen=True, slots=True)
class LLMResponse[T: BaseModel]:
    value: T
    model: str
    usage: TokenUsage
    cost_usd: Decimal
    cache_hit: bool
    attempts: int
    latency_ms: int
