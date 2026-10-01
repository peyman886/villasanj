# Villasanj · ویلاسنج

> یک ویلا، همه‌ی حقیقت: one villa, the whole truth.

A Torob-style product for Iranian villa rentals (Ramsar–Tonekabon), built for the Torob "AI Product
Engineer" challenge: **crawl offers → normalize messy data → rank by user intent → explain the best
choice.** Each real villa is meant to get one page that brings its listings from different
platforms together, with the all-in price for your dates and group, a calendar, reviews and a
truth check of what the listing claims. Every number shown has a source and an observation time.

Status (2026-10-02): milestones M0–M2 delivered; **M3 (the entity-resolution hypothesis test) is
open** and waits for the owner's hand labels of ~300 listing pairs. Work that does not depend on M3
was built ahead of its milestone and is marked provisional in [`docs/ROADMAP.md`](docs/ROADMAP.md).

## What works today

| Step | What it does | Measured |
|---|---|---|
| Crawl | Polite, ToS-audited crawlers for **jabama** and **shab** (the other platforms forbid crawling; ADR-0011). One request per host every ≥ 3 s, robots.txt honoured, stop on block, every response snapshotted. | 2,985 + 601 listings in the region, 281k calendar observations, 14.4k reviews, 17.9k photos selected (5 per listing) |
| Normalize | Pure parsers from snapshots: rial/toman, Jalali dates, Persian text, platform quirks (e.g. jabama's `0` means "not set"). Place names through a curated gazetteer. | 0 parse failures on the second discovery pass |
| Price | All-in offer per listing, stay and group, every component with provenance. Unknown fees give an open bound ("حداقل …"), never an invented cap. | every bookable offer is OPEN today: neither platform publishes its fees |
| Understand | A Persian query becomes a structured intent (LLM). A verifier rejects any number the query did not say; dates are resolved by code against a sourced holiday calendar. | draft 50-query eval: 99.3% slots, 0 invented numbers (provisional until the owner reviews the set) |
| Rank | Filters with a stated reason, cautions for unknowns, requested features confirmed first, then a transparent score (price per person and night, Bayesian rating). No commission factor. | `/search` |
| Explain | The LLM writes Persian prose around fact slots (`{F1}`); code formats every number and decides every comparison; a verifier rejects digits and comparatives outside slots; a template is the fallback. | |
| Truth check | Distance-to-the-sea claims against the OSM coastline, as ranges over the listing's blurred location; "contradicted" only when even the best case fails. | 170 of 1,909 jabama listings with a sea claim have one contradicted |
| Drive time | Free-flow OSRM times from Tehran on a clipped OSM graph, as a range over the blur circle. | 100% of 3,586 listings routed, median 4 h 21 min |
| Match listings | Blocking (location + rooms, photo hashes, DINOv2 image embeddings), evidence, rule score, constrained clustering. | **not evaluated yet**: precision/recall come from the M3 gold set |

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
make health             # web=ok db=ok blob=ok llm=fake-ok (or llm=avalai-ok with a key)
```

- Web: <http://localhost:3300> (`/search`, `/listings/<platform>/<id>`, `/label`) · API:
  <http://localhost:8800/docs> · Postgres: `127.0.0.1:5433`.
- Without `AVALAI_API_KEY` the stack runs with a deterministic fake LLM provider.
- Crawled snapshots and photos are never committed. A fresh clone has an empty catalog: crawl
  (`make crawl P=jabama LIVE=1`) or rebuild from your own snapshots (`make reparse`).

## Main flows

```bash
make crawl P=jabama LIVE=1        # polite crawl (needs CRAWL__CONTACT); default replays snapshots
make reparse                      # rebuild the catalog from snapshots, zero network
make match                        # photo hashes + embeddings, blocking, evidence, scores
cd backend && uv run villasanj er queue --name gold-v1   # draw the stratified labelling queue
# label pairs at http://localhost:3300/label (keyboard: M / N / U)
make eval                         # precision/recall with Wilson CIs against the labels
make osm-download osm-prepare routing-up geo   # coastline, coast distances, drive times, sea check
cd backend && uv run villasanj discovery search "ویلای استخردار در رامسر برای ۶ نفر آخر هفته بعد"
cd backend && uv run villasanj llm spend       # LLM cost from the ledger (hard cap $30)
```

## Development

```bash
make test               # unit + architecture tests (no network, no Docker) + frontend tests
make test-integration   # Postgres + PostGIS in a throwaway container
make test-e2e           # Playwright on the running app: provenance clicks, axe, keyboard
make lint               # ruff, mypy --strict, import-linter, tsc, eslint, prettier
make help               # every target
```

## Documentation

- [Architecture](docs/ARCHITECTURE.md): bounded contexts, layers, domain model, schema, ports, assumptions
- [Roadmap](docs/ROADMAP.md): milestones, acceptance criteria, what was built ahead and what is blocked
- [Decisions](docs/adr/README.md): ADRs 0001–0013 (LLM gateway and cost, provenance, crawling ethics,
  entity resolution, image matching, geo evidence)
- [Sources](docs/sources/README.md): robots/ToS audit and what each platform publishes
- [Labelling protocol](docs/er-labeling-protocol.md) (Persian) and the
  [research review](docs/research-review.md)

Map data © OpenStreetMap contributors (ODbL).
