"""The LLM residue for feature claims: verbatim quotes, one retry, rules first."""

import hashlib
from decimal import Decimal
from typing import Any

from villasanj.enrichment.application import claim_extraction
from villasanj.enrichment.application.claim_extraction import (
    ClaimOut,
    ClaimsOut,
    ReadClaim,
    ReadClaimsWithLLM,
    as_read,
    with_residue,
)
from villasanj.enrichment.domain.claim_eval import Stance
from villasanj.enrichment.domain.features import (
    Feature,
    Polarity,
    extract_claims,
    with_read_claims,
)
from villasanj.shared.application.llm.types import (
    JobContext,
    LLMRequest,
    LLMResponse,
    LLMTask,
    TokenUsage,
)

CTX = JobContext("job", Decimal(1))
TEXT = "ویلا با استخر، منظره ابدی دریا و جای پارک دو خودرو"
PINNED = {"1": ""}


class Scripted:
    def __init__(self, *answers: ClaimsOut) -> None:
        self.answers = list(answers)
        self.requests: list[LLMRequest[Any]] = []

    async def generate(
        self, request: LLMRequest[Any], ctx: JobContext, *, model: str | None = None
    ) -> LLMResponse[Any]:
        self.requests.append(request)
        usage = TokenUsage(input_tokens=400, output_tokens=50)
        return LLMResponse(self.answers.pop(0), "model-a", usage, Decimal("0.0002"), False, 1, 5)


def claims(*items: tuple[str, str, str]) -> ClaimsOut:
    return ClaimsOut(claims=[ClaimOut(feature=f, stance=s, quote=q) for f, s, q in items])


def test_prompt_changes_require_a_version_bump() -> None:
    text = claim_extraction.SYSTEM_PROMPT + claim_extraction.RETRY_TEMPLATE
    digest = hashlib.sha256(text.encode()).hexdigest()
    assert claim_extraction.CLAIM_PROMPT_VERSION == "1"
    assert digest == PINNED_DIGEST, "the claim prompt changed: bump the version and pin the hash"


PINNED_DIGEST = "a06c9dc6cf45c80789b865d3f9bf449caeff461c3da954b80d4b4a32582cae27"


async def test_verbatim_quotes_are_kept_with_one_call() -> None:
    client = Scripted(
        claims(("sea_view", "has", "منظره ابدی دریا"), ("parking", "has", "جای پارک"))
    )
    read = await ReadClaimsWithLLM(client).run(TEXT, CTX)
    assert [(c.feature, c.stance) for c in read.claims] == [
        (Feature.SEA_VIEW, Stance.HAS),
        (Feature.PARKING, Stance.HAS),
    ]
    assert (read.retried, read.dropped) == (False, 0)
    (request,) = client.requests
    assert request.task is LLMTask.CLAIM_EXTRACTION


async def test_a_quote_not_in_the_text_is_sent_back_once_then_dropped() -> None:
    invented = claims(("jacuzzi", "has", "جکوزی اختصاصی"))
    client = Scripted(invented, invented)
    read = await ReadClaimsWithLLM(client).run(TEXT, CTX)
    assert read.claims == ()
    assert (read.retried, read.dropped) == (True, 1)
    assert "جکوزی اختصاصی" in client.requests[1].messages[-1].text


def test_the_rules_keep_what_they_found_and_the_llm_fills_the_rest() -> None:
    rules = {Feature.POOL: Stance.HAS, Feature.PARKING: Stance.NONE}
    read = [
        ReadClaim(Feature.POOL, Stance.SHARED, "استخر"),  # the rules already said "has"
        ReadClaim(Feature.PARKING, Stance.SHARED, "جای پارک"),
        ReadClaim(Feature.PARKING, Stance.HAS, "جای پارک"),  # its own word first
    ]
    merged = with_residue(rules, read)
    assert (merged[Feature.POOL], merged[Feature.PARKING]) == (Stance.HAS, Stance.HAS)
    assert merged[Feature.FOREST] is Stance.NONE


def test_read_claims_join_the_rules_as_located_spans() -> None:
    text = "ویلا با استخر و از تراس دریا پیداست"
    read = [
        ReadClaim(Feature.SEA_VIEW, Stance.HAS, "از تراس دریا پیداست"),
        ReadClaim(Feature.POOL, Stance.HAS_NOT, "استخر"),  # the rules found the pool
        ReadClaim(Feature.FOREST, Stance.HAS, "جنگل"),  # not in the text: skipped
    ]
    merged = with_read_claims(extract_claims(text), as_read(read), text)
    by_feature = {c.feature: c for c in merged}
    assert by_feature[Feature.POOL].polarity is Polarity.HAS
    assert not by_feature[Feature.POOL].by_llm
    sea = by_feature[Feature.SEA_VIEW]
    assert sea.by_llm
    assert text[sea.start : sea.end] == "از تراس دریا پیداست"
    assert Feature.FOREST not in by_feature
