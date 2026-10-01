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
| 1 | Skeleton & LLM platform | $0.20 | ✅ delivered |
| 2 | First vertical slice (jabama → shab) | $0.50 | ✅ approved 2026-10-01 |
| 3 | Hypothesis test (ER baseline + pricing core + H1–H3) | $0.50 | **open**: waits for the photo crawl and the owner's labels; then the mandatory re-prioritisation review |
| 4 | Coverage: permission-gated adapters, wider region, scheduled scenario crawls | $0.50 | **partly started in parallel** with M3 (only parts independent of M3 results) |
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

## M2 — First vertical slice: jabama → shab ✅ (approved 2026-10-01)

**Audit outcome (2026-10-01, [`docs/sources/README.md`](sources/README.md), ADR-0011):** jajiga,
otaghak and mihmansho forbid crawling in their Terms → not crawled; permission requests drafted in
[`docs/outreach/`](outreach/permission-request-fa.md). jabama and shab approved by the owner.

Scope: `SourceAdapter` port, `PoliteFetcher`, `SnapshotStore`, frontier queue, `CrawlPlatform`,
`ReparseSnapshots`; **jabama adapter first**; regional inventory count for both platforms from
sitemaps; Catalog normalization (ی/ک, digits, ZWNJ, money units, Jalali dates, gazetteer v1 with
100–200 places/aliases for Ramsar–Tonekabon); photo download (≤ 800 px) + pHash; scenario capture
(calendar + rates + direct quotes when public) for scenario dates fixed from the official calendar;
then the **shab adapter as the Open/Closed proof**.

Acceptance criteria:
1. Crawl is blocked (unit + integration tested) for any URL disallowed by the cached robots.txt;
   per-domain rate ≤ configured (default 1 req / 3 s + jitter, honouring larger `Crawl-delay`); on 403,
   429 storms or captcha markers, the platform is marked `BLOCKED` and the run stops.
2. jabama: **every** listing discoverable in the region is crawled, or the coverage gap is reported
   with its reason. Listing parse success ≥ 98%, and failures are quarantined with `ParseError` reasons.
3. Contract tests: ≥ 6 trimmed fixtures per adapter (search/sitemap page, listing, calendar, reviews, a
   listing with missing fields, an unusual price format) with exact expected `ParsedPage` outputs.
4. Normalizer: ≥ 60 table-driven cases, covering «۱۲٫۵ میلیون», «۱،۵۰۰،۰۰۰ تومان», Arabic digits,
   «ك/ي», ZWNJ variants and place aliases (کلاردشت = کلار دشت = Kelardasht).
5. `make reparse` rebuilds catalog tables from snapshots with **0 network requests** (a network-deny
   test fixture proves it) and yields identical row hashes on two runs.
6. **OCP proof:** the shab PR diff touches only `ingestion/infrastructure/sources/shab/**`, its
   tests/fixtures, one entry-point line in `pyproject.toml`, and a `FeePolicy` data row
   (checked with `git diff --stat` and quoted in the report).
7. Scenario capture: for each scenario × {4, 8} guests, observations exist for ≥ 90% of in-region
   listings on both platforms, all taken within one 24 h window (per-listing timestamp spread reported).
8. Regional inventory of both platforms counted from sitemaps and reported (input to the region decision).

---

### M2 results (2026-10-01)

Live crawl on 2026-10-01 (UTC): jabama 07:51–11:11, shab 08:09–09:31, plus a shab photo sample at
11:03–11:15. That is 4,491 stored responses, with no retries, give-ups or blocks. Details per host
are in [`docs/sources/README.md`](sources/README.md).

