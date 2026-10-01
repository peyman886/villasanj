# Villasanj — Roadmap

Every milestone ends with a **stop**: report → owner review → approval before the next one starts.
A milestone is **done only if** `make lint` and `make test` are green, `CLAUDE.md` and this file are
updated, and the report lists LLM spend (from the ledger), decisions and remaining tech debt.

Changes vs. the initial proposal (and why):

* **Pricing core moved into M3.** H2 (all-in price difference) cannot be measured without the
  engine. M3 builds the pure-domain engine; M6 adds fee-policy sourcing, ranges and offers.
* **Scenario price/calendar capture moved into M2.** The data is time-sensitive: comparing platforms
  requires observations taken within the same short window, so capture starts with the first adapter.
* **New M4 (coverage)** adds platforms 3–4 before full ER, so ER is built and evaluated on all four.
* **Labelling UI in M3** also bootstraps the Next.js app early, so the frontend does not start late.
* Result: M0–M11 (12 milestones) instead of M0–M10.

LLM budget column = planned cap for that milestone (hard caps are enforced by the ledger; project
hard cap $30). Estimates come from [ADR-0005](adr/0005-llm-model-selection-and-cost.md).

| M | Name | LLM cap | Checkpoint with owner |
|---|---|---|---|
| 0 | Understanding & design | $0.05 | ✅ approved 2026-10-01 |
| 1 | Skeleton & LLM platform | $0.20 | ✅ delivered, awaiting review |
| 2 | First vertical slice (jajiga → jabama) | $0.50 | report + robots/ToS audit sign-off |
| 3 | Hypothesis test (ER baseline + pricing core + H1–H3) | $0.50 | **mandatory re-prioritisation review** |
| 4 | Coverage: otaghak + shab, scheduled scenario crawls | $0.50 | report |
| 5 | Full ER | $8.00 | report + precision sign-off |
| 6 | Pricing complete & offers | $0.50 | report |
| 7 | API & canonical villa page | $0.50 | report + UX review |
| 8 | Search: intent, retrieval, ranking, drive time | $2.00 | report |
| 9 | Enrichment & truth check | $6.00 | report |
| 10 | Reviews & "why this villa?" | $6.00 | report |
| 11 | Demo polish | $3.00 | final |

---

## M0 — Understanding & design ✅ (approved 2026-10-01)

Deliverables: `CLAUDE.md`, `docs/ARCHITECTURE.md`, `docs/ROADMAP.md`, ADR-0001…0010,
`docs/research-review.md`, `docs/reference/avalai-models-2026-10-01.csv`, `.gitignore`, `.env.example`.

Acceptance:
- [x] All context files read; understanding summarised to the owner.
- [x] Hardware/environment inventoried (M4, 10 cores, 16 GB, Docker Desktop 29.6 with 7.75 GB, 168 GB free).
- [x] `.env` checked without printing secrets; `/v1/models` fetched (365 models); tier inferred (3).
- [x] Model per LLM task proposed with evidence from a small probe (total spend ≈ $0.006).
- [x] No executable project code written.

---

## M1 — Skeleton & LLM platform ✅ (delivered 2026-10-01, awaiting review)

Scope: monorepo layout; `docker compose` (profiles `core`, `pipeline`, `routing`); custom Postgres image
(PostGIS + pgvector, arm64); Alembic baseline; `Makefile` (`setup up down logs test test-integration
test-live lint fmt typecheck seed crawl reparse match eval dry-run health ci`); Pydantic Settings with
`SecretStr`; `config/llm.toml` task→model routing; structlog JSON logging with secret redaction;
composition root; shared kernel value objects; `LLMClient` port + `AvalAIProvider` + `FakeLLMProvider` +
decorators (cache, fallback, retry, cost governor) + ledger tables + dry-run planner; FastAPI `/health`;
Next.js skeleton (RTL, Vazirmatn) calling `/health`; pre-commit (ruff, mypy, import-linter, gitleaks,
eslint, prettier).

Acceptance criteria:
1. On a clean clone: `make setup && make up` starts `db`, `api` and `web` healthy within 180 s, and
   `make health` prints `db=ok blob=ok llm=fake-ok` (exit code 0).
