# ADR-0005 — Model per LLM task and total cost estimate

Status: Accepted (M0 approval, 2026-10-01) · Date: 2026-10-01 · Evidence: `docs/reference/avalai-models-2026-10-01.csv`

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

## Amendment (M1 live smoke, 2026-10-01)

`make test-live` and `make llm-smoke` each made one structured call per task route plus one per
distinct fallback model (8 calls). **All returned schema-valid output.** Persisted ledger
(`ops.llm_call`) for the `make llm-smoke` run:

| Task | Model | In | Out (of which reasoning) | Cost |
|---|---|---|---|---|
| query_understanding / claim_extraction / text_normalization / vision_tagging | gemini-3.1-flash-lite | 37–38 | 13–14 (0) | $0.000029–0.000031 each |
| er_judge | gemini-3.8-flash | 37 | 175 (164) | $0.000684 |
| review_summary | gemini-3.8-flash | 37 | 227 (208) | $0.000879 |
| explanation | gemini-3.8-flash | 35 | 264 (255) | $0.001016 |
| query_understanding (fallback check) | gpt-5.4-mini | 91 | 18 (0) | $0.000149 |
| **Total** | | | | **$0.002845** |

Rate-limit headers confirm tier 3 (1000 RPM for both Gemini models and for gpt-5.4-mini).

**Consequence for the cost estimate.** `gemini-3.8-flash` thinks by default. If real judge,
summary and explanation calls spend ~1–2k reasoning tokens, those three lines in the estimate above
grow by roughly $2–5 in total. This still fits the $30 cap, but it must be measured. Action: the M5
judge bake-off and the M10 summary review compare `reasoning_effort` settings (default vs low) per
task, and the setting goes into `config/llm.toml` with the measured quality/cost trade-off.

## Amendment (review summaries, 2026-10-02): `reasoning_effort = "low"` for `review_summary`

Measured on the same two jabama listings (6 reviews with text each), prompt v1, ledger rows in
`ops.llm_call`:

| Setting | Reasoning tokens | Output tokens | Cost (2 listings) | Latency | Notes |
|---|---|---|---|---|---|
| default | 675–1,141 | 934–1,485 | $0.0153 | ~6 s | one call hit the 1,500-token cap (`truncated`) and was re-run by the retry layer |
| `low` | 0 | 246–413 | $0.0035 | ~2.7 s | no truncation |

The points and their citations were essentially the same (same pros and cons, one extra
well-cited point with `low`). `config/llm.toml` now sets `reasoning_effort = "low"` for
`review_summary`. Provisional: two listings are a small sample. M10 criterion 3 (the owner's
blind review of 20 villas) is the real quality gate and may reverse this. The judge and the
explanation keep the default until their own bake-offs.

Lesson for estimates: the dry-run's "worst case" assumes one attempt per request, so a truncated
reasoning call plus its retry can exceed it. Tasks on thinking models need a measured
`expected_output_tokens` before a batch is priced.

## Amendment (explanations, 2026-10-02): `reasoning_effort = "low"` for `explanation`

With the default effort, a retried explanation was truncated twice at the 800-token cap
(796 output tokens each, $0.0034 per attempt) before an answer came back; the search request took
~8 s. With `low`, three searches gave 0 reasoning tokens, 48–61 output tokens, ~$0.0005 per
explanation, no truncation, and the same factual content (the verifier passed all three).
Latency was 2.4–5.4 s, so M10 criterion 4 (p95 ≤ 4 s uncached) is **not** guaranteed by the
setting: it depends on the provider's response time and is measured on the real query set in M10.
Cached explanations are instant. Provisional, like the summary setting.

## Amendment (query understanding bake-off, 2026-10-02): `gpt-5.4-mini` for `query_understanding`

M8 criterion 1 asks for slot accuracy ≥ 90%, 0 invented numeric constraints and p95 latency
≤ 3 s uncached, reported per model. On the 50-query draft (`eval/query-understanding/draft-v1.jsonl`,
written by the agent; **provisional until the owner reviews it**), prompt v3, each model alone (no
fallback), the same hour:

| Model | Slots | Exact | Invented | Failed | p50 | p95 | Cost / 50 queries |
|---|---|---|---|---|---|---|---|
| gemini-3.1-flash-lite (previous) | 99.3% | 98% | 0 | 0 | 2.9 s | 5.5 s | $0.018 |
| **gpt-5.4-mini** (chosen) | 97.9% | 94% | 0 | 0 | 1.0 s | 1.3 s | $0.062 |
| gemini-3.5-flash-lite | 95.8% | 92% | 0 | 0 | 1.0 s | 2.0 s | $0.026 |
| gpt-4.1-mini | 95.1% | 90% | 0 | 0 | 1.3 s | 2.6 s | $0.014 |
| claude-haiku-4-5 | 90.1% | 84% | 0 | 4 | 2.6 s | 15.1 s | $0.118 |

