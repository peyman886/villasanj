# Villasanj · ویلاسنج

> یک ویلا، همه‌ی حقیقت: one villa, the whole truth.

A Torob-style product for Iranian villa rentals (Ramsar–Tonekabon), built for the Torob "AI Product
Engineer" challenge: **crawl offers → normalize messy data → rank by user intent → explain the best
choice.** Each real villa gets one page that brings its listings from different platforms
together, with the all-in price for your dates and group, a calendar, reviews and a
truth check of what the listing claims. Every number shown has a source and an observation time.

Status (2026-10-08): every milestone is done. Four criteria were closed by the owner's decision
rather than met as written (no new platforms, no public direct quote, explanation latency accepted
with the cache, the retrieval eval on 11 judged queries instead of 30); they are marked so, not as
done. The status of every criterion, with its evidence, is generated into
[`docs/ROADMAP.md`](docs/ROADMAP.md) and shown in the app at **`/docs/milestones`**.

**Documentation and technical report: [`/docs`](http://localhost:3300/docs)** inside the app
(Persian): architecture, entity resolution and the label-correction history, search, truth check,
LLM use and cost, every evaluation with its confidence interval, tests, milestones, ADRs and the
generated reports, with 20 diagrams. It works in the offline demo too.

## What works today

| Step | What it does | Measured |
|---|---|---|
| Crawl | Polite, ToS-audited crawlers for **jabama** and **shab** (the other platforms forbid crawling; ADR-0011). One request per host every ≥ 3 s, robots.txt honoured, stop on block, every response snapshotted. | 2,987 + 601 listings in the region; every calendar captured again within one window on 2026-10-03 (jabama 3.2 h, shab 0.6 h); 14.4k reviews, 17.9k photos selected (5 per listing) |
| Normalize | Pure parsers from snapshots: rial/toman, Jalali dates, Persian text, platform quirks (e.g. jabama's `0` means "not set"). Place names through a curated gazetteer. | 0 parse failures on the second discovery pass |
| Price | All-in offer per listing, stay and group, every component with provenance. Unknown fees give an open bound ("حداقل …"), never an invented cap. | every bookable offer is OPEN today: neither platform publishes its fees |
| Understand | A Persian query becomes a structured intent (LLM). A verifier rejects any number the query did not say; dates are resolved by code against a sourced holiday calendar. | on the owner-reviewed 50-query set, uncached (2026-10-08): 99.3% slots, 0 invented numbers, p95 2.1 s ([report](reports/understanding-2026-10-08.md)); wishes it cannot measure are said back |
| Rank | Filters with a stated reason, cautions for unknowns (including a contradicted claim), requested features confirmed first, then a transparent score (price per person and night, Bayesian rating). No commission factor; the rules are public at `/how-we-rank`. | `/search`; on 11 owner-judged queries nDCG@10 0.786 against 0.581 for cheapest-first and best-rated-first ([report](reports/relevance-2026-10-08.md)) |
| Explain | The LLM writes Persian prose around fact slots (`{F1}`); code formats every number and decides every comparison; a verifier rejects digits, comparatives and availability stated as a fact; a template is the fallback, also when no model can answer. It streams in after the results. | 20 draft queries: 100% LLM text, 0% fallback; p95 6–10 s uncached (not yet the 4 s target) |
| Truth check | Every published distance against the OSM coastline and OSM places (town centres can contradict; shops, restaurants and woods only support, the map lists only some), as ranges over the listing's blurred location; description features against the listing's own amenity list. "Contradicted" only when even the best case fails. Two listings of one villa that state a claim differently are shown side by side, never as which one is wrong. | H4 ([report](reports/h4-2026-10-08.md)): listings with a claim the map contradicts or the other platform states differently: jabama 9.7% (8.5–11.0%), shab 5.5% (3.9–7.6%) |
| Drive time | Free-flow OSRM times from Tehran on a clipped OSM graph, as a range over the blur circle. | 100% of 3,588 listings routed |
| Match listings | Blocking (location + rooms, photo hashes, DINOv2 image embeddings), evidence, a transparent rule score, constrained clustering (≤ 1 listing per platform). An LLM judge reads photo grids for close calls: it vetoes rule merges it calls different villas (units of one complex), and its own suggestions wait for a human (ADR-0014). | on 362 owner-labelled pairs (48 complex-unit labels corrected on 2026-10-04): precision 100% (95.9–100%), recall 65.0%; the owner also labelled all 376 pairs the judge queued ([report](reports/er-eval-2026-10-08.md)) |
| One villa | `/villas/<id>`: each platform's own offer side by side (never merged), both calendars with the nights free on one and taken on the other, where the listings disagree, every review with its platform and one cited summary. | 3,211 villas, 377 on both platforms (the owner confirmed 70 of the judge's 72 decided suggestions); 20.7% of nights seen on both are free on one and taken on the other ([report](reports/hypotheses-2026-10-04.md)) |

## Principles (enforced in code and tests)

1. **No fabricated number.** Every price or claim has provenance (source, snapshot, observed time).
   Unknown means a range or an open bound.
2. **LLMs never write digits into user-facing text** (ADR-0007): facts go in as slots, a
   deterministic renderer fills them, a verifier checks the text.
3. **Prices are never merged across listings**; a villa has at most one listing per platform.
4. **Truth checks are not accusations**: «تأیید نشد» unless the best case contradicts.
5. **Availability and prices are observations with an age**, never states.
6. **Ethical crawling** (ADR-0008): robots.txt and ToS audit per platform before the first request,
   identifying user agent, no evasion of blocks, captchas or logins.

## Quick start

Requirements: Docker (Compose v2.24+), [uv](https://docs.astral.sh/uv/), Node.js ≥ 20.9, GNU Make.

```bash
cp .env.example .env    # optional: AVALAI_API_KEY for the real LLM gateway; CRAWL__CONTACT for live crawls
make setup              # dependencies, git hooks, Docker images
make up                 # db, migrations, api, web
make health             # web=ok db=ok blob=ok llm=fake-ok (or llm=avalai-ok with a key); non-zero if degraded
```

- Web: <http://localhost:3300> (`/search`, `/villas/<id>`, `/listings/<platform>/<id>`, `/metrics`,
  `/how-we-rank`, **`/docs`**, the owner's review hub `/review`; labelling: `/label`, `/label?queue=er-human`, `/label/photos`, `/label/summaries`,
  `/label/claims`) · API:
  <http://localhost:8800/docs> · Postgres: `127.0.0.1:5433`.
- Without `AVALAI_API_KEY` the stack runs with a deterministic fake LLM provider.
- Crawled snapshots and photos are never committed. A fresh clone has an empty catalog: crawl
  (`make crawl P=jabama LIVE=1`) or rebuild from your own snapshots (`make reparse`).

## Offline demo

```bash
make demo-bundle        # dump the database, LLM cache included, into data/demo (~55 MB)
make demo               # a separate stack on http://localhost:3400 from the bundle; cached LLM answers only
make demo-down
```

The five-minute script is [`docs/demo-script.md`](docs/demo-script.md); every number in it names the
generated report it comes from. The reviewer's guide is at `/docs/demo` (on the demo:
<http://localhost:3400/docs/demo>); the documentation needs no network.

## Main flows

```bash
make crawl P=jabama LIVE=1        # polite crawl (needs CRAWL__CONTACT); default replays snapshots
make reparse                      # rebuild the catalog from snapshots, zero network
make match                        # photo hashes + embeddings, blocking, evidence, scores
cd backend && uv run villasanj er queue --name gold-v1   # draw the stratified labelling queue
# label pairs at http://localhost:3300/label (keyboard: M / N / U)
make eval                         # precision/recall with Wilson CIs against the labels
cd backend && uv run villasanj er report     # reports/er-eval-<date>.md (curve, policies, B-cubed, ablations)
cd backend && uv run villasanj er villas     # canonical villas at config/er.toml's policy
make osm-download osm-prepare routing-up geo   # coastline + places, distances, drive times, truth checks
cd backend && uv run villasanj discovery search "ویلای استخردار در رامسر برای ۶ نفر آخر هفته بعد"
cd backend && uv run villasanj llm spend       # LLM cost from the ledger (hard cap $30)
```

## Development

```bash
make test               # unit + architecture tests (no network, no Docker) + frontend tests
make test-integration   # Postgres + PostGIS in a throwaway container
make test-e2e           # Playwright on the running app: provenance clicks, axe, keyboard
make lint               # ruff, mypy --strict, import-linter, tsc, eslint, prettier, diagrams
make quality-report     # every suite with machine-readable results -> reports/quality-<date>.json
make help               # every target
```

## Documentation

- **In the app: `/docs`** (Persian, the full technical report with live numbers and diagrams;
  reviewer's guide at `/docs/demo`)
- [Architecture](docs/ARCHITECTURE.md): bounded contexts, layers, domain model, schema, ports, assumptions
- [Roadmap](docs/ROADMAP.md): milestones, acceptance criteria, what was built ahead and what is blocked
- [Decisions](docs/adr/README.md): ADRs 0001–0014 (LLM gateway and cost, provenance, crawling ethics,
  entity resolution, image matching, geo evidence, the ER decision policy)
- [Reports](reports/): hypotheses H1–H3, the ER evaluation, H4, the judge bake-off, quality and
  performance — generated, each with a JSON artifact (command, time, provenance)
- [Sources](docs/sources/README.md): robots/ToS audit and what each platform publishes
- [Labelling protocol](docs/er-labeling-protocol.md) (Persian) and the
  [research review](docs/research-review.md)

Map data © OpenStreetMap contributors (ODbL).
