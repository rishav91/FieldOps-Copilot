# CLAUDE.md — FieldOps Copilot

Orientation for anyone (human or agent) working in this repo. Read this first, then the design suite.

## What this is

AI triage + work-order automation over **NYC 311 service requests**, built as a **portfolio/interview artifact**. Ingest service requests → dedup + route deterministically → run **one** agent loop only on the genuinely ambiguous tail → draft human-gated work orders into a system of record → prove the agent beats a trivial baseline. The thesis is *judgment about where an agent belongs*, measured — not "more AI."

## Current state

**Design phase — no application code yet.** The repo holds the design suite. Implementation follows [docs/ROADMAP.md](docs/ROADMAP.md) (Phase 0 = walking skeleton). When you add code, keep it consistent with the docs and update the relevant doc in the same change.

## The design suite (source of truth)

Start at [docs/README.md](docs/README.md), then read in order:

1. [docs/README.md](docs/README.md) — scope, governing principle, locked stack, doc map
2. [docs/PRD.md](docs/PRD.md) — problem, personas, use cases, success metrics, risks
3. [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — tiers, flows, data model, lifecycle, failure modes
4. [docs/AI-ARCHITECTURE.md](docs/AI-ARCHITECTURE.md) — the agent loop, cascade, evaluation, safety, fairness
5. [docs/ADRs.md](docs/ADRs.md) — the contested decisions and their alternatives
6. [docs/REQUIREMENTS.md](docs/REQUIREMENTS.md) — `FR-`/`NFR-` IDs, priorities, capacity sizing
7. [docs/EVAL-SPEC.md](docs/EVAL-SPEC.md) — offline correctness: metrics, eval-data governance, agent-vs-baseline statistical protocol, judge validation, CI gates
8. [docs/OBSERVABILITY.md](docs/OBSERVABILITY.md) — live behavior: tracing, SLOs/alerting, drift monitoring, spend circuit breaker, override→label feedback loop
9. [docs/ROADMAP.md](docs/ROADMAP.md) — MVP-first phases + the GO/NO-GO ambiguity gate

The [docs/](docs/) suite is the single source of truth. Diagram sources: the two `.mermaid` files at the repo root, embedded inline in the architecture docs.

## Non-negotiables (enforce in review)

- **Governing principle.** An LLM/agent earns its place only where (a) the next action genuinely depends on the last result *and* (b) it provably beats a trivial baseline. Everywhere else: deterministic. **No LLM ever emits a trusted number, a final routing decision without confidence, or a side-effecting action.**
- **One agent loop, at intake triage only.** Resist adding agents elsewhere ([ADR-001](docs/ADRs.md#adr-001), [ADR-008](docs/ADRs.md#adr-008)).
- **No side-effecting tool in the agent's menu.** The agent reasons; deterministic code + the human gate act.
- **Honesty about what's simulated.** Linear is a simulated sink; 311 labels are reused as ground truth; any amplified ambiguous data is disclosed. Never fabricate a city integration. See [README §what's real vs simulated](docs/README.md#whats-real-vs-simulated-read-this-honestly).
- **Standing guardrails are P0.** Redact PII before any external (OpenAI/Groq) LLM call; constrain agency to a valid enum and bound agent `split` fan-out; enforce (don't just configure) the spend ceiling. See [AI-ARCHITECTURE §6](docs/AI-ARCHITECTURE.md#6-safety-guardrails--red-team) and [REQUIREMENTS FR-10](docs/REQUIREMENTS.md#fr-10--guardrails).
- **Claims need intervals.** The agent-beats-baseline result ships only with stated `n` and a 95% CI whose lower bound on (agent − Baseline B) > 0. See [EVAL-SPEC §5](docs/EVAL-SPEC.md#5-agent-path-eval--the-headline).

## LLM providers

Use a **provider-agnostic `LLMClient` interface**. Default binding (see [ADR-003](docs/ADRs.md#adr-003)):

- **OpenAI** (GPT-4-class) — agent, drafting, LLM-judge; `text-embedding-3` for embeddings.
- **Groq (groq.com)** — the cheap/high-volume classifier tier; prefer it for free/cheaper inferencing wherever quality permits.

**Do not use Claude/Anthropic models** in this project.

## Locked stack

Python · FastAPI · Postgres + pgvector (single store) · LangGraph (the one agent) · Socrata SODA API (311 ingest, app token) · Linear GraphQL + OAuth (simulated sink) · LangSmith/OpenTelemetry tracing + Streamlit eval dashboard. Cron for the daily delta. Demo-scale now, designed for borough→citywide headroom.

## Conventions

- **Stable IDs:** `FR-x.y`, `NFR-x.y`, `ADR-00N` — append-only, never renumbered. Reference inline (e.g. "enforces NFR-4.1").
- **Scope discipline:** SLA model, Playwright enrichment, Airflow/dbt/warehouse, and citywide scale are explicitly **deferred** — don't pull them into the MVP.
- **Everything is traced; everything is idempotent** (upsert by `unique_key`, agent by `routing_decision_id`, submission by `draft_hash`).
- **Branch + plan before building a phase.** Before implementing any [ROADMAP](docs/ROADMAP.md) phase, (1) check out a dedicated branch off `main` (e.g. `phase-1-ingest-dedup`), and (2) write `docs/plans/phase-N.md` (template + index in [docs/plans/](docs/plans/README.md)) — what it achieves + commit-sized sub-phases — and get it reviewed first. Then implement sub-phase by sub-phase.
- **Commits:** Conventional Commits; no `Co-Authored-By` trailer.
- Keep docs cross-linked with relative links and the [docs/README.md](docs/README.md) map current when adding a doc.
