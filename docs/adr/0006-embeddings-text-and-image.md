# ADR-0006 — Embeddings: image local, text via AvalAI behind an eval gate

Status: Accepted (M0 approval, 2026-10-01); image part superseded by [ADR-0012](0012-image-matching-evidence.md) · Date: 2026-10-01

## Context

- **Image similarity** is the strongest ER signal (the research report ranks it first). It is needed
  for 20–40k photos and must be reproducible and free per run.
- **Text embeddings** serve two narrow purposes: (a) a soft text-similarity feature in ER and (b)
  optional dense retrieval for soft preferences ("دنج", "ویو جنگل"). With 1.5–3k documents, hard
  filters dominate retrieval (ADR-0002).
- Hardware: 16 GB RAM, with Docker at 7.75 GB and no GPU in containers (ADR-0003).
- Measured: `text-embedding-3-small` → 1536 dims; `gemini-embedding-001` → 3072 dims, usage reported 0.
  Tier 3 limits: 5000 RPM and 500 RPM respectively.
- pgvector can index `vector` columns up to 2,000 dimensions with HNSW (`halfvec` up to 4,000).

## Decision

### Image (local, behind `ImageEmbedder` / `PerceptualHasher`)
1. **pHash + dHash** (imagehash) for all photos from M2. They catch exact and near-exact copies and
   are the M3 baseline.
2. **DINOv2** (ViT-S/14 by default, ViT-B/14 if measured recall justifies the cost; Apache-2.0) from
   M5, for "same pool from a different angle" and re-encoded/cropped photos. The encoder runs on CPU
   in the `worker` container, or on host MPS as an optional runner. Weights are pinned by hash in the
   `models` volume.
3. **SigLIP** (zero-shot tags) from M9 for amenity/visual evidence. It is a separate port
   implementation, because semantic tagging and instance matching are different jobs.
4. SSCD only if the M5 eval shows DINOv2 misses watermark or crop copies (licence to verify first).
5. Photo document frequency (how many listings share a near-identical photo) down-weights generic or
   shared marketing photos (ADR-0009).

### Text (AvalAI by default, behind `TextEmbedder`)
1. Default: **gemini-embedding-001** requested at **768 dims**. It is MRL-trained, so truncation is
   valid. Whether AvalAI forwards `dimensions` is **unverified**; if it does not, the adapter truncates
   and re-normalises. The result fits a pgvector HNSW index.
2. Fallback: **text-embedding-3-small** (1536 dims, $0.02/M).
3. Local alternative adapter: `bge-m3` via sentence-transformers, **not deployed by default** (≈ 2 GB
   resident RAM in the API for query-time embedding).
4. Embeddings are cached (same cache as LLM calls) and stored with `model_id`, so switching models
   never mixes vector spaces.
5. **Eval gate (M8):** 30 judged Persian queries. FTS-only vs FTS+dense, and gemini-embedding vs
   3-small vs bge-m3 (offline). Dense retrieval ships only if nDCG@10 improves by ≥ 0.03; otherwise
   text embeddings are used only as an ER feature, or dropped.

## Alternatives considered

- **Local text embeddings by default.** No per-call cost and offline, but ~2 GB RAM pinned in the API
  and slower on CPU. The AvalAI cost is < $1 for the whole project. The local adapter stays available.
- **One multimodal embedding (e.g. CLIP) for both ER and tagging.** Semantic models blur "the same
  villa" and "a similar-looking villa", which is exactly the hard-negative failure we must avoid.
- **Image embeddings through AvalAI** (`gemini-embedding-2`, tongyi vision embeddings exist). Rejected:
  30k images × per-image cost, network dependency and non-reproducibility for our most critical signal.

## Consequences

- (+) The most important ER signal is free, deterministic and offline.
- (+) Text dense retrieval must earn its place with numbers.
- (−) CPU embedding time for ~30k photos is a one-off cost; it is measured in M5, and the MPS runner
  is the escape hatch.
