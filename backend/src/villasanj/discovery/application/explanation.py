"""Why the first result fits: a short Persian explanation built on fact slots (ROADMAP M10).

Built ahead of M10 and provisional. Code computes and formats every fact (price, price per person
and night, rating, the evidence for each requested feature, the stay, the cautions) and decides
the direction of every comparison; the LLM only writes prose around ``{F1}``/``{C1}`` slots. The
ADR-0007 verifier rejects digits, money words and measurable comparatives outside slots, and an
explanation must use at least two facts. One retry carries the violations; after that a
deterministic template is rendered instead, so a wrong number can never be shown.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from villasanj.catalog.domain.listing import Listing
from villasanj.discovery.domain.dates import describe_fa
from villasanj.discovery.domain.ranking import Caution, Ranked
from villasanj.enrichment.domain.features import Feature, FeatureEvidence
from villasanj.pricing.domain.offer import Offer
from villasanj.shared.application.llm.ports import LLMClient
from villasanj.shared.application.llm.types import (
    JobContext,
    LLMRequest,
    LLMTask,
    Message,
    Role,
    TextPart,
)
from villasanj.shared.domain.fa_format import fa_decimal, fa_int, fa_toman
from villasanj.shared.domain.persian_text import ZWNJ
from villasanj.shared.domain.provenance import Provenance, ProvenanceMethod
from villasanj.shared.domain.slots import (
    SLOT,
    Comparison,
    Fact,
    Relation,
    RenderedText,
    Violation,
    ViolationCode,
    render,
    verify_text,
)
from villasanj.shared.domain.stay import DateRange

EXPLAIN_PROMPT_ID = "explain_choice"
EXPLAIN_PROMPT_VERSION = "3"  # bump whenever SYSTEM_PROMPT or RETRY_TEMPLATE changes (pinned)
MIN_SLOTS = 2
HOURS_SHOWN_AS_HOURS = 48

SYSTEM_PROMPT = """\
You explain in Persian, in two or three short sentences, why the first search result fits the
traveller's request. You get facts and comparisons as slots: write their ids in braces, like {F1}
or {C1}, never their values.
Rules:
- No digits, no prices or money words, and no measurable comparisons such as cheaper, closer,
  bigger or more outside slots: the slots carry every number and every comparison.
- Use only the facts given, and at least two of them. If a caution is given, say it plainly and
  without blame.
- Availability and prices are observations, not promises: when you mention them, use the facts
  that say when they were observed.
- A slot marked "a whole clause" is a complete clause: give it its own sentence or put it after «؛»,
  and do not wrap it in words such as «طبق» or «بر اساس».
