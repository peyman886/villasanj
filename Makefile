# Villasanj task runner. Compatible with GNU Make 3.81 (macOS default): no .ONESHELL.
SHELL := /bin/bash
COMPOSE := docker compose
WEB_PORT ?= $(or $(VILLASANJ_WEB_PORT),3300)
JOB ?= llm-smoke

.DEFAULT_GOAL := help
.PHONY: help setup build up down logs ps health migrate test test-integration test-ml test-live openapi openapi-check lint fmt \
	test-e2e osm-download osm-prepare routing-up routing-down geo \
	typecheck ci dry-run llm-smoke llm-models seed crawl crawl-scenarios crawl-status crawl-metrics reparse report match eval eval-hypotheses

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "} {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

# ---------------------------------------------------------------- environment

setup: ## Install backend/frontend dependencies, git hooks, and build images
	cd backend && uv sync
	cd frontend && npm ci
	backend/.venv/bin/pre-commit install
	$(COMPOSE) build

build: ## Rebuild Docker images
	$(COMPOSE) build

up: ## Start core services (db, migrate, api, web) and wait until healthy
	$(COMPOSE) up -d --wait

down: ## Stop services (data volumes are kept)
	$(COMPOSE) down

logs: ## Follow service logs
	$(COMPOSE) logs -f --tail=200

ps: ## Show service status
	$(COMPOSE) ps -a

health: ## End-to-end health: web -> api -> db, blob store, LLM provider
	@curl -fsS "http://localhost:$(WEB_PORT)/api/health" \
		| python3 -c 'import json, sys; print(json.load(sys.stdin)["summary"])'

migrate: ## Apply database migrations
	$(COMPOSE) run --rm migrate

# ---------------------------------------------------------------- quality

test: ## Unit, contract and architecture tests (no network, no Docker); domain coverage >= 95%, pricing 100%
	cd backend && uv run pytest -q --cov --cov-report= \
		&& uv run coverage report --include='*/domain/*' --fail-under=95 \
		&& uv run coverage report --include='*/pricing/domain/*' --fail-under=100
	cd frontend && npm test

test-integration: ## Integration tests against a throwaway Postgres (needs Docker)
	cd backend && uv run pytest -m integration -q

test-ml: ## Opt-in tests with the real local image model (downloads pinned weights once)
	cd backend && uv run pytest -m ml -q

test-live: ## Opt-in live AvalAI smoke tests (real calls, capped at $0.05)
	cd backend && uv run pytest -m live_llm -q -s

openapi: ## Regenerate the OpenAPI schema and the frontend's TypeScript types from it
	cd backend && uv run villasanj api openapi
	cd frontend && npm run -s api:types

OSM_SNAPSHOT ?= iran-260930

test-e2e: ## Playwright E2E on the running app (provenance clicks, axe, keyboard); E2E_BASE_URL to override
	cd frontend && PLAYWRIGHT_HTML_OPEN=never npx playwright test

osm-download: ## Download the Geofabrik Iran extract (230 MB on 2026-10-02) and check its MD5
	mkdir -p data/osm && cd data/osm && curl -sSfL -o $(OSM_SNAPSHOT).osm.pbf.md5 \
		https://download.geofabrik.de/asia/$(OSM_SNAPSHOT).osm.pbf.md5 \
		&& curl -sSfL --retry 3 -o $(OSM_SNAPSHOT).osm.pbf \
		https://download.geofabrik.de/asia/$(OSM_SNAPSHOT).osm.pbf \
		&& test "$$(md5 -q $(OSM_SNAPSHOT).osm.pbf 2>/dev/null || md5sum $(OSM_SNAPSHOT).osm.pbf | cut -d' ' -f1)" \
		= "$$(cut -d' ' -f1 $(OSM_SNAPSHOT).osm.pbf.md5)"

osm-prepare: ## Clip to the Tehran-Caspian box, export the coastline, build the OSRM graph
	docker build -q -t villasanj-osmium:local infra/docker/osmium
	OSM_SNAPSHOT=$(OSM_SNAPSHOT) infra/osm/prepare.sh

routing-up: ## Start OSRM (profile "routing"); the core stack is not touched
	docker compose --profile routing up -d osrm

