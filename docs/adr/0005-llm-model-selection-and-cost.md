# ADR-0005 — Model per LLM task and total cost estimate

Status: Proposed · Date: 2026-10-01 · Evidence: `docs/reference/avalai-models-2026-10-01.csv`

## Context

`/v1/models` (fetched 2026-10-01) lists 365 models: 251 chat, 16 embedding, 6 rerank, and others.
Prices below are the snapshot's figures in **USD per 1M tokens** (assumption A2, to be verified
against the dashboard in M1). The account is **tier 3** (measured), so rate limits do not constrain
model choice.

Many listed models were released after my knowledge cut-off (e.g. `gpt-6-luna`, `gemini-3.8-flash`).
**I do not infer quality from a model's name.** The choices below rest on (1) capabilities in the
snapshot (vision, `response_schema`, deprecation date), (2) price, and (3) a small smoke probe on our
own task. Final choices are made by cheap bake-offs on our own labelled data at the milestone that
needs each task.

### Probe (2026-10-01, synthetic messy Persian listing, n = 1 per model; a smoke test, not an eval)

| Model | Test | Result | Prompt / output tokens | Latency |
|---|---|---|---|---|
| gemini-3.1-flash-lite | strict JSON-schema claim extraction | valid; 12 claims; **all spans verbatim**; base (6) and extra (2) capacity kept separate | 129 / 730 | 5.8 s |
| gemini-3.8-flash | same | valid; 12 claims; all spans verbatim; richer units | 129 / 805 | 3.8 s |
| gpt-5-nano (`reasoning_effort=minimal`) | same | valid JSON but **every span = whole text**, digits altered inside "verbatim" spans, 6+2 merged into base_capacity 8 | 251 / 1051 | 6.4 s |
| gemini-3.1-flash-lite | vision, 32×32 PNG | correct; **~1,090 tokens per image**; `detail: low` ignored (1,098) | 1,105 / 1 | 3.0 s |
| gpt-5.4-mini | vision, same image | correct; 34 tokens (`low`) / 60 (`high`) | 34 / 1 | 1.7 s |
| claude-sonnet-5-5 | tier probe (tier ≥ 1 model) | 200 OK; all 5 tokens went to reasoning, so empty text | 137 / 5 | 1.5 s |
| text-embedding-3-small | Persian sentence | 1536 dims, 26 tokens | — | 0.5 s |
| gemini-embedding-001 | Persian sentence | 3072 dims; **usage reported as 0** | — | 0.7 s |

Probe spend ≈ **$0.006** (usage × list price).

### Shortlist (snapshot prices)

| Model | In | Out | Cached in | Vision | JSON schema | Min tier | Deprecation |
|---|---|---|---|---|---|---|---|
| gpt-6-luna | 0.10 | 0.50 | 0.01 | ✓ | ✓ | 0 | — |
| deepseek-v4.1-flash | 0.15 | 0.60 | 0.003 | ✓ | ✓ | 0 | — |
| gemini-3.1-flash-lite | 0.25 | 1.50 | 0.025 | ✓ | ✓ | 0 | 2027-05-07 |
| gemini-3.8-flash | 0.75 | 3.75 | 0.075 | ✓ | ✓ | 0 | — |
| gpt-5.4-mini | 0.75 | 4.50 | 0.075 | ✓ | ✓ | 0 | — |
| claude-sonnet-5-5 | 2.00 | 10.00 | 0.20 | ✓ | ✓ | 1 | — |
| gpt-5.4 | 2.50 | 15.00 | 0.25 | ✓ | ✓ | 0 | — |
| gemini-embedding-001 | 0.15 | — | 0.075 | — | — | 0 | — |
| text-embedding-3-small | 0.02 | — | 0.01 | — | — | 0 | — |

