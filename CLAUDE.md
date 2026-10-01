# CLAUDE.md — Villasanj (ویلاسنج)

Persistent project memory for agent sessions. Read this first, then `docs/ARCHITECTURE.md` and
`docs/ROADMAP.md`. Update this file and ROADMAP at the end of every milestone.

## What this is

A Torob-style product for Iranian villa rentals, built for the Torob "AI Product Engineer" challenge
(`challenge.html`: *crawl offers → normalize messy data → rank by user intent → explain the best
choice*, 5-minute demo). Concept: **«ویلاسنج: یک ویلا، همه‌ی حقیقت»**. Each real villa gets one
canonical page that aggregates its listings on jajiga, jabama, otaghak and shab (region
Ramsar–Tonekabon, 1.5–3k listings): all-in offers per stay + group size, merged calendar, aggregated
reviews, and a truth check of listing claims.

Context files (local):
- `research-prompt.md`: **the deep-research REPORT** (the file names are swapped). It is the
  reference for product decisions. Critique: `docs/research-review.md`.
- `research-report.md`: the research **prompt**.
- `challenge.html`: the challenge page (git-ignored; third-party content).

## Current status

- **Milestone 0 (design) delivered, awaiting owner approval.** No executable code yet.
- Next: M1 (skeleton & LLM platform). See `docs/ROADMAP.md`.

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
  (use cases, `typing.Protocol` ports, Pydantic DTOs/LLM schemas, prompt templates) ← `infrastructure`
  (vendors, ORM, HTTP, ML).
- No platform slug outside `ingestion/infrastructure/sources/<slug>/`, config and tests.
- Composition root is hand-written (`entrypoints/container.py`); no DI framework.
- Abstraction only if it isolates I/O/vendors (testability) or has ≥ 2 real implementations.

### Extension recipes (OCP)
- **New platform:** `ingestion/infrastructure/sources/<slug>/` implementing `SourceAdapter` (pure: no
  I/O), plus trimmed fixtures + contract tests, one entry point in `backend/pyproject.toml`
  (`villasanj.sources`), and a sourced `FeePolicy` row. Nothing else changes.
- **New LLM provider:** a provider adapter + `LLM__PROVIDER`. Model names go in `config/llm.toml`.
- **New embedding / search engine:** an adapter for `ImageEmbedder` / `TextEmbedder` / `SearchIndex`
  + composition-root switch.

## LLM usage rules (ADR-0004, ADR-0005)

- Only through the `LLMClient` port with an `LLMTask`. **No model name in code**: models are configured
  per task in `config/llm.toml` (primary + fallbacks).
- Decorator chain: cache → fallback → retry (+ validation retry) → cost governor (budget + ledger) → provider.
- Deterministic first (regex, rules, pHash); the LLM handles only the residue.
- Every LLM-using use case implements `plan()` so `--dry-run` can estimate cost with 0 calls.
- Bump `prompt_version` whenever a prompt template changes (a test hashes templates).
- Tests never hit the real API: `FakeLLMProvider`. Live tests carry the `live_llm` marker,
  run via `make test-live`, and are capped at $0.05.
- Account facts (2026-10-01): AvalAI **tier 3**; Gemini bills ~1,090 tokens/image regardless of
  size → use composite grids; `gemini-embedding-001` reports 0 usage → ledger marks it estimated;
  `finish_reason=length` on reasoning models = error. Project hard cap **$30**.
- Current routing: bulk/latency tasks → `gemini-3.1-flash-lite`; ER judge, review summary, explanation →
  `gemini-3.8-flash`; fallbacks → `gpt-5.4-mini`; embeddings → `gemini-embedding-001` @768
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
`.env` currently has `AVALAI_API_KEY = …` with spaces, to be normalised to `KEY=value` in M1.

## Commands (planned in M1; not available yet)

```
make setup          # uv sync, npm ci, build images, pre-commit install
make up / down      # docker compose (profile core); make logs
make health         # end-to-end healthcheck
make test           # unit + contract + architecture tests (no network, no Docker needed)
make test-integration  # testcontainers Postgres
make test-live      # opt-in live LLM tests (live_llm marker, $0.05 cap)
make lint           # ruff + mypy --strict + import-linter + tsc + eslint
make fmt            # ruff format + prettier
make seed           # gazetteer, scenarios, fee policies
make crawl P=<platform> [LIVE=1]   # default offline (snapshots only)
make reparse        # rebuild catalog from snapshots (0 network)
make match          # ER pipeline
make eval           # ER evaluation report; make eval-hypotheses (H1–H3)
make dry-run JOB=<job>  # LLM call/cost plan, 0 calls
make ci             # everything CI runs
```

## Tooling preferences (owner's global instructions)

- Before using any external library API, fetch current docs via **context7** (the server needs
  authentication via `/mcp` first).
- Browser automation / E2E: `playwright-cli` skill first; Playwright MCP only as fallback.
- UI work: start with the `ui-skills-root` skill.

## Docs map

- `docs/ARCHITECTURE.md`: contexts, layers, diagrams, domain model, schema, ports, assumptions.
- `docs/ROADMAP.md`: milestones M0–M11 with acceptance criteria and LLM caps.
- `docs/adr/`: decisions 0001–0010.
- `docs/research-review.md`: critique of the research report.
- `docs/reference/avalai-models-2026-10-01.csv`: model/pricing snapshot used for cost estimates.
