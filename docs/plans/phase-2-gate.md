# Phase 2 — GO / NO-GO ambiguity gate (decision)

The hard gate before any agent code ([ROADMAP](../ROADMAP.md#phase-2), [PRD R2](../PRD.md#7-risks)): **does a real ambiguous / multi-agency population exist to justify the agent?** This records the measured result and the decision.

**Status: ⏳ RECOMMENDED GO (with amplification) — awaiting your confirmation.** Phase 3 must not start until confirmed.

## The run (bounded ~3k sample)

- Ingested **3,089** Brooklyn tickets (12-month window, top-10 complaint types); **3,041** embedded (OpenAI `text-embedding-3-small`, batched).
- Classifier eval on a held-out split (`n_calib=1552`, **`n_test=1537`**), calibration fit on calib, metrics on test.

| Metric | Result | Target | |
|--------|--------|--------|--|
| Routing macro-F1 | **0.997** | ≥ 0.85 ([NFR-4.2](../REQUIREMENTS.md#nfr-4--correctness--calibration)) | ✓ |
| Accuracy | 0.997 | — | |
| ECE (calibrated) | **0.0008** | ≤ 0.05 ([NFR-4.1](../REQUIREMENTS.md#nfr-4--correctness--calibration)) | ✓ |
| Cheap-tier false-confidence | **0.0** (n=1525) | low ([FR-8.11](../REQUIREMENTS.md#fr-8--evaluation--observability)) | ✓ |
| Gate split (fast / agent) | **91.3% / 8.7%** | — | |

Ambiguity profile over all 3,089: **9.6% ambiguous** — 7.7% thin-text (238) + 1.9% multi-issue (59).

## Interpretation (honest)

- **The classifier is near-perfect because the task is near-deterministic.** In 311, `complaint_type` almost fixes `agency`, and the cheap kNN essentially recovers that mapping. This is exactly the framing in [README](../README.md#whats-real-vs-simulated-read-this-honestly): the classifier *reproduces* the city's routing — it is not the differentiator. The strong F1/ECE confirm the deterministic spine works; they are **not** evidence the agent is needed.
- **The agent-bound tail is real but modest (~8.7%).** On a borough-year (~150–300k tickets) that's ~13–26k/yr — a genuine population. **But it is dominated by low-confidence single-agency cases, not multi-agency ones.**
- **Genuine multi-agency is thin (< 2%, and inflated).** The 1.9% multi-issue count is an upper bound — the coarse heuristic over-flags "X cracked" patterns (e.g. *"Branch Cracked and Will Fall"* trips tree+structural but is one issue). The true multi-agency rate that the agent's `split` behavior targets is likely **≲ 1%**.

## Decision ([ADR-009](../ADRs.md#adr-009))

**Recommendation: GO, with disclosed amplification of genuine multi-agency cases.**

Rationale:
- A real low-confidence tail (~8.7%) gives the agent a legitimate population to demonstrate value on (resolving uncertain single-agency routing via tool use) — enough for the agent-vs-baseline study ([EVAL-SPEC §5](../EVAL-SPEC.md#5-agent-path-eval--the-headline)).
- The *multi-agency split* behavior — the agent's most distinctive capability — has **too thin** a natural population to evaluate honestly. Per [ADR-009](../ADRs.md#adr-009), **amplify/synthesize multi-agency cases and label them clearly**, keeping a held-out natural slice reported separately.

Alternatives considered:
- **GO on natural data only** — rejected: the multi-agency tail is too thin to measure `split` correctness with any power.
- **NO-GO / rescope (cut the agent)** — rejected: a real low-confidence tail exists, so the agent isn't unjustified; cutting it would discard the project's thesis prematurely.

## Caveats / inputs to revisit

- Bounded 3k sample; a full uncapped 12-month backfill would tighten the tail estimate.
- The multi-issue heuristic needs refinement (false positives on single-issue "cracked" text); the real multi-agency signal should come from the classifier + jurisdiction reasoning (the agent's tools), not the profiler.
- `TOP_COMPLAINT_TYPES` is a curated set; broadening it would change the ambiguity mix.

## To confirm

Reply **GO** (I'll start Phase 3: the triage agent **and** its baseline proof, with amplified+disclosed multi-agency data) or **NO-GO / rescope**.