Excluded: `gpt-5-nano` (failed the probe's span and field-separation checks); models deprecating within
weeks (`gemini-2.5-flash-lite` and `gemini-2.5-flash/pro` on 2026-10-20; `gpt-4.1-nano` and `o4-mini`
on 2026-10-23); frontier models at $4–10/M input (not needed at this scale).

## Decision

Primary = Google, fallback = OpenAI, so a vendor outage behind the gateway does not stop a job.

| Task (`LLMTask`) | Primary | Fallback | Why | Gate that can change it |
|---|---|---|---|---|
| `CLAIM_EXTRACTION` (bulk) | gemini-3.1-flash-lite | gpt-5.4-mini | Cheapest model that passed the probe; strict schema; far deprecation | M9: bake-off with gpt-6-luna and deepseek-v4.1-flash on 60 labelled descriptions (≈ $0.3); cheapest with precision ≥ 90% / recall ≥ 80% wins |
| `TEXT_NORMALIZATION` (house rules, cancellation text; batched 10 listings/call) | gemini-3.1-flash-lite | gpt-5.4-mini | Same | M6/M9 spot checks |
| `ER_JUDGE` (gray zone, multimodal) | gemini-3.8-flash *(provisional)* | gpt-5.4-mini | Mid price, vision + schema; composite photo grids keep images to 2 per call | **M5 bake-off** on ≈ 80 hard gold pairs vs gpt-5.4-mini and claude-sonnet-5-5 (≈ $1.9): cheapest model with `MATCH` precision ≥ 95% |
| `QUERY_UNDERSTANDING` | gemini-3.1-flash-lite | gpt-5.4-mini | Latency and cost; strict schema | M8: slot accuracy ≥ 90%, p95 ≤ 3 s; gpt-5.4-mini may win on latency |
| `VISION_TAGGING` (targeted checks only) | gemini-3.1-flash-lite | gpt-5.4-mini | Bulk tags are local (SigLIP); VLM only where local tags are inconclusive; one composite per villa | M9 photo-tag eval |
| `REVIEW_SUMMARY` | gemini-3.8-flash | gpt-5.4-mini | User-visible Persian prose | M10: blind faithfulness review; downgrade to flash-lite if it ties on 10 villas |
| `EXPLANATION` | gemini-3.8-flash | gpt-5.4-mini | User-visible; low volume; slot-based output (ADR-0007) | M10 |
| Text embeddings | gemini-embedding-001 | text-embedding-3-small | See ADR-0006 | M8 retrieval eval |

## Cost estimate (whole project, demo scale)

Assumptions: 3,000 listings (upper end of scope); 400–800 gray-zone pairs; ~1,000 villas with ≥ 3
reviews; Persian ≈ 4.3 chars/token on Gemini (one sample; recalibrated after M2 with dry-run on real
data); Gemini images ≈ 1,090 tokens each; ER judge sends 2 composite grids + ~1.2k text tokens.

| Task | Model | Calls | In tok | Out tok | $/call | Total |
|---|---|---|---|---|---|---|
| Claim extraction | flash-lite | 3,000 | 1,000 | 500 | 0.0010 | $3.00 |
| Free-text normalization (batched) | flash-lite | 300 | 3,000 | 1,500 | 0.0030 | $0.90 |
| ER judge bake-off (3 models × 80) | mixed | 240 | ~3,200 | 600 | ~0.008 | $1.90 |
| ER judge calibration on gold | 3.8-flash | 300 | 3,400 | 600 | 0.0048 | $1.40 |
| ER judge production | 3.8-flash | 400–800 | 3,400 | 600 | 0.0048 | $1.90–3.80 |
| Targeted vision checks | flash-lite | 1,500 | 1,400 | 200 | 0.00065 | $1.00 |
| Query understanding (dev + eval + demo) | flash-lite | 600 | 1,500 | 250 | 0.00075 | $0.45 |
| Review summaries | 3.8-flash | 1,000 | 2,500 | 500 | 0.0038 | $3.80 |
| Explanations | 3.8-flash | 500 | 2,000 | 350 | 0.0028 | $1.40 |
| Text embeddings | gemini-embedding-001 | — | ~6M total | — | — | $0.90 |
| Live tests & probes | mixed | ~100 | — | — | — | $0.20 |
| **Base total** | | | | | | **$16.9–18.8** |
| **With 30% iteration contingency** | | | | | | **≈ $22–25** |

- **Hard project cap: $30** (`LLM__BUDGET__PROJECT_USD`), enforced by the ledger. Per-milestone caps are
  in ROADMAP.
- **Lean profile** (`config/llm.lean.toml`): flash-lite everywhere, summaries only for demo villas,
  judge only on in-scope pairs, for **≈ $8–10**.
- Output tokens dominate costs for extraction (the probe spent 730 output vs 129 input tokens). The
  schema will drop redundant fields such as `value_text` (the span already carries it), which is
  expected to cut output by about a third.
- Caching makes re-runs free unless inputs or prompt versions change.

## Consequences

- (+) Every choice has a measured gate. Models are swapped by editing `config/llm.toml`.
- (+) The expected spend is well under the cap with headroom for iteration.
- (−) Gemini's flat per-image cost makes naive multi-image prompts expensive. This is mitigated by
  composite grids and local pre-filtering (ADR-0009).
- (−) `gemini-embedding-001` reports zero usage, so the ledger marks its cost as `estimated`.
