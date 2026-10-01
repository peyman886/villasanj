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

- M0 (design) approved 2026-10-01.
- **M1 (skeleton & LLM platform) delivered 2026-10-01, awaiting owner review.**
- M2 in progress: ToS audit done and signed off (jabama + shab); ingestion core next.

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
  (`villasanj.sources`), and a sourced `FeePolicy` row. Nothing else changes.
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
make seed/crawl/reparse (M2), make match/eval/eval-hypotheses (M3): not implemented yet
```

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
