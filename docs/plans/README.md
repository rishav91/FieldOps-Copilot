# Implementation plans

One plan per [ROADMAP](../ROADMAP.md) phase, written **before** any code for that phase and reviewed first. A plan states what the phase achieves and breaks it into **commit-sized sub-phases** — each sub-phase is a sensible checkpoint roughly equal to one git commit, with its own acceptance.

These are *implementation* docs (the how-and-in-what-order), distinct from the design suite (the *what* and *why*, which remains the source of truth). A plan never overrides the design docs; if implementation forces a design change, update the design doc in the same change.

Status is tracked on **two axes** (DR-18): **implementation** = planned / in-progress / complete, **validation** = pending / partial / complete (exit criteria actually met). "Complete + partial" means the code is merged but some declared exit criteria are still open.

| Phase | Plan | Implementation | Validation |
|-------|------|----------------|------------|
| 0 | [phase-0.md](phase-0.md) | complete | complete |
| 1 | [phase-1.md](phase-1.md) | complete | **partial** — full 12-mo backfill + live dedup precision still open |
| 2 | [phase-2.md](phase-2.md) · [gate](phase-2-gate.md) | complete | **partial** — GO recommended, not yet confirmed; leakage-firewall + temporal-split fixes pending (DR-02/08) |
| 3 | _not started_ | planned | pending |

## Template

```markdown
# Phase N — <title>

**Goal (from ROADMAP):** one sentence.
**Achieves:** what exists at the end that didn't before; which FR/NFR IDs close.
**Depends on:** prior phases / external prerequisites.
**Exit criteria:** the checkable definition of done for the whole phase.

## Sub-phases (commit-sized checkpoints)

| # | Checkpoint | Achieves | Key files | Acceptance | Commit message |
|---|-----------|----------|-----------|-----------|----------------|
| N.1 | ... | ... | ... | ... | `type(scope): ...` |

## Risks / open questions
- ...
```

Commit messages follow Conventional Commits (`feat`, `fix`, `test`, `docs`, `chore`) and carry **no** `Co-Authored-By` trailer.
