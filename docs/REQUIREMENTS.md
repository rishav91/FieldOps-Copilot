# Requirements — FieldOps Copilot

The contract. Functional requirements (`FR-x.y`) are prioritized **P0 / P1 / P2**; **P0 = the MVP**. Non-functionals (`NFR-x.y`) are quantified — no adjectives without numbers. IDs are append-only. Rationale lives in [ADRs](ADRs.md); design in [ARCHITECTURE](ARCHITECTURE.md) / [AI-ARCHITECTURE](AI-ARCHITECTURE.md).

---

## 1. Functional requirements

### FR-1 — Ingestion
| ID | Requirement | Pri | Acceptance |
|----|-------------|-----|-----------|
| FR-1.1 | Pull the NYC 311 daily delta via Socrata SODA with app-token auth. | P0 | Cron run fetches records since the last watermark; auth via token. |
| FR-1.2 | Normalize each record to the canonical `ticket` schema; retain the raw payload. | P0 | `raw_311_record` immutable copy + populated `ticket`. |
| FR-1.3 | Idempotent upsert by `unique_key`. | P0 | Re-running the same delta produces no duplicate rows. |
| FR-1.4 | 12-month backfill loader (one borough, top-10 free-text types). | P0 | Backfill completes; counts match source query. |
| FR-1.5 | Watermark + retry/backoff on Socrata errors. | P1 | Transient API failure does not advance the watermark; resumes cleanly. |

