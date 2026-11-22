# Single entry point for dev tasks. Targets are filled in by work packages F-01..F-05.
SHELL := /bin/bash
COMPOSE_DEV := docker compose -f deploy/docker-compose.dev.yml
COMPOSE_PROD := docker compose --env-file .env -f deploy/docker-compose.yml

.PHONY: help dev-db dev-db-down dev-api dev-worker dev-web migrate seed test test-backend test-web test-e2e lint typecheck check gen-api

help: ## List targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  %-14s %s\n", $$1, $$2}'

dev-db: ## Start local Postgres (5433) + mailpit (8025)
	$(COMPOSE_DEV) up -d

dev-db-down: ## Stop local services
	$(COMPOSE_DEV) down

dev-api: ## Run FastAPI with reload on :8000
	cd backend && uv run uvicorn scheduler.api.app:app --reload --port 8000

dev-worker: ## Run the worker (APScheduler + job queue)
	cd backend && uv run python -m scheduler.worker

dev-web: ## Run Next.js on :3000 (rewrites /api to :8000)
	cd web && pnpm dev

migrate: ## Apply DB migrations
	cd backend && uv run alembic upgrade head

seed: ## Seed default settings and vocabularies (idempotent)
	cd backend && uv run scheduler-cli seed

test-backend: ## Backend tests
	cd backend && uv run pytest

test-web: ## Web unit tests
	cd web && pnpm test --run

test: test-backend test-web ## All unit/service/API tests

test-e2e: ## Playwright against the compose stack (FAKE_GOOGLE=1)
	cd web && pnpm e2e

lint: ## Lint backend + web
	cd backend && uv run ruff check . && uv run ruff format --check . && uv run python scripts/check_no_magic_numbers.py
	cd web && pnpm lint

typecheck: ## Type-check backend engine + web
	cd backend && uv run mypy src/scheduler/engine
	cd web && pnpm typecheck

check: lint typecheck test ## Everything CI runs (except e2e)

gen-api: ## Regenerate web/src/api/schema.d.ts from the FastAPI OpenAPI schema
	cd backend && uv run python -c "import json;from scheduler.api.app import create_app;print(json.dumps(create_app().openapi()))" > ../web/src/api/openapi.json
	cd web && pnpm gen:api
	cp backend/tests/fixtures/parser_cases.json web/src/features/capture/__fixtures__/parser_cases.json 2>/dev/null || true