| # | Criterion | Result |
|---|---|---|
| 1 | robots.txt, pacing and stop-on-block, unit + integration tested | ✅ 13 PoliteFetcher and 3 crawl-loop unit tests, plus a local-HTTP integration test of the real httpx + protego stack: disallowed paths are never requested (also after a redirect), Crawl-delay is honoured, and the user agent is sent. The integration test found that the first request after robots.txt ignored Crawl-delay. That is fixed, and neither platform publishes a Crawl-delay. A 429 storm now stops the run like a 403 streak does. A blocked platform stays blocked: the next live run refuses to start until the owner passes `--after-block`. |
| 2 | jabama: every regional listing, parse ≥ 98%, failures quarantined | ✅ 2,952/2,952 stay pages that answered 200 were parsed (**100%**, 0 failures). ⚠️ Coverage gap: the search pages declare 2,800 (Ramsar) and 976 (Tonekabon) results, and we collected 2,772 and 973 unique stays. The missing 31 were never shown on a fetched page; result order shifting during the 3 h crawl is the likely cause, but it is not verified. Also excluded: 8 stays outside the region box, and 2 stays that answered 404 (removed). |
| 3 | ≥ 6 trimmed fixtures per adapter | ✅ jabama 6 (search, last search page, page without flight data, stay, unpriced new stay, removed stay); shab 6 (sitemap, house, house outside the region, house without data, two calendar payload shapes). ⚠️ No reviews fixture: reviews are not parsed until M10. "Unusual price format": both platforms publish integer prices; their quirks are covered (jabama `0` = not set, shab in toman), and text prices are covered by the normalizer table. |
| 4 | Normalizer ≥ 60 table-driven cases | ✅ 111 cases: 39 money-text, 11 Persian-text, 28 gazetteer, 33 gazetteer-config. They include «۱۲٫۵ میلیون», «۱،۵۰۰،۰۰۰ تومان», ك/ي, ZWNJ variants and کلاردشت = کلار دشت = Kelardasht. |
| 5 | `make reparse`: 0 network requests, identical row hashes | ✅ The ingest use case has no Fetcher, and a socket-blocking test proves it. The catalog was truncated and rebuilt twice from snapshots: incremental build, rebuild 1 and rebuild 2 gave identical hashes for 3,552 listings, 278,172 calendar observations, 0 parse failures and 199 photos. |
| 6 | OCP proof | ✅ with one caveat. The shab commit `9a92fa9` touches 11 files: `sources/shab/**` (2), its contract test (2), 6 fixtures and **one** entry-point line in `pyproject.toml`. It needed one generic core extension first (`f5f9077`: calendars served on their own page, 8 files), which is stated openly. ⚠️ No `FeePolicy` row: fee policies arrive with the pricing engine (M3). |
| 7 | Scenario capture ≥ 90% of in-region listings, within 24 h | ✅ jabama 2,951/2,951 (100%) for weekend, midweek and holiday, spread 3.2 h. shab 597/597 in-region listings (597/601 = 99.3% including the 4 with bogus coordinates), spread 0.6 h. Calendar observations do not depend on group size; {4, 8} guests change only the price, which M3's pricing engine computes. No direct quotes: neither platform exposes a public quote request that we use. |
| 8 | Regional inventory | ✅ shab sitemaps list 601 houses (516 Ramsar + 85 Tonekabon). jabama publishes no sitemap, so its inventory comes from search pages: 2,961 unique stays (2,953 in the region box). Together: **3,554 listing pages** for 3,552 parsed listings. |

Also delivered:
- **Gazetteer v1:** [`config/gazetteer.toml`](../config/gazetteer.toml) has 117 places (6 cities, 111 localities) and 21 aliases, curated from observed names. Of 559 shab locality texts, 401 (72%) resolve to a locality and 42 name a city. The other 116 are streets, squares, sentences or typos, which are deliberately left unresolved. All 27 non-trivial resolutions were reviewed by hand; there is no other ground truth. jabama's neighbourhood field is always empty, so jabama listings are placed by city and coordinates (400 m radius) only.
- **Photos and pHash:** 199 shab photos (40 listings) were fingerprinted with 0 unreadable. Throughput was 3.7 s per photo at the polite rate; storage 115 MB (593 KB on average). ⚠️ "≤ 800 px" is not met for shab: its smaller renditions are 4:3 crops, which break pHash for portrait photos (distance 20–32; ADR-0008 amendment 5). Photos are fetched on demand, and M3 sets how many per listing.
- **Data-quality findings for later milestones:** 4 shab listings with impossible coordinates (input for the "contradiction" badge); 541 jabama listings with no reviews; 10 jabama listings that allow extra guests but publish no extra-guest price (unknown, never "free").

LLM spend in M2: **$0** (no LLM calls).