flash-lite's lead in accuracy is partly the prompt: it was tuned on flash-lite's mistakes. Only
gpt-5.4-mini meets all three targets with margin; its misses are arguable («ماه عسل» not read as a
couple, a basis inferred for «زیر ۱۵ میلیون» over three nights, «۴۵ دقیقه تا ساحل» read as near the
sea). Haiku returned fields outside the schema on four queries (`check_in`, `bedrooms`), which the
validator rejected on every retry. `config/llm.toml` now routes `query_understanding` to gpt-5.4-mini
with gemini-3.1-flash-lite as the fallback (~$0.0012 per query). Re-run the bake-off after the owner
reviews the draft set; the decision may change.

Follow-up (same day): gpt-5.4-mini guessed a basis for budgets that state none («زیر ۲۰ میلیون»),
which hid the budget question in search. A deterministic guard now keeps a basis only when the
query names it (A19). Re-scored from the cached gpt-5.4-mini answers ($0): slots 98.6%, exact
96%, 0 invented; latency is the uncached run's above.


## Amendment (explanation bake-off, 2026-10-02): `gemini-3.8-flash` stays; the explanation streams

M10 criterion 4 asks for explanation latency p95 ≤ 4 s uncached; criterion 2 for the verifier pass
and fallback rates. `discovery eval-explanations` runs the 50 draft queries through search and
explains the first result (20 queries produce one; the rest lack dates or results). Each model
alone, prompt v3, 03:08–03:40 UTC; latency includes the retry when there was one:

| Model | LLM text | Template | Retried | p50 | p95 | Cost / 20 |
|---|---|---|---|---|---|---|
| **gemini-3.8-flash** (kept) | 100% | 0% | 4 | 6.4 s | 10.6 s | $0.014 |
| gemini-3.5-flash-lite | 100% | 0% | 7 | 1.5 s | 3.0 s | $0.006 |
| gemini-3.1-flash-lite | 100% | 0% | 11 | 2.6 s | 3.3 s | $0.006 |
| gpt-5.4-mini | 90% | 10% | 5 | 3.1 s | 4.9 s | $0.033 |
| gpt-4.1-mini | 80% | 20% | 14 | 3.5 s | 4.3 s | $0.013 |

Every text shown passed the verifier (a failing one is replaced by the template), so the
choice is about the prose. Reading the texts side by side
(`docs/reference/explanation-bakeoff-2026-10-02.md`): gemini-3.8-flash writes grammatical Persian
that ties the facts together; the flash-lite models meet the latency target but drop slots into
broken sentences («دارای همه‌ی شب‌ها … آزاد بود … است»); gpt-5.4-mini repeats facts it has
already slotted. gemini-3.8-flash's output is short (mean 63 tokens, no reasoning at low
effort), so its latency is the provider's, not ours.

Decision: keep gemini-3.8-flash and take the explanation off the results' critical path. The
search page asks `POST /search` with `explain: false` (1.1 s with a cached understanding) and
streams `POST /search/explanation` in under Suspense. **M10 criterion 4 is not met** for the
explanation itself (p95 6.1–10.6 s uncached on 2026-10-02); results no longer wait for it. The
review found one verifier gap, «در دسترس قرار دارد» stated as a fact, now rejected with its
variants. `expected_output_tokens` for the task is 120 (was 350) from these measurements. Re-run
the bake-off at a busier hour and after the owner reviews the texts; a prompt that makes a lite
model's prose acceptable would meet the target.


## Amendment (estimator check, 2026-10-02): review summaries within ±25%

M9 criterion 5 asks that a dry run's estimate for an enrichment job be within ±25% of the ledger.
The only LLM enrichment job so far is review summaries (claims are rule-based; VLM checks wait
for photo-tag thresholds). On 24 random jabama listings with ≥ 5 text reviews the estimate was
$0.0540 against $0.0346 spent (+56%): `expected_output_tokens = 500` against a measured mean of
292 (reasoning included, low effort). Set to 300 from that sample, then checked on 24 **other**
listings: estimate $0.0363, spent $0.0352 (+3%). All 48 summaries passed the verifier on the
first try (0 retries, 0 dropped points).


## Amendment (query understanding prompt v4, 2026-10-02): wishes are said back, not dropped

