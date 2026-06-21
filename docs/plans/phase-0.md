# Phase 0 — Walking skeleton

**Goal (from [ROADMAP](../ROADMAP.md#phase-0)):** thinnest end-to-end slice that proves the architecture wiring.

**Achieves:** a single ticket flows `ingest → store → (stub) classify → (stub) draft → console` over a real Postgres + pgvector store, through a provider-agnostic `LLMClient`, under a tracing skeleton. Every later phase plugs into this spine. No FR/NFR *closes* here (it's scaffolding) — but FR-1/FR-3/FR-6 get their seams, and [NFR-3.2](../REQUIREMENTS.md#nfr-3--availability--reliability) (idempotent upsert) and [NFR-6.1](../REQUIREMENTS.md#nfr-6--observability) (per-stage tracing) are exercised.

**Depends on:** nothing (first phase). Runs offline — no LLM keys needed (classify/draft are stubs).

**Exit criteria:** `fieldops demo` flows one ticket end to end with traced spans; `pytest` green (offline unit + DB); `GET /health` ok; `ruff` clean. — **all met ✅**

> Written in hindsight (this phase predates the plan-first convention). The sub-phase split below is how Phase 0 **would be committed**; it was built as one pass and is not yet in git.

## Sub-phases (commit-sized checkpoints)

| # | Checkpoint | Achieves | Key files | Acceptance | Commit message | Done |
|---|-----------|----------|-----------|-----------|----------------|------|
| 0.1 | Scaffold & tooling | Installable package, dockerized store, dev ergonomics | `pyproject.toml`, `docker-compose.yml`, `.env.example`, `.gitignore`, `Makefile`, `README.md` | `pip install -e ".[dev]"` succeeds | `chore: scaffold project + tooling` | ✅ |
| 0.2 | Config + tracing | Config-driven knobs; `trace`/`span` with correlation IDs ([OBSERVABILITY §2](../OBSERVABILITY.md#2-tracing--correlation)) | `src/fieldops/config.py`, `tracing.py` | spans log with `trace_id`/`ticket_id` | `feat(core): settings + tracing skeleton` | ✅ |
| 0.3 | Datastore | Canonical schema ([ARCHITECTURE §5](../ARCHITECTURE.md#5-data-model-folded-in)); pgvector extension + `create_all` | `src/fieldops/models.py`, `db.py` | `fieldops init-db` creates extension + tables | `feat(db): canonical schema + pgvector init` | ✅ |
| 0.4 | LLMClient | Tier→provider binding ([ADR-003](../ADRs.md#adr-003)); vendor SDKs lazy so it imports offline | `src/fieldops/llm/{base,openai_client,groq_client,factory}.py` | imports without keys; `llm-health` probes set keys | `feat(llm): provider-agnostic client (OpenAI + Groq)` | ✅ |
| 0.5 | Pipeline spine | `ingest` (idempotent) + stub `classify`/`draft` + `runner`, all under one trace; sample 311 record | `src/fieldops/pipeline/{ingest,classify,draft,runner}.py`, `data/sample_311.json` | `fieldops demo` → ticket `DRAFTED` | `feat(pipeline): ingest→store→stub classify→stub draft spine` | ✅ |
| 0.6 | API + CLI | HTTP + console surfaces over the spine | `src/fieldops/api/app.py`, `cli.py` | `GET /health` ok; `fieldops {init-db,demo,llm-health}` | `feat(api): FastAPI app + fieldops CLI` | ✅ |
| 0.7 | Smoke tests | Offline unit suite + DB integration (auto-skips without Postgres) | `tests/test_unit.py`, `test_pipeline_db.py` | `pytest` green; `ruff` clean | `test: phase-0 smoke tests` | ✅ |

## Completion checks (verified)

Acceptance — each checked against a real run:

- [x] **Install** — `pip install -e ".[dev]"` succeeds (note: build-Python `ssl` gotcha → used Homebrew `python3` 3.13; see Risks).
- [x] **Schema** — `fieldops init-db` → "pgvector extension + tables ready."
- [x] **Console flow** — `fieldops demo` → `status=DRAFTED`, `predicted_agency=DEP`, `routing_path=fast`, non-empty `draft_hash` + `trace_id`.
- [x] **Tracing** — per-stage spans emitted (`ingest.normalize`, `classify.stub`, `draft.stub`, `pipeline.run`) with shared `trace_id`.
- [x] **Idempotency** ([NFR-3.2](../REQUIREMENTS.md#nfr-3--availability--reliability)) — running the spine twice yields **one** ticket row for the `unique_key` (asserted in `test_ingest_is_idempotent`).
- [x] **Tests** — `pytest` → **9 passed** (7 offline unit + 2 DB) against live Postgres+pgvector; **2 skipped** when DB is down.
- [x] **API** — `GET /health` → `{"status":"ok","phase":0}`.
- [x] **Lint** — `ruff check src tests` → all checks passed.

Non-negotiables honored:

- [x] No LLM emits a number/decision/action — classify/draft are offline stubs; confidence left `null`; gate not wired (deferred to Phase 2 by design, [ADR-007](../ADRs.md#adr-007)).
- [x] No side-effecting tool anywhere; no submission (human gate is Phase 4).
- [x] Honesty — classify's stand-in prediction reuses the 311 ground-truth agency ([ADR-006](../ADRs.md#adr-006)), commented as a stub.

## Risks / notes carried forward

- **Build-Python `ssl`:** the repo's `python3` shim (pyenv 3.11.0) is compiled without `ssl`; pip can't reach PyPI. Use `/opt/homebrew/bin/python3` for the venv. Worth a `.python-version` or a README note.
- **Trace root `ticket_id`:** logged as `None` at the root (the id doesn't exist until after ingest); per-span attrs carry it. Minor polish — propagate after ingest in a later pass.
- **Not yet committed:** Phase 0 code + the planning docs are uncommitted on `main`. When committing, branch off `main` (e.g. `phase-0-skeleton`) and use the per-checkpoint messages above.
- **Cost wiring:** `CompletionResult.cost_usd` is `0.0` until per-provider pricing lands with the spend breaker ([OBSERVABILITY §6](../OBSERVABILITY.md#6-cost-observability--spend-circuit-breaker)).