- Do not praise beyond the facts: no "the best", no "perfect"."""

RETRY_TEMPLATE = """\
Your text broke these rules:
{violations}
Write it again with the same facts."""

FEATURE_FA: dict[Feature, str] = {
    Feature.POOL: "استخر",
    Feature.JACUZZI: "جکوزی",
    Feature.NEAR_SEA: "نزدیکی به دریا",
    Feature.SEA_VIEW: f"منظره{ZWNJ}ی دریا",
    Feature.FOREST: "طبیعت جنگلی",
    Feature.FIREPLACE: "شومینه",
    Feature.PARKING: "پارکینگ",
    Feature.BARBECUE: "باربیکیو",
}
EVIDENCE_FA: dict[FeatureEvidence, str] = {
    FeatureEvidence.LISTED: "در فهرست امکانات آگهی آمده است",
    FeatureEvidence.DESCRIBED: "فقط در توضیحات آگهی آمده و در فهرست امکانات نیست",
    FeatureEvidence.UNKNOWN: "تأیید نشد",
    FeatureEvidence.DENIED: "در آگهی رد شده است",
}
CAUTION_FA: dict[Caution, str] = {
    Caution.MAY_EXCEED_BUDGET: (
        f"هزینه{ZWNJ}های جانبی پلتفرم منتشر نشده و مبلغ نهایی ممکن است از بودجه بیشتر شود"
    ),
    Caution.CAPACITY_UNKNOWN: "ظرفیت آگهی منتشر نشده است",
    Caution.BEDROOMS_UNKNOWN: "تعداد اتاق خواب منتشر نشده است",
    Caution.PRICE_UNKNOWN: "قیمت این اقامت معلوم نیست",
    Caution.FEATURE_UNCONFIRMED: f"یکی از امکانات خواسته{ZWNJ}شده تأیید نشد",
    Caution.FEATURE_ONLY_DESCRIBED: f"یکی از امکانات خواسته{ZWNJ}شده فقط در توضیحات آگهی آمده است",
}


class ExplanationOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=700)


class Source(StrEnum):
    LLM = "llm"
    TEMPLATE = "template"  # the LLM text failed the verifier twice, or there was no LLM text


@dataclass(frozen=True, slots=True)
class Slots:
    facts: dict[str, Fact]
    comparisons: dict[str, Comparison]
    meanings: dict[str, str]  # what each slot is, in English, for the prompt
    template: str  # a deterministic explanation with the same slots


@dataclass(frozen=True, slots=True)
class Explanation:
    rendered: RenderedText
    slots: Slots
    source: Source
    retried: bool
    models: tuple[str, ...]
    cost_usd: Decimal


def build_slots(
    top: Ranked,
    runner_up: Ranked | None,
    offer: Offer,
    listing: Listing,
    platform_name: str,
    stay: DateRange,
    guests: int | None,
    features: Sequence[Feature],
    now: datetime,
) -> Slots:
    facts: dict[str, Fact] = {}
    comparisons: dict[str, Comparison] = {}
    meanings: dict[str, str] = {}
    parts: list[str] = []

    def fact(meaning: str, text: str, provenance: Provenance) -> str:
        slot = f"F{len(facts) + 1}"
        facts[slot] = Fact(slot, text, provenance)
        meanings[slot] = meaning
        return slot

    stay_slot = fact("the stay", describe_fa(stay), _derived(now, listing.provenance))
    # Quoted: a platform's name can be a common word («شب» is also "night").
    where = fact("the booking platform", f"«{platform_name}»", listing.provenance)
    if offer.quote.total is not None:
        total = fact(
            "the all-in price of the stay", fa_toman(offer.quote.total), offer.quote.provenance
        )
        parts.append(f"{{{total}}} برای {{{stay_slot}}} در {{{where}}}")
    if top.candidate.bookable:
        free = fact(
            "availability, as last observed (a whole clause)",
            f"همه{ZWNJ}ی شب{ZWNJ}ها در آخرین مشاهده آزاد بود ({_age_fa(offer)})",
            offer.quote.provenance,
        )
        parts.append(f"{{{free}}}")
    per_person = top.price_per_person_night_toman
    if per_person is not None and guests and offer.quote.total is not None:
        at_least = "" if offer.quote.total.is_exact else "حداقل "
        per = fact(
            "the price per person and night",
            f"{at_least}{fa_int(int(per_person))} تومان برای هر نفر در هر شب",
            _derived(now, offer.quote.provenance),
        )
        compared = ""
        theirs = runner_up.price_per_person_night_toman if runner_up else None
        if theirs is not None and theirs != per_person:
            relation = Relation.CHEAPER if per_person < theirs else Relation.PRICIER
            comparisons["C1"] = Comparison("C1", relation, _derived(now, offer.quote.provenance))
            meanings["C1"] = f"per person and night, {relation} than the second result"
            compared = f"، {{C1}} از گزینه{ZWNJ}ی دوم"
        parts.append(f"یعنی {{{per}}}{compared}")
    if listing.rating_avg is not None and listing.rating_count:
        rating = fact(
            "the guests' rating on the platform",
            f"{fa_decimal(listing.rating_avg)} از ۵ با {fa_int(listing.rating_count)} رأی",
            listing.provenance,
        )
        parts.append(f"امتیاز مهمان{ZWNJ}ها {{{rating}}} است")
    for feature in features:
        evidence = top.candidate.features.get(feature, FeatureEvidence.UNKNOWN)
        slot = fact(
            f"the evidence for the requested {feature} (a whole clause)",
            f"{FEATURE_FA[feature]} {EVIDENCE_FA[evidence]}",
            listing.provenance,
        )
        parts.append(f"{{{slot}}}")
    for caution in sorted(top.warnings):
        if caution in (Caution.FEATURE_UNCONFIRMED, Caution.FEATURE_ONLY_DESCRIBED) and features:
            continue  # already said by the feature facts
        slot = fact("a caution (a whole clause)", CAUTION_FA[caution], offer.quote.provenance)
        parts.append(f"{{{slot}}}")
    return Slots(facts, comparisons, meanings, "؛ ".join(parts) + ".")


def _age_fa(offer: Offer) -> str:
    hours = int(offer.age / timedelta(hours=1))
    if hours < 1:
        return "کمتر از یک ساعت پیش"
    if hours < HOURS_SHOWN_AS_HOURS:
        return f"{fa_int(hours)} ساعت پیش"
    return f"{fa_int(hours // 24)} روز پیش"


def _derived(now: datetime, *inputs: Provenance) -> Provenance:
    return Provenance(ProvenanceMethod.DERIVED, now, derived_from=tuple(inputs))


def explanation_request(query: str, slots: Slots) -> LLMRequest[ExplanationOut]:
    lines = [
        f"{slot}: {meaning} = {_value(slots, slot)}" for slot, meaning in slots.meanings.items()
    ]
    return LLMRequest(
        task=LLMTask.EXPLANATION,
        prompt_id=EXPLAIN_PROMPT_ID,
        prompt_version=EXPLAIN_PROMPT_VERSION,
        messages=(
            Message.system(SYSTEM_PROMPT),
            Message.user(f"Search: {query}\nSlots:\n" + "\n".join(lines)),
        ),
        output_schema=ExplanationOut,
    )


def _value(slots: Slots, slot: str) -> str:
    if slot in slots.facts:
        return slots.facts[slot].text
    return slots.comparisons[slot].text


def check(text: str, slots: Slots) -> list[Violation]:
    violations = verify_text(text, slots.facts, slots.comparisons)
    used = set(SLOT.findall(text)) & set(slots.facts)
    if len(used) < min(MIN_SLOTS, len(slots.facts)):
        violations.append(Violation(ViolationCode.TOO_FEW_FACTS, f"uses {len(used)}"))
    return violations


class ExplainChoice:
    def __init__(self, client: LLMClient) -> None:
        self._client = client

    async def explain(self, query: str, slots: Slots, ctx: JobContext) -> Explanation:
        request = explanation_request(query, slots)
        response = await self._client.generate(request, ctx)
        models, cost = [response.model], response.cost_usd
        text, retried = response.value.text, False
        violations = check(text, slots)
        if violations:
            listed = "\n".join(f"- {v.code}: {v.detail}" for v in violations)
            again = await self._client.generate(
                LLMRequest(
                    task=request.task,
                    prompt_id=request.prompt_id,
                    prompt_version=request.prompt_version,
                    messages=(
                        *request.messages,
                        Message(Role.ASSISTANT, (TextPart(text),)),
                        Message.user(RETRY_TEMPLATE.format(violations=listed)),
                    ),
                    output_schema=ExplanationOut,
                ),
                ctx,
            )
            models.append(again.model)
            cost += again.cost_usd
            text, retried = again.value.text, True
            violations = check(text, slots)
        if violations:
            rendered = render(slots.template, slots.facts, slots.comparisons)
            return Explanation(rendered, slots, Source.TEMPLATE, retried, tuple(models), cost)
        rendered = render(text, slots.facts, slots.comparisons)
        return Explanation(rendered, slots, Source.LLM, retried, tuple(models), cost)


def template_only(slots: Slots) -> RenderedText:
    """The deterministic explanation (no LLM), e.g. for a dry run or when the LLM is off."""
    return render(slots.template, slots.facts, slots.comparisons)
