# Villasanj · ویلاسنج

> یک ویلا، همه‌ی حقیقت: one villa, the whole truth.

A Torob-style product for Iranian villa rentals. Each real villa gets one canonical page that
aggregates its listings across platforms: all-in prices for your dates and group size, a merged
calendar, aggregated reviews, and a truth check of listing claims. Every number shown has a
source and an observation time.

Status: **Milestone 1** (skeleton and LLM platform). See [`docs/ROADMAP.md`](docs/ROADMAP.md).

## Quick start

Requirements: Docker (Compose v2.24+), [uv](https://docs.astral.sh/uv/), Node.js ≥ 20.9, GNU Make.

```bash
cp .env.example .env    # optional: add AVALAI_API_KEY to use the real LLM gateway
make setup              # dependencies, git hooks, Docker images
make up                 # db, migrations, api, web
make health             # web=ok db=ok blob=ok llm=fake-ok (or llm=avalai-ok with a key)
```

- Web: <http://localhost:3300> · API: <http://localhost:8800/health> · Postgres: `127.0.0.1:5433`
- Without `AVALAI_API_KEY` the stack runs with a deterministic fake LLM provider.

## Development

```bash
make test               # unit + architecture tests (no network, no Docker) + frontend tests
make test-integration   # Postgres in a throwaway container
make lint               # ruff, mypy --strict, import-linter, tsc, eslint, prettier
make ci                 # all of the above
make help               # every target
```

## Documentation

- [Architecture](docs/ARCHITECTURE.md): bounded contexts, layers, domain model, schema, ports
- [Roadmap](docs/ROADMAP.md): milestones and measurable acceptance criteria
- [Decisions](docs/adr/README.md): ADRs, including LLM model choice and cost estimate
- [Research review](docs/research-review.md): critique of the market research behind the product