### FR-2 — Deduplication
| ID | Requirement | Pri | Acceptance |
|----|-------------|-----|-----------|
| FR-2.1 | Embed each ticket and store the vector (pgvector, HNSW). | P0 | Vector present per ticket; ANN query returns neighbors. |
| FR-2.2 | Link near-duplicates within a geo + time window above a similarity threshold. | P0 | `duplicate_of` edge written; canonical `report_count` increments; no deletion. |
| FR-2.2a | **Three-band dedup** (DR-15): very-high-confidence auto-link, a gray-zone *review* band (no auto-suppression), no-link. Preserve all source descriptions on the canonical; don't suppress a report carrying materially new issue/severity content. | P1 | Auto-link target set well above 0.90 with a reported lower CI bound; gray-zone cases flagged, not merged. |
| FR-2.3 | Hand-labeled eval set of a few hundred dedup pairs. | P0 | Labeled set exists; precision/recall computed against it ([NFR-4.2](#nfr-4--correctness--calibration)). |
| FR-2.4 | Dedup threshold is config-tunable. | P1 | Change threshold without redeploy. |

### FR-3 — Classification & routing
| ID | Requirement | Pri | Acceptance |
|----|-------------|-----|-----------|
| FR-3.1 | Cascade classifier: classical/cheap tier → Groq fallback → (rare) OpenAI. | P0 | Most tickets resolved at the cheap tier; fallback only on uncertainty. |
| FR-3.2 | Output agency + complaint-type label with a **calibrated** confidence. | P0 | `routing_decision` row with `confidence_calibrated`. |
| FR-3.3 | Detect multi-label / multi-agency cases. | P0 | Such cases flagged for the gate regardless of score. |
| FR-3.4 | Score calibration (Platt/isotonic) on a held-out set + reliability curve. | P0 | ECE meets [NFR-4.1](#nfr-4--correctness--calibration); curve is an artifact. |
| FR-3.5 | **Inference feature contract** (DR-02, [ADR-011](ADRs.md#adr-011)): classifiers/agent/tools receive a typed as-of `InferenceTicket`, never the raw canonical row/payload; target + post-outcome fields are prohibited from prediction paths. | P0 | A test fails if a target/post-outcome field enters a prompt, embedding, or retrieval feature. |

### FR-4 — Confidence gate
| ID | Requirement | Pri | Acceptance |
|----|-------------|-----|-----------|
| FR-4.1 | Route high-confidence single-agency tickets to the deterministic fast path. | P0 | `path = fast` recorded; no agent invoked. |
| FR-4.2 | Route low-confidence / multi-label / multi-agency tickets to the agent. | P0 | `path = agent` recorded. |
| FR-4.3 | Gate threshold config-tunable, versioned on the decision. | P1 | `gate_version` stored; retune without redeploy. |

### FR-5 — Intake triage agent
| ID | Requirement | Pri | Acceptance |
|----|-------------|-----|-----------|
| FR-5.1 | LangGraph loop with a **read-only** tool menu (`find_similar_tickets`, `lookup_agency_jurisdiction`, `get_historical_resolutions`, `classify_subissue`). | P0 | No side-effecting tool present; tools callable. |
| FR-5.2 | Decide `route` / `split into N` / `escalate` as a *proposal* feeding deterministic drafting. | P0 | Decision recorded; never finalizes routing itself. |
| FR-5.3 | Per-turn tracing to `agent_trace` (tool, args, result, reflection, tokens, cost). | P0 | One row per turn; visible in dashboard. |
| FR-5.4 | Hard turn cap with graceful give-up → human queue (partial findings attached). | P0 | Cap hit → status `ESCALATED`, no silent guess. |
| FR-5.5 | Structured tool-arg validation before each call; idempotency keyed on `routing_decision_id`. | P0 | Invalid args rejected pre-call; re-runs don't duplicate. |
| FR-5.6 | Agent must beat the **information-matched Baseline C** (fixed retrieval + one call). | P0 | See [NFR-4.3](#nfr-4--correctness--calibration); fails C → keep fixed workflow, cut the loop (DR-05). |
| FR-5.7 | **As-of retrieval** (DR-08, [ADR-011](ADRs.md#adr-011)): every tool/eval retrieval enforces `candidate.created_date < subject.created_date`, excludes self / split children / known duplicates, and pins a snapshot. | P0 | Adversarial future-/self-/duplicate-neighbor tests pass. |

### FR-6 — Work-order drafting DAG
| ID | Requirement | Pri | Acceptance |
|----|-------------|-----|-----------|
| FR-6.1 | Concurrent fan-out of read-only context tools into a bundle. | P0 | Bundle assembled; parallel calls traced. |
| FR-6.2 | One structured generation of the draft (owner, next action, due date, cited precedent). | P0 | Draft has all required fields. |
| FR-6.3 | Deterministic validator: precedent-ID membership, agency match, required fields. | P0 | Invalid drafts flagged, not submitted. |
| FR-6.4 | At most **one** bounded repair re-prompt with specific errors. | P0 | ≤1 repair; second failure → human with errors. |

### FR-7 — Human gate & submission
| ID | Requirement | Pri | Acceptance |
|----|-------------|-----|-----------|
| FR-7.1 | Review UI: approve / edit / reject, showing routing rationale + agent trace. | P0 | Handler can act; trace visible. |
| FR-7.2 | Deterministic submission to Linear (GraphQL + OAuth) on approval. | P0 | Approved order creates a Linear issue. |
| FR-7.3 | Idempotent submission keyed on `draft_hash` (ticket id + draft). | P0 | Replays don't double-create. |
| FR-7.4 | Nothing reaches Linear without human approval. | P0 | No code path submits pre-gate. |

### FR-8 — Evaluation & observability
| ID | Requirement | Pri | Acceptance |
|----|-------------|-----|-----------|
| FR-8.1 | Discriminative eval vs. 311 labels (F1, precision/recall, confusion, calibration). | P0 | Metrics reproducible from a script. |
| FR-8.2 | Generative eval: hard checks → LLM-judge → human spot-check, with judge↔human agreement. | P0 | All three reported; agreement rate shown. |
| FR-8.3 | Agent-vs-baseline study (correctness, turn dist, give-up rate, cost, trace assertions). | P0 | Headline comparison reproducible. |
| FR-8.3a | **Information-matched baseline C** (DR-05): fixed retrieval + one structured call, same tools/context/model/schema as the agent, no loop. Ship gate compares agent vs. **C**. | P0 | [EVAL-SPEC §5](EVAL-SPEC.md#5-agent-path-eval--the-headline); tool ablations reported. |
| FR-8.3b | **Adjudicated route/split/escalate gold set** (DR-04) with set-based split metrics; abstention scored separately. | P1 | ≥2 annotators + κ; natural vs. synthetic separate. |
| FR-8.3c | **Human-workflow study** (DR-03/07): unaided vs. agent-assisted review; non-inferior correctness + reduced handling time (95% CI). Minimal blinded harness is a **Phase-3** deliverable. | P1 | [EVAL-SPEC §5a](EVAL-SPEC.md#5a-human-workflow-study-dr-03dr-07). |
| FR-8.4 | Operational metrics: latency, cost per path, override rate, abandoned steps, retries. | P0 | Streamlit dashboard surfaces them. |
| FR-8.5 | Fairness audit: Census/ACS tract join by complaint type; ecological-fallacy caveat. | P1 | Disparity reported *or* claim explicitly downgraded ([AI-ARCH §7](AI-ARCHITECTURE.md#7-fairness--governance)). |
| FR-8.6 | Red-team study: prompt injection + adversarial mis-routing; document break + mitigation. | P1 | Write-up exists. |
| FR-8.7 | Agent-vs-baseline reported with **sample size, bootstrap 95% CIs, and a significance test**; cut-decision uses the CI lower bound on **(agent − Baseline C)**. | P0 | See [EVAL-SPEC §5](EVAL-SPEC.md#5-agent-path-eval--the-headline); meets [NFR-4.5](#nfr-4--correctness--calibration). |
| FR-8.8 | LLM-judge **validated** (gold-set agreement, position/verbosity-bias, prompt sensitivity) before its scores are trusted. | P1 | [EVAL-SPEC §4](EVAL-SPEC.md#4-generative-eval); judge fails → downgraded to advisory. |
| FR-8.9 | Eval datasets **versioned + provenance-tracked**, with a **frozen test split never used for tuning/calibration**. | P0 | Dataset cards exist; test split isolated by time. |
| FR-8.10 | **Eval gates in CI**: regression beyond a set delta on key metrics fails the build. | P1 | [EVAL-SPEC §11](EVAL-SPEC.md#11-ci-gates--reproducibility). |
| FR-8.11 | **Cheap-tier false-confidence eval**: error rate among high-confidence cheap-tier resolutions that skip the gate. | P0 | Silent-mis-route rate bounded + reported. |
| FR-8.12 | **End-to-end compounding-error eval** scoring the final outcome over the full pipeline. | P1 | E2E rate vs. per-stage product reported. |
| FR-8.13 | Human override/edit captured as **labeled data** feeding eval/golden-set refresh. | P1 | `edited_fields` / `reject_reason` stored ([OBSERVABILITY §7](OBSERVABILITY.md#7-human-in-the-loop-feedback-loop)). |
| FR-8.14 | **Inter-annotator agreement** (κ) on hand-labeled sets + human spot-checks. | P1 | ≥2 annotators; κ reported. |
| FR-8.15 | **Provider-swap regression harness**: per-tier metric deltas across providers/versions. | P2 | OpenAI↔Groq / version bumps compared ([ADR-003](ADRs.md#adr-003)). |

### FR-9 — SLA risk (deferred / MVP-light)
| ID | Requirement | Pri | Acceptance |
|----|-------------|-----|-----------|
| FR-9.1 | Tabular SLA risk score from **as-of-creation** features only (no leakage). | P2 | Excludes `status`, resolution text, post-resolution features. May stub `null` in MVP. |

### FR-10 — Guardrails
| ID | Requirement | Pri | Acceptance |
|----|-------------|-----|-----------|
| FR-10.1 | **PII detection + redaction** on ticket text before any external (OpenAI/Groq) LLM call and before telemetry. | P0 | No raw address/name/phone leaves the boundary ([NFR-8.4](#nfr-8--privacy--fairness)); verified by test. |
| FR-10.2 | **Spend + concurrency circuit breaker**: per-day ceiling hard-stop, global concurrency cap, provider 429 backoff. | P0 | Breaker trips at 100% ceiling; queues, never drops ([OBSERVABILITY §6](OBSERVABILITY.md#6-cost-observability--spend-circuit-breaker)). |
| FR-10.3 | **Structured-output enforcement**: classifier/agent agency constrained to a valid enum; agent `split into N` bounded (N ≤ cap). | P0 | Invalid agency / oversized split rejected pre-use. |
| FR-10.4 | **Standing prompt-injection defense** (delimiting/spotlighting + injection heuristics), not just the red-team study. | P1 | Tool results treated as data; defense documented ([AI-ARCH §6](AI-ARCHITECTURE.md#6-safety-guardrails--red-team)). |
| FR-10.5 | **Malformed-LLM-output fallback** for the classifier path (→ treat as low-confidence / human). | P1 | Unparseable output never silently routes. |

### FR-11 — Monitoring & drift
| ID | Requirement | Pri | Acceptance |
|----|-------------|-----|-----------|
| FR-11.1 | Monitor **calibration drift, input-distribution drift, and cheap-tier accuracy** with thresholds + auto re-fit flag. | P1 | [OBSERVABILITY §5](OBSERVABILITY.md#5-drift--decay-monitoring). |
| FR-11.2 | **SLO definitions + burn alerts** for latency, cost, ECE, give-up rate. | P1 | Alerts fire per [OBSERVABILITY §4](OBSERVABILITY.md#4-slos--alerting). |
| FR-11.3 | **Trace/log retention + sampling** policy; **no PII in logs**. | P1 | Agent path 100% traced; retention ≥30d ([NFR-6.5](#nfr-6--observability)). |

### P0 summary (the MVP)
Ingest + backfill (FR-1) → dedup with eval set (FR-2) → calibrated cascade classifier + routing (FR-3) → confidence gate (FR-4) → the one triage agent that beats both baselines (FR-5) → deterministic drafting DAG with validator (FR-6) → human gate + Linear submission (FR-7) → discriminative/generative/agent/operational eval + dashboard (FR-8.1–8.4). **P0 rigor/guardrails:** statistical proof + cheap-tier false-confidence + frozen eval split (FR-8.7, FR-8.11, FR-8.9), PII redaction, spend breaker, structured-output constraints (FR-10.1–10.3). Fairness (FR-8.5), red-team (FR-8.6), judge validation (FR-8.8), CI gates (FR-8.10), drift/SLO monitoring (FR-11), and SLA (FR-9) are P1/P2.

---

## 2. Non-functional requirements (NFR)

### NFR-1 — Latency
| ID | Requirement |
|----|-------------|
| NFR-1.1 | Fast-path resolution (classify → draft, excluding human review) **p95 ≤ 5 s**. |
| NFR-1.2 | Agent-path resolution **p95 ≤ 30 s** within the turn cap. |
| NFR-1.3 | Daily delta batch (ingest → all routed) completes in **≤ 15 min** at demo scale (§3). |

### NFR-2 — Cost
| ID | Requirement |
|----|-------------|
| NFR-2.1 | ≥ 70% of tickets resolved at the **classical/cheap tier** (no expensive LLM call). |
| NFR-2.2 | LLM cost per fast-path ticket **≤ $0.01**; per agent-path ticket **≤ $0.10** (default-provider estimate; see §3). |
| NFR-2.3 | Per-run cost ceiling is configurable; the dashboard reports cost per path and total spend. |

### NFR-3 — Availability & reliability
| ID | Requirement |
|----|-------------|
| NFR-3.1 | LLM provider outage degrades to the alternate provider **only for a provider/model/prompt/calibrator combo that has passed tier eval** ([ADR-003](ADRs.md#adr-003), DR-14); an unvalidated alternate **fails closed** to low-confidence → human/queue. If all fail, tickets queue for replay with **zero data loss** ([ARCHITECTURE §7](ARCHITECTURE.md#7-failure-modes--degradation)). |
| NFR-3.2 | All writes idempotent: upsert by `unique_key`, agent by `routing_decision_id`, submission by `draft_hash`. Replays never double-write. |
| NFR-3.3 | Validator and submission **fail closed** — on doubt, nothing is submitted. |

### NFR-4 — Correctness & calibration
| ID | Requirement |
|----|-------------|
| NFR-4.1 | Classifier **Expected Calibration Error (ECE) ≤ 0.05** on the held-out set; reliability curve published ([ADR-007](ADRs.md#adr-007)). Report calibration/error **by tier** (cheap/Groq/OpenAI) and important class, plus a **declared maximum tolerated fast-path error** (with a CI) and a risk-vs-coverage curve at the chosen gate operating point (DR-13). |
| NFR-4.2 | Routing **macro-F1 ≥ 0.85** on top-10 types vs. 311 labels; dedup precision **≥ 0.90** on the labeled pair set. |
| NFR-4.3 | Triage agent **beats the information-matched Baseline C** (fixed retrieval + one call) on the ambiguous set (routing/split correctness), at acceptable give-up rate. Failing C → keep the fixed workflow, cut the loop (DR-05, [AI-ARCH §5](AI-ARCHITECTURE.md#5-evaluation)). Baseline B is a cost/coverage reference, not a correctness comparator (DR-03). |
| NFR-4.4 | Generative drafts pass deterministic hard checks **100%** before reaching a human (validator gate); judge↔human agreement reported. |
| NFR-4.5 | The agent-beats-baseline claim is reported with stated `n` and **bootstrap 95% CIs**; the agent ships only if the **lower CI bound of (agent − Baseline C) > 0** ([EVAL-SPEC §5](EVAL-SPEC.md#5-agent-path-eval--the-headline)). |

### NFR-5 — Security & safety
| ID | Requirement |
|----|-------------|
| NFR-5.1 | Secrets (Socrata token, LLM keys, Linear OAuth) in a secret store; never logged or traced. |
| NFR-5.2 | Ticket text / tool results treated as **data, not instructions**; injection cannot redirect the agent to a non-menu action (read-only blast radius). |
| NFR-5.3 | Linear OAuth uses least-scope tokens. |
| NFR-5.4 | **Per-day spend ceiling and max concurrency are enforced** (hard stop / queue), not merely configured ([FR-10.2](#fr-10--guardrails)). |
| NFR-5.5 | All external LLM/API calls use bounded retries with **exponential backoff + jitter**, honoring provider `429`/`Retry-After`; sustained limit → provider failover. |

### NFR-6 — Observability
| ID | Requirement |
|----|-------------|
| NFR-6.1 | Per-stage + per-agent-turn traces with correlation to `ticket_id` / `routing_decision_id`. |
| NFR-6.2 | Every LLM call logs tokens + cost; dashboard shows cost per path. |
| NFR-6.3 | One documented end-to-end **debugging narrative** (symptom → diagnosis → fix) as a deliverable. |
| NFR-6.4 | **Drift alerts** fire when rolling calibration **ECE > 0.08** or input-distribution divergence (KL/PSI) exceeds threshold ([OBSERVABILITY §5](OBSERVABILITY.md#5-drift--decay-monitoring)). |
| NFR-6.5 | Traces retained **≥ 30 days** (demo); agent path traced at **100%**; logs carry correlation IDs and **never PII** ([OBSERVABILITY §8](OBSERVABILITY.md#8-logging-retention--data-protection)). |

### NFR-7 — Scalability & capacity
| ID | Requirement |
|----|-------------|
| NFR-7.1 | Designed to scale from demo (one borough) to citywide by partitioning `ticket`/`raw_311_record` by month and (if needed) swapping pgvector for a dedicated vector DB — **without rearchitecting** the pipeline ([ADR-010](ADRs.md#adr-010)). |
| NFR-7.2 | Cost and latency scale **sub-linearly with the cheap tier ratio** (NFR-2.1): the gate keeps the agent share roughly constant as volume grows. |

### NFR-8 — Privacy & fairness
| ID | Requirement |
|----|-------------|
| NFR-8.1 | Use only data 311 already publishes; no inference of attributes about individual reporters. |
| NFR-8.2 | No fairness statistic on a cell below the minimum sample size; ecological-fallacy caveat stated ([AI-ARCH §7](AI-ARCHITECTURE.md#7-fairness--governance)). |
| NFR-8.3 | The governance won't-build list is honored in code review. |
| NFR-8.4 | **No raw PII leaves the system boundary** to a third-party LLM; ticket text **and retrieved tool results** are redacted before any external call or telemetry ([FR-10.1](#fr-10--guardrails)); verified by test. |
| NFR-8.5 | **Per-destination egress policy** (DR-17): a field matrix governs what reaches local storage / embeddings / agent tools+traces / reviewer UI / Linear. Default to minimization; use coarse location for routing; send exact location to Linear only if needed and disclosed ([ADR-005](ADRs.md#adr-005)). |

---

## 3. Capacity sizing

Scale posture: **demo-scale now, designed for scale** (per the intake decision). Numbers below are for one borough (Brooklyn), top-10 free-text complaint types, 12-month backfill. *Assumption: figures are order-of-magnitude estimates from public 311 volumes; revisit against the actual backfill query.*

**Volume (the math):**
- NYC 311 ≈ **3M requests/yr** citywide. Brooklyn ≈ 28% ⇒ ≈ **840k/yr** all types.
- Top-10 free-text types ≈ 30% of that ⇒ **≈ 250k tickets** backfill.
- Daily delta: 250k ÷ 365 ≈ **~685/day** (size for ~700/day, bursty to ~1.5×).

**Storage:**
- Embeddings: 250k × ~1536-dim float32 (~6 KB) ≈ **1.5 GB** raw; HNSW overhead ~2× ⇒ **~3 GB**.
- `ticket` + `raw_311_record` (jsonb payload ~3 KB) ≈ 250k × ~4 KB ⇒ **~1 GB**.
- Traces/decisions grow with the agent share, not total volume — small. **Total well within a single Postgres instance.**

**LLM call budget (per day, ~700 new tickets):**
- Cheap tier resolves ≥ 70% ⇒ ~490 tickets, **0 expensive calls**.
- Groq fallback on ~30% ⇒ **~210 calls/day** (free/low-cost tier).
- Ambiguous tail to agent ≈ 12% ⇒ ~85 tickets × ~6 OpenAI calls ⇒ **~510 agent calls/day**.
- Drafting: ~700 routed × ~1.3 (incl. occasional repair) ⇒ **~910 generations/day**.

**Cost envelope:** dominated by the agent tail + drafting (OpenAI), not the bulk (classical tier + Groq) — exactly what the cascade + gate are for. Per-ticket targets in [NFR-2.2](#nfr-2--cost). Exact dollars depend on current OpenAI / Groq pricing; the **structure** is what bounds spend, and it holds as volume grows because the cheap-tier ratio (NFR-2.1) is roughly volume-invariant.

**Headroom to citywide:** ×~12 volume (≈ 3M/yr, ~8–10k/day). Mitigations already designed in: monthly partitioning (NFR-7.1), the volume-invariant cascade ratio (NFR-7.2), and a pgvector→dedicated-vector-DB swap behind the same access pattern. No pipeline rearchitecture required.
