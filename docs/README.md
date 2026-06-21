# FieldOps Copilot — Design Suite

AI triage and work-order automation over **NYC 311 Service Requests**.

Ingest municipal service requests, deduplicate and route them deterministically, run **one** real agent loop only on the genuinely ambiguous tail, draft human-gated work orders into a system of record, and **prove the agent earns its place** with a baseline comparison — all with observability, evals, guardrails, and a fairness audit.

> This suite is the single source of truth for FieldOps Copilot. Rendered diagram sources: [architecture](../fieldops-architecture.mermaid), [agent loop](../fieldops-agent-loop.mermaid) (also embedded inline in [ARCHITECTURE](ARCHITECTURE.md) and [AI-ARCHITECTURE](AI-ARCHITECTURE.md)).

---

## What this is

A staff/senior-level **portfolio artifact**: a system that demonstrates *where an agent belongs and where it doesn't*, and the discipline to measure the difference. The single most important scope decision: **exactly one agent loop, placed at intake triage** — the only step where the next action genuinely depends on what the last tool returned. Everything downstream is a deterministic DAG.

## Governing principle

> **An LLM — and especially an agent loop — earns its place only where (a) the next action genuinely depends on the last result *and* (b) it provably beats a trivial baseline. Everywhere else, the system is deterministic. No LLM ever emits a trusted number, query, or side-effecting action.**

