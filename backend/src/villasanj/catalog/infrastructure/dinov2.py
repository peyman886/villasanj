"""Local DINOv2 image embeddings (ADR-0012): instance-level features, pinned weights.

The whole image is resized to 224x224 (no centre crop, so nothing at the borders is lost) and
normalised with ImageNet statistics; the CLS token, L2-normalised, is the embedding. Runs on Apple
MPS when available, otherwise on CPU. torch and transformers are imported lazily: they live in the
``ml`` dependency group, which the API image does not install.
"""

from __future__ import annotations

import asyncio
import io
from collections.abc import Sequence
from typing import Any

import numpy as np
from PIL import Image, UnidentifiedImageError

DEFAULT_MODEL = "facebook/dinov2-small"
DEFAULT_REVISION = "ed25f3a31f01632728cabb09d1542f84ab7b0056"  # Hugging Face commit, 2026-10-01
INPUT_SIZE = 224
_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)


class DinoV2Embedder:
    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        revision: str = DEFAULT_REVISION,
        device: str | None = None,
    ) -> None:
        self._model_name = model
        self._revision = revision
        self._device = device
        self._model: Any = None
        self._torch: Any = None

    @property
    def model_id(self) -> str:
        return f"{self._model_name}@{self._revision[:12]}"

    async def embed(self, images: Sequence[bytes]) -> list[tuple[float, ...] | None]:
        return await asyncio.to_thread(self._embed, images)

    def _load(self) -> None:
        import torch
        from transformers import AutoModel

        self._torch = torch
        if self._device is None:
            self._device = "mps" if torch.backends.mps.is_available() else "cpu"
        model = AutoModel.from_pretrained(self._model_name, revision=self._revision)
        self._model = model.to(self._device).eval()

    def _embed(self, images: Sequence[bytes]) -> list[tuple[float, ...] | None]:
        if self._model is None:
            self._load()
        arrays: list[np.ndarray | None] = [_pixels(image) for image in images]
        readable = [a for a in arrays if a is not None]
        vectors: list[tuple[float, ...]] = []
        if readable:
            batch = self._torch.from_numpy(np.stack(readable).transpose(0, 3, 1, 2))
            with self._torch.inference_mode():
                output = self._model(pixel_values=batch.to(self._device))
                cls = self._torch.nn.functional.normalize(output.last_hidden_state[:, 0, :], dim=-1)
            vectors = [tuple(float(x) for x in row) for row in cls.cpu().numpy()]
        produced = iter(vectors)
        return [next(produced) if a is not None else None for a in arrays]


def _pixels(image: bytes) -> np.ndarray | None:
    try:
        with Image.open(io.BytesIO(image)) as picture:
            rgb = picture.convert("RGB").resize((INPUT_SIZE, INPUT_SIZE), Image.Resampling.BICUBIC)
    except (UnidentifiedImageError, OSError):
        return None
    return ((np.asarray(rgb, dtype=np.float32) / 255.0 - _MEAN) / _STD).astype(np.float32)
