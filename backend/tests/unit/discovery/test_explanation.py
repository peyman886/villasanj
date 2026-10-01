"""Explanations: facts by code, prose by the LLM around slots, verifier, retry, template."""

import hashlib
from datetime import date
from decimal import Decimal
from typing import Any

from tests.fakes.llm import NOW
from tests.unit.pricing.test_quote import FINAL, ask, listing, night
from villasanj.discovery.application import explanation
from villasanj.discovery.application.explanation import (
    ExplainChoice,
    ExplanationOut,
    Slots,
    Source,
    build_slots,
    check,
    template_only,
)
from villasanj.discovery.domain.ranking import Candidate, Caution, Ranked, Requirements, rank
from villasanj.enrichment.domain.features import Feature, FeatureEvidence
from villasanj.pricing.domain.offer import Offer
from villasanj.pricing.domain.quote import quote_stay
from villasanj.shared.application.llm.types import (
    JobContext,
    LLMRequest,
    LLMResponse,
    LLMTask,
    TokenUsage,
)
from villasanj.shared.domain.money import Money, MoneyRange
from villasanj.shared.domain.slots import ViolationCode

# A prompt change needs a new version, so answers cached for the old prompt are not reused.
PINNED = {"3": "98b8b35b62eb08fab11ed8ead7af0b6ccafd7514de3c7eb053a31cb2eae9bb30"}
CTX = JobContext("job", Decimal(1))
ZWNJ = "\N{ZERO WIDTH NON-JOINER}"
REQUEST = ask()
OFFER = Offer(
    quote_stay(
        listing(rating_avg=4.8, rating_count=120),
        [night(REQUEST.stay.check_in), night(date(2026, 10, 16))],
        REQUEST,
        FINAL,
    ),
    NOW,
)
LISTING = listing(rating_avg=4.8, rating_count=120)


def ranked_pair() -> tuple[Ranked, ...]:
    total = OFFER.quote.total
    assert total is not None
    dearer = MoneyRange.exact(Money.from_rial(total.low.amount_rial * 2))
    ranking = rank(
        [
            Candidate("a", total, True, 6, 2, 4.8, {Feature.POOL: FeatureEvidence.LISTED}),
            Candidate("b", dearer, True, 6, 2, 4.0, {Feature.POOL: FeatureEvidence.LISTED}),
        ],
        Requirements(
            nights=REQUEST.stay.night_count, guests=REQUEST.guests.value, features=(Feature.POOL,)
        ),
    )
    return ranking.results


def slots() -> Slots:
    top, second = ranked_pair()
    return build_slots(
        top,
        second,
        OFFER,
        LISTING,
        "پلتفرم",
        REQUEST.stay,
        REQUEST.guests.value,
        [Feature.POOL],
        NOW,
    )


def test_prompt_changes_require_a_version_bump() -> None:
    text = explanation.SYSTEM_PROMPT + explanation.RETRY_TEMPLATE
    digest = hashlib.sha256(text.encode()).hexdigest()
    assert PINNED.get(explanation.EXPLAIN_PROMPT_VERSION) == digest, (
        "the explanation prompt changed: bump EXPLAIN_PROMPT_VERSION and pin the new hash"
    )


def test_facts_are_formatted_by_code_and_the_template_passes_the_verifier() -> None:
    built = slots()
    texts = [f.text for f in built.facts.values()]
    assert any(t.endswith("تومان") for t in texts)
    assert "۴٫۸ از ۵ با ۱۲۰ رأی" in texts
    assert any("در آخرین مشاهده آزاد بود (کمتر از یک ساعت پیش)" in t for t in texts)
    assert any(t.startswith("استخر در فهرست امکانات") for t in texts)
    assert built.comparisons["C1"].relation == "cheaper"
    assert check(built.template, built) == []
    rendered = template_only(built)
    assert "{" not in rendered.text
    assert "C1" in rendered.used


