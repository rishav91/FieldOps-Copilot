# Observability — FieldOps Copilot

How the system is traced, monitored, alerted, and kept honest in operation. The companion to [EVAL-SPEC](EVAL-SPEC.md) (offline correctness) — this doc is about *running* behavior. Requirements: [REQUIREMENTS §FR-11](REQUIREMENTS.md#fr-11--monitoring--drift) and the `NFR-6` group. System context: [ARCHITECTURE §7–8](ARCHITECTURE.md#7-failure-modes--degradation).

> **Why a standalone doc:** the design already traces per-turn and tracks cost. What was missing is the *operational rigor* layer — drift detection on a calibration step the whole gate depends on, SLO alerting (not just dashboards), spend enforcement (not just a configurable ceiling), and the human-override feedback loop that turns review clicks into labeled data. Those are collected here.

---

## 1. What we instrument (tenets)

1. **Everything is traced; nothing is sampled away on the agent path.** The ambiguous tail is low-volume and high-value — trace it at 100%. Sample the fast path if volume demands ([§8](#8-logging-retention--data-protection)).
2. **Confidence is a monitored quantity, not a one-time fit.** Calibration is load-bearing for the gate ([ADR-007](ADRs.md#adr-007)); it is monitored for drift, not assumed stable.
3. **Cost is enforced, not just observed.** A configurable ceiling without a breaker is theater ([§6](#6-cost-observability--spend-circuit-breaker)).
4. **Human actions are signal.** Every approve/edit/reject is captured as labeled data ([§7](#7-human-in-the-loop-feedback-loop)).
5. **No PII in telemetry.** Traces and logs carry correlation IDs and redacted text only ([§8](#8-logging-retention--data-protection)).

## 2. Tracing & correlation

One trace per ticket, propagated across every hop. IDs:

| ID | Scope | Carried by |
|----|-------|-----------|
| `ticket_id` | the canonical ticket, end to end | every span, log line, metric label |
| `trace_id` | one pipeline run for a ticket | OTel/LangSmith root span |
| `routing_decision_id` | one classify→gate→(agent) decision | agent spans, `agent_trace` rows |
| `draft_hash` | one work-order draft | drafting + submission spans |

**Span tree (per ticket):**

```
trace[ticket_id]
├─ ingest.normalize
├─ dedup.embed · dedup.ann_query        (attrs: neighbors, top_sim)
├─ classify.cheap_tier                  (attrs: label, raw_conf, resolved?)
├─ classify.groq_fallback               (attrs: label, raw_conf)         [conditional]
├─ calibrate                            (attrs: calibrated_conf)
├─ gate.decide                          (attrs: path=fast|agent, gate_version)
├─ agent.turn[n]  ──per turn──▶ tool.call (attrs: tool, args_valid, latency, tokens, cost)
│   └─ agent.reflect                    (attrs: confident?, decision)    [agent path]
├─ draft.fanout · draft.generate · draft.validate (attrs: validator_status, repair_count)
├─ human.gate                           (attrs: review_status, edited_fields)
└─ submit.linear                        (attrs: linear_id, idempotent_hit?)
```

Every LLM span carries `provider`, `model`, `model_version`, `tokens_in/out`, `cost`, `latency`. The `agent.turn` spans persist to the `agent_trace` table ([ARCHITECTURE §5](ARCHITECTURE.md#5-data-model-folded-in)) so the headline trace assertions ([EVAL-SPEC §5](EVAL-SPEC.md#5-agent-path-eval--the-headline)) are queryable, not just visible.

**Stack:** LangSmith for agent/LLM traces; OpenTelemetry for pipeline spans; both export to one backend so a `ticket_id` joins them.

## 3. Metrics & dashboards

The Streamlit dashboard ([FR-8.4](REQUIREMENTS.md#fr-8--evaluation--observability)) has four panels, each tied to an NFR:

| Panel | Metrics | Enforces |
|-------|---------|----------|
| **Throughput & latency** | tickets/day by path, fast-path p95, agent-path p95, batch duration | [NFR-1](REQUIREMENTS.md#nfr-1--latency) |
| **Cost** | cost per fast-path ticket, cost per agent ticket, daily spend vs ceiling, cost by provider/tier | [NFR-2](REQUIREMENTS.md#nfr-2--cost) |
| **Quality (live)** | rolling routing agreement vs 311 labels, calibration ECE (rolling), agent give-up rate, override rate | [NFR-4](REQUIREMENTS.md#nfr-4--correctness--calibration) |
| **Health** | error/abandon rate per stage, retry counts, dead-letter depth, provider 429 rate | [NFR-3](REQUIREMENTS.md#nfr-3--availability--reliability) |

## 4. SLOs & alerting

Dashboards alone don't page anyone. Each SLO has an alert and a defined response.

| SLO | Target | Alert trigger | Response |
|-----|--------|---------------|----------|
| Fast-path latency | p95 ≤ 5 s ([NFR-1.1](REQUIREMENTS.md#nfr-1--latency)) | p95 > 5 s for 15 min | check provider latency; degrade to cheap tier |
| Agent give-up rate | ≤ target | give-up rate > 2× baseline for 1 h | inspect recent traces; likely tool or prompt regression |
| Calibration | ECE ≤ 0.05 ([NFR-4.1](REQUIREMENTS.md#nfr-4--correctness--calibration)) | rolling ECE > 0.08 ([NFR-6.4](REQUIREMENTS.md#nfr-6--observability)) | trigger recalibration ([§5](#5-drift--decay-monitoring)) |
| Daily spend | ≤ ceiling ([NFR-2.3](REQUIREMENTS.md#nfr-2--cost)) | 80% of ceiling | warn; at 100% the breaker trips ([§6](#6-cost-observability--spend-circuit-breaker)) |
| Pipeline health | dead-letter ≈ 0 | dead-letter depth > 0 | replay after fix; nothing is lost (idempotent) |

## 5. Drift & decay monitoring

Calibration is fit once but the world moves. Monitored continuously, recalibrated on trigger:

- **Calibration drift** — rolling ECE on the stream of decisions that later get a 311 ground-truth label; when ECE crosses [NFR-6.4](REQUIREMENTS.md#nfr-6--observability), auto-flag for re-fit ([ADR-007](ADRs.md#adr-007) consequence).
- **Input distribution drift** — KL-divergence / PSI on complaint-type mix and descriptor-embedding centroids vs. the training window; catches new complaint patterns the cascade hasn't seen.
- **Cheap-tier false-confidence** — the classical/Groq tier can resolve *high-confidence and skip the gate*, so its drift is the most dangerous. Tracked separately ([EVAL-SPEC §3](EVAL-SPEC.md#3-discriminative-eval)).
- **Agent behavior drift** — turn-count distribution and give-up rate over time; a creeping rise signals prompt/tool/model-version regression.

Cadence: rolling daily windows; alerts as in §4. Drift is a *monitoring* concern here; the offline re-fit + re-eval protocol lives in [EVAL-SPEC](EVAL-SPEC.md).

## 6. Cost observability & spend circuit breaker

Every LLM span logs tokens + cost; the dashboard aggregates per path and per provider. **Enforcement** ([FR-10.2](REQUIREMENTS.md#fr-10--guardrails), [NFR-5.4](REQUIREMENTS.md#nfr-5--security--safety)):

- **Per-day spend ceiling** — a hard stop. At 100%, new agent-path work is queued (not dropped) and the fast path continues; cleared next window. At 80%, warn.
- **Global concurrency cap** — bounds parallel LLM calls so a backfill or retry storm can't fan out unbounded.
- **Provider rate-limit handling** — bounded retries with exponential backoff + jitter, honoring `429`/`Retry-After` ([NFR-5.5](REQUIREMENTS.md#nfr-5--security--safety)); on sustained limit, fail over to the alternate provider ([ADR-003](ADRs.md#adr-003)).

## 7. Human-in-the-loop feedback loop

The human gate produces **free labeled data** that the original design measured but discarded. Closed here:

```
human.gate ──▶ approve            ─▶ confirms routing+draft (positive label)
            ──▶ edit(fields)      ─▶ correction signal (what was wrong → labeled delta)
            ──▶ reject            ─▶ negative label + reason code
                     │
                     ▼
        override/edit store ──▶ feeds EVAL-SPEC golden-set refresh (FR-8.13)
                            ──▶ candidate recalibration data
                            ──▶ red-flag clustering (recurring edit patterns → prompt/tool fix)
```

Captured on every review: `review_status`, `edited_fields`, `reject_reason`. This is the cheapest, highest-quality label source in the system ([EVAL-SPEC §2](EVAL-SPEC.md#2-eval-datasets--governance)).

## 8. Logging, retention & data protection

- **Structured logs** keyed by `ticket_id` / `trace_id`, with levels; one event schema across stages.
- **No PII in telemetry.** Ticket text is redacted before it reaches traces/logs ([§ guardrails](AI-ARCHITECTURE.md#6-safety-guardrails--red-team), [NFR-6.5](REQUIREMENTS.md#nfr-6--observability)). Secrets never logged ([NFR-5.1](REQUIREMENTS.md#nfr-5--security--safety)).
- **Retention & sampling** — traces retained ≥ 30 days (demo) ([NFR-6.5](REQUIREMENTS.md#nfr-6--observability)); agent path traced at 100%, fast path sampled if volume demands.
- **Failure observability** — failed stages land in a dead-letter store with full context for replay; idempotency ([NFR-3.2](REQUIREMENTS.md#nfr-3--availability--reliability)) makes replay safe.

## 9. The debugging-narrative deliverable

[NFR-6.3](REQUIREMENTS.md#nfr-6--observability) requires one documented end-to-end debug story (symptom → diagnosis → fix) using these traces — the artifact that proves the observability is real, not decorative.
