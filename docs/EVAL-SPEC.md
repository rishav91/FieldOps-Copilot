# Evaluation Spec — FieldOps Copilot

The offline correctness contract: exact metrics, datasets, statistical protocol, and CI gates. Companion to [OBSERVABILITY](OBSERVABILITY.md) (live behavior). Expands [AI-ARCHITECTURE §5](AI-ARCHITECTURE.md#5-evaluation) from "what we measure" to "how, with what rigor." Requirements: [REQUIREMENTS §FR-8](REQUIREMENTS.md#fr-8--evaluation--observability).

> **Why a standalone doc:** the suite already splits evals by task type and names the agent-vs-baseline comparison. What was missing is *rigor* — the headline claim had no sample size or confidence interval, the LLM-judge was itself unvalidated, eval datasets had no governance/frozen test split, and nothing gated CI on regression. This doc closes those.

---

## 1. Principles

1. **Split by task type** (discriminative / generative / agent / end-to-end). The split itself is a design statement: different tasks need different evidence.
2. **Hard checks before soft judgment.** Deterministic membership/assertion checks first; an LLM-judge only after; humans last.
3. **A claim is a number with an interval.** "Beats baseline" without `n` and a CI is an anecdote ([§5](#5-agent-path-eval--the-headline)).
4. **The judge is a model under test too** ([§4](#4-generative-eval)).
5. **Test data is frozen and never tuned on** ([§2](#2-eval-datasets--governance)).

## 2. Eval datasets & governance

| Dataset | Source | Size | Governance |
|---------|--------|------|-----------|
| Routing/classification gold | 311 labels ([ADR-006](ADRs.md#adr-006)) | full held-out split | **frozen test split never used for tuning/calibration**; train/calib/test by time to avoid leakage |
| Dedup pairs | hand-labeled | few hundred | **≥2 annotators**, inter-annotator agreement (Cohen's κ) reported ([FR-8.14](REQUIREMENTS.md#fr-8--evaluation--observability)) |
| Ambiguous/agent set | natural + (if needed) amplified ([ADR-009](ADRs.md#adr-009)) | profiled in [Phase 1](ROADMAP.md#phase-1) | **held-out natural slice** reported separately from synthetic; synthetic clearly tagged |
| Generative gold | curated work-order references | small | used to calibrate the judge ([§4](#4-generative-eval)) |
| Override-derived | human gate ([OBSERVABILITY §7](OBSERVABILITY.md#7-human-in-the-loop-feedback-loop)) | grows | corrections fold into gold sets on a versioned cadence ([FR-8.13](REQUIREMENTS.md#fr-8--evaluation--observability)) |

Each dataset carries a **dataset card**: provenance, version, split logic, label definitions, known biases. Versions are pinned in every eval run manifest ([§11](#11-ci-gates--reproducibility)).

## 3. Discriminative eval

Classification, routing, dedup, SLA. Scored against 311 labels / computed outcomes; unit-testable.

- **Metrics:** precision / recall / **macro-F1** (routing target ≥ 0.85, [NFR-4.2](REQUIREMENTS.md#nfr-4--correctness--calibration)), per-class confusion, dedup precision ≥ 0.90.
- **Calibration:** reliability curve + **ECE ≤ 0.05** ([NFR-4.1](REQUIREMENTS.md#nfr-4--correctness--calibration)); Platt/isotonic fit on the calibration split, evaluated on the frozen test split.
- **Cheap-tier false-confidence eval ([FR-8.11](REQUIREMENTS.md#fr-8--evaluation--observability)).** The classical/Groq tier can resolve *high-confidence and skip the gate*, so its calibration is the most safety-critical. Measured separately: among cheap-tier high-confidence resolutions, what fraction were actually wrong? This bounds the silent mis-route rate — the failure the gate can't catch.
- **Gate operating point.** The threshold is an *eval output*, not a guess: sweep it, plot the precision (correct fast-path routes) vs. agent-load trade-off, pick the point where fast-path error ≤ tolerated and report it.

## 4. Generative eval

Work-order drafts and resolution summaries.

1. **Deterministic hard checks first (gate, 100% — [NFR-4.4](REQUIREMENTS.md#nfr-4--correctness--calibration)):** cited-precedent-ID membership in the bundle, agency match to routing, required fields present. A draft failing any check never reaches a human.
2. **LLM-judge rubric:** actionability, grounding, specificity — scored on survivors of step 1.
3. **Human spot-check** on a sample; report **judge↔human agreement** (κ / correlation).

**Judge validation ([FR-8.8](REQUIREMENTS.md#fr-8--evaluation--observability)) — the part usually skipped:** before trusting judge scores, validate the judge on the generative gold set ([§2](#2-eval-datasets--governance)): agreement with human gold, **position/order bias** (swap A/B, expect stable verdicts), **verbosity bias** (longer ≠ better), and prompt-sensitivity (paraphrase the rubric, expect stable scores). A judge that fails these is fixed or downgraded to advisory before its numbers are reported. *Use a different provider/model for the judge than the generator where possible to reduce self-preference bias.*

## 5. Agent-path eval — the headline

The central empirical bet. The triage agent must beat **two** baselines on the ambiguous set:
- **Baseline A** — single classifier call (top label).
- **Baseline B** — escalate all low-confidence to a human.

**Metrics:** routing/split **correctness**, **turn-count distribution**, **give-up rate**, **cost per resolution**, and **trace assertions** (e.g. *did it call `lookup_agency_jurisdiction` before deciding to split?* — queried from `agent_trace`, [OBSERVABILITY §2](OBSERVABILITY.md#2-tracing--correlation)).

**Statistical protocol ([FR-8.7](REQUIREMENTS.md#fr-8--evaluation--observability), [NFR-4.5](REQUIREMENTS.md#nfr-4--correctness--calibration)) — non-negotiable:**
- **Sample size** `n` stated for the ambiguous set; power-checked so a meaningful delta is detectable.
- **Bootstrap 95% confidence intervals** on the correctness delta (agent − baseline).
- **Significance test** (paired, on per-ticket outcomes — McNemar for the paired binary correctness).
- **Decision rule:** the agent ships only if the **lower bound of the 95% CI on (agent − Baseline B) > 0** — i.e. it's better *with confidence*, not on a point estimate. **If not, the agent is cut** ([PRD R3](PRD.md#7-risks)). Report natural-slice and synthetic results separately ([§2](#2-eval-datasets--governance)).
- Report the **cost delta** alongside: a tiny accuracy win at large cost is still a cut candidate.

## 6. End-to-end / compounding-error eval

Component metrics miss compounding failure (a correct route + a bad draft = a bad outcome). [FR-8.12](REQUIREMENTS.md#fr-8--evaluation--observability): run a sample of tickets through the **full pipeline** and score the *final* outcome (correct routed-and-drafted work order) end to end. The gap between per-stage product and the measured end-to-end rate is the compounding-error budget.

## 7. Operational eval

Latency, cost per path, override rate, abandoned steps, retries — defined and surfaced in [OBSERVABILITY §3–4](OBSERVABILITY.md#3-metrics--dashboards). Offline, these are reported per release; live, they are SLOs with alerts.

## 8. Fairness eval

Per [AI-ARCHITECTURE §7](AI-ARCHITECTURE.md#7-fairness--governance): Census/ACS tract join testing whether SLA risk / auto-priority differs by borough/income **for the same complaint type**; **minimum-sample suppression** (no statistic on a cell below threshold, [NFR-8.2](REQUIREMENTS.md#nfr-8--privacy--fairness)); the **ecological-fallacy** caveat stated. Without the join, the claim is **downgraded, not checkboxed** ([PRD R8](PRD.md#7-risks)).

## 9. Red-team & robustness eval

- **Prompt injection** via malicious ticket text surfacing in tool results — does the standing defense ([AI-ARCH §6](AI-ARCHITECTURE.md#6-safety-guardrails--red-team)) hold? Document breaks + mitigations ([FR-8.6](REQUIREMENTS.md#fr-8--evaluation--observability)).
- **Adversarial mis-routing** — descriptions crafted to force a wrong agency.
- **Robustness** — typos, truncated descriptors, and **non-English** text (NYC 311 is multilingual): does routing degrade gracefully or fail silently?

## 10. Provider-swap regression harness

[ADR-003](ADRs.md#adr-003) makes providers swappable; [FR-8.15](REQUIREMENTS.md#fr-8--evaluation--observability) makes that safe. A harness re-runs the per-tier evals across providers/versions (OpenAI vs Groq on the classifier tier; OpenAI model-version bumps on the agent) and reports the metric deltas, so a swap is a measured decision, not a leap. Model behavior isn't portable even though the interface is.

## 11. CI gates & reproducibility

- **CI gates ([FR-8.10](REQUIREMENTS.md#fr-8--evaluation--observability)):** the discriminative + hard-check + agent-vs-baseline evals run in CI on the frozen test split; a regression beyond a set delta on macro-F1, ECE, cheap-tier false-confidence, or the agent CI-lower-bound **fails the build**. Evals are tests, not a one-off notebook.
- **Reproducibility:** every eval run emits a manifest — dataset versions, pinned model IDs + provider, prompt versions, seeds, git SHA — so any number can be regenerated.