2. `make lint` = 0 findings: ruff, `mypy --strict` (backend), `tsc --noEmit` strict + eslint (frontend),
   and import-linter with the contracts: domain purity, layer order, context DAG.
3. Architecture test fails if any `*/domain/*` module imports a non-stdlib package or if a platform slug
   appears in a core package (verified by a deliberately failing fixture in the test itself).
4. Shared kernel unit + property tests: `Money`, `MoneyRange`, `DateRange`, `GuestCount`, `GeoPoint`,
   Jalali conversion (≥ 1,000 random dates round-trip against `jdatetime`), Persian normalizer
   idempotency. Domain line coverage ≥ 95%.
5. LLM stack unit tests (FakeLLMProvider, zero network):
   - identical request twice → provider called once (cache hit recorded in ledger, cost 0);
   - invalid JSON then valid → success on attempt 2; the ledger has 2 rows;
   - 3× invalid → `LLMOutputInvalid` (domain error, no raw body in message);
   - 5xx on primary → fallback model used; ledger records actual model;
   - projected cost > remaining job budget → `BudgetExceeded` **before** the provider call;
   - `--dry-run` reports call count, cache hits and estimated USD with 0 provider calls.
6. Opt-in live test (`make test-live`, pytest marker `live_llm`, excluded by default): one structured
   call per configured task model; asserts schema-valid output; total spend < $0.05; header-reported
   tier logged.
7. Secret hygiene: a test asserts that `repr(settings)`, logs and exception strings never contain the
   key; gitleaks runs in pre-commit; `.env` is ignored and the owner's `.env` is normalised to
   `KEY=value` (no spaces).
8. Cost unit check: the ledger total for the live test run is compared with the AvalAI dashboard, and
   the result is recorded in ADR-0005 (validates assumption A2).

---

### M1 results (2026-10-01)

| # | Criterion | Result |
|---|---|---|
| 1 | Clean clone → `make setup && make up` healthy ≤ 180 s; `make health` | ✅ Fresh clone without `.env`: setup 17 s (warm Docker/npm/uv caches), up 29 s, `web=ok db=ok blob=ok llm=fake-ok`. With `.env`: `llm=avalai-ok`. A cold machine also needs image and package downloads. |
| 2 | `make lint` = 0 findings | ✅ ruff, mypy `--strict` (103 files), import-linter (2 contracts kept), tsc strict, eslint, prettier |
| 3 | Architecture test with deliberately failing fixtures | ✅ domain purity, no foreign infrastructure imports, no platform names in core, no invisible characters (each rule has a fixture that must fail) |
| 4 | Kernel tests; domain coverage ≥ 95% | ✅ 98% branch coverage; Jalali conversion checked on every day 1925–2125 (73k days) against jdatetime, plus property tests |
| 5 | LLM stack unit tests (zero network) | ✅ cache hit, validation retry with feedback, `LLMOutputInvalid` without content leaks, fallback on 5xx/4xx, no fallback on auth errors, `BudgetExceeded` before calling (job and project), concurrent budget reservation, dry-run with 0 calls |
| 6 | Opt-in live test, spend < $0.05, tier logged | ✅ all 7 routes + fallback valid; $0.0025 per run; headers show 1000 RPM (tier 3) |
| 7 | Secret hygiene | ✅ tests for repr/logs/errors; gitleaks + exact-match `.env` scanner in pre-commit; `.env` normalised to `KEY=value`; images contain no `.env` |
| 8 | Ledger vs AvalAI dashboard | ⏳ needs the owner: compare the dashboard with the spend listed in the M1 report |

Totals: 120 unit/architecture tests, 6 integration tests, 7 frontend tests, 1 live test (opt-in).

## M2 — First vertical slice: jajiga → jabama

