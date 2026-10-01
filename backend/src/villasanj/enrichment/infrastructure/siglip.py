"""Local SigLIP 2 zero-shot photo tags (M9): one sigmoid score per tag prompt, pinned weights.

The prompts are embedded once; each image batch is embedded and compared with them exactly as
the model's own forward pass does (normalised embeddings, learned scale and bias, sigmoid). Runs
on Apple MPS when available. torch and transformers are imported lazily (the ``ml`` group).
"""

from __future__ import annotations

import asyncio
import io
from collections.abc import Sequence
from typing import Any

from PIL import Image, UnidentifiedImageError

from villasanj.enrichment.domain.photo_tags import PROMPT_VERSION, PROMPTS, PhotoTag

DEFAULT_MODEL = "google/siglip2-base-patch16-224"
DEFAULT_REVISION = "75de2d55ec2d0b4efc50b3e9ad70dba96a7b2fa2"  # Hugging Face commit, 2025-02-21
TEXT_LENGTH = 64  # SigLIP was trained with text padded to 64 tokens


class SigLip2Tagger:
    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        revision: str = DEFAULT_REVISION,
        device: str | None = None,
    ) -> None:
        self._model_name = model
        self._revision = revision
        self._device = device
        self._torch: Any = None
        self._model: Any = None
        self._processor: Any = None
        self._text: Any = None
        self._tags = list(PROMPTS)

    @property
    def model_id(self) -> str:
        return f"{self._model_name}@{self._revision[:12]}#prompts-{PROMPT_VERSION}"

    async def scores(self, images: Sequence[bytes]) -> list[dict[PhotoTag, float] | None]:
        return await asyncio.to_thread(self._scores, images)

    def _load(self) -> None:
        import torch
        from transformers import AutoModel, AutoProcessor

        self._torch = torch
        if self._device is None:
            self._device = "mps" if torch.backends.mps.is_available() else "cpu"
        self._model = (
            AutoModel.from_pretrained(self._model_name, revision=self._revision)
            .to(self._device)
            .eval()
        )
        processor_type: Any = AutoProcessor  # untyped in transformers
        self._processor = processor_type.from_pretrained(self._model_name, revision=self._revision)
        texts = self._processor(
            text=[PROMPTS[tag] for tag in self._tags],
            padding="max_length",
            max_length=TEXT_LENGTH,
            return_tensors="pt",
        ).to(self._device)
        with torch.inference_mode():
            text = self._model.get_text_features(**texts)
        self._text = torch.nn.functional.normalize(_tensor(text), dim=-1)

    def _scores(self, images: Sequence[bytes]) -> list[dict[PhotoTag, float] | None]:
        if self._model is None:
            self._load()
        pictures = [_picture(image) for image in images]
        readable = [p for p in pictures if p is not None]
        rows: list[list[float]] = []
        if readable:
            torch = self._torch
            inputs = self._processor(images=readable, return_tensors="pt").to(self._device)
            with torch.inference_mode():
                image = torch.nn.functional.normalize(
                    _tensor(self._model.get_image_features(**inputs)), dim=-1
                )
                logits = (
                    image @ self._text.T * self._model.logit_scale.exp() + self._model.logit_bias
                )
                rows = torch.sigmoid(logits).cpu().tolist()
        produced = iter(rows)
        return [
            dict(zip(self._tags, next(produced), strict=True)) if p is not None else None
            for p in pictures
        ]


def _tensor(output: Any) -> Any:
    """``get_*_features`` gives a tensor or, in newer releases, an output holding the pooled one."""
    return getattr(output, "pooler_output", output)


def _picture(image: bytes) -> Image.Image | None:
    try:
        with Image.open(io.BytesIO(image)) as picture:
            return picture.convert("RGB")
    except (UnidentifiedImageError, OSError):
        return None
