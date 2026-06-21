# Phase 2 — Cascade classifier + routing + calibrated confidence

**Status:** ✅ shipped on `phase-2-cascade-routing` (2.1–2.8). Live gate run done; **GO/NO-GO decision in [phase-2-gate.md](phase-2-gate.md) — recommended GO, awaiting confirmation.** macro-F1 0.997, ECE 0.0008, cheap-tier false-confidence 0.0 on a 1,537-ticket held-out split.

**Goal (from [ROADMAP](../ROADMAP.md#phase-2)):** route the easy majority with a confidence score that *means something*, then decide at the **GO/NO-GO gate** whether a real ambiguous population justifies the agent.

**Achieves:** the cascade classifier (cheap → Groq → OpenAI) producing an agency label + **calibrated** confidence; multi-label/agency detection; the confidence gate (fast vs. agent); discriminative eval vs. 311 labels; and the gate decision. Closes **FR-3**, **FR-3.4**, **FR-4**; stands up **FR-8.1** + **FR-8.11**; enforces **FR-10.3** (enum-constrained output) and **FR-10.5** (malformed-output fallback); meets **NFR-4.1** (ECE ≤ 0.05) and **NFR-4.2** (macro-F1 ≥ 0.85).

**Depends on:** Phase 1 (canonical tickets + embeddings + the PII guardrail). **Requires `OPENAI_API_KEY`** in `.env` for the live cheap-tier embeddings, the OpenAI cascade fallback, and the gate run. The cascade's cheap LLM tier uses Groq (`GROQ_API_KEY`, optional — falls back to OpenAI if unset).

**Bounded-sample decision:** the gate run uses a **~3,000-record** bounded Brooklyn backfill (per your call) — enough to estimate the ambiguous tail without the full-year cost. Scale up later if the gate is marginal.

**Exit criteria:** calibrated classifier with ECE ≤ 0.05 and macro-F1 ≥ 0.85 on a held-out split of the bounded sample; a working confidence gate; a written **GO/NO-GO decision** with the measured ambiguous-tail size.

## Sub-phases (commit-sized checkpoints — commit each on completion)

| # | Checkpoint | Achieves | Key files | Acceptance | Commit |
|---|-----------|----------|-----------|-----------|--------|
| 2.1 | Agency taxonomy | Valid agency enum + `complaint_type`→agency ground-truth mapping from 311; the enum that constrains LLM output (FR-10.3) | `classify/taxonomy.py` | enum + mapping; unit tests | `feat(classify): agency taxonomy + 311 label mapping` |
| 2.2 | Cheap tier | Embedding-kNN classifier over existing vectors → agency + raw confidence (vote margin); no LLM | `classify/cheap.py` | kNN predicts + scores; offline tests w/ fixtures | `feat(classify): cheap embedding-kNN tier` |
| 2.3 | LLM cascade | Low-confidence → Groq classify (enum-constrained, PII-redacted) → OpenAI fallback; malformed-output → low-confidence (FR-10.5) | `classify/cascade.py`, `classify/llm_classify.py` | injected fake LLM tests; enum enforced | `feat(classify): Groq→OpenAI cascade with enum-constrained output` |
| 2.4 | Multi-agency detect | Flag tickets spanning ≥2 agencies (reuse 1.7 multi-issue + taxonomy) for the gate | `classify/multilabel.py` | offline tests on known cases | `feat(classify): multi-label / multi-agency detection` |
| 2.5 | Calibration | Platt/isotonic fit on a held-out split: raw conf → calibrated prob; reliability curve + ECE (FR-3.4) | `classify/calibration.py`, `eval/calibration.py` | ECE computed; offline tests on synthetic scores | `feat(classify): confidence calibration + reliability curve` |
| 2.6 | Confidence gate | Threshold on calibrated conf + multi-agency flag → `path=fast\|agent`; `gate_version`; config-tunable (FR-4) | `classify/gate.py` | routes per threshold; offline tests | `feat(routing): calibrated confidence gate` |
| 2.7 | Discriminative eval | Macro-F1 / confusion / ECE vs. 311 labels (FR-8.1) + cheap-tier false-confidence (FR-8.11); `classify-eval` CLI | `eval/classify_eval.py`, `cli.py` | metrics reproducible; offline tests | `test(classify): discriminative eval (F1, ECE) + cheap-tier false-confidence` |
| 2.8 | **GO/NO-GO gate run** | Live: bounded ~3k backfill → embed → classify → calibrate → gate; measure ambiguous-tail size; write the decision | `docs/plans/phase-2-gate.md` | decision doc with `n`, tail size, GO/amplify/rescope | `docs(gate): Phase 2 GO/NO-GO ambiguity gate result` |

## Risks / open questions

- **Live runs need the key.** 2.2–2.8 exercise embeddings + LLM calls; without `OPENAI_API_KEY` they're covered only by offline tests (fakes/fixtures). The 2.8 gate decision needs the live run.
- **Calibration needs enough labeled data.** ECE/Platt on ~3k records with a held-out split should be adequate; if classes are thin per agency, report per-class caveats ([EVAL-SPEC §3](../EVAL-SPEC.md#3-discriminative-eval)).
- **The gate is your decision (2.8).** I'll produce the measured tail size + a recommendation; **GO** (build the agent, Phase 3) vs **NO-GO** ([ADR-009](../ADRs.md#adr-009): amplify+disclose or rescope) is yours to confirm.
- **Cheap-tier false-confidence (FR-8.11)** is the safety-critical metric — a high-confidence wrong cheap-tier call skips the gate. Reported separately.
