# Villasanj task runner. Compatible with GNU Make 3.81 (macOS default): no .ONESHELL.
SHELL := /bin/bash
COMPOSE := docker compose
WEB_PORT ?= $(or $(VILLASANJ_WEB_PORT),3300)
JOB ?= llm-smoke

.DEFAULT_GOAL := help
.PHONY: help setup build up down logs ps health migrate test test-integration test-live lint fmt \
	typecheck ci dry-run llm-smoke llm-models seed crawl crawl-status reparse report match eval eval-hypotheses

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

test: ## Unit, contract and architecture tests (no network, no Docker); domain coverage >= 95%
	cd backend && uv run pytest -q --cov --cov-report= \
		&& uv run coverage report --include='*/domain/*' --fail-under=95
	cd frontend && npm test

test-integration: ## Integration tests against a throwaway Postgres (needs Docker)
	cd backend && uv run pytest -m integration -q

test-live: ## Opt-in live AvalAI smoke tests (real calls, capped at $0.05)
	cd backend && uv run pytest -m live_llm -q -s

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

ci: lint test test-integration ## Everything CI runs (local)

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

crawl: ## Crawl a platform: make crawl P=jabama [LIVE=1] [MAX=50] (default: offline replay)
	cd backend && uv run villasanj crawl run $(P) --max-requests $(MAX) $(if $(LIVE),--live,)

crawl-status: ## Frontier counts: make crawl-status P=jabama
	cd backend && uv run villasanj crawl status $(P)

reparse: ## Rebuild listings, calendars and photo hashes from stored snapshots (zero network)
	cd backend && uv run villasanj catalog ingest && uv run villasanj catalog fingerprint-photos

report: ## Catalog numbers: scenario coverage and gazetteer resolution (zero network)
	cd backend && uv run villasanj catalog coverage && uv run villasanj catalog places

seed: ## Not needed yet: reference data is versioned config; demo dataset seed comes in M11
	@echo "make $@: nothing to seed. Region, scenarios and gazetteer live in config/*.toml and are read at use; a demo dataset seed is planned for M11 (docs/ROADMAP.md)."; exit 1

match eval eval-hypotheses: ## Available from M3 (entity resolution)
	@echo "make $@: not implemented yet (planned for M3, see docs/ROADMAP.md)"; exit 1
