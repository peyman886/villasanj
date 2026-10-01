# ADR-0012 — Image matching evidence: local DINOv2 + pHash, chosen by measurement

Status: Accepted (2026-10-01) · Supersedes the image part of ADR-0006 · Evidence:
`backend/benchmarks/image_embeddings.py` (report regenerated with the command at the end)

## Context

- ADR-0006 chose local DINOv2 for image similarity from M5, partly to avoid per-image API cost.
  On 2026-10-01 the owner removed cost as a constraint. The choice between local processing and
  AvalAI should now rest on ER quality, latency, reproducibility and simplicity. The owner also
  asked to use platform image URLs directly where that avoids needless downloads, and to store every
  cacheable output (such as embeddings) so it is never recomputed.
- M2 showed that pHash misses cropped copies: shab's thumbnails are 4:3 crops, and for portrait
  originals the pHash distance to the thumbnail is 20–32 bits (ADR-0008 amendment 5).
- AvalAI probe (2026-10-01): two image-capable embedding models answer on the OpenAI-compatible
  `/embeddings` endpoint, each with its own input shape.
  - `gemini-embedding-2` takes a data-URL string and returns 3072 dimensions, billed ~258 tokens per
    image.
  - `tongyi-embedding-vision-flash` takes `{"contents": [{"image": …}]}` and returns 768
    dimensions. It allows 75 requests/min on tier 3.
  - A wrong shape for gemini is not rejected: it is silently embedded as a 1-token text.
- The gold set (M3) must be sampled from the blocking sources that production will use. If image
  embeddings arrive only in M5, pairs found only by embeddings would be missing from gold set v1 and
  would need a second labelling round.

## Benchmark (label-free, on our own crawl)

