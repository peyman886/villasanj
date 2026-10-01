# ADR-0009 — Staged, precision-first entity resolution

Status: Accepted (M0 approval, 2026-10-01) · Date: 2026-10-01

## Context

- There is no shared identifier. Titles are generic (jajiga), brand-like (jabama) or codes. Exact
  coordinates are hidden or obfuscated. Structural fields disagree (the "کاخ آرشام" case: 4 vs 3
  bedrooms). **Photos are the strongest signal.**
- Error costs are asymmetric. A wrong merge sends a user to the wrong villa and destroys the trust the
  product sells. A missed merge only loses value. Target: **precision ≥ 95%**.
- A hard case the research report does not address: **villa complexes that reuse the same marketing
  photos for several units**. Photo-first matching will score them as identical although they are
  different rentable units.
- The research cites LLM-as-matcher results (Peeters & Bizer; Steiner & Bizer). These are useful
  priors, but they are on product benchmarks, not Persian villas. We measure on our own data.

## Decision

### Stages
1. **Blocking (recall first; target ≥ 98% on gold positives):** union of
   (a) same normalized place + rooms ±1, (b) pHash LSH buckets (any shared near-duplicate photo),
   (c) top-k DINOv2 neighbours at the photo level (M5), (d) geo distance range overlap when coordinates
   exist. Pairs are only cross-platform, plus same-platform pairs for the complex-unit hard negatives.
2. **Evidence/features:** photo set-to-set similarity (best bipartite matching over photos, pHash
   Hamming and DINOv2 cosine), **weighted by photo document frequency** (a photo appearing in ≥ 3
   listings contributes little); rooms / capacity / area diffs (soft); place match and distance range;
   host-name similarity where shown; rare-n-gram text similarity; nightly-rate ratio.
3. **Scoring:** M3 uses a transparent rule baseline. M5 uses **Splink** (Fellegi–Sunter, DuckDB). Match
   weights are explainable per comparison, which suits the demo's "why merged" view. Continuous
   similarities are binned into comparison levels.
4. **Adjudication:** above the high threshold → auto `MATCH`; below the low threshold → `NON_MATCH`;
   gray zone → **LLM judge** with a structured verdict (`MATCH | NON_MATCH | UNSURE`), confidence,
   rationale and cited evidence. It receives **two composite photo grids** (Gemini bills ~1.1k tokens
   per image regardless of size) plus structured fields. `UNSURE` or low confidence → **human review
   queue**. Human decisions become must-link/cannot-link constraints and future training data.
5. **Clustering:** greedy merge by descending match weight, with constraints: **≤ 1 listing per
   platform**, no cannot-link violated, and no merge through a complex-unit conflict. A blocked merge
   is flagged for review, never forced. The invariant is enforced in the `CanonicalVilla` aggregate and
   by a unique DB index.
6. **Canonical record:** members by platform; photos as a deduplicated union (photo groups); field
   conflicts surfaced as trust signals; **prices never merged** (each member → its own offer).
   Canonical IDs are stable across runs (overlap reconciliation, with split/merge history).
7. **Complex units:** if a photo set is shared by ≥ 2 listings on the same platform, those listings
   form a *shared-photo group*. Cross-platform matches into that group require non-photo evidence
   (unit-specific rooms/capacity/price or host confirmation), otherwise the result is "same complex,
   unit unknown" and the pair is not merged.

### Evaluation protocol
- **Gold set labelled by a human (the owner)**: ≥ 300 pairs in M3, plus ≥ 150 in M5 for the new
  platforms. Stratified sampling across score deciles, all blocking sources, and explicit hard
  negatives (same host or complex). Labels: `match / non_match / unsure`; `unsure` is excluded from
  P/R, and its rate is reported. The labelling UI hides model scores and LLM suggestions to avoid
  anchoring. **LLM labels are never evaluation truth.** They may be used as weak supervision only.
- Metrics: pairwise P/R/F1 with **Wilson 95% CIs**, B-cubed P/R/F1 on clusters, blocking recall,
  PR curve, and ablations (photo-only / text-only / full) for H5. Reports are keyed by dataset hash
  + run id, so they are reproducible.
- Operating point: choose the threshold where the precision **lower bound** ≥ 92% and the point
  estimate ≥ 95%. Pairs just below it are shown as «احتمالاً همین ویلا» with evidence, not merged.

## Alternatives considered

- **LLM on every candidate pair.** Most expensive; unnecessary for clear matches or non-matches;
  non-deterministic. The LLM only sees the gray zone.
- **Supervised classifier (logistic regression / GBM) on the gold set.** A viable simple alternative
  to Splink. Kept as an M5 comparison if Splink's EM is unstable on ~3k records, and chosen by eval
  numbers.
- **Ditto / fine-tuned PLM.** Needs more labels and a GPU. Post-demo.
- **Zingg / Dedupe.** Zingg is heavy (Spark). Dedupe does not cover images natively.

## Consequences

- (+) Every merge is explainable: blocking key → evidence → match weight → decision (who decided and why).
- (+) Precision claims come with honest intervals.
- (−) The owner's labelling time (≈ 3 h) is on the critical path of M3/M5.
- (−) Complex-unit handling may lower recall; the drop is reported.