The intent had no place for wishes outside its fields («دوبلکس», «حیاط بزرگ», «سونا»), so they
disappeared silently. Prompt v4 adds `unhandled`: short phrases copied from the query, checked
verbatim like places (a phrase not in the query is dropped). Search says them back («این خواسته‌ها
را نمی‌توانیم بسنجیم») and marks the results whose own text mentions one word for word; they
never filter or rank. On the 50-query draft (provisional, agent-written), gpt-5.4-mini with v4
and the basis guard: slots 100%, exact 100%, 0 invented, p95 1.4 s uncached, $0.067. `unhandled`
itself is not scored yet: the draft has no expected values for it.


## Amendment (ER judge bake-off, 2026-10-03): `gemini-3.8-flash` for `er_judge`

M5 criterion 2 asks for the gray-zone judge's precision and recall against the gold set, per
model. `er judge-eval` sends the 142 gold-v1 pairs scored −3 to 3 to each model alone (no
fallback), prompt `er_judge` v1, photo grids of both listings plus structured facts:

| Model | False matches | Recall (weighted) | Unsure | p95 uncached | Cost / 142 |
|---|---|---|---|---|---|
| **gemini-3.8-flash** (chosen) | 0 | 93.8% | 1.4% | 34 s | $0.32 |
| gpt-5.4-mini (fallback) | 0 | 79.8% | 1.4% | 5.5 s | $0.31 |
| gemini-3.5-flash | 1 | 94.4% | 0.7% | 31 s | $0.79 |

gpt-5.4-mini calls 21 of 76 labelled matches non-matches: it is safe but misses what the judge
is there to find. gemini-3.5-flash finds slightly more and costs 2.5× with one false match.
Latency does not matter in a batch job. `expected_output_tokens = 180` from these calls (mean
173, 95 of them reasoning). How the verdicts are used: ADR-0014.


## Amendment (ER judge bake-off re-scored, 2026-10-04)

After the owner's label revision (ADR-0014 amendment of 2026-10-04) the bake-off was scored again on
the same 141 labelled gold pairs in [−3, 3], from the LLM cache (`LLM__PROVIDER=offline`, no call,
$0; `reports/judge-eval-<model>-2026-10-04.md`):

| Model | False matches | Match precision (weighted) | Match recall (weighted) | Unsure |
|---|---|---|---|---|
| **gemini-3.8-flash** | 0 | 100% (75.4–100%) | 100% (75.4–100%) | 1.4% |
| gpt-5.4-mini | 3 | 94.9% (62.7–99.5%) | 80.7% (52.2–94.1%) | 1.4% |
| gemini-3.5-flash | 2 | 97.8% (72.7–99.9%) | 99.2% (74.2–100%) | 0.7% |

The extra false matches of the other two models are pairs now labelled "not the same villa" (units
of one complex). The choice stands; cost and latency are those of the first run above.


## Amendment (owner's decision, 2026-10-05): explanation latency accepted with the cache

M10 criterion 4 (explanation p95 at most 4 s uncached) was not met: 6.1–10.6 s uncached on
2026-10-02. Because the results never wait for the explanation and every cached path is instant,
the owner accepted the latency and closed the criterion. gemini-3.8-flash stays the explanation
model; no faster-model re-run is planned unless the owner asks for one.


## Amendment (owner-reviewed query set and a vision check, 2026-10-08)

- **Query understanding on the reviewed set.** The owner reviewed the 50 drafted cases and
  accepted all of them (`eval/query-understanding/reviewed-v1.jsonl`). A run that skips cache
  reads (`discovery eval-understanding --fresh`, a new `JobContext.fresh` flag: answers still
  refresh the cache) measured gpt-5.4-mini uncached: slots 99.3%, exact 98.0%, 0 invented numbers,
  p50 1.3 s, p95 2.1 s, $0.067 (`reports/understanding-2026-10-08.md`). M8 criterion 1 is met.
- **Vision check for sea view and fireplace.** gemini-3.1-flash-lite (`vision_tagging`, prompt
  `photo_vlm_tags` v1, one photo per call) on the owner's 336 labelled photos: sea view 35 of 48
  positive calls agree with the labels (about 73%, recall 35/35), fireplace 18 of 26 (about 69%,
  recall 18/20); answers are near-certain, so no threshold reaches 85% and none is stored. Of four
  "false positives" inspected, all four show the sea or a fireplace the labels missed, so the
  model's real precision is likely higher; the owner's labels stay the judge of it and the two
  tags stay unused. About $0.21. The run over the 75 listings that claim one was not made: it
  would produce scores nothing uses.