Every "should we add AI here?" is settled by this rule. It is the reason the work-order step is a DAG, not an agent (see [ADR-008](ADRs.md#adr-008)), and the reason the agent must beat two baselines before it ships (see [EVAL §agent path](AI-ARCHITECTURE.md#5-evaluation)).

| | What | Why |
|---|------|-----|
| **In** | Ingest → dedup → classify/route → **one** triage agent on the ambiguous tail → deterministic, human-gated work-order drafting into Linear; evals, observability, guardrails, fairness audit. | The end-to-end slice that proves the thesis. |
| **Deferred** | SLA risk model (MVP-light or v2), Playwright 311-portal enrichment, Airflow/dbt/warehouse, citywide & multi-borough scale. | Valuable but not load-bearing for the thesis; sequenced after the differentiator. |
| **Excluded** | Any agent action with side effects before a human gate; any LLM producing a trusted number, routing decision treated as final without confidence, or autonomous submission. | Direct violation of the governing principle. |

## Locked stack / key constraints

- **Language/API:** Python · FastAPI.
- **Ingest:** NYC 311 Socrata SODA API (app-token auth), daily delta via cron.
- **Storage:** Postgres + **pgvector** (single store for MVP — canonical tickets, embeddings, traces). See [ADR-010](ADRs.md#adr-010).
- **LLM:** **provider-agnostic interface**; default **OpenAI** (GPT-4-class) for the agent, drafting, and LLM-judge, with **Groq (groq.com)** on the cheap/high-volume classifier tier for free/low-cost inferencing wherever quality permits. Embeddings via OpenAI; Azure OpenAI is a swappable enterprise alternate. See [ADR-003](ADRs.md#adr-003). *(Assumption: OpenAI primary + Groq cheap tier; swap is config-only — revisit if a deployment target dictates Azure.)*
- **Agent runtime:** **LangGraph** for the single triage loop (explicit state graph, turn caps, per-node tracing). See [ADR-004](ADRs.md#adr-004).
- **System of record:** **Linear** GraphQL API + OAuth — a *simulated sink* (see [ADR-005](ADRs.md#adr-005)).
- **Observability:** LangSmith or OpenTelemetry tracing + a Streamlit eval dashboard.
- **Scale posture:** demo-scale backfill + small daily delta **now**, capacity model sized with headroom to a borough slice and citywide. See [REQUIREMENTS §capacity](REQUIREMENTS.md#3-capacity-sizing).

## What's real vs. simulated (read this honestly)

These are deliberate engineering choices, disclosed up front:

- **311 labels are ground truth.** `complaint_type`, `descriptor`, `agency`, `closed_date` already exist. The classifier/router *reproduces and could pre-fill* a decision the city already makes; the labels are **free evaluation ground truth**. Real-world analogue: cutting call-center handle time by pre-filling routing.
- **The input is a post-intake, controlled-vocabulary record — not raw citizen narrative (DR-01).** NYC 311's `complaint_type`/`descriptor` are the city's *own taxonomized* fields (and the dataset only includes requests already directable to an agency), so the deterministic classifier reproduces a near-deterministic mapping — which is why its F1 is ~0.99 ([phase-2-gate](plans/phase-2-gate.md)). That is honestly **not evidence the agent is needed**. Any "raw ambiguous intake" the *agent* reasons over is **curated/synthetic and disclosed as such** — we'd be simulating the *input modality*, not merely amplifying a natural tail. The agent's real natural population is the **low-confidence tail** of the controlled-vocabulary data, not invented narratives.
- **Linear is a simulated destination.** 311 has no work-order submission endpoint, so Linear stands in to demonstrate robust API integration + OAuth — not integration with a city system we don't have.
- **The ambiguous "hard tail" may be amplified.** Genuinely multi-agency / multi-issue requests are a minority. If the natural population is too thin (the [Phase 2 gate](ROADMAP.md#phase-2)), we synthesize/amplify and **label it clearly**. See [ADR-006](ADRs.md#adr-006) and [ADR-009](ADRs.md#adr-009).

## Document map

| # | Doc | Purpose |
|---|-----|---------|
| 1 | **README.md** (this file) | Front door: scope, governing principle, locked stack, conventions. |
| 2 | [PRD.md](PRD.md) | Problem, personas, use cases, scope tiers, success metrics, risks. |
| 3 | [ARCHITECTURE.md](ARCHITECTURE.md) | System tiers, key flows, data model, lifecycle, failure modes, scale. |
| 4 | [AI-ARCHITECTURE.md](AI-ARCHITECTURE.md) | "Earns its place" test, cascade, the one agent loop, deterministic drafting, grounding, evaluation, safety, fairness. |
| 5 | [ADRs.md](ADRs.md) | The contested decisions: context → decision → alternatives → consequences. |
| 6 | [REQUIREMENTS.md](REQUIREMENTS.md) | `FR-x.y` (P0/P1/P2) + `NFR-x.y` quantified + capacity sizing. |
| 7 | [EVAL-SPEC.md](EVAL-SPEC.md) | Offline correctness: metrics, eval-data governance, the agent-vs-baseline **statistical protocol**, judge validation, CI gates. |
| 8 | [OBSERVABILITY.md](OBSERVABILITY.md) | Live behavior: tracing, SLOs + alerting, drift monitoring, spend circuit breaker, the override→label feedback loop. |
| 9 | [ROADMAP.md](ROADMAP.md) | MVP-first phases with the GO/NO-GO ambiguity gate. |

### Advisory review artifacts

These documents record review findings and proposed changes. They are not part of the design contract until accepted recommendations are folded into the source-of-truth documents above.

- [DESIGN-REVIEW.md](DESIGN-REVIEW.md) — pressure-tested issues and corresponding recommendations across the design suite, with emphasis on data fitness, the agent evaluation, and the human gate.

## Reading order

1. **README** (here) → 2. **PRD** (why/what) → 3. **ARCHITECTURE** (how) → 4. **AI-ARCHITECTURE** (the differentiator + how it's measured) → 5. **ADRs** (why these choices) → 6. **REQUIREMENTS** (the contract) → 7. **EVAL-SPEC** + 8. **OBSERVABILITY** (rigor: proving and running it) → 9. **ROADMAP** (the order of work).

## Conventions

- **Stable IDs:** `FR-x.y` functional, `NFR-x.y` non-functional, `ADR-00N` decisions. IDs are append-only — never renumbered. Reference inline (e.g. "enforces [NFR-4.1](REQUIREMENTS.md#nfr-4--correctness--calibration)").
- **Non-negotiables:** no side-effecting tool in the agent's menu; no LLM-produced trusted number/decision; every AI component passes the "earns its place" test in writing before it's built.
- **Assumptions** are marked inline in *italic* and are debts to be retired by a later answer or experiment.