Tech debt carried forward:
- A second pass over jabama search pages to close the 31-listing gap.
- 45 thumbnail requests from the crop experiment were not stored as snapshots, because it was a one-off script.
- The parent city of `khazar-kenar` is a split vote (ramsar 7, tonekabon 1), and `chalkesh` has no parent (tie).

## M3 — Hypothesis test (review with owner before continuing) — in progress

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

### M3 progress (2026-10-01)

Owner decisions for M3 (2026-10-01): keep RFC 9309 robots handling; AvalAI cost is not a constraint;
photos may be processed locally or through AvalAI, whichever is technically better (decided in
ADR-0012, by measurement); avoid downloading photos needlessly.

Built and tested:
- **Pricing engine v1** (`pricing/domain`, 100% branch coverage enforced by `make test`): nightly
  sum, extra guests, min nights, unavailable/unknown nights, rate-card fallback as a range, open
  upper bound for unknown fees (`config/fees.toml`: neither platform publishes fees), direct-quote
  precedence. `villasanj pricing quote`.
- **Image embeddings:** local DINOv2-small, pinned revision, stored once per image content
  (ADR-0012, chosen by a label-free benchmark against pHash, DINOv2-base and two AvalAI models).
- **ER baseline:** blocking union (location + rooms, pHash, embedding neighbours, same-platform
  shared photos, wide net), photo evidence weighted by document frequency, transparent rule score,
  dataset hash per run (`make match`).
- **Gold set tooling:** stratified queue (score bands × photo/geo groups, same-platform hard
  negatives, wide net; weights by stratum), labelling UI at `/label` (keyboard, no scores shown),
  `docs/er-labeling-protocol.md`, weighted P/R with Wilson CIs and blocking recall (`make eval`).
- **Hypothesis report** H1–H3 (`make eval-hypotheses`).

Photo policy in practice: 5 coverage photos per listing are fetched politely (~14.7k jabama,
~3k shab; jabama ~15 h at 1 request / ~3.6 s), because photo-based blocking needs photos of every
listing (83% of jabama listings are within 1 km of a shab listing with ±1 bedrooms, so a location
prefilter would save little). The labelling UI shows every photo straight from the platforms' CDNs
(no copy on our server).

Waiting for: the photo crawl → `make match` → `villasanj er queue --name gold-v1` → **owner labels
≥ 300 pairs** → `make eval` → `make eval-hypotheses` → owner review (criterion 5).

Stack (2026-10-02): the `api` and `web` images were rebuilt and only those two containers recreated (the db and the crawl untouched), so `/label`, `/search` and the listing pages run current code on port 3300. A throwaway queue `rehearsal-20261002` (362 pairs from the rehearsal candidates) was opened in `/label` to check the UI end to end and then deleted; no label was recorded.

Rehearsal (2026-10-02, **not a result**): `make match` on the photos downloaded so far finished in
2 min 46 s (4,379 new embeddings; 153,923 candidate pairs, 28,059 from the narrow blocks). It
proves the path end to end and front-loads the embeddings (stored once per image), so after the
crawl only the remaining photos are processed. The candidates are replaced by the post-crawl run
before gold-v1 is built.

---

## M4 — Coverage: permission-gated adapters and wider region — partly in progress (parallel to M3)

Scope (changed by ADR-0011): adapters for any platform that grants written permission (jajiga,
otaghak, mihmansho), each recorded in ADR-0011 before the first request; widening the region on jabama
and shab if M3 shows too few cross-platform pairs; scheduled same-window scenario crawls; photo pipeline
at scale; crawl metrics.

Acceptance criteria:
1. Each new adapter meets the M2 criteria 1–3 and 6 (the OCP diff rule applies to each), and its
   written permission is linked from ADR-0011.
2. Regional coverage reported per platform (listing count and coverage estimate).
3. One `make crawl-scenarios` run captures all scenarios for all permitted platforms with a per-listing
   timestamp spread ≤ 6 h (reported).
4. Photo pipeline: ≥ 99% of referenced photos downloaded or reason logged; pHash for all downloaded
   photos; storage footprint reported.

### M4 progress, in parallel with the open M3 (2026-10-01)

