# Architecture Decision Records — FieldOps Copilot

Each ADR: **context → decision → alternatives → consequences**. Alternatives (≥2) and the **minuses** of the chosen path are mandatory. Reference by ID (e.g. "per [ADR-002](#adr-002)"). Status: `Accepted` unless noted.

## Index

| ID | Title | Status |
|----|-------|--------|
| [ADR-001](#adr-001) | Deterministic by default; exactly one agent loop | Accepted |
| [ADR-002](#adr-002) | A calibrated confidence gate routes only the tail to the agent | Accepted |
| [ADR-003](#adr-003) | Provider-agnostic LLM interface; OpenAI primary + Grok cheap tier | Accepted |
| [ADR-004](#adr-004) | LangGraph for the single triage loop | Accepted |
| [ADR-005](#adr-005) | Linear as a *simulated* system of record | Accepted |
| [ADR-006](#adr-006) | 311 labels as evaluation ground truth | Accepted |
| [ADR-007](#adr-007) | Calibration as a first-class pipeline step | Accepted |
| [ADR-008](#adr-008) | Work-order drafting is a deterministic DAG, not an agent | Accepted |
| [ADR-009](#adr-009) | Amplify + disclose if the ambiguous population is too thin | Accepted (conditional) |
| [ADR-010](#adr-010) | Postgres + pgvector as the single store for MVP | Accepted |

---

## ADR-001
### Deterministic by default; exactly one agent loop

**Context.** Agent frameworks tempt you to make everything agentic. Loops are expensive (5–8 LLM calls), non-deterministic, hard to test, and hard to trust for an ops tool. But intake triage on ambiguous reports genuinely needs planning. The question is *where* an agent belongs.

**Decision.** The system is deterministic everywhere except **one** agent loop at **intake triage** — the only step where the next action genuinely depends on what the last tool returned. This is encoded as the [governing principle](README.md#governing-principle).

**Alternatives.**
- *Agentic end-to-end (e.g. an agent that also drafts and submits).* Rejected: downstream inputs are already disambiguated, so a loop there adds cost, latency, and non-determinism with no decision to make ([ADR-008](#adr-008)).
- *No agent at all (pure cascade + human for the rest).* Rejected: the ambiguous tail's route/split/escalate decision genuinely benefits from planning; this is the project's thesis — and we *prove* it beats the no-agent baseline (AI-ARCH §5).

**Consequences.**
- `+` One place to reason about non-determinism; everything else is unit-testable.
- `+` Cost and latency bounded — only the tail pays for an agent.
- `+` A crisp senior narrative: *where* the agent goes, justified and measured.
- `−` Requires the discipline to *resist* adding agents elsewhere; the governing principle must be actively enforced in review.
- `−` Puts a large bet on one component; if the agent can't beat its baseline ([ADR-009](#adr-009), AI-ARCH §5) the headline feature is cut.

## ADR-002
### A calibrated confidence gate routes only the tail to the agent

**Context.** Sending every ticket to the agent is wasteful; sending none defeats the purpose. We need a principled fork.

**Decision.** A **confidence gate** thresholds the classifier's *calibrated* score (plus multi-label/multi-agency flags). Above threshold + single agency → deterministic fast path. Below, or multi-label/agency → the agent.

**Alternatives.**
- *Fixed rules to decide ambiguity (keyword lists).* Rejected: brittle exactly on the linguistic tail we care about.
- *Send everything to the agent, let it decide it's easy.* Rejected: pays agent cost on the easy majority; violates [ADR-001](#adr-001).

**Consequences.**
- `+` Tunable on the reliability curve; gate threshold is config, not code.
- `+` Directly controls the cost/quality trade-off.
- `−` Only as good as the calibration ([ADR-007](#adr-007)); a miscalibrated score makes the gate arbitrary.
- `−` Threshold choice is a real tuning task with a precision/recall trade-off (too low → agent floods; too high → mis-routes slip to fast path).

## ADR-003
### Provider-agnostic LLM interface; OpenAI primary + Grok cheap tier

**Context.** For a portfolio artifact, single-vendor lock-in is both a risk and a portability story, and **cost on the high-volume tiers matters**. We want quality where it counts (the agent, drafting, the judge) and the cheapest credible option on the bulk classifier tier.

**Decision.** All LLM access goes through one `LLMClient` interface (`complete`, `tool_call`, `embed`). Default binding: **OpenAI** (GPT-4-class for the agent, drafting, and judge; `text-embedding-3` for embeddings), with **Grok (xAI)** on the cheap/high-volume classifier fallback tier for free/low-cost inferencing wherever quality permits. Azure OpenAI is a swappable enterprise alternate. *Assumption: OpenAI primary + Grok cheap tier; revisit if a deployment dictates Azure for compliance/residency.*

**Alternatives.**
- *Hard-code a single vendor for everything.* Rejected: lock-in, weaker failover, and no cheap-tier cost lever on the bulk traffic.
- *One provider with no abstraction.* Rejected: loses swappability, the provider-failover degradation posture ([ARCHITECTURE §7](ARCHITECTURE.md#7-failure-modes--degradation)), and the ability to route tiers to the cheapest credible model.

**Consequences.**
- `+` Provider failover is a real degradation path, not a slide.
- `+` Tiering maps cleanly to cost: Grok absorbs high-volume classification cheaply; OpenAI carries the quality-critical reasoning.
- `−` Two providers to key, monitor, and rate-limit; the abstraction must design to their common subset (can't lean on provider-specific features).
- `−` Evals must be re-run per tier if a default model changes — behavior isn't portable even though the interface is; Grok and OpenAI must each be eval'd on the tier they serve.

## ADR-004
### LangGraph for the single triage loop

**Context.** The one agent needs explicit control: a turn cap, per-node tracing, structured tool-arg validation, and graceful give-up. We need control over magic.

**Decision.** Build the triage loop on **LangGraph** — an explicit state graph — pairing with LangSmith for tracing.

**Alternatives.**
- *Hand-rolled tool-use loop (OpenAI SDK directly).* Strong contender: maximum transparency. Rejected for the MVP because LangGraph gives turn caps, state, and tracing out of the box; the hand-rolled version remains a viable simplification if the graph proves heavyweight.
- *CrewAI / AutoGen.* Rejected: multi-agent frameworks are heavier than one tightly-scoped loop needs; less control over the exact turn structure.

**Consequences.**
- `+` Turn caps, state, and per-node spans are first-class.
- `+` The graph *is* documentation of the loop.
- `−` A framework dependency and its learning curve for a single loop — arguably more than strictly necessary.
- `−` Some indirection between our code and the raw provider calls; mitigated by the `LLMClient` boundary ([ADR-003](#adr-003)).

## ADR-005
### Linear as a *simulated* system of record

**Context.** NYC 311 has no endpoint to submit work orders to. We still want to demonstrate robust external API integration + OAuth.

**Decision.** Use **Linear** (GraphQL + OAuth, free plan) as a **stand-in destination**, disclosed as a simulated sink in [README](README.md#whats-real-vs-simulated-read-this-honestly).

**Alternatives.**
- *Fabricate a fake city work-order API.* Rejected: dishonest and unimpressive; a reviewer discovering it is the worst outcome.
- *No sink — stop at the draft.* Rejected: loses the OAuth + real-API-integration demonstration that hits named JD skills.

**Consequences.**
- `+` Real OAuth + GraphQL integration with idempotency, on a clean free API.
- `+` Honest framing reads as maturity ([PRD R1](PRD.md#7-risks)).
- `−` Not a real city integration; the "last mile" to an actual municipal system is unproven.
- `−` Linear's schema isn't a work-order schema; we map onto issues, which is an approximation.

## ADR-006
### 311 labels as evaluation ground truth

**Context.** `complaint_type`, `descriptor`, `agency`, `closed_date` already exist in the 311 data. We need eval ground truth without manual labeling at scale.

**Decision.** Treat the existing 311 labels as **free ground truth** for discriminative eval. The classifier/router *reproduces and pre-fills* a decision the city already makes; we do not claim to discover it de novo.

**Alternatives.**
- *Hand-label a fresh gold set.* Rejected for scale: expensive; the published labels already are the city's decision. (We *do* hand-label a few hundred **dedup pairs**, which 311 doesn't label.)
- *No ground truth, judge-only.* Rejected: discriminative tasks deserve hard metrics, not an LLM's opinion.

**Consequences.**
- `+` Free, large, real ground truth → real F1/precision/recall/calibration.
- `+` Honest framing of what the system does (pre-fill, not discover).
- `−` Ground truth inherits the city's own labeling errors/biases; "beating" it is bounded by its quality.
- `−` Doesn't evaluate true cold-start intake (no label exists at the moment of a real call) — a known gap, disclosed.

## ADR-007
### Calibration as a first-class pipeline step

**Context.** The entire deterministic/agentic fork ([ADR-002](#adr-002)) rests on the confidence score *meaning* what it says. Raw model scores are typically miscalibrated.

**Decision.** Calibrate the classifier's confidence (reliability curve + Platt or isotonic regression on a held-out set) as an explicit, evaluated pipeline step. Track **ECE** as an NFR ([NFR-4.1](REQUIREMENTS.md#nfr-4--correctness--calibration)).

**Alternatives.**
- *Use raw model probabilities.* Rejected: miscalibrated → the gate threshold is arbitrary and over/under-routes to the agent.
- *Skip confidence, route by rules.* Rejected: loses the principled fork.

**Consequences.**
- `+` The gate threshold has a real, interpretable meaning.
- `+` A reliability curve is a concrete artifact that demonstrates rigor.
- `−` Needs a held-out calibration set and periodic re-fit as data drifts.
- `−` Adds a step that must itself be evaluated and maintained.

## ADR-008
### Work-order drafting is a deterministic DAG, not an agent

**Context.** Once routing is decided, the inputs to drafting are disambiguated. An agent loop here would add cost and non-determinism with no real decision to make.

**Decision.** Drafting is a fixed DAG: concurrent fan-out of read-only context tools → **one** structured LLM generation → **deterministic validator** (precedent-ID membership, agency match, required fields) → on failure, **one** bounded repair re-prompt → human gate → deterministic submit.

**Alternatives.**
- *Agentic drafting (let the model loop until satisfied).* Rejected: open-ended loops are 5–8× the calls, non-deterministic, and undermine an ops tool. Violates [ADR-001](#adr-001).
- *No validator, trust the generation.* Rejected: hallucinated precedent IDs / agency mismatches would reach humans (or Linear).

**Consequences.**
- `+` Testable, parallel, cheap (1–2 calls vs 5–8), bounded.
- `+` The validator catches hallucination/manipulation before a human sees it (AI-ARCH §6).
- `−` A genuinely novel drafting situation the single repair can't fix falls to the human queue rather than being "figured out."
- `−` The fixed DAG is less flexible than a loop if requirements grow — accepted, and revisited only if real cases demand it.

## ADR-009
### Amplify + disclose if the ambiguous population is too thin

**Status:** Accepted (conditional — triggered only if the [Phase 2 gate](ROADMAP.md#phase-2) fails).

**Context.** Genuinely multi-agency / multi-issue requests are a minority. If the natural population is too thin, the agent has nothing to justify it.

**Decision.** At the Phase 2 GO/NO-GO gate, profile the ambiguous population. If too thin: **synthesize/amplify** ambiguous cases and **label the synthetic set clearly**, keeping a held-out *natural* slice for honest reporting. If amplification can't produce a credible set, **rescope** (cut the agent).

**Alternatives.**
- *Proceed regardless.* Rejected: builds a feature with no evidence it's needed; the central risk ([PRD R2](PRD.md#7-risks)).
- *Silently synthesize.* Rejected: undisclosed synthetic data is the dishonest failure mode.

**Consequences.**
- `+` The agent's justification is tested *before* it's built.
- `+` Honest disclosure of any synthesis preserves credibility.
- `−` Synthetic cases may not reflect real ambiguity distributions; results on them are weaker evidence than natural ones (hence the held-out natural slice).

## ADR-010
### Postgres + pgvector as the single store for MVP

**Context.** We need relational data (tickets, decisions, work orders), vector search (dedup, similar-ticket retrieval), and traces. At demo scale, operational simplicity beats a polyglot stack.

**Decision.** One **Postgres + pgvector** instance holds canonical tickets, embeddings (HNSW index), routing decisions, agent traces, and work orders.

**Alternatives.**
- *Dedicated vector DB (Pinecone/Weaviate/Qdrant) + Postgres.* Rejected for MVP: two systems to operate, sync, and reason about for demo-scale volume; pgvector is sufficient.
- *Warehouse (BigQuery/Snowflake) for analytics.* Deferred: cron + Postgres covers the access patterns now; lift to a warehouse with Airflow/dbt later ([ROADMAP v2](ROADMAP.md)).

**Consequences.**
- `+` One store, transactional integrity across entities + vectors, simple ops.
- `+` HNSW in pgvector handles dedup/retrieval at the target scale ([REQUIREMENTS §3](REQUIREMENTS.md#3-capacity-sizing)).
- `−` pgvector won't match a dedicated vector DB at very large scale or very high QPS — accepted given demo scale; the partition plan + a later vector-DB swap is the escape hatch.
- `−` Mixing OLTP + vector + trace workloads on one instance needs care as volume grows.
