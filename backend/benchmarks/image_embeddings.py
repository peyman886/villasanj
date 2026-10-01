"""Image-embedding bake-off for entity resolution (evidence for ADR-0012).

Label-free copy-detection benchmark on our own crawled photos. Each query is a deterministic
transformation of a gallery photo (a platform-style 4:3 thumbnail crop, a 70% crop, a
recompressed downscale). A method is good for ER when

- the transformed photo retrieves its own original (recall@1), and
- at the similarity that keeps 95% of those true pairs, few photos of *other* listings score
  as high (cross-listing false-positive rate).

Methods: pHash (baseline), DINOv2 small/base (local), gemini-embedding-2 and
tongyi-embedding-vision-flash (AvalAI). API results are cached on disk, so reruns are free.

Run from ``backend/`` (needs the stack's database and blob store; ML packages are not project
dependencies until a local model wins):

    uv run --with torch --with transformers python benchmarks/image_embeddings.py
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import hashlib
import io
import json
import random
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
import imagehash
import numpy as np
from PIL import Image, ImageEnhance
from sqlalchemy import text

from villasanj.entrypoints.container import build_container
from villasanj.shared.infrastructure.settings import Settings

PHOTOS_SQL = text(
    """
    SELECT p.platform, p.external_id, p.sha256, s.blob_key
    FROM catalog.photo p JOIN ingestion.snapshot s ON s.id = p.snapshot_id
    ORDER BY p.sha256
    """
)
API_MAX_SIDE = 512
HTTP_OK = 200
TONGYI_INTERVAL_S = 0.9
LOAD_MAX_SIDE = 640
POSITIVE_RECALL = 0.95
DETERMINISM_SAMPLE = 10


@dataclass(frozen=True)
class Photo:
    listing: str
    sha256: str
    image: Image.Image


# ---------------------------------------------------------------- transformations


def _rng(photo: Photo, name: str) -> random.Random:
    seed = int(hashlib.sha256(f"{photo.sha256}:{name}".encode()).hexdigest(), 16)
    return random.Random(seed)  # noqa: S311 - reproducible sampling, not security


def _jpeg(image: Image.Image, quality: int) -> Image.Image:
    buffer = io.BytesIO()
    image.save(buffer, "JPEG", quality=quality)
    return Image.open(io.BytesIO(buffer.getvalue())).convert("RGB")


def platform_thumbnail(photo: Photo) -> Image.Image:
    """What shab's thumbnails do: a centred 4:3 landscape crop, scaled to 400x300."""
    image = photo.image
    width, height = image.size
    crop_w, crop_h = (
        (width, round(width * 3 / 4))
        if width * 3 <= height * 4
        else (
            round(height * 4 / 3),
            height,
        )
    )
    left, top = (width - crop_w) // 2, (height - crop_h) // 2
    return _jpeg(image.crop((left, top, left + crop_w, top + crop_h)).resize((400, 300)), 80)


def crop70(photo: Photo) -> Image.Image:
    rng = _rng(photo, "crop70")
    width, height = photo.image.size
    scale = 0.7**0.5
    crop_w, crop_h = round(width * scale), round(height * scale)
    left = rng.randint(0, width - crop_w)
    top = rng.randint(0, height - crop_h)
    return _jpeg(photo.image.crop((left, top, left + crop_w, top + crop_h)), 85)


