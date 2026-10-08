"""The vision model as a photo tagger for sea view and fireplace (scores, selection, prompt pin)."""

import hashlib
from decimal import Decimal
from typing import Any

from tests.fakes.ingestion import InMemoryBlobStore
from tests.fakes.llm import FixedClock
from tests.unit.catalog.test_reports import listing
from villasanj.enrichment.application import photo_vlm
from villasanj.enrichment.application.photo_tags import TagScore
from villasanj.enrichment.application.photo_vlm import (
    PhotoVerdict,
    TagCall,
    TagPhotosWithVlm,
    claims_a_tag,
    media_type,
    model_id,
    score,
)
from villasanj.enrichment.domain.photo_tags import PhotoTag
from villasanj.shared.application.errors import LLMUnavailable
from villasanj.shared.application.llm.types import (
    ImagePart,
    JobContext,
    LLMRequest,
    LLMResponse,
    TokenUsage,
)

PINNED = {"1": "962e82916993d23708b6c3eaa43599d9f2585bb20f9d80694730481a3b808562"}
CTX = JobContext("job", Decimal(1))
JPEG = b"\xff\xd8\xff\xe0" + b"jpeg-bytes"
NOT_AN_IMAGE = b"<html>gone</html>"


def test_prompt_changes_require_a_version_bump() -> None:
    digest = hashlib.sha256((photo_vlm.SYSTEM_PROMPT + photo_vlm.QUESTION).encode()).hexdigest()
    assert PINNED.get(photo_vlm.VLM_PROMPT_VERSION) == digest, (
        "the vision prompt changed: bump VLM_PROMPT_VERSION and pin the new hash"
    )


def test_media_types_come_from_the_bytes() -> None:
    assert media_type(JPEG) == "image/jpeg"
    assert media_type(b"\x89PNG\r\n\x1a\n...") == "image/png"
    assert media_type(b"RIFF\x00\x00\x00\x00WEBPVP8 ") == "image/webp"
    assert media_type(NOT_AN_IMAGE) is None


def test_a_score_ranks_a_confident_yes_highest_and_a_confident_no_lowest() -> None:
    assert score(TagCall(visible=True, confidence=1.0)) == 1.0
    assert score(TagCall(visible=False, confidence=1.0)) == 0.0
    assert score(TagCall(visible=True, confidence=0.2)) > score(
        TagCall(visible=False, confidence=0.2)
    )


def test_only_a_villa_s_own_claim_asks_the_photos() -> None:
    assert claims_a_tag(listing("a", description="ویلا با ویو دریا و شومینه")) == {
        PhotoTag.SEA_VIEW,
        PhotoTag.FIREPLACE,
    }
    assert claims_a_tag(listing("b", description="ویلا با استخر")) == frozenset()


class Client:
    def __init__(self, fail: bool = False) -> None:
        self.requests: list[LLMRequest[Any]] = []
        self.fail = fail

    async def generate(
        self, request: LLMRequest[Any], ctx: JobContext, *, model: str | None = None
    ) -> LLMResponse[Any]:
        self.requests.append(request)
        if self.fail:
            raise LLMUnavailable("no credit")
        verdict = PhotoVerdict(
            sea_view=TagCall(visible=True, confidence=0.9),
            fireplace=TagCall(visible=False, confidence=0.8),
        )
        return LLMResponse(verdict, "m", TokenUsage(1200, 40), Decimal("0.0001"), False, 1, 5)


class Scores:
    def __init__(self) -> None:
        self.rows: list[TagScore] = []

    async def scored(self, model: str) -> set[str]:
        return {r.sha256 for r in self.rows if r.model == model}

    async def save(self, rows: list[TagScore]) -> None:
        self.rows.extend(rows)

    async def scores(self, model: str) -> dict[str, dict[PhotoTag, float]]:
        return {}


async def test_each_readable_photo_is_asked_once_and_stored_under_the_model_id() -> None:
    blobs, store, client = InMemoryBlobStore(), Scores(), Client()
    image = (await blobs.put(JPEG)).key
    broken = (await blobs.put(NOT_AN_IMAGE)).key
    tagger = TagPhotosWithVlm(client, blobs, store, FixedClock(), "vision-model")  # type: ignore[arg-type]
    report = await tagger.run([image, broken, image], CTX)
    assert (report.photos, report.scored, report.unreadable, report.failed) == (2, 1, 1, 0)
    assert {(r.tag, round(r.score, 6)) for r in store.rows} == {
        (PhotoTag.SEA_VIEW, 0.95),
        (PhotoTag.FIREPLACE, 0.1),
    }
    assert {r.model for r in store.rows} == {model_id("vision-model")}
    (request,) = client.requests
    assert isinstance(request.messages[1].parts[1], ImagePart)
    again = await tagger.run([image], CTX)
    assert (again.already_scored, len(client.requests)) == (1, 1)  # never asked twice


async def test_a_failed_call_is_counted_and_nothing_is_guessed() -> None:
    blobs, store = InMemoryBlobStore(), Scores()
    image = (await blobs.put(JPEG)).key
    tagger = TagPhotosWithVlm(Client(fail=True), blobs, store, FixedClock(), "m")  # type: ignore[arg-type]
    report = await tagger.run([image], CTX)
    assert (report.scored, report.failed, store.rows) == (0, 1, [])
