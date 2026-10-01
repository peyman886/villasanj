"""The gray-zone judge: requests, verdict schema, grids, and the prompt-version pin."""

import hashlib
import io
from collections.abc import Sequence
from decimal import Decimal
from typing import Any, cast

import pytest
from PIL import Image
from pydantic import BaseModel, ValidationError

from tests.fakes.er import ListingsFake
from tests.unit.entity_resolution.test_application import J1, S1, S4
from tests.unit.entity_resolution.test_scoring_support import NO_EVIDENCE
from villasanj.catalog.domain.listing import ListingId
from villasanj.entity_resolution.application import judge
from villasanj.entity_resolution.application.judge import (
    JudgeInput,
    JudgePairs,
    JudgeVerdict,
    judge_request,
)
from villasanj.entity_resolution.domain.pairs import PairKey
from villasanj.entity_resolution.infrastructure.grid import COLUMNS, TILE, PillowGridRenderer
from villasanj.shared.application.llm.types import (
    ImagePart,
    JobContext,
    LLMRequest,
    LLMResponse,
    LLMTask,
    TextPart,
    TokenUsage,
)

# A prompt change needs a new version, so answers cached for the old prompt are not reused.
PINNED = {"1": "63be30234a1d131d68ce6cf687e0afe801ebd6d5fbe6c7a1da056d8dae26092b"}


def test_prompt_changes_require_a_version_bump() -> None:
    digest = hashlib.sha256((judge.SYSTEM_PROMPT + judge.FACTS_TEMPLATE).encode()).hexdigest()
    assert PINNED.get(judge.JUDGE_PROMPT_VERSION) == digest, (
        "the judge prompt changed: bump JUDGE_PROMPT_VERSION and pin the new hash"
    )


def jpeg(color: tuple[int, int, int], size: tuple[int, int] = (800, 600)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, color).save(buffer, "JPEG")
    return buffer.getvalue()


def test_grid_tiles_photos_in_order_without_cropping_and_is_deterministic() -> None:
    renderer = PillowGridRenderer()
    photos = [jpeg((200, 0, 0)), jpeg((0, 200, 0), (300, 900)), b"broken", jpeg((0, 0, 200))]
    grid = renderer.render(photos)
    assert grid == renderer.render(photos)
    with Image.open(io.BytesIO(grid)) as image:
        assert image.size == (TILE[0] * COLUMNS, TILE[1])  # three readable photos: one row
        red, _, _ = cast(tuple[int, int, int], image.getpixel((10, 10)))
        assert red > 150  # the first tile is the red photo
    with Image.open(io.BytesIO(renderer.render([]))) as empty:
        assert empty.size == (TILE[0] * COLUMNS, TILE[1])


def test_request_anonymises_platforms_and_sends_two_grids() -> None:
    request = judge_request(J1, S4, NO_EVIDENCE, b"grid-a", b"grid-b")
    assert (request.task, request.prompt_id) == (LLMTask.ER_JUDGE, "er_judge")
    (_, user) = request.messages
    texts = [p.text for p in user.parts if isinstance(p, TextPart)]
    images = [p for p in user.parts if isinstance(p, ImagePart)]
    assert [i.data for i in images] == [b"grid-a", b"grid-b"]
    assert "Listing A" in texts[0]
    assert "Listing B" in texts[0]
    assert "jabama" not in texts[0]
    assert "shab" not in texts[0]
    assert "at least 250 m apart" in texts[0]


@pytest.mark.parametrize(
    "payload",
    [
        {"verdict": "maybe", "confidence": 0.5, "evidence": [], "rationale": "x"},
        {"verdict": "match", "confidence": 1.5, "evidence": [], "rationale": "x"},
        {"verdict": "match", "confidence": 0.9, "evidence": ["vibes"], "rationale": "x"},
        {"verdict": "match", "confidence": 0.9, "evidence": [], "rationale": "x", "extra": 1},
    ],
)
def test_invalid_verdicts_are_rejected(payload: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        JudgeVerdict.model_validate(payload)


class Photos:
    async def photos(self, listing: ListingId, limit: int) -> list[bytes]:
        return [jpeg((10, 10, 10))] * min(limit, 2)


class ScriptedClient:
    def __init__(self) -> None:
        self.requests: list[LLMRequest[Any]] = []

    async def generate(
        self, request: LLMRequest[Any], ctx: JobContext, *, model: str | None = None
    ) -> LLMResponse[Any]:
        self.requests.append(request)
        value = request.output_schema.model_validate(
            {
                "verdict": "unsure",
                "confidence": 0.4,
                "evidence": ["shared_complex_photos"],
                "rationale": "pool only",
            }
        )
        usage = TokenUsage(input_tokens=2300, output_tokens=60)
        return LLMResponse(
            cast(BaseModel, value), "fake-judge", usage, Decimal("0.001"), False, 1, 5
        )


async def test_run_judges_each_pair_and_skips_listings_no_longer_in_the_catalog() -> None:
    reader = ListingsFake([J1, S1])
    client = ScriptedClient()
    pairs = JudgePairs(reader, Photos(), PillowGridRenderer(), client)
    inputs: Sequence[JudgeInput] = [
        JudgeInput(PairKey.of(J1.id, S1.id), NO_EVIDENCE),
        JudgeInput(PairKey.of(J1.id, ListingId("shab", "gone")), NO_EVIDENCE),
    ]
    assert len(await pairs.requests(inputs)) == 1
    (judgement,) = await pairs.run(inputs, JobContext("job", Decimal("1")))
    assert judgement.key == PairKey.of(J1.id, S1.id)
    assert judgement.verdict.verdict == "unsure"
    assert judgement.model == "fake-judge"
    assert len(client.requests) == 1
