# Roadmap — FieldOps Copilot

MVP-first, **depth before breadth**. The order is deliberately chosen so the differentiator (the agent + its proof) gets first-class time, and so the biggest risk ([PRD R2](PRD.md#7-risks)) is retired *before* the agent is built. Requirement IDs reference [REQUIREMENTS](REQUIREMENTS.md).

---

## Phase 0
**Walking skeleton.**
**Goal:** thinnest end-to-end slice that proves the architecture wiring.
**Ships:** repo scaffold; FastAPI app; Postgres + pgvector up; `LLMClient` interface ([ADR-003](ADRs.md#adr-003)) with the OpenAI binding (+ Groq cheap tier); a single ticket flows ingest → store → (stub) classify → (stub) draft → console. Tracing skeleton.
**Unlocks:** every later phase plugs into a working spine.

## Phase 1
**Ingest + dedup.**
**Goal:** real data in, duplicates suppressed, *and the ambiguity population profiled*.
**Ships:** FR-1 (Socrata pull, normalize, idempotent upsert, 12-month Brooklyn backfill), FR-2 (embeddings, geo/time dedup, hand-labeled pair eval set). **Profile the ambiguous-request population** (counts of multi-agency / multi-issue / low-text-confidence) to feed the Phase 2 gate.
**Unlocks:** clean canonical tickets + the data needed to decide whether the agent is justified.

## Phase 2
**Cascade classifier + routing + calibrated confidence.**
**Goal:** route the easy majority with a confidence score that *means something*.
**Ships:** FR-3 (cheap → Groq → OpenAI cascade, multi-label/agency detection), FR-3.4 calibration (Platt/isotonic + reliability curve), FR-4 confidence gate. Discriminative eval (FR-8.1) against 311 labels; ECE meets [NFR-4.1](REQUIREMENTS.md#nfr-4--correctness--calibration).

> ### GO / NO-GO GATE
> **Confirm a real population of genuinely ambiguous / multi-agency requests exists** (from Phase 1 profiling + the calibrated gate's tail size).
> - **GO** → build the agent (Phase 3).
> - **NO-GO (population too thin)** → trigger [ADR-009](ADRs.md#adr-009): amplify + disclose (keep a held-out natural slice) **or** rescope and cut the agent. Decide *here*, before any agent code — this retires [PRD R2](PRD.md#7-risks).

## Phase 3
**Intake triage agent + agent-vs-baseline proof.**
**Goal:** the differentiator, built **with its proof in the same phase**.
**Ships:** FR-5 (LangGraph loop, read-only tools, turn cap + graceful give-up, per-turn tracing, tool-arg validation, idempotency), and **simultaneously** the FR-8.3 agent-vs-baseline study — correctness, turn distribution, give-up rate, cost, trace assertions, vs. Baseline A (single classifier) and Baseline B (escalate-all). Meets [NFR-4.3](REQUIREMENTS.md#nfr-4--correctness--calibration).
**Decision built in:** if the agent can't beat Baseline B, it is **cut** ([PRD R3](PRD.md#7-risks)) — the loop and its evidence are inseparable here, by design.
**Unlocks:** the headline result; everything else is plumbing around a proven (or honestly-rejected) core.

## Phase 4
**Work-order drafting DAG + Linear + human gate.**
**Goal:** grounded, human-reviewable orders into the system of record.
**Ships:** FR-6 (fan-out context → one generation → deterministic validator → ≤1 repair, [ADR-008](ADRs.md#adr-008)), FR-7 (review UI, Linear OAuth + GraphQL submit, idempotency, human gate), generative eval FR-8.2 (hard checks → judge → human, with agreement rate).
**Unlocks:** the full end-to-end demo on real Brooklyn data (PRD success metric: time-to-first-value).

## Phase 5
**Eval + observability + the honest extras.**
**Goal:** make every claim measurable and the system debuggable.
**Ships:** FR-8.4 operational dashboard (latency, cost per path, override rate, abandoned steps, retries); FR-8.5 fairness audit (Census/ACS tract join + ecological-fallacy caveat, or downgraded claim); FR-8.6 red-team study; the NFR-6.3 debugging narrative; the as-is/to-be workflow one-pager.
**Unlocks:** the portfolio's named-skill coverage (debugging, process redesign, fairness, red-team).

---

## v2+ (deferred — explicitly out of MVP)

| Item | Why deferred | Discipline carried forward |
|------|--------------|----------------------------|
| **SLA risk model** (full tabular study) | Not load-bearing for the thesis | Leakage discipline ([PRD R5](PRD.md#7-risks)): as-of-creation features only; lead with it when built. |
| **Playwright** 311-status-portal enrichment | Read-only enrichment, not core | Real target, no fabricated portal; read-only so it never creates live requests. |
| **Airflow / dbt / warehouse** | Cron + Postgres suffices at demo scale | Lift when volume/partitioning ([NFR-7.1](REQUIREMENTS.md#nfr-7--scalability--capacity)) demands it. |
| **Citywide / multi-borough scale** | Demo is one borough | Capacity headroom already designed ([REQUIREMENTS §3](REQUIREMENTS.md#3-capacity-sizing)). |

## Sequencing rationale

- **Profiling before the agent (Phase 1 → Phase 2 gate).** The single largest risk is building an agent with no ambiguity to justify it. We measure the population *first* and put a hard gate before any agent code.
- **Calibration before the gate is usable (Phase 2).** The whole deterministic/agentic fork rests on a calibrated score; an uncalibrated gate is meaningless ([ADR-007](ADRs.md#adr-007)).
- **Agent + proof together (Phase 3).** The differentiator and its evidence are one unit — building the loop without the baseline comparison would let a gimmick survive.
- **Drafting after the agent (Phase 4).** Drafting is deterministic plumbing ([ADR-008](ADRs.md#adr-008)); it gets the time left after the differentiator, not the reverse.
- **Honesty extras last but not optional (Phase 5).** Fairness, red-team, and the debugging narrative are P1 deliverables that turn claims into evidence.