Scope: robots.txt + ToS audit per platform (`docs/sources/<platform>.md`, with the robots snapshot id);
`SourceAdapter` port, `PoliteFetcher`, `SnapshotStore`, frontier queue, `CrawlPlatform`,
`ReparseSnapshots`; jajiga adapter; Catalog normalization (ی/ک, digits, ZWNJ, money units, Jalali dates,
gazetteer v1 with 100–200 places/aliases for Ramsar–Tonekabon); photo download (≤ 800 px) + pHash;
scenario capture (calendar + rates + direct quotes when public) for the scenario dates fixed from the
official calendar; then the jabama adapter.

**Plan B:** if jabama's robots.txt or ToS forbids crawling, stop and report. The OCP proof then uses
otaghak or shab.

Acceptance criteria:
1. Crawl is blocked (unit + integration tested) for any URL disallowed by the cached robots.txt;
   per-domain rate ≤ configured (default 1 req / 3 s + jitter, honouring larger `Crawl-delay`); on 403,
   429 storms or captcha markers, the platform is marked `BLOCKED` and the run stops.
2. jajiga: **every** listing discoverable in the region is crawled, or the coverage gap is reported
   with its reason. Listing parse success ≥ 98%, and failures are quarantined with `ParseError` reasons.
3. Contract tests: ≥ 6 trimmed fixtures per adapter (search page, listing, calendar, reviews, a listing
   with missing fields, an unusual price format) with exact expected `ParsedPage` outputs.
4. Normalizer: ≥ 60 table-driven cases, covering «۱۲٫۵ میلیون», «۱،۵۰۰،۰۰۰ تومان», Arabic digits,
   «ك/ي», ZWNJ variants and place aliases (کلاردشت = کلار دشت = Kelardasht).
5. `make reparse` rebuilds catalog tables from snapshots with **0 network requests** (a network-deny
   test fixture proves it) and yields identical row hashes on two runs.
6. **OCP proof:** the jabama PR diff touches only `ingestion/infrastructure/sources/jabama/**`, its
   tests/fixtures, one entry-point line in `pyproject.toml`, and a `FeePolicy` data row
   (checked with `git diff --stat` and quoted in the report).
7. Scenario capture: for each scenario × {4, 8} guests, observations exist for ≥ 90% of in-region
   listings on both platforms, all taken within one 24 h window (per-listing timestamp spread reported).

---

## M3 — Hypothesis test (review with owner before continuing)

Scope: ER baseline (blocking: place + rooms ±1 and pHash LSH; features: photo set-to-set pHash matches
weighted by photo document frequency, structural diffs, place, price ratio); **labelling UI** (Next.js,
keyboard-driven, side-by-side photos/fields, `match / non-match / unsure`, stratified queue); gold set
v1; pricing engine v1 (pure domain + unit tests); `make eval-hypotheses` report.

Acceptance criteria:
1. Gold set v1: ≥ 300 human-labelled pairs. Stratified over score deciles plus hard negatives (same host
   or complex, different unit). Label protocol written in `docs/er-labeling-protocol.md`. `unsure`
   rate reported.
2. Baseline matcher report: precision, recall and F1 at the chosen threshold with **95% Wilson CIs**,
   blocking recall on gold positives, and the confusion matrix. Reproducible: same dataset hash ⇒ same
   numbers.
3. Pricing engine v1: unit tests for nightly sum, extra guests above base capacity, min-nights,
   unavailable nights, unknown components → open range, direct quote precedence. 100% branch coverage
   on `pricing/domain`.
4. `reports/hypotheses-<date>.md` generated from the DB, with:
   - **H1** overlap: share of in-region canonical villas present on both platforms, with CI and explicit
     caveats (lower bound limited by ER recall and crawl coverage);
   - **H2** all-in difference for matched pairs per scenario × guests: n, median, p90, and the share
     where the cheaper platform flips between scenarios;
   - **H3** "hidden night" rate: nights free on one platform and booked on the other, among matched pairs,
     restricted to observation pairs < 6 h apart.
5. Owner review meeting: the feature priority for M4–M11 is confirmed or changed based on the results.
   The decision is recorded in this file.

---

## M4 — Coverage: otaghak + shab

Scope: two new adapters (robots/ToS audits first); scheduled same-window scenario crawls for all four
platforms; photo pipeline at scale (20–40k photos); crawl metrics.

