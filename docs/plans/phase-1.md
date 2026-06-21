# Phase 1 — Ingest + dedup (+ ambiguity profiling)

**Goal (from [ROADMAP](../ROADMAP.md#phase-1)):** real data in, duplicates suppressed, *and the ambiguous-request population profiled* to feed the Phase 2 GO/NO-GO gate.

**Achieves:** clean canonical Brooklyn tickets (12-month backfill + daily-delta path) with embeddings and deterministic dedup links, a labeled dedup eval set with a measured precision, and a profile of how much genuine ambiguity exists — the data needed to decide whether the agent is justified ([PRD R2](../PRD.md#7-risks)). Closes **FR-1**, **FR-2**, and stands up **FR-8.1/8.9/8.14** for dedup; activates the **FR-10.1 / NFR-8.4** PII guardrail (embeddings call an external provider).

**Depends on:** Phase 0 spine. New external prerequisites — `SOCRATA_APP_TOKEN` and `OPENAI_API_KEY` (embeddings are real LLM calls now, unlike Phase 0's offline stubs).

**Exit criteria:** 12-month Brooklyn backfill loaded idempotently; dedup precision meets [NFR-4.2](../REQUIREMENTS.md#nfr-4--correctness--calibration) (≥ 0.90) on the labeled pair set; an ambiguity-population report exists and is ready to drive the [Phase 2 gate](../ROADMAP.md#phase-2).

## Sub-phases (commit-sized checkpoints)

| # | Checkpoint | Achieves | Key files | Acceptance | Commit message |
|---|-----------|----------|-----------|-----------|----------------|
| 1.1 | Socrata SODA client | App-token auth, paging, SoQL filters (borough, complaint-type whitelist, date window), typed records | `ingest/socrata.py`, config | Pulls a bounded page; unit test with mocked HTTP | `feat(ingest): Socrata SODA client with paging + app-token auth` |
| 1.2 | Backfill + delta | 12-month Brooklyn backfill + incremental delta via `created_date` watermark; idempotent upsert (reuse `ingest_record`); top-10 free-text complaint types | `ingest/backfill.py`, `cli.py` (`ingest`) | Backfill loads; re-run adds no duplicate tickets (NFR-3.2) | `feat(ingest): 12-month Brooklyn backfill + incremental delta` |
| 1.3 | PII guardrail | Detect + redact address/name/phone **before** any external embedding call ([FR-10.1](../REQUIREMENTS.md#fr-10--guardrails), [NFR-8.4](../REQUIREMENTS.md#nfr-8--privacy--fairness)) | `guardrails/pii.py` | Redaction unit tests; verified no raw PII reaches embed input | `feat(guardrails): redact PII before external LLM calls` |
| 1.4 | Embeddings + index | Embed redacted descriptor via `LLMClient` EMBED tier; populate `embedding`; pgvector **HNSW** index; batched within the concurrency cap ([NFR-5.4/5.5](../REQUIREMENTS.md#nfr-5--security--safety)) | `dedup/embed.py` | Embeddings populated; ANN neighbor query returns results | `feat(dedup): embeddings + pgvector HNSW index` |
| 1.5 | Dedup linking | Geo + time window + cosine threshold → `duplicate_of` link, `report_count` increment, `DUPLICATE` status; deterministic, never deletes ([ARCHITECTURE §3/§6](../ARCHITECTURE.md#3-components)) | `dedup/link.py` | Known dup pair links to canonical; count increments | `feat(dedup): geo/time + cosine dedup with canonical linking` |
| 1.6 | Dedup eval | Hand-labeled pairs (≥2 annotators, Cohen's κ — [FR-8.14](../REQUIREMENTS.md#fr-8--evaluation--observability)); precision/recall harness; dataset card + frozen split ([FR-8.9](../REQUIREMENTS.md#fr-8--evaluation--observability)) | `eval/dedup_eval.py`, `data/dedup_pairs.jsonl` | Precision ≥ 0.90 ([NFR-4.2](../REQUIREMENTS.md#nfr-4--correctness--calibration)); κ reported | `test(dedup): labeled pair eval set + precision/recall harness` |
| 1.7 | Ambiguity profile | Counts of multi-agency / multi-issue / low-text-confidence candidates over the backfill → report for the Phase 2 gate ([PRD R2](../PRD.md#7-risks)) | `profiling/ambiguity.py`, report output | Report with counts + examples; documented for the gate decision | `feat(profiling): ambiguous-request population profile` |

## Risks / open questions

- **Top-10 complaint-type selection** needs a quick look at the live data to pick types with *genuine free text* (avoid templated/near-empty descriptors, [PRD §5](../PRD.md#4-core-use-cases)) — do this in 1.2 and record the chosen list.
- **Geo distance without PostGIS:** the `pgvector/pgvector:pg16` image has no PostGIS. Plan: bound candidates by a lat/lng bounding box in SQL, then haversine in Python — avoids a new extension. Revisit if volume demands.
- **Dedup threshold** is a tuned parameter; 1.6's harness picks the operating point (precision-first), not a guess.
- **Gate dependency:** 1.7's output is the input to the Phase 2 GO/NO-GO. If ambiguity is thin, that triggers [ADR-009](../ADRs.md#adr-009) (amplify + disclose, or rescope) — decided at the gate, not here.
