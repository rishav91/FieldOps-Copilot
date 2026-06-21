# FieldOps Copilot

AI triage + work-order automation over **NYC 311 service requests** — a portfolio artifact about *where an agent belongs*, proven against a baseline.

**Design is the source of truth → start at [docs/README.md](docs/README.md).** Operating instructions: [AGENTS.md](AGENTS.md). This file is just the developer quickstart.

## Status

**Phase 0 — walking skeleton** (see [docs/ROADMAP.md](docs/ROADMAP.md#phase-0)). A single ticket flows end to end through the real spine; classify and draft are deliberate stubs that later phases replace. What's wired:

- FastAPI app + health endpoint
- Postgres + pgvector store, schema faithful to [ARCHITECTURE §5](docs/ARCHITECTURE.md#5-data-model-folded-in)
- Provider-agnostic `LLMClient` ([ADR-003](docs/ADRs.md#adr-003)) — OpenAI primary, Groq cheap tier
- Pipeline spine: `ingest → store → (stub) classify → (stub) draft → console`
- Tracing skeleton: per-stage spans with `ticket_id` / `trace_id` correlation

## Quickstart

```bash
python -m venv .venv && source .venv/bin/activate
make install            # pip install -e ".[dev]"
cp .env.example .env     # keys optional for the skeleton (stubs run offline)

make db-up               # Postgres + pgvector via docker compose
make init-db             # create extension + tables

make demo                # flow one sample ticket through the spine
make api                 # FastAPI on :8000  (GET /health, POST /tickets/demo)
make test                # smoke tests
```

The `make demo` flow and the smoke tests run **without LLM keys** — classify/draft are stubs in Phase 0. `make llm-health` exercises the real providers if keys are set.

## Layout

```
src/fieldops/
  config.py        settings (pydantic-settings), all pipeline knobs
  tracing.py       lightweight span/correlation-ID skeleton (OTel upgrade path)
  db.py            engine/session + init_db (pgvector extension + create_all)
  models.py        canonical tables: raw_311_record, ticket, embedding,
                   routing_decision, work_order  (ARCHITECTURE §5)
  llm/             provider-agnostic client: base · openai · groq · factory
  pipeline/        ingest · classify (stub) · draft (stub) · runner (the spine)
  api/app.py       FastAPI app
  cli.py           `fieldops` entrypoint (init-db · demo · llm-health)
  data/            sample 311 record for the skeleton
tests/             smoke tests
```