Acceptance criteria:
1. Each new adapter meets the M2 criteria 1–3 and 6 (the OCP diff rule applies to each).
2. The full region is crawled on all permitted platforms: 1,500–3,000 listings total (actual count
   reported per platform with coverage estimate).
3. One `make crawl-scenarios` run captures all scenarios for all platforms with a per-listing
   timestamp spread ≤ 6 h (reported).
4. Photo pipeline: ≥ 99% of referenced photos downloaded or reason logged; pHash for all downloaded
   photos; storage footprint reported.

---

## M5 — Full entity resolution

Scope: DINOv2 image embeddings (CPU in Docker; optional host MPS runner); image kNN blocking; Splink
model (comparisons: image set similarity levels, rooms/capacity/area diffs, distance range, host
similarity, rare-n-gram text similarity, price ratio); LLM judge bake-off and production judge (composite
photo grids, structured verdict + rationale + cited evidence); constrained clustering (highest-weight
first, ≤ 1 per platform, human cannot-links); review queue UI; canonical ID reconciliation; gold set v2
(+ ≥ 150 pairs from the new platforms); ablations for H5.

Acceptance criteria:
1. Blocking recall ≥ 98% on gold positives, with the candidate-pair count reported.
2. End-to-end **precision ≥ 95% (Wilson lower bound ≥ 92%)** on gold at the operating point, with
   recall reported. If this is not met, the threshold is raised and the recall cost reported, never
   hidden.
3. Pairwise P/R/F1, B-cubed P/R/F1 and a precision-recall curve with the chosen threshold, in
   `reports/er-eval-<date>.md`. Reproducible from dataset hash + run id.
4. Judge bake-off (≈ 80 hard gold pairs × 3 candidate models) → chosen model and cost per pair
   recorded in ADR-0005. The judge's `MATCH` precision on gold ≥ 95%.
5. Clustering invariant: 0 clusters with 2+ listings from one platform (DB constraint plus a test).
   Every merge is traceable to `MatchDecision`s.
6. Ablations: photo-only vs text-only vs full model recall at fixed precision (tests H5).
7. Human queue: every `UNSURE` or low-confidence judge verdict lands in the queue, and resolving it
   updates clusters idempotently.

---

## M6 — Pricing complete & offers

