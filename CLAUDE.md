# CLAUDE.md — Villasanj (ویلاسنج)

Persistent project memory for agent sessions. Read this first, then `docs/ARCHITECTURE.md` and
`docs/ROADMAP.md`. Update this file and ROADMAP at the end of every milestone.

## What this is

A Torob-style product for Iranian villa rentals, built for the Torob "AI Product Engineer" challenge
(`challenge.html`: *crawl offers → normalize messy data → rank by user intent → explain the best
choice*, 5-minute demo). Concept: **«ویلاسنج: یک ویلا، همه‌ی حقیقت»**. Each real villa gets one
canonical page that aggregates its listings across platforms (region Ramsar–Tonekabon). **Crawled
platforms: jabama and shab only** (ADR-0011); jajiga, otaghak and mihmansho forbid crawling in their
ToS and are excluded unless written permission arrives: all-in offers per stay + group size, merged calendar, aggregated
reviews, and a truth check of listing claims.

Context files (local):
- `research-prompt.md`: **the deep-research REPORT** (the file names are swapped). It is the
  reference for product decisions. Critique: `docs/research-review.md`.
- `research-report.md`: the research **prompt**.
- `challenge.html`: the challenge page (git-ignored; third-party content).

## Current status

- M0–M3 done (M3 completed 2026-10-03: gold-v1, 362 owner labels; threshold −0.25; H1–H3).
- **2026-10-03, owner's instruction "complete every milestone as far as dependencies allow":**
  status per criterion is in each milestone's section of `docs/ROADMAP.md`. In short:
  - M4: same-window capture done (jabama 3.2 h, shab 0.6 h); new platforms ⛔ (no permission).
  - M5: done, 7/7 (`reports/er-eval-2026-10-03.md`). The machine merges are the rules' (P 98.1%,
    R 67.1%); the gemini-3.8-flash judge is **advisory** (`config/er.toml`: `judge_merges` and
    `judge_vetoes` false) because its merges cannot be verified at the bar with gold-v1, and it
    orders the human queue `er-human` (376 pairs). ADR-0014 and its amendment.
  - M6–M10: met except M6 crit. 3 (no public quote), M8 crit. 1–2 (owner's query review and
    relevance judgements), M10 crit. 4 (explanation latency uncached).
  - M11: `make demo` (offline stack from a database bundle), `docs/demo-script.md`; cache warm-up
    and the dashboard reconciliation wait.
- Production villas: 3,267 from 3,588 listings, 321 on both platforms.
- **The AvalAI key's monthly limit (13.10 units, set by the owner) is reached** (2026-10-03 18:23
  UTC): every call answers 429 `monthly_quota_exceeded`, which is now a non-retried
  `ProviderQuotaError`. Ledger: $12.31 of the $30 cap. Pages degrade (summaries omitted,
  explanations fall back to the template); nothing needing new LLM calls can run until the owner
  raises the limit.
- Owner decisions pending: the complex-unit labels (5 cross-platform pairs the judge vetoes, 41
  same-platform pairs), local photo copies for the offline demo, the `er-human` queue, the M8 query
  set and relevance judgements, the M7 UX review.

## Working agreement (from the owner)

- Work **milestone by milestone**. Before coding a milestone, give a short plan (files, classes,
  interfaces, tests, estimated LLM cost). At the end, **stop**, report (what was built, how to run it,
  decisions + why, LLM spend from the ledger, tech debt, next step) and wait for approval.
- A milestone is done only when `make lint` and `make test` are green.
- Small coherent commits, Conventional Commits (`feat:`, `fix:`, `docs:`, `test:`, `refactor:`, `chore:`).
- Run tests + lint after every change; fix failures first.
- **Never fabricate data, prices or evaluation results.** If something does not work, say so.
- **Never print, log or commit `.env` or the API key.** Check variables by presence/length only.
- Code, identifiers and comments in English. UI in Persian, RTL. Talk to the owner in **Persian**.
- Ask only questions whose answers change the design; otherwise assume, and record the assumption in
  `docs/ARCHITECTURE.md` §10.