Gallery: crawled photos from both platforms (ordered by content hash). Queries: three deterministic
transformations of 200 gallery photos:
- a centred 4:3 crop scaled to 400×300 (what shab's thumbnails do);
- a 70% crop;
- a 50% downscale with +8% brightness and contrast, JPEG quality 60.

Metrics:
- recall@1: the transformed photo retrieves its own original;
- cross-listing false-positive rate: at the similarity that keeps 95% of true pairs, the share of
  photos from *other* listings that score as high;
- p99 cross-listing similarity (how alike unrelated villas look to the model);
- throughput, and for API models the cost and repeat-call stability.

Run on 2026-10-01: 872 gallery photos from 175 listings, 600 queries.

| Method | Dims | Recall@1 (thumbnail / crop 70% / recompressed) | Cross-listing FPR at 95% recall | Queries with a false hit | Similarity threshold for 95% recall | p99 similarity of unrelated listings | Throughput |
|---|---|---|---|---|---|---|---|
| phash | 64 | 0.743 (0.88 / 0.35 / 1.00) | 29.9797% | 100.0% | 0.125 | 0.312 | 1,266 img/s (local) |
| dinov2-small | 384 | 1.000 (1.00 / 1.00 / 1.00) | 0.0008% | 0.7% | 0.903 | 0.656 | 112 img/s (local, Apple MPS) |
| dinov2-base | 768 | 1.000 (1.00 / 1.00 / 1.00) | 0.0010% | 0.8% | 0.892 | 0.622 | 42 img/s (local, Apple MPS) |
| gemini-embedding-2 | 3072 | 0.995 (1.00 / 0.99 / 0.99) | 0.0029% | 2.3% | 0.924 | 0.830 | 4.3 img/s (API, 4 in flight; first uncached run) |
| tongyi-embedding-vision-flash | 768 | 0.997 (1.00 / 0.99 / 1.00) | 0.0015% | 1.3% | 0.860 | 0.591 | 0.5 img/s (API, 1 in flight under the 75 req/min cap) |

- pHash fails on crops: the 70% crop retrieves its original only 36% of the time, and keeping 95%
  of true pairs would accept 30% of unrelated photos.
- Every embedding retrieves nearly every copy. They differ in **separation**: how far the copies sit
  above unrelated villas. For DINOv2-small, unrelated listings reach 0.656 at p99, against a 0.903
  threshold. For gemini-embedding-2 they reach 0.830, against 0.924. A semantic model sees "a villa
  with a pool" in many different villas, which is exactly the hard-negative failure ADR-0006 feared.
- API embeddings were deterministic: a repeat call gave cosine 1.0 for both models.
- Spend: the benchmark called AvalAI directly, outside the LLM ledger. From the reported usage and
  the model prices, gemini-embedding-2 cost ≈ $0.08 (~1.5k images × ~258 tokens × $0.20/M) and
  tongyi-embedding-vision-flash cost ≈ $0.01.

## Decision

1. **Local DINOv2-small** (`facebook/dinov2-small`, revision pinned in
   `catalog/infrastructure/dinov2.py`) is the image embedding for blocking and evidence, **from M3**.
   The whole image is resized to 224×224 (no centre crop) and the CLS token is L2-normalised.
2. **pHash/dHash stay.** They are cheap, exact-copy evidence and group near-identical photos for the
   document-frequency weight.
3. **Computed once.** Embeddings are stored per *(image content hash, model id)*: an image shared by
   several listings is embedded once, and reruns skip what exists. pHash fingerprints are
   incremental too. Search is exact and in memory (numpy), not an approximate index: at ~20k photos
   it takes seconds, and the same input always gives the same neighbours.
4. **Bytes for computation, URLs for display.** pHash and embeddings need the image bytes, so a
   fixed number of coverage photos per listing is fetched once, politely, through the crawler. Every
   photo shown to a person (the labelling UI, later the villa page) is loaded straight from the
   platform's CDN, so nothing is copied for display. We do not pass platform URLs to AvalAI:
   - a third party would then fetch from the platforms outside our rate limit, robots handling and
     identifying user agent;
   - URLs change (two jabama stays were already gone during M2), which would make results
     irreproducible.
5. **AvalAI vision stays where it is strongest:** the gray-zone ER judge (M5) reads the same stored
   bytes the matcher used, so its verdicts are about the same evidence.

## Alternatives considered

- **gemini-embedding-2 (AvalAI).** Recall is equal, but separation is the weakest (p99 of unrelated
  listings 0.83), which costs precision exactly where ER is hardest. It is also network-bound and
  needs the bytes uploaded anyway.
- **tongyi-embedding-vision-flash (AvalAI).** Separation is good, but recall@1 is 0.997 and
  throughput is ~0.5 images/s at the 75 requests/min tier-3 limit: ~10 h for the ~17.5k coverage
  photos against ~3 minutes locally.
- **DINOv2-base.** No measurable gain over small (both have recall@1 1.0; false hits 0.8% vs 0.7%),
  at 2.7× the time and twice the dimensions.
- **pHash only (the original M3 plan).** It misses cropped and re-framed copies (above), which would
  hide matches from blocking and from the gold set.
- **Passing platform URLs to an API instead of downloading.** Rejected for the reasons in decision 4.
  For display, URLs are used directly.

## Consequences

- (+) The strongest ER signal is crop-robust, deterministic for a pinned model, offline and fast
  (Apple MPS).
- (+) Gold set v1 is sampled from the final blocking sources, so M5 does not need a relabelling round
  for embedding-only pairs.
- (−) torch and transformers (~580 MB installed on macOS arm64) are a dependency, kept in the `ml` group and out of the API
  image. A run on CPU instead of MPS can differ in the last float digits; ranking at our thresholds
  is unaffected, and the model id records the revision.
- (−) Copy detection is not villa identity. Two photos of the same room from different angles, or the
  same marketing shot reused across a complex, are judged by the gold set, not by this benchmark.

Rerun: `cd backend && uv run --with torch --with transformers python benchmarks/image_embeddings.py`
(API embeddings are cached under `var/bench/`).