Scope: `FeePolicy` rows per platform with sources (observed checkout breakdowns where public,
otherwise the platform's own published pages; research-report figures are context only);
component ranges; optional fees (e.g. pool heating from claims) shown separately; `Offer` read model
per member listing; staleness rules.

Acceptance criteria:
1. Every `PriceQuote` component has provenance. Property test: no quote without provenance can be
   constructed.
2. For each scenario × guests, each offer is `EXACT`, `RANGE` (bounded) or `OPEN` (≥ low), with the
   distribution reported per platform.
3. Where a platform exposes a direct quote, the computed total and the direct quote are compared on
   ≥ 100 listings, and the error distribution is reported. The engine is fixed or the rule documented
   when |error| > 1%.
4. Staleness: an offer older than the configured max age (default 24 h) is flagged in the API output.

---

## M7 — API & canonical villa page

Scope: FastAPI endpoints (villa, offers by stay+guests, merged calendar, photo groups, conflicts,
provenance); OpenAPI → generated TS client; Next.js canonical page (RTL, Vazirmatn, MapLibre with a
local PMTiles basemap or OSM tiles with attribution); conflict badges; "observed N hours ago" labels.

Acceptance criteria:
1. OpenAPI schema is generated in CI; the TS client compiles in strict mode; API contract tests pass.
2. The canonical page renders for 100% of multi-platform villas without errors (a Playwright smoke
   test over a sample of 50).
3. Every number on the page links to its provenance (source, observed_at). An E2E test clicks 10
   random numbers and asserts that a provenance popover is shown.
4. Accessibility: no critical axe violations. Keyboard navigation works for calendar and offers.
5. p95 API latency < 300 ms for villa + offers on the demo dataset (local).

---

## M8 — Search: intent, retrieval, ranking, drive time

Scope: `UnderstandQuery` (LLM → `SearchIntent` with relative date expressions resolved
deterministically with a Jalali + holiday table; numbers verified against the query text; editable
chips; ambiguity questions only when the answer changes results, shown with result counts); OSRM
routing on a clipped extract (free-flow, labelled); hybrid retrieval (filters → Postgres FTS ± pgvector,
RRF only if it beats FTS in eval); transparent utility ranking with per-feature breakdown and a public
"how we rank" note (no commission factor).

Acceptance criteria:
1. Query-understanding eval: 50 hand-written Persian queries with expected intents; slot accuracy ≥ 90%;
   0 invented numeric constraints; p95 latency ≤ 3 s uncached (reported per model).
2. Retrieval eval: 30 queries with judged relevant villas; nDCG@10 and Recall@20 reported for FTS-only
   vs hybrid. Dense retrieval ships only if it improves nDCG@10 by ≥ 0.03.
3. Drive time: free-flow OSRM time from Tehran for 100% of villas with coordinates; displayed as a range
   when the location is obfuscated. A coverage note is shown ("with 2 h → X villas, with 3 h → Y").
4. Every ranked result exposes its score breakdown in the API and UI.

---

## M9 — Enrichment & truth check

Scope: SigLIP zero-shot photo tags (pool indoor/outdoor, sea/forest view, fireplace, …) locally;
deterministic-first claim extraction (regex + LLM for the residue), with spans verified verbatim;
evidence: photo tags, coastline distance (PostGIS, range under obfuscation), cross-platform fields;
targeted VLM checks with composite images only where local tags are inconclusive; verdicts with
«تأیید نشد» tone; truth bar on the canonical page.

Acceptance criteria:
1. Claim extraction eval on 60 hand-labelled descriptions: claim-level precision ≥ 90%, recall ≥ 80%;
   100% of returned spans are verbatim substrings (enforced by the verifier; failures retried/dropped).
2. Photo-tag eval on 300 hand-labelled photos: per-tag precision/recall reported; tags below 85%
   precision are not used as evidence.
3. Verdict rule tests: `CONTRADICTED` only when the best-case evidence contradicts; distance claims
   evaluated for walk and drive when the mode is unknown.
4. H4 measured: share of listings with ≥ 1 `CONTRADICTED` or `INCONSISTENT_ACROSS_PLATFORMS` claim, with CI.
5. The dry-run estimate for the full enrichment job is within ±25% of the ledger actual (validates the
   estimator).

---

## M10 — Reviews & "why this villa?"

Scope: cross-platform review aggregation (source-labelled, Bayesian-shrunk rating); LLM review summaries
as pros/cons with cited review ids (a point needs ≥ 2 supporting reviews or is labelled as a single
opinion); `ExplainChoice` with fact slots + deterministic verifier + template fallback.

Acceptance criteria:
1. Verifier unit tests: rejects any raw digit outside slots, unknown slot ids, comparisons that
   contradict facts, and uncited summary points.
2. In production runs, 100% of displayed explanations/summaries passed the verifier. Fallback rate
   reported.
3. Blind owner review of 20 villas' summaries vs raw reviews: ≥ 18/20 judged faithful (the result is
   recorded either way).
4. Explanation latency p95 ≤ 4 s uncached; cached demo paths are instant.

---

## M11 — Demo polish

Scope: final same-window crawl; metrics dashboard (overlap, precision with CI, hidden nights, unverified
claims, LLM spend by task); group mode (per-person cost, nearby villas for split groups); storyboard
scenarios rehearsed with real data (every number in the video traceable); README for reviewers.

Acceptance criteria:
1. `make demo` brings up the full stack from a local data bundle with no network access except
   explicitly cached LLM responses.
2. Every number in the demo script appears in a generated report with provenance.
3. Total project LLM spend ≤ $30 (ledger) and reconciled with the AvalAI dashboard.
4. E2E Playwright suite green for the storyboard paths.

---

## Out of scope for the demo (explicit)

Learning-to-rank from clicks, price history / "book now or wait", price alerts, image search, host
profiles across platforms, stock-photo fraud detection across unrelated villas, partner feeds.
These are revisited after M3/M5 findings.
