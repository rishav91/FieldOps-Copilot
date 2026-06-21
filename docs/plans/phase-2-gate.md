# Phase 2 — GO / NO-GO ambiguity gate (decision)

The hard gate before any agent code ([ROADMAP](../ROADMAP.md#phase-2), [PRD R2](../PRD.md#7-risks)): **does a real population exist that genuinely needs the agent?** This records the measured result and the decision.

**Status: ✅ RECOMMENDED GO — awaiting your confirmation.** Phase 3 must not start until confirmed.

## What the agent is for (the framing that matters)

The agent's job is **not** "detect multi-agency." It is **resolve genuinely uncertain routing by gathering context before deciding.** Two kinds of hard tickets:

1. **Low-confidence single-agency (the bulk)** — vague/garbled descriptors, or disagreeing neighbors, where the cheap classifier isn't sure. The agent looks up similar tickets, historical resolutions, and sub-issues, then commits to *one* agency with confidence — or escalates. **All real data.**
2. **Multi-agency (the minority)** — one report needing ≥2 agencies (e.g. "water from the ceiling **and** the floor is buckling" → DEP + DOB); the agent *splits* it.

The agent earns its place on **both**, but #1 is where most of the value is. Multi-agency split is a *secondary* capability, not the justification — so the decision does **not** lean on it.

## The run (bounded ~10k sample)

- Ingested **10,155** Brooklyn tickets (12-month window, top-10 complaint types); ~10,071 embedded (OpenAI `text-embedding-3-small`, batched).
- Classifier eval on a held-out split (`n_calib≈1996`, **`n_test=2004`**); calibration fit on calib, metrics on test.

| Metric | Result | Target | |
|--------|--------|--------|--|
| Routing macro-F1 | **0.997** | ≥ 0.85 ([NFR-4.2](../REQUIREMENTS.md#nfr-4--correctness--calibration)) | ✓ |
| Accuracy | 0.998 | — | |
| ECE (calibrated) | **0.005** | ≤ 0.05 ([NFR-4.1](../REQUIREMENTS.md#nfr-4--correctness--calibration)) | ✓ |
| Cheap-tier false-confidence | **0.0** (n=1949) | low ([FR-8.11](../REQUIREMENTS.md#fr-8--evaluation--observability)) | ✓ |
| Gate split (fast / agent) | **89.6% / 10.4%** | — | |

Ambiguity profile over all 10,155: **8.4% ambiguous** — 6.7% thin-text (679) + 1.7% multi-issue (172).

## Interpretation (honest)

- **The classifier is near-perfect because the task is near-deterministic.** In 311, `complaint_type` almost fixes `agency`, and the cheap kNN recovers that. Per [README](../README.md#whats-real-vs-simulated-read-this-honestly), the classifier *reproduces* the city's routing — it is **not** the differentiator. Strong F1/ECE confirm the deterministic spine; they are not evidence the agent is needed.
- **The agent-bound tail is real and sufficient: ~10% ≈ ~1,000 tickets.** That's a genuine population to build and evaluate the agent on — no synthetic data required. On a borough-year (~150–300k) this is ~15–30k/yr.
- **Multi-agency is thin (≲2%, inflated) — and that's fine.** The 1.7% multi-issue is an upper bound; the heuristic over-counts single-issue "X cracked" text (e.g. *"Branch Cracked and Will Fall"*). We don't rely on it.

## Decision ([ADR-009](../ADRs.md#adr-009))

**Recommendation: GO.**

- **Primary agent population = the natural low-confidence tail (~1,000 real tickets).** This is enough for an honest agent-vs-baseline study ([EVAL-SPEC §5](../EVAL-SPEC.md#5-agent-path-eval--the-headline)) with real `n` and CIs — **no amplification needed.**
- **Multi-agency split = secondary capability.** Evaluate it on whatever natural multi-agency cases exist; **optionally** add a *small, clearly-labeled* synthetic set **only** to cover split-correctness, reported separately ([ADR-009](../ADRs.md#adr-009)). Not load-bearing for the GO.

This reverses the earlier draft's emphasis (which leaned on amplified multi-agency). The bigger sample shows the real low-confidence population is large enough on its own.

Alternatives considered:
- **NO-GO / rescope (cut the agent)** — rejected: a real ~1k-ticket low-confidence population exists; the agent isn't unjustified.
- **Lean on amplified multi-agency** — rejected: unnecessary now, and over-relying on synthetic data weakens the result.

## Caveats / inputs to revisit

- Bounded ~10k sample (oldest 12-month slice); a full uncapped backfill would grow the absolute tail further.
- The multi-issue heuristic needs refinement; the genuine multi-agency signal should come from the agent's jurisdiction tools, not the profiler.
- `classify-eval` metrics are from a 2k held-out split; the full-set agent population will be enumerated when Phase 3 builds the agent queue.

## To confirm

Reply **GO** (I'll start Phase 3: the triage agent on the **low-confidence tail**, with multi-agency split as a secondary eval) or **NO-GO / rescope**.