The owner asked to continue with work that does not depend on M3's final outputs while the photo
crawl runs. M3 stays **open**: gold-v1, the labels, threshold calibration, precision/recall, the H1–H3
results and the re-prioritisation review are not done and nothing provisional is recorded as final.

| M4 part | Status | Why |
|---|---|---|
| Adapters for jajiga / otaghak / mihmansho | ⛔ blocked | No written permission yet (ADR-0011). |
| Wider region | ⏸ waits for M3 | Only "if M3 shows too few cross-platform pairs" (H1). |
| Same-window scenario capture (criterion 3) | ✅ built, **not run** | `make crawl-scenarios` plans the capture (currently jabama 2.9 h, shab 0.6 h, in parallel; LIVE=1 runs it). Running it now would change the catalog under the M3 gold set, so it runs after M3 or for the M11 final crawl. |
| Crawl metrics | ✅ built | `make crawl-metrics`: traffic per host with measured pacing (every host: min interval ≥ 3.05 s, median ~3.7 s). |
| Photo pipeline report (criterion 4) | ✅ built; final numbers after the crawl | `catalog photo-report`: selected / downloaded / failed with reasons / coverage / hashed / embedded / storage. "≥ 99% of referenced photos" is read as ≥ 99% of the photos the policy selects (5 per listing, ADR-0012). The full 66k would be ~50 h of polite crawling for little ER gain. |
| Regional coverage per platform (criterion 2) | ✅ built | `catalog inventory`. A second discovery pass was run before gold-v1 exists, so no label is affected. jabama search pages again (119 pages): **34 new stays**, catalog 2,951 → 2,985, 0 parse failures. shab sitemaps again: 0 new houses (601). Their coverage photos were queued too. |
| Photo pipeline, shab (2026-10-01 16:46 UTC) | ✅ complete | 3,004 selected → 3,004 downloaded (100%), 3,004 fingerprinted, 2,962 distinct images embedded, 1.09 GB. jabama is still crawling (`catalog photo-report`). |

M5–M11: only parts that do not depend on M3's outputs were built, all provisional; see "Work done ahead of its milestone" below. M3's review can still reorder them.


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

## Work done ahead of its milestone (while M3 waits for the photo crawl and labels)

The owner asked to use the waiting time for work that does **not** depend on M3's final outputs
(gold-v1, threshold calibration, precision/recall, H1–H3) or on final entity resolution. Everything
below is deterministic logic, schemas, interfaces, APIs or tests, built ahead of its milestone and
**provisional until the M3 review confirms the priorities**. Nothing here was run as a final ER
result.