class ScriptedClient:
    def __init__(self, *texts: str) -> None:
        self.texts = list(texts)
        self.requests: list[LLMRequest[Any]] = []

    async def generate(
        self, request: LLMRequest[Any], ctx: JobContext, *, model: str | None = None
    ) -> LLMResponse[Any]:
        self.requests.append(request)
        value = ExplanationOut(text=self.texts.pop(0))
        return LLMResponse(value, "model-a", TokenUsage(500, 120), Decimal("0.002"), False, 1, 900)


GOOD = "این ویلا با {F3} برای {F1} انتخاب شد و {F6}."


async def test_a_verified_llm_text_is_rendered() -> None:
    client = ScriptedClient(GOOD)
    result = await ExplainChoice(client).explain("ویلا با استخر", slots(), CTX)
    assert (result.source, result.retried) == (Source.LLM, False)
    assert "{" not in result.rendered.text
    (request,) = client.requests
    assert request.task is LLMTask.EXPLANATION
    assert "F1: the stay = " in request.messages[-1].text


async def test_digits_or_too_few_facts_are_retried_then_replaced_by_the_template() -> None:
    client = ScriptedClient("این ویلا ۲ خوابه و {F1} است", "یک ویلای خوب و {F1}.")
    result = await ExplainChoice(client).explain("ویلا", slots(), CTX)
    assert (result.source, result.retried) == (Source.TEMPLATE, True)
    assert result.rendered.text == template_only(slots()).text
    assert result.cost_usd == Decimal("0.004")
    feedback = client.requests[1].messages[-1].text
    assert "digit_outside_slot" in feedback
    assert "too_few_facts" in feedback


async def test_a_fixed_retry_is_used() -> None:
    client = ScriptedClient(f"{{F1}} ارزان{ZWNJ}تر است", GOOD)
    result = await ExplainChoice(client).explain("ویلا", slots(), CTX)
    assert (result.source, result.retried) == (Source.LLM, True)
    codes = [v.code for v in check(f"{{F1}} ارزان{ZWNJ}تر است", slots())]
    assert ViolationCode.COMPARATIVE_OUTSIDE_SLOT in codes


def test_missing_facts_are_left_out_and_cautions_are_said() -> None:
    bare = Ranked(
        Candidate("x", None, True, None, None, None, {}),
        0,
        0.0,
        (),
        frozenset({Caution.PRICE_UNKNOWN, Caution.FEATURE_UNCONFIRMED}),
        None,
    )
    unknown = listing()  # no rating
    no_price = Offer(quote_stay(unknown, [], REQUEST, FINAL), NOW)
    with_feature = build_slots(
        bare, None, no_price, unknown, "پلتفرم", REQUEST.stay, None, [Feature.POOL], NOW
    )
    texts = [f.text for f in with_feature.facts.values()]
    assert "استخر تأیید نشد" in texts
    assert "قیمت این اقامت معلوم نیست" in texts
    assert not any("یکی از امکانات" in t for t in texts)  # said once, by the feature fact
    assert with_feature.comparisons == {}
    assert check(with_feature.template, with_feature) == []
    without = build_slots(bare, None, no_price, unknown, "پلتفرم", REQUEST.stay, None, [], NOW)
    assert any("یکی از امکانات" in f.text for f in without.facts.values())


def test_the_availability_fact_says_how_old_the_observation_is() -> None:
    top, second = ranked_pair()
    for age_hours, said in ((9, "۹ ساعت پیش"), (72, "۳ روز پیش")):
        nights = [night(REQUEST.stay.check_in, age_hours=age_hours), night(date(2026, 10, 16))]
        old = Offer(quote_stay(LISTING, nights, REQUEST, FINAL), NOW)
        built = build_slots(top, second, old, LISTING, "پلتفرم", REQUEST.stay, 4, [], NOW)
        assert any(f"آزاد بود ({said})" in f.text for f in built.facts.values())