routing-down: ## Stop OSRM
	docker compose --profile routing stop osrm

geo: ## Coastline into PostGIS, coast distances, drive times, sea truth check (OSRM must be up)
	cd backend && uv run villasanj enrichment coastline-load && uv run villasanj enrichment coast \
		&& uv run villasanj discovery drive-times && uv run villasanj enrichment truth-sea

openapi-check: ## Fail if the committed OpenAPI schema or TS types are out of date
	@tmp=$$(mktemp -d) && cd backend && uv run villasanj api openapi --out $$tmp/openapi.json >/dev/null \
		&& diff -q $$tmp/openapi.json ../frontend/src/lib/api/openapi.json \
		|| { echo "OpenAPI schema is stale: run make openapi"; exit 1; }

lint: ## ruff, mypy --strict, import-linter, tsc, eslint, prettier
	cd backend && uv run ruff check src tests migrations \
		&& uv run ruff format --check src tests migrations \
		&& uv run mypy \
		&& uv run lint-imports
	cd frontend && npm run typecheck && npm run lint && npm run format:check

typecheck: ## Type checks only
	cd backend && uv run mypy
	cd frontend && npm run typecheck

fmt: ## Format all code
	cd backend && uv run ruff format src tests migrations && uv run ruff check --fix-only src tests migrations
	cd frontend && npm run format

ci: lint openapi-check test test-integration ## Everything CI runs (local)

# ---------------------------------------------------------------- LLM operations

dry-run: ## Price an LLM job with zero API calls (stack must be up): make dry-run JOB=llm-smoke
	$(COMPOSE) exec api villasanj $(subst -, ,$(JOB)) --dry-run

llm-smoke: ## One tiny live call per task and fallback model; spend recorded in the ledger
	$(COMPOSE) exec api villasanj llm smoke

llm-models: ## Refresh config/llm-models.json from AvalAI /v1/models (free call)
	cd backend && uv run villasanj llm refresh-models

# ---------------------------------------------------------------- pipeline

P ?= jabama
MAX ?= 50
QUEUE ?= gold-v1

crawl: ## Crawl a platform: make crawl P=jabama [LIVE=1] [MAX=50] (default: offline replay)
	cd backend && uv run villasanj crawl run $(P) --max-requests $(MAX) $(if $(LIVE),--live,)

crawl-scenarios: ## Re-observe all calendars in one window: plan only; LIVE=1 captures (not during labelling)
	cd backend && uv run villasanj crawl capture $(if $(LIVE),--live,)

crawl-status: ## Frontier counts: make crawl-status P=jabama
	cd backend && uv run villasanj crawl status $(P)

reparse: ## Rebuild listings, calendars and photo hashes from stored snapshots (zero network)
	cd backend && uv run villasanj catalog ingest && uv run villasanj catalog fingerprint-photos

report: ## Catalog numbers: inventory, photo pipeline, scenario coverage, gazetteer (zero network)
	cd backend && uv run villasanj catalog inventory && uv run villasanj catalog photo-report \
		&& uv run villasanj catalog coverage && uv run villasanj catalog places

crawl-metrics: ## Traffic per host with measured pacing, queue progress and recent runs (zero network)
	cd backend && uv run villasanj crawl metrics

seed: ## Not needed yet: reference data is versioned config; demo dataset seed comes in M11
	@echo "make $@: nothing to seed. Region, scenarios and gazetteer live in config/*.toml and are read at use; a demo dataset seed is planned for M11 (docs/ROADMAP.md)."; exit 1

match: ## Fingerprint + embed new photos, then blocking, evidence and scores for all pairs
	cd backend && uv run villasanj catalog fingerprint-photos && uv run villasanj catalog embed-photos \
		&& uv run villasanj er match

eval: ## Matcher precision/recall against the owner's labels: make eval [QUEUE=gold-v1]
	cd backend && uv run villasanj er evaluate --queue $(QUEUE)

eval-hypotheses: ## H1-H3 report into reports/ (needs labels, or THRESHOLD=<score> for a provisional run)
	cd backend && uv run villasanj er hypotheses --queue $(QUEUE) $(if $(THRESHOLD),--threshold $(THRESHOLD),)