| Built (commit) | Milestone, criterion | Status | Depends on M3/ER for |
|---|---|---|---|
| Quote provenance on every component, OfferKind EXACT/RANGE/OPEN, offers with staleness, distribution report (`90a5e5d`) | M6 crit. 1, 2, 4 | ✅ done, per listing | nothing; villa-level offers group listings after M5 |
| Slot renderer and verifier (`6483aa7`) | M10 crit. 1 (ADR-0007) | ✅ done | nothing |
| Reviews parsed from stored pages (14.4k), Bayesian rating prior (`0ceee65`) | M10 prerequisite | ✅ done, per listing | cross-platform aggregation per villa (M5) |
| Constrained clustering, stable villa ids, B-cubed, `er.villa*` schema with DB constraint (`985aa50`) | M5 crit. 3 (B-cubed), 5 | ✅ built, **not run** | final match decisions (gold set) |
| Listing read API with required provenance, OpenAPI → typed TS client, drift check (`4b82fef`) | M7 crit. 1 | ✅ done, listing level | villa endpoints (M5) |
| Gray-zone LLM judge: grids, verdict schema, pinned prompt, dry-run pricing (`175a7bf`) | M5 crit. 4 (infrastructure) | ✅ built, **dry-run only** | the bake-off, model choice and thresholds (gold set) |
| Distance claims → ranges; verdicts per reading (walk and drive when the mode is unknown); `enrichment claims` coverage report: 100% of 18,707 jabama + 3,919 shab claims parse (`79c3047`) | M9 crit. 3 | ✅ rule built and tested; **no real verdicts yet** | nothing; real verdicts need measured distances (coastline/POIs, an external OSM download the owner has not approved yet) |
| Persian number mentions; date-expression resolver; holiday calendar (Fridays + fixed solar holidays from `config/holidays.toml` + lunar holidays only where jabama flags them); provisional `SearchIntent` with number/place verifier; `discovery holidays` (`3baffb5`) | M8 crit. 1 (0 invented numbers), date resolution | ✅ deterministic parts built; **no LLM call yet** | nothing; the M8 query eval (50 queries) and model choice are still to do |
| Listing page `/listings/<platform>/<id>`: offers per scenario × group, 60-night Jalali calendar, reviews; every number opens its provenance card (native Popover API) (`1661ee4`) | M7 crit. 3 (listing level), 4 (keyboard: Escape/Tab checked by hand) | ✅ built, checked with playwright-cli on a jabama and a shab listing (1280/375 px) | the canonical villa page (M5); E2E and axe tests come with it |
| API latency measured on 50 random listings (25 per platform), host API, local db: listing + offer p95 = 8 ms (no commit: a measurement) | M7 crit. 5 (listing level) | ✅ measured 2026-10-01 | villa + offers latency is measured again with M5's villa endpoints |
| `UnderstandQuery`: LLM → `SearchIntent`, verifier, one retry with violations, then drop; `discovery understand [--dry-run]`; prompt v2 (`43a2e8d`) | M8 crit. 1 (infrastructure) | ✅ built; live sanity check on 9 queries, all correct, $0.0031 | nothing; the 50-query eval (who writes the gold intents is the owner's call) and the model bake-off are still to do |
| Review summaries: cited pros/cons, single opinions labelled by code, verifier + one retry + drop; `enrichment summarize [--dry-run]`; `reasoning_effort = "low"` measured (ADR-0005 amendment) (`6106916`) | M10 crit. 1–2 (infrastructure) | ✅ built; live on 2 listings, $0.0188 in total | villa-level summaries over merged reviews (M5); storing and showing them; the owner's blind review of 20 villas (crit. 3) |
| Feature vocabulary shared with search intents; rule-based description claims (verbatim spans, negation, shared facilities); `config/features.toml` amenity mapping; `enrichment features` report: jabama pool 123 agree / 2 disagree, parking 523 / 11 (`c9a9ff1`) | M9 (deterministic stage of claim extraction) | ✅ built; 3 rule errors found by reading the report are tests now | the 60-description eval (crit. 1), the LLM residue, photo tags and coastline evidence, cross-platform checks (M5) |
| `llm spend`: ledger totals per task and model and the remaining cap (`be4ef79`) | M11 crit. 3 (and every milestone report) | ✅ built; $0.0247 of $30 on 2026-10-02 | nothing |
| Ranking: reasons for every exclusion, cautions for unknowns, confirmed requested features first, then a named-contribution score; ambiguous budget basis returns the counts per reading. `SearchListings`: query → intent → dates → places → batch offers → feature evidence → ranking; `discovery search` (`b45991d`, `a897f3f`) | M8 crit. 4 (score breakdown), ambiguity questions | ✅ built at listing level; live run on real data, $0.0004 per query | canonical villas (M5) replace listings; the retrieval/ranking eval (crit. 2) tunes the weights; OSRM drive time (crit. 3) needs an OSM extract |
| `ExplainChoice`: facts and comparison built by code, Persian prose around slots, verifier + ≥ 2 facts, one retry, template fallback; availability shown with its observation age; prompt v3 after three live runs (`4e0d586`) | M10 crit. 1, 2, 4 (infrastructure) | ✅ built; live on real searches, $0.0005–0.0009 each, 2.9 s | villa-level facts (M5); fallback rate over a real query set; the owner's review |
| Search API `POST /search` and `/search` page: chips of the query as understood, date caveats, budget question with counts per reading, explanation with a provenance card on every value, result cards with cautions and score breakdown linking to the listing page (`e183dcd`) | M8 scope (chips, ambiguity questions with counts), crit. 4; M10 crit. 2 | ✅ built at listing level; playwright-cli check at 1280/375 px | editable chips; villa results (M5); E2E tests with M7 |
| Query-understanding eval harness; `discovery eval-understanding`; **50-case draft set** `eval/query-understanding/draft-v1.jsonl` with a note per case (`ee59207`, `1387487`) | M8 crit. 1 | ✅ built. **Provisional until the owner reviews the draft:** slots 99.3%, exact 98%, 0 invented numbers after prompt v3 and a parser fix found by the first run (95.1% before); latency p50 2.9 s / p95 5.5 s (target ≤ 3 s, not met) | the owner's review of the 50 expected intents; a latency fix (model bake-off or a shorter path) |
| Geo evidence (ADR-0013): OSM snapshot iran-260930 clipped to the Tehran–Caspian box; coastline in PostGIS; coast distance with its blur range for 3,583 listings; OSRM free-flow drive times from Azadi Square for 100% of 3,586 listings (median 261 min); `enrichment truth-sea`: 170/1,909 jabama and 11/175 shab listings with a sea claim have one contradicted, after three accusatory rule errors were fixed (`1825c48`) | M8 crit. 3 (listing level); M9 crit. 3, crit. 4 (H4, sea claims, listing level) | ✅ done at listing level | villa ranges (M5); other claim targets need OSM POIs; INCONSISTENT_ACROSS_PLATFORMS needs M5 |
| Geo in search and pages: drive limit (too_far, straddle caution), near_sea from the map (A17), drive and coast facts in explanations, `/listings/{p}/{id}/geo`, geo on search cards with provenance notes (`49d3697`) | M8 crit. 3 (display as a range), crit. 4 | ✅ done at listing level | villa ranges (M5); a coverage note "with N h → X villas" on the search page |
| Playwright E2E `make test-e2e`: 10 seeded random numbers open their provenance on the listing and search pages; axe: no serious/critical violation (one contrast issue found and fixed); calendar keyboard; no sideways scroll at 375 px (`285db69`) | M7 crit. 3, 4 (listing and search pages) | ✅ 8 passed | the same checks on the canonical villa page (M5), crit. 2 smoke over 50 villas |
| Editable chips (remove a constraint, search again from the cached understanding; removing never adds a number) and the drive-limit coverage note (results with a 3/4/5/6 h free-flow limit) (`16215b2`) | M8 scope (editable chips), crit. 3 (coverage note) | ✅ done at listing level; E2E covers chip removal | villa counts after M5 |
| Listing map: MapLibre, static, OSM raster tiles with attribution, the pin and its blur circle (dashed when assumed) (`4facc3d`, ADR-0003 amendment) | M7 scope (map) | ✅ done | a local basemap for the offline demo (M11 crit. 1) |
| Photo tags: local SigLIP 2 zero-shot scores per image (pool, jacuzzi, sea_view, forest, fireplace, barbecue), a stratified labelling queue, `/label/photos`, per-tag thresholds at ≥ 85% precision or "not used" (`78f044c`) | M9 crit. 2 (infrastructure) | ✅ built; scoring all photos | the owner's ~300 photo labels (queue `photos-v1`, drawn after the crawl); only then can tags count as evidence |

Still blocked or waiting:
- **M3:** photo crawl (jabama, ~11 h left on 2026-10-01 17:00 UTC) → `make match` → gold-v1 → owner labels → eval → H1–H3 → review.
- **M4:** new adapters (no written permission); wider region (H1).
- **M5:** Splink / supervised model, judge bake-off, ablations, human review queue for UNSURE, clustering on real data — all need the gold set.
- **M6 crit. 3:** direct-quote comparison: no public quote source found on either platform.
- **M8:** the 50-query eval set needs the owner's review before its result counts; the latency target is not met yet; retrieval eval (crit. 2) and villa-level ranking need M5.
- **M9:** sea claims are judged (ADR-0013); other targets need OSM POIs; the 60-description claim eval and the 300-photo tag eval need hand labels; photo tags (SigLIP) not started.
- **M10–M11:** not started beyond the pieces above.

---

## Out of scope for the demo (explicit)

Learning-to-rank from clicks, price history / "book now or wait", price alerts, image search, host
profiles across platforms, stock-photo fraud detection across unrelated villas, partner feeds.
These are revisited after M3/M5 findings.
