# PRD — FieldOps Copilot

Product requirements: the *why* and the *what*. For the *how*, see [ARCHITECTURE](ARCHITECTURE.md) and [AI-ARCHITECTURE](AI-ARCHITECTURE.md). For scope governance, see [README §governing principle](README.md#governing-principle).

---

## 1. Problem

Municipal service-request intake (the workflow behind NYC 311) routes a high volume of citizen complaints to the correct agency, deduplicates near-identical reports, and opens work orders. Today the human-heavy parts of that loop are:

- **Triage of ambiguous reports.** Most reports are clearly one issue for one agency. A minority describe overlapping problems ("water pouring from the ceiling and the floor is buckling") that span agencies, or are too vague to route with confidence. These cost the most handler time and are where mis-routes happen — each mis-route adds days to resolution and bounces between agencies.
- **Duplicate suppression.** The same pothole or outage gets reported many times; handlers manually recognize and merge.
- **Work-order drafting.** Turning a routed complaint into an actionable order (owner, next action, due date, cited precedent) is repetitive copy-work.

**What it costs:** handler minutes per ticket, multiplied across hundreds of thousands of tickets; SLA breaches from slow or wrong routing; citizen trust erosion from duplicate/ignored reports.

**How it's solved today:** rule tables and human queues. Rules are brittle on the ambiguous tail; humans are the fallback for everything they don't cover, which is exactly the expensive part.

**The wedge:** an LLM cascade pre-fills routing on the easy majority *with a calibrated confidence score*, and a single, tightly-scoped agent loop reasons through the ambiguous tail — while the system stays deterministic everywhere the inputs are already disambiguated. The differentiator is **judgment about where the agent goes**, proven against a baseline — not "more AI."

> **Framing honesty:** 311 already publishes the ground-truth labels (`agency`, `complaint_type`). This system *reproduces and pre-fills* those decisions; it does not claim to discover them de novo. That makes the labels free evaluation ground truth (see [ADR-006](ADRs.md#adr-006)). The real-world analogue is reducing call-center handle time, not replacing the city.

## 2. Goals & non-goals

**Goals (outcomes):**
- G1 — Pre-fill agency routing on the easy majority with calibrated confidence, so humans only see what's genuinely uncertain.
- G2 — Resolve the ambiguous tail with one agent loop that **provably beats** both a single-classifier call and a blanket escalate-to-human baseline.
- G3 — Produce grounded, human-reviewable work orders with zero ungated side effects.
- G4 — Make every claim measurable: discriminative metrics against 311 labels, hard checks + judge for generation, a fairness audit, and a red-team study.

**Non-goals:**

| Type | Item | Reason |
|------|------|--------|
| Deferred | SLA risk model as a full tabular study | Sequenced after the differentiator; MVP may ship light or skip. Leakage discipline ([ADR](ADRs.md) / [risk R5](#7-risks)) makes it real work, not a checkbox. |
| Deferred | Playwright enrichment against the real 311 status portal | Read-only v2 enrichment; not load-bearing for the thesis. |
| Deferred | Airflow / dbt / warehouse | Cron + Postgres suffices at demo scale; lift later. |
| Deferred | Citywide / multi-borough scale | Demo is one borough; capacity model carries headroom ([REQUIREMENTS §3](REQUIREMENTS.md#3-capacity-sizing)). |
| **Excluded** | Any side-effecting tool in the agent's menu | Governing principle: the agent reasons, humans + deterministic code act. |
| **Excluded** | LLM emitting a trusted number, final routing decision without confidence, or autonomous Linear submission | Governing principle. |
| **Excluded** | A fabricated 311 portal or fake city integration | Honesty: simulate only the sink (Linear), disclosed in [README](README.md#whats-real-vs-simulated-read-this-honestly). |

## 3. Personas

| Persona | Scope | Primary need | RBAC / visibility |
|---------|-------|--------------|-------------------|
| **Intake handler** (primary user) | Sees the queue of triaged tickets + drafted work orders; approves/edits/rejects at the human gate. | Trust the routing; fast review of drafts; clear "why this agency" rationale + agent trace. | Read all tickets in their borough; write = approve/edit/reject only. |
| **Ops lead** | Oversees throughput, override rates, SLA risk. | Dashboards: routing accuracy, override rate, agent give-up rate, cost per path. | Read aggregates + drill-down; no direct submit. |
| **ML/Platform engineer** (builder) | Owns pipeline, agent, evals. | Traces, eval harness, calibration curves, red-team results. | Full system access in non-prod; prod read + deploy. |
| **Auditor / reviewer** | Fairness & governance. | Fairness audit join, won't-build list, suppression rules. | Read aggregates only; no PII beyond what 311 already publishes. |

The system is **single-tenant** (one municipality) for the MVP; multi-tenancy is not in scope. Borough is a *filter*, not a tenant boundary.

## 4. Core use cases

1. **Easy ticket, auto-routed.** A pothole report arrives → normalized → not a duplicate → classifier returns `DOT`, confidence 0.93 (calibrated) → above gate → SLA-light → work-order DAG drafts an order → handler approves → submitted to Linear. No agent involved.
2. **Duplicate suppressed.** A second pothole report at the same intersection within the time/geo window → dedup links it to the canonical ticket → no new work order; canonical ticket's report-count increments.
3. **Ambiguous ticket, agent triage.** "Water through the ceiling, floor buckling" → classifier low-confidence / multi-label → **gate routes to the agent** → agent calls `find_similar_tickets` (mixed precedents) → infers two sub-issues → `lookup_agency_jurisdiction` for each → discovers split ownership (DEP + HPD) → **decides split into 2** → reflects "confident enough" → back to deterministic pipeline, two work orders drafted → handler reviews both with the full agent trace.
4. **Agent gives up gracefully.** Same flow, but after the turn cap the agent is still unsure → routes to human queue with its partial findings attached. No silent guess.
5. **Operator reviews quality.** Ops lead opens the dashboard: routing F1 by complaint type, calibration curve, agent-vs-baseline correctness, override rate, fairness audit by tract income — drills into a specific bad trace.

## 5. Scope / governing rule applied

The [governing principle](README.md#governing-principle) decides each component's nature:

| Component | Agentic? | Why |
|-----------|----------|-----|
| Ingest, normalize, upsert | No | Fixed transform. |
| Dedup | No | Embedding similarity + geo/time window — deterministic scoring. |
| Classify + route | No | Cascade of model calls, but a fixed pipeline; output is a *label + calibrated confidence*, not an action. |
| Confidence gate | No | A threshold (see [ADR-002](ADRs.md#adr-002)). |
| **Intake triage** | **Yes — the one loop** | Next tool genuinely depends on the last result; the reflection is genuinely fuzzy. Must beat a baseline. |
| Work-order drafting | No | Inputs already disambiguated → fixed DAG, one bounded repair ([ADR-008](ADRs.md#adr-008)). |
| Submit to Linear | No | Deterministic, post human gate. |

## 6. Success metrics

**Product (portfolio-framed — "did it demonstrably work"):**
- Routing pre-fill: agency-routing **F1 ≥ existing rule-table baseline** on held-out 311 labels (target macro-F1 ≥ 0.85 on top-10 types).
- Human review load: ≥ 60% of tickets auto-handled below the gate (no agent, single-pass draft).
- Agent value (headline): triage agent beats **both** baselines on the ambiguous set — see [NFR-4.3](REQUIREMENTS.md#nfr-4--correctness--calibration) and [EVAL §agent path](AI-ARCHITECTURE.md#5-evaluation). If it can't beat "escalate all low-confidence to human," it is cut.
- Time-to-first-value: end-to-end demo (ingest → routed → drafted → submitted) runs on real Brooklyn data within Phase 4.

**Technical / SLO (quantified — see [REQUIREMENTS §NFR](REQUIREMENTS.md#2-non-functional-requirements-nfr)):**
- Fast-path p95 latency, agent-path p95 latency, cost per path, calibration error (ECE), availability — all pinned as `NFR-x.y`.

## 7. Risks

| ID | Risk | Mitigation |
|----|------|-----------|
| R1 | Realism gap *discovered* by a reviewer rather than disclosed | [README §what's real vs simulated](README.md#whats-real-vs-simulated-read-this-honestly) states it up front; [ADR-005](ADRs.md#adr-005), [ADR-006](ADRs.md#adr-006). |
| R2 | Ambiguous population too thin → agent unjustified | **Phase 2 GO/NO-GO gate** ([ROADMAP](ROADMAP.md#phase-2)) profiles the population *before* building the agent; amplify+disclose or rescope ([ADR-009](ADRs.md#adr-009)). |
| R3 | Agent fails to beat the escalate-all baseline → it's a gimmick | The [EVAL agent-path comparison](AI-ARCHITECTURE.md#5-evaluation) forces the honest answer early; cut the agent if it loses. |
| R4 | Calibration treated as free, gate becomes garbage | Calibration is a first-class pipeline step ([ADR-007](ADRs.md#adr-007), [NFR-4.1](REQUIREMENTS.md#nfr-4--correctness--calibration)). |
| R5 | SLA model leakage → invalid AUC | As-of-creation features only; exclude `status`, resolution text, post-resolution backlog features. Deferred, but the discipline is documented. |
| R6 | Prompt injection via malicious ticket text in tool results | Instruction/data separation + read-only tools + standing guardrails + [red-team study](AI-ARCHITECTURE.md#6-safety-guardrails--red-team). |
| R7 | Cost blows up at volume | Cascade + confidence gate bound the LLM bill; per-path cost is an SLO ([NFR-2](REQUIREMENTS.md#nfr-2--cost)). |
| R8 | Fairness claim made without the data to back it | Census/ACS tract join or **downgrade the claim**; name the ecological-fallacy caveat ([AI-ARCH §7](AI-ARCHITECTURE.md#7-fairness--governance)). |
| R9 | Scope creep across phases | Hold the MVP cut; Playwright/SLA/Airflow are explicitly deferred ([README scope table](README.md#governing-principle)). |
