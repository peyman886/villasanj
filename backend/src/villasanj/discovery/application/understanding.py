"""Query understanding: a Persian search query becomes a verified ``SearchIntent`` (ROADMAP M8).

Built ahead of M8 and provisional: the model, the prompt and the field set are settled by the M8
eval (50 hand-written queries). The LLM fills the intent; the deterministic verifier checks it
(numbers said, places verbatim, dates complete). A broken rule gets one retry with the violations
spelled out; whatever is still broken is dropped, never kept, and the caller can ask the user.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

from villasanj.discovery.application.intent import (
    SearchIntent,
    drop_violations,
    verify_intent,
)
from villasanj.shared.application.llm.ports import LLMClient
from villasanj.shared.application.llm.types import (
    JobContext,
    LLMRequest,
    LLMTask,
    Message,
    Role,
    TextPart,
)
from villasanj.shared.domain.slots import Violation

QUERY_PROMPT_ID = "query_understanding"
QUERY_PROMPT_VERSION = "2"  # bump whenever SYSTEM_PROMPT or RETRY_TEMPLATE changes (a test pins it)

SYSTEM_PROMPT = """\
You turn a Persian villa-rental search query (Iran, northern provinces) into a JSON search intent.
Dates are Jalali and money is toman. Leave out everything the query does not say.

Numbers
- Write a number only when the query says that number, in digits or in words, and copy it as said:
  «زیر ۵ میلیون» is budget.max_toman 5000000; «دو ساعت و نیم» is max_drive {value 2.5, unit hours};
  «۹۰ دقیقه» is max_drive {value 90, unit minutes}; «سه شب» is nights 3.
- Never compute, convert or add up numbers. List each group part as said: «۴ بزرگسال و ۲ بچه» is
  guest_parts [4, 2]. A group size said only in words is party: alone is "solo", a couple
  («من و همسرم», «زوج») is "couple".
- budget.basis is per_night for «شبی» or «هر شب», whole_stay when the query says the total, else
  unknown.

Dates: name the expression, never write a date you computed.
- kind: tonight «امشب», tomorrow «فردا», day_after_tomorrow «پس\N{ZERO WIDTH NON-JOINER}فردا»,
  weekday (with weekday, e.g. «پنجشنبه» thursday), weekend «آخر هفته»,
  jalali_day («۱۵ مهر»: month 7, day 15), jalali_month («آبان»: month 8), nowruz «نوروز»,
  next_holiday «تعطیلات بعدی».
- which: this, next («هفته بعد»), after_next. year only when the query says it.
- Jalali months: فروردین 1, اردیبهشت 2, خرداد 3, تیر 4, مرداد 5, شهریور 6, مهر 7, آبان 8, آذر 9,
  دی 10, بهمن 11, اسفند 12.

Places: names of the destination (city, village, area) exactly as written in the query. The origin
of a drive limit («از تهران») is not a place, and neither is «دریا» or «جنگل».

Features the villa should have, as codes: pool «استخر», jacuzzi «جکوزی», near_sea «نزدیک دریا» or
«ساحلی», sea_view «ویو دریا», forest «جنگلی», fireplace «شومینه», parking «پارکینگ»,
barbecue «باربیکیو»."""

RETRY_TEMPLATE = """\
Your answer broke these rules:
{violations}
Answer again: fix each value so it is exactly what the query says, or leave the field out."""


def understanding_request(query: str) -> LLMRequest[SearchIntent]:
    return LLMRequest(
        task=LLMTask.QUERY_UNDERSTANDING,
        prompt_id=QUERY_PROMPT_ID,
        prompt_version=QUERY_PROMPT_VERSION,
        messages=(Message.system(SYSTEM_PROMPT), Message.user(f"Query: {query}")),
        output_schema=SearchIntent,
    )


def retry_request(
    query: str, answer: SearchIntent, violations: Sequence[Violation]
) -> LLMRequest[SearchIntent]:
    listed = "\n".join(f"- {v.code}: {v.detail}" for v in violations)
    first = understanding_request(query)
    return LLMRequest(
        task=first.task,
        prompt_id=first.prompt_id,
        prompt_version=first.prompt_version,
        messages=(
            *first.messages,
            Message(Role.ASSISTANT, (TextPart(answer.model_dump_json(exclude_none=True)),)),
            Message.user(RETRY_TEMPLATE.format(violations=listed)),
        ),
        output_schema=SearchIntent,
    )


@dataclass(frozen=True, slots=True)
class Understanding:
    query: str
    intent: SearchIntent  # verified: nothing in it breaks a rule
    retried: bool
    dropped: tuple[str, ...]  # fields removed because they still broke a rule after the retry
    models: tuple[str, ...]
    cost_usd: Decimal
    latency_ms: int = 0  # all calls together (a cache hit is near zero)
    cache_hit: bool = False  # the first answer came from the cache


class UnderstandQuery:
    def __init__(self, client: LLMClient, queries: Sequence[str] = ()) -> None:
        self._client = client
        self._queries = tuple(queries)

    def plan(self) -> list[LLMRequest[SearchIntent]]:
        """The first request per query (a retry, when needed, is at most one more each)."""
        return [understanding_request(q) for q in self._queries]

    async def run(self, query: str, ctx: JobContext) -> Understanding:
        response = await self._client.generate(understanding_request(query), ctx)
        models, cost, latency = [response.model], response.cost_usd, response.latency_ms
        intent, retried = response.value, False
        violations = verify_intent(intent, query)
        if violations:
            again = await self._client.generate(retry_request(query, intent, violations), ctx)
            intent, retried = again.value, True
            models.append(again.model)
            cost += again.cost_usd
            latency += again.latency_ms
        kept, dropped = drop_violations(intent, query)
        return Understanding(
            query, kept, retried, dropped, tuple(models), cost, latency, response.cache_hit
        )
