# Dataset card — `dedup_pairs.jsonl`

**Purpose:** frozen eval split for the dedup precision/recall harness (FR-2, FR-8.1).
**Version:** v0 (Phase 1).
**Provenance:** **synthetic** — hand-authored pairs modeled on real 311 descriptors,
clearly tagged as synthetic per the honesty rule ([README](../../../docs/README.md#whats-real-vs-simulated-read-this-honestly)).
Replaced/augmented by labeled *real* pairs as the backfill lands (FR-8.13).
**Split:** this file is the **test split** — never used to tune the dedup threshold ([FR-8.9](../../../docs/REQUIREMENTS.md#fr-8--evaluation--observability)).
**Labels:** `label` = ground truth (same underlying report?). `ann1`/`ann2` = two
independent annotators, for Cohen's kappa ([FR-8.14](../../../docs/REQUIREMENTS.md#fr-8--evaluation--observability)).
**Known bias:** synthetic pairs are cleaner than live text (no typos/multilingual);
real pairs will be noisier. Treat v0 precision as an upper bound.
