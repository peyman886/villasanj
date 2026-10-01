# ADR-0002 — Technology stack (and what we deliberately leave out)

Status: Proposed · Date: 2026-10-01

## Context

The proposed stack was Python 3.12+, FastAPI, SQLAlchemy 2, Pydantic/Pydantic Settings, Playwright,
Splink, imagehash + DINOv2/SSCD/CLIP, OpenAI SDK (AvalAI base_url); Next.js + TypeScript, RTL,
MapLibre, Vazirmatn; services such as PostgreSQL+PostGIS+pgvector, Redis or a queue, MinIO and OSRM.
Constraints: Apple M4 / 16 GB (ADR-0003). `uv` 0.11 and Node 26 are installed. The system Python is 3.9.

## Decision

**Backend:** Python **3.12** (installed through `uv`; widest wheel coverage on linux/arm64 for torch,
duckdb, psycopg). `uv` for env/lock. FastAPI + uvicorn. SQLAlchemy 2 (async) + psycopg 3 + Alembic.
Pydantic v2 + pydantic-settings (TOML + env). Typer for CLI jobs. structlog for JSON logs. httpx for
HTTP. Playwright (Python) only for pages that need JavaScript. `protego` for robots.txt. Splink 4
(DuckDB backend) for probabilistic matching. imagehash + Pillow. torch (CPU) + DINOv2 via `timm` or
`transformers` (decided in M5 by the smaller image). OpenAI Python SDK for AvalAI. Test stack: pytest,
hypothesis, testcontainers, respx (httpx mocking). Quality: ruff (lint + format), mypy `--strict`,
import-linter, pre-commit, gitleaks.

**Frontend:** Next.js (App Router, current stable at M1, verified through docs) + TypeScript strict;
Tailwind with logical properties (`ms-`/`me-`) for RTL; Radix/shadcn primitives; Vazirmatn
self-hosted; MapLibre GL; `openapi-typescript` for a typed API client; Vitest + Testing Library;
Playwright E2E.

**Left out on purpose (YAGNI):**

| Proposed | Decision | Reason |
|---|---|---|
| Redis / Celery / a broker | **Not used.** Postgres `SKIP LOCKED` frontier + Typer jobs. LLM cache in Postgres. | Batch pipeline on one machine; the per-domain rate limit is the bottleneck, not dispatch. One fewer service and memory budget. Revisit if we need a live multi-worker scheduler. |
| MinIO | **Not used by default.** `BlobStore` port with a content-addressed local-filesystem adapter on a Docker volume. | Single machine, a few GB. The port keeps an S3 adapter a pure addition (MinIO/SeaweedFS/Garage) with no core change. MinIO's community-edition distribution has changed over 2025; the current image/licence status is **unverified** and would need checking before adoption. |
| OpenSearch / Elasticsearch | **Not used.** Postgres FTS (`simple` config on normalized text) + `pg_trgm` + pgvector behind `SearchIndex`. | 1.5–3k documents; hard filters do most of the work; a JVM service costs 1–2 GB RAM. |
| Hazm / Parsivar | **Not used.** Small in-house normalizer in the shared kernel. | We need character/digit/ZWNJ normalization and a gazetteer, not a full NLP toolkit; this also keeps the domain dependency-free. |
| SSCD | **Deferred.** DINOv2 first; SSCD only if M5 eval shows missed crops or watermarks. Licence to verify. | One learned embedding is enough until measured otherwise. |
| Local LLM (Ollama) | **Not used** (adapter slot kept). | 16 GB RAM cannot host a model with good Persian quality next to the stack; AvalAI is cheap (ADR-0005). |

## Alternatives considered

- **Python 3.13:** viable, but 3.12 minimises wheel risk on linux/arm64 containers. Revisit in M1 if
  every locked dependency ships 3.13 wheels.
- **Poetry:** `uv` is already installed and much faster; lockfile + Python management in one tool.
- **Django:** heavier ORM coupling. FastAPI + SQLAlchemy keeps the ORM in infrastructure.
- **SvelteKit / Remix:** fine, but Next.js was proposed, is familiar to reviewers and has mature RTL
  examples. No reason to deviate.

## Consequences

- (+) Fewer moving parts: `docker compose` runs db, api, web, worker, plus optional browser and osrm.
- (+) Every omitted service can be added later behind an existing port.
- (−) Postgres carries many roles (queue, cache, vectors, FTS, GIS). This is fine at demo scale, and
  ADR-0010 lists the limits.
- Library APIs will be checked against current docs (context7) before code is written. Note: the
  context7 MCP server currently needs authentication (via `/mcp`).