def recompressed(photo: Photo) -> Image.Image:
    width, height = photo.image.size
    small = photo.image.resize((max(1, width // 2), max(1, height // 2)))
    small = ImageEnhance.Brightness(small).enhance(1.08)
    small = ImageEnhance.Contrast(small).enhance(1.08)
    return _jpeg(small, 60)


TRANSFORMS: dict[str, Callable[[Photo], Image.Image]] = {
    "platform-thumbnail": platform_thumbnail,
    "crop-70": crop70,
    "recompressed": recompressed,
}

# ---------------------------------------------------------------- embedders


class Embedder:
    name: str

    def embed(self, images: Sequence[Image.Image]) -> np.ndarray:
        raise NotImplementedError


class PHash(Embedder):
    """Bits as a +-1 vector: cosine = 1 - 2 * hamming / 64, so ranking equals Hamming ranking."""

    name = "phash"

    def embed(self, images: Sequence[Image.Image]) -> np.ndarray:
        bits = [imagehash.phash(image).hash.flatten() for image in images]
        return np.array([np.where(b, 1.0, -1.0) for b in bits]) / 8.0


class DinoV2(Embedder):
    def __init__(self, model_id: str) -> None:
        import torch
        from transformers import AutoModel

        self.name = model_id.split("/")[-1]
        self._torch = torch
        self.device = "mps" if torch.backends.mps.is_available() else "cpu"
        self._model = AutoModel.from_pretrained(model_id).to(self.device).eval()
        self.revision = getattr(self._model.config, "_commit_hash", None)
        self._mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
        self._std = np.array([0.229, 0.224, 0.225], dtype=np.float32)

    def _tensor(self, images: Sequence[Image.Image]) -> Any:
        arrays = [
            (
                np.asarray(i.resize((224, 224), Image.Resampling.BICUBIC), dtype=np.float32) / 255.0
                - self._mean
            )
            / self._std
            for i in images
        ]
        batch = np.stack(arrays).transpose(0, 3, 1, 2)
        return self._torch.from_numpy(batch).to(self.device)

    def embed(self, images: Sequence[Image.Image]) -> np.ndarray:
        out = []
        with self._torch.inference_mode():
            for start in range(0, len(images), 32):
                hidden = self._model(pixel_values=self._tensor(images[start : start + 32]))
                cls = hidden.last_hidden_state[:, 0, :]
                out.append(self._torch.nn.functional.normalize(cls, dim=-1).cpu().numpy())
        return np.concatenate(out)


class AvalAIEmbedder(Embedder):
    """OpenAI-compatible /embeddings with the input shape each model accepts (probed 2026-10-01)."""

    def __init__(
        self, model: str, settings: Settings, cache_dir: Path, usd_per_mtok: float
    ) -> None:
        self.name = model
        self._settings = settings
        self._cache_path = cache_dir / f"{model}.jsonl"
        self._cache: dict[str, list[float]] = {}
        if self._cache_path.exists():
            for line in self._cache_path.read_text().splitlines():
                row = json.loads(line)
                self._cache[row["key"]] = row["embedding"]
        self._usd_per_mtok = usd_per_mtok
        self.tokens = 0
        self.calls = 0

    @staticmethod
    def data_url(image: Image.Image) -> str:
        image = image.copy()
        image.thumbnail((API_MAX_SIDE, API_MAX_SIDE))
        buffer = io.BytesIO()
        image.save(buffer, "JPEG", quality=90)
        return "data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode()

    def _payload(self, url: str) -> object:
        if self.name.startswith("tongyi"):
            return {"contents": [{"image": url}]}
        return url

    async def _one(self, client: httpx.AsyncClient, url: str, use_cache: bool) -> list[float]:
        key = hashlib.sha256(f"{self.name}\0{url}".encode()).hexdigest()
        if use_cache and key in self._cache:
            return self._cache[key]
        headers = {"Authorization": f"Bearer {self._settings.avalai_api_key.get_secret_value()}"}
        response: httpx.Response | None = None
        for attempt in range(6):
            try:
                response = await client.post(
                    "/embeddings",
                    headers=headers,
                    json={"model": self.name, "input": self._payload(url)},
                )
            except httpx.TransportError:  # timeouts and dropped connections are retried too
                response = None
            if response is not None and response.status_code == HTTP_OK:
                break
            await asyncio.sleep(2**attempt)
        if response is None:
            raise RuntimeError(f"{self.name}: no response after retries")
        response.raise_for_status()
        body = response.json()
        usage = body.get("usage") or {}
        self.tokens += int(usage.get("prompt_tokens") or 0)
        self.calls += 1
        embedding: list[float] = body["data"][0]["embedding"]
        if use_cache:
            self._cache[key] = embedding
            with self._cache_path.open("a") as handle:
                handle.write(json.dumps({"key": key, "embedding": embedding}) + "\n")
        return embedding

    async def _all(self, images: Sequence[Image.Image], use_cache: bool) -> np.ndarray:
        # tongyi-embedding-vision-flash allows 75 requests/min on tier 3 (gemini: 500).
        slow = self.name.startswith("tongyi")
        semaphore = asyncio.Semaphore(1 if slow else 4)
        urls = [self.data_url(i) for i in images]
        async with httpx.AsyncClient(
            base_url=self._settings.avalai_base_url, timeout=120
        ) as client:

            async def bounded(url: str) -> list[float]:
                async with semaphore:
                    before = self.calls
                    vector = await self._one(client, url, use_cache)
                    if slow and self.calls > before:  # pace real calls only, not cache hits
                        await asyncio.sleep(TONGYI_INTERVAL_S)
                    return vector

            vectors = await asyncio.gather(*(bounded(u) for u in urls))
        matrix = np.array(vectors, dtype=np.float32)
        return matrix / np.linalg.norm(matrix, axis=1, keepdims=True)

    def embed(self, images: Sequence[Image.Image]) -> np.ndarray:
        return asyncio.run(self._all(images, use_cache=True))

    def determinism(self, images: Sequence[Image.Image]) -> float:
        """Lowest cosine between a cached embedding and a fresh call for the same image."""
        cached = asyncio.run(self._all(images, use_cache=True))
        fresh = asyncio.run(self._all(images, use_cache=False))
        return float(np.min(np.sum(cached * fresh, axis=1)))

    @property
    def usd(self) -> float:
        return self.tokens * self._usd_per_mtok / 1_000_000


# ---------------------------------------------------------------- evaluation


def evaluate(
    gallery: np.ndarray,
    queries: np.ndarray,
    sources: list[int],
    listings: list[str],
) -> dict[str, float]:
    sims = queries @ gallery.T
    positives = sims[np.arange(len(sources)), sources]
    top1 = sims.argmax(axis=1)
    threshold = float(np.quantile(positives, 1 - POSITIVE_RECALL))
    other_listing = np.array(
        [[listings[g] != listings[s] for g in range(len(listings))] for s in sources]
    )
    negatives = sims[other_listing]
    return {
        "recall_at_1": float(np.mean(top1 == np.array(sources))),
        "threshold_95": threshold,
        "cross_listing_fpr": float(np.mean(negatives >= threshold)),
        "queries_with_false_hit": float(np.mean(((sims >= threshold) & other_listing).any(axis=1))),
        "median_positive": float(np.median(positives)),
        "p99_cross_listing": float(np.quantile(negatives, 0.99)),
    }


async def load_photos(limit: int) -> list[Photo]:
    container = build_container()
    try:
        async with container.engine.connect() as conn:
            rows = (await conn.execute(PHOTOS_SQL)).all()
        photos = []
        for row in rows[:limit]:
            raw = await container.blobs.get(row.blob_key)
            image = Image.open(io.BytesIO(raw)).convert("RGB")
            image.thumbnail((LOAD_MAX_SIDE, LOAD_MAX_SIDE))  # bounds memory; every method downsizes
            photos.append(Photo(f"{row.platform}:{row.external_id}", row.sha256, image))
        return photos
    finally:
        await container.aclose()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gallery", type=int, default=800)
    parser.add_argument("--queries", type=int, default=200)
    parser.add_argument("--out", type=Path, default=Path("../var/bench/image-embeddings"))
    parser.add_argument("--skip", nargs="*", default=[], help="method names to skip")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    photos = asyncio.run(load_photos(args.gallery))
    query_photos = list(range(min(args.queries, len(photos))))
    query_images, sources, transform_of = [], [], []
    for name, transform in TRANSFORMS.items():
        for index in query_photos:
            query_images.append(transform(photos[index]))
            sources.append(index)
            transform_of.append(name)
    listings = [p.listing for p in photos]
    gallery_images = [p.image for p in photos]

    settings = Settings()
    prices = {m["id"]: m for m in json.loads(settings.models_path.read_text())["models"]}
    embedders: list[Callable[[], Embedder]] = [
        PHash,
        lambda: DinoV2("facebook/dinov2-small"),
        lambda: DinoV2("facebook/dinov2-base"),
        *(
            (lambda m=m: AvalAIEmbedder(m, settings, args.out, prices[m]["input_usd_per_mtok"]))
            for m in ("gemini-embedding-2", "tongyi-embedding-vision-flash")
        ),
    ]
    report: dict[str, Any] = {
        "gallery": len(photos),
        "listings": len(set(listings)),
        "queries": len(query_images),
        "transforms": list(TRANSFORMS),
        "methods": {},
    }
    for make in embedders:
        embedder = make()
        if embedder.name in args.skip:
            continue
        started = time.perf_counter()
        gallery = embedder.embed(gallery_images)
        queries = embedder.embed(query_images)
        seconds = time.perf_counter() - started
        result: dict[str, Any] = {
            "dims": int(gallery.shape[1]),
            "images_per_second": round((len(gallery_images) + len(query_images)) / seconds, 1),
            "all": evaluate(gallery, queries, sources, listings),
        }
        for name in TRANSFORMS:
            mask = [i for i, t in enumerate(transform_of) if t == name]
            result[name] = evaluate(gallery, queries[mask], [sources[i] for i in mask], listings)
        if isinstance(embedder, DinoV2):
            result["device"], result["revision"] = embedder.device, embedder.revision
        if isinstance(embedder, AvalAIEmbedder):
            result["min_cosine_repeat_call"] = embedder.determinism(
                gallery_images[:DETERMINISM_SAMPLE]
            )
            result["usd_this_run"] = round(embedder.usd, 4)
            result["api_calls_this_run"] = embedder.calls
        report["methods"][embedder.name] = result
        print(json.dumps({embedder.name: result["all"], "ips": result["images_per_second"]}))
    (args.out / "report.json").write_text(json.dumps(report, indent=1))
    print(f"report: {args.out / 'report.json'}")


if __name__ == "__main__":
    main()
