.PHONY: help install db-up db-down init-db run api test lint demo llm-health

help:
	@echo "FieldOps Copilot — Phase 0 (walking skeleton)"
	@echo "  make install     install the package + dev deps (use a venv)"
	@echo "  make db-up       start Postgres + pgvector (docker compose)"
	@echo "  make init-db     create the pgvector extension + tables"
	@echo "  make demo        run a single ticket: ingest -> store -> classify -> draft -> console"
	@echo "  make api         run the FastAPI app on :8000"
	@echo "  make test        run the smoke tests"
	@echo "  make lint        ruff check"
	@echo "  make llm-health  probe the configured LLM providers (needs keys)"

install:
	pip install -e ".[dev]"

db-up:
	docker compose up -d

db-down:
	docker compose down

init-db:
	fieldops init-db

demo:
	fieldops demo

api:
	uvicorn fieldops.api.app:app --reload --port 8000

test:
	pytest -q

lint:
	ruff check src tests

llm-health:
	fieldops llm-health