## Non-negotiable product rules

1. No fabricated number. Every price or claim shown has provenance (source, snapshot, `observed_at`).
   Unknown means a range, or an open upper bound ("≥ X"). Never invent a cap.
2. LLMs never write digits into user-facing text: facts go in as IDs, the LLM writes `{slot}`s, and a
   deterministic renderer + verifier fill and check them (ADR-0007).
3. Prices are never merged across listings; each member listing yields its own offer.
4. A canonical villa has ≤ 1 listing per platform (aggregate invariant + DB unique index).
5. Truth-check tone is «تأیید نشد», never accusatory. `CONTRADICTED` only when best-case evidence contradicts.
6. Availability and prices are *observations* with age, not states.

## Architecture rules (enforced by import-linter + architecture tests)

- Modular monolith, package `villasanj`. Contexts: `ingestion`, `catalog`, `entity_resolution`,
  `pricing`, `enrichment`, `discovery`; plus `shared` (kernel + cross-cutting ports/adapters) and
  `entrypoints` (CLI, API, workers, composition root).
- Context DAG: `shared ← ingestion ← catalog ← {entity_resolution, pricing} ← enrichment ← discovery ← entrypoints`.
  `pricing` and `entity_resolution` are independent. Import upstream **domain/application** only,
  never upstream infrastructure.
- Layers per context: `domain` (stdlib + `shared.domain` only, frozen dataclasses) ← `application`
  (use cases, `typing.Protocol` ports, Pydantic DTOs/LLM schemas, structlog, prompt templates) ←
  `infrastructure` (vendors, ORM, HTTP, ML).
- No platform slug outside `ingestion/infrastructure/sources/<slug>/`, config and tests.
- Composition root is hand-written (`entrypoints/container.py`); no DI framework.
- Abstraction only if it isolates I/O/vendors (testability) or has ≥ 2 real implementations.

### Extension recipes (OCP)
- **New platform:** `ingestion/infrastructure/sources/<slug>/` implementing `SourceAdapter` (pure: no
  I/O), plus trimmed fixtures + contract tests, one entry point in `backend/pyproject.toml`
  (`villasanj.sources`), and a `config/fees.toml` policy (sourced, or `fees_known = false`).
  Nothing else changes.
- **New LLM provider:** a `RawModelProvider` adapter + a branch in `build_provider` + `LLM__PROVIDER`.
  Model names go in `config/llm.toml`.
- **New embedding / search engine:** an adapter for `ImageEmbedder` / `TextEmbedder` / `SearchIndex`
  + composition-root switch.

## LLM usage rules (ADR-0004, ADR-0005)

- Only through the `LLMClient` port with an `LLMTask`. **No model name in code**: models are configured
  per task in `config/llm.toml` (primary + fallbacks).
- Chain: RoutedLLMClient (routing/fallback) → cache → retry (+ validation feedback) → cost governor
  (worst-case reservation + ledger) → structured-output validation → provider. Compose it only in
  `entrypoints/container.py::build_llm_stack`.
- Deterministic first (regex, rules, pHash); the LLM handles only the residue.
- Every LLM-using use case implements `plan()` so `--dry-run` can estimate cost with 0 calls.
- Bump `prompt_version` whenever a prompt template changes (a test hashes templates).
- Tests never hit the real API: `FakeLLMProvider`. Live tests carry the `live_llm` marker,
  run via `make test-live`, and are capped at $0.05.
- Account facts (2026-10-01): AvalAI **tier 3**; Gemini bills ~1,090 tokens/image regardless of
  size → use composite grids; `gemini-embedding-001` reports 0 usage → ledger marks it estimated;
  `finish_reason=length` on reasoning models = error. Project hard cap **$30**.
- Current routing: query understanding → `gpt-5.4-mini` (bake-off 2026-10-02, fallback flash-lite);
  other bulk tasks → `gemini-3.1-flash-lite`; ER judge, review summary, explanation → `gemini-3.8-flash`
  (`reasoning_effort = "low"` for summary and explanation); fallbacks → `gpt-5.4-mini`; embeddings → `gemini-embedding-001` @768
  (fallback `text-embedding-3-small`). `gpt-5-nano` is excluded (failed the extraction probe).

## Crawling rules (ADR-0008)

- Robots.txt + ToS audit and owner sign-off per platform **before** the first listing request.
  Disallowed means stop and report.
- `PoliteFetcher`: 1 in-flight request per host; default 1 req/3 s + jitter (or Crawl-delay if larger);
  backoff on 429/5xx; **stop-on-block** (403 bursts or captcha means halt; no evasion, proxies or stealth).
- Identifying UA with `CRAWL__CONTACT`. Every response is snapshotted (content-addressed); parsing is a
  pure function of a snapshot. Default `CRAWL__MODE=offline`.
- Never commit snapshots or photos. Fixtures are trimmed and scrubbed of personal data.

## Environment (measured 2026-10-01)

Apple M4 (10 cores), 16 GB RAM, macOS 26.5.2 arm64; Docker Desktop 29.6.2 with **7.75 GB** for the VM
(CPU only; no GPU in containers; all images must be linux/arm64); 168 GB free disk; uv 0.11.32,
Node 26.5, GNU Make **3.81** (no `.ONESHELL` or other ≥ 3.82 features), system Python 3.9.6 (use uv's 3.12).
`.env` was normalised to `KEY=value` in M1 (values untouched).

## Commands

```
make setup             # uv sync, npm ci, pre-commit install, build images
make up / down / logs  # core stack: db (5433), migrate, api (8800), web (3300); ports via VILLASANJ_*_PORT
make health            # end-to-end via web: "web=ok db=ok blob=ok llm=avalai-ok"
make test              # backend unit + architecture tests (domain coverage >= 95%) + frontend vitest
make test-integration  # testcontainers Postgres built from infra/docker/postgres
make test-live         # opt-in real AvalAI calls (live_llm marker, $0.05 cap)
make lint              # ruff + mypy --strict + import-linter + tsc + eslint + prettier
make fmt               # ruff format/fix + prettier
make ci                # lint + test + test-integration
make dry-run JOB=llm-smoke  # price an LLM job with zero calls (stack must be up)
make llm-smoke         # live smoke through the stack; spend persisted in ops.llm_call
make llm-models        # refresh config/llm-models.json from /v1/models (free)
make crawl P=jabama [LIVE=1] [MAX=50]   # default replays snapshots; LIVE=1 needs CRAWL__CONTACT
make crawl-status P=jabama              # frontier counts
make reparse                            # rebuild catalog + photo hashes from snapshots (zero network)
make report                             # scenario coverage + gazetteer resolution (zero network)
make match                              # fingerprint + embed new photos, then blocking/evidence/scores
make eval [QUEUE=gold-v1]               # precision/recall with Wilson CIs against the owner's labels
make eval-hypotheses [THRESHOLD=..]     # reports/hypotheses-<date>.md (H1-H3)
make test-ml                            # opt-in test with the real image model (pinned weights)
make test-e2e / test-smoke              # Playwright on the running app / 50 sampled listing pages
make crawl-scenarios [LIVE=1]           # same-window re-capture of all calendars (plan only by default)
make crawl-metrics                      # traffic per host with measured pacing, queue, runs
make openapi / openapi-check           # regenerate / verify the OpenAPI schema and TS types
make osm-download / osm-prepare         # Geofabrik Iran snapshot -> clipped extract, coastline, OSRM graph
make routing-up / routing-down          # OSRM (compose profile routing); core stack untouched
make geo                                # coastline + places into PostGIS, distances, drive times, truth checks
make basemap                            # offline basemap (Protomaps extract, 13 MB) in data/basemap
make demo-bundle / demo / demo-down     # DB bundle (with LLM cache) -> offline stack on :3400 (own volume)
make seed                               # nothing to seed until M11
```

Useful CLI (from `backend/`): `uv run villasanj crawl probe <platform> <url> --kind listing`
(one polite fetch + snapshot), `crawl run <platform> --live --kind photo` (photo hosts only),
`crawl run … --after-block` (only after the owner decides to resume a blocked platform),
`catalog ingest`, `catalog coverage`, `catalog places`, `catalog enqueue-photos`,
`catalog fingerprint-photos`, `catalog embed-photos`, `pricing quote <platform> <id>`,
`er match`, `er queue --name <q>`, `er evaluate`, `er hypotheses`, `crawl capture [--live]`,
`crawl requeue <platform> --kind <k>`, `crawl metrics`, `catalog photo-report`, `catalog inventory`,
`catalog reviews`, `pricing offers`, `er judge --low --high --dry-run`, `api openapi`,
`enrichment claims` (distance-claim parse coverage), `discovery holidays` (days off with sources),
`discovery understand [--dry-run] <query>...` (query → verified intent + resolved dates; live calls),
`enrichment summarize <platform> <id>... [--dry-run]` (cited pros/cons of a listing's reviews; live calls),
`enrichment features` (description claims vs amenity lists), `llm spend` (ledger totals and the cap),
`discovery search <query>` (query → ranked listings with reasons; one LLM call),
`discovery eval-understanding <cases.jsonl> [--dry-run]` (M8 crit. 1 harness), `enrichment coast`,
`enrichment truth-sea`, `enrichment places-load` / `places` / `truth-distances`, `discovery drive-times` (OSRM up), `enrichment tag-photos` / `photo-queue` /
`photo-tags-eval` (SigLIP 2 tags, gated by labels at `/label/photos`), `er report` (M5 evaluation
into reports/), `er villas` / `er villas-eval` (policy from `config/er.toml`, flags override),
`er judge-zone`, `enrichment h4 [--out]`. Search page: `/search`; villa page: `/villas/<id>`.
Labelling UIs (stack on 3300): `/label` (ER pairs, gold-v1), `/label?queue=er-human` (the judge's
suggestions and disputes; each label rebuilds the villas), `/label/photos` (photos-v1),
`/label/summaries` (summaries-v1), `/label/claims` (claims-v1); `/metrics` shows progress. Host dev: `npm run dev` with `API_URL` set.

Backend CLI inside the stack: `docker compose exec api villasanj --help`.
On the host: `cd backend && uv run villasanj --help` (talks to the db on 127.0.0.1:5433).

## Gotchas learned (keep these in mind)

- **Escapes in written files:** the file-writing tool decodes `\uXXXX` into real characters. In Python
  source, write invisible/special characters as `\N{NAME}` (e.g. `"\N{ZERO WIDTH NON-JOINER}"`). An
  architecture test rejects invisible characters in `.py` files.
- **Docker builds:** BuildKit sometimes times out resolving Docker Hub metadata from this network. If a
  build fails with `DeadlineExceeded`, `docker pull <base-image>` first, then rebuild.
- **Ports:** another local project (shopping-assistant) uses 3000/8000/6379/6333, which is why
  Villasanj defaults to 3300/8800/5433.
- **OpenAI SDK 3.x uses httpx2**; mock it with `httpx2.MockTransport` in tests.
- **gemini-3.8-flash thinks by default** (~165–255 reasoning tokens even on trivial replies); measure
  `reasoning_effort` per task before scaling judge/summary/explanation calls (ADR-0005 amendment).
- `.env.example` must stay value-free; the owner's contact belongs only in `.env`.
- pre-commit runs from the repo root (`backend/.venv/bin/pre-commit`); it blocks commits on lint/format
  failures, so run `make fmt` before committing.
- Research files are excluded from whitespace fixers so the owner's files stay untouched.
- **Clock:** the Mac's local time is Tehran (+03:30); logs and DB timestamps are UTC. Compare like with
  like before concluding that a background job is stuck.
- **Platforms differ in units and shapes:** jabama money is rial, shab money is toman; shab's calendar
  API returns two payload shapes and keys days by Jalali month; jabama's `disabled` nights do not say
  whether they are booked or closed (stored as `unavailable`).
- **jabama needs `Accept: text/html`** or it serves a page shell without listings (HttpxFetcher sets it).
- **jabama uses `0` for "not set"** (weekend/holiday/extra-guest prices, rating): parse to `None`
  (unknown), never to free or zero-rated. Its neighbourhood field is always empty.
- **shab photos:** originals are 538×424 to 1600×1200 (~593 KB). The thumbnails are 4:3 crops that
  break pHash for portrait photos, so keep originals as the matching evidence (ADR-0008 amendment 5).
- **`s3gw.shab.ir/robots.txt` answers 403** (an S3 `AccessDenied`, no such object). RFC 9309 says
  4xx = no restrictions, and the owner was told. A 403/429 streak on *content* stops the run, and
  the platform stays blocked until `--after-block`.
- **ML packages** (torch, transformers) are the `ml` dependency group: installed by `uv sync` for
  development and batch jobs, never in the API image (`--no-default-groups`). The image model is
  pinned by Hugging Face revision in `catalog/infrastructure/dinov2.py`.
- **AvalAI image embeddings** need model-specific input shapes: `gemini-embedding-2` takes a data
  URL string; `tongyi-embedding-vision-flash` takes `{"contents":[{"image": …}]}` and allows only
  75 requests/min on tier 3. A wrong shape for gemini is silently embedded as text (1 token).
- **Next.js dev:** open `http://localhost:<port>`, not `127.0.0.1` (dev resources are blocked
  cross-origin and the page never hydrates). `agentRules: false` keeps `next dev` from writing
  its own CLAUDE.md/AGENTS.md under `frontend/`.
- **Commit only after reading the `make test` result**; pre-commit runs lint, not tests.
- **Do not rebuild or restart the stack while host jobs run** (crawls, embeddings): `make up` recreates
  the db container when its image changed, and running jobs lose their connection. Interrupted
  claims are recovered by the next crawl run after 10 minutes.
- **Gazetteer edits:** `config/gazetteer.toml` is curated, precision first. Add only real place
  names seen in data; never alias roads/streets or guess typo merges. `make report` shows the
  resolution rate and the top unresolved texts.
- **Restart host servers after backend changes:** the `api-host` preview (uvicorn on 8801, no
  reload) keeps running old code; a label in `er-human` triggers a villa rebuild with whatever code
  it runs. The E2E suite targets the host dev server (3301 → 8801) unless `E2E_BASE_URL` is set.
- **ER policy lives in `config/er.toml`**; the CLI flags only override it. Rebuilding villas after a
  policy change reconciles ids (history in `er.villa_event`).
- **Never commit the probe/recon by-products**: raw responses live in `var/blobs` and `data/audit`
  (git-ignored); fixtures are trimmed and scrubbed (no host or reviewer names).

## Tooling preferences (owner's global instructions)

- Before using any external library API, fetch current docs via **context7** (the server needs
  authentication via `/mcp` first).
- Browser automation / E2E: `playwright-cli` skill first; Playwright MCP only as fallback.
- UI work: start with the `ui-skills-root` skill.

## Docs map

- `docs/ARCHITECTURE.md`: contexts, layers, diagrams, domain model, schema, ports, assumptions.
- `docs/ROADMAP.md`: milestones M0–M11 with acceptance criteria and LLM caps.
- `docs/adr/`: decisions 0001–0014 (0014: ER decisions, the judge zone, the advisory amendment).
- `reports/`: generated, reproducible reports (hypotheses, er-eval, h4); `docs/demo-script.md`.
- `docs/er-labeling-protocol.md`: how the owner labels gold-set pairs (Persian).
- `docs/sources/README.md`: robots/ToS audit, crawl-time observations, inventory, photo experiment.
- `docs/research-review.md`: critique of the research report.
- `docs/reference/avalai-models-2026-10-01.csv`: model/pricing snapshot used for cost estimates.
