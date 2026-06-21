# Design Review — Issues and Recommended Improvements

**Status:** Advisory review; not part of the design contract until its recommendations are accepted and folded into the source-of-truth documents.  
**Reviewed:** 2026-06-21  
**Scope:** [PRD](PRD.md), [ARCHITECTURE](ARCHITECTURE.md), [AI-ARCHITECTURE](AI-ARCHITECTURE.md), [ADRs](ADRs.md), [REQUIREMENTS](REQUIREMENTS.md), [EVAL-SPEC](EVAL-SPEC.md), [OBSERVABILITY](OBSERVABILITY.md), [ROADMAP](ROADMAP.md), and phase plans.

## Overall assessment

The governing idea is strong: deterministic by default, one bounded read-only agent loop, deterministic validation, and a human-controlled side effect. That is a credible portfolio thesis.

The largest risks are not framework choices. They are:

1. whether the public 311 data represents the pre-routing, free-text intake problem the product claims to solve;
2. whether target labels are isolated from model inputs;
3. whether the agent can be evaluated against meaningful and sufficiently strong baselines; and
4. whether the human-in-the-loop design demonstrates reduced human effort rather than merely adding an agent before a mandatory approval.

The agent should remain a **provisional Phase 3 decision**, not a foregone conclusion. The human gate should remain; its two distinct functions need to be specified separately.

## Priority legend

| Priority | Meaning |
|---|---|
| **P0 — decision blocker** | Resolve before the Phase 3 agent implementation or before making the headline claim. |
| **P1 — design correction** | Resolve before the relevant production/demo workflow is considered complete. |
| **P2 — strengthening** | Improves rigor, clarity, or maintainability but does not independently block the MVP. |

## Summary

| ID | Priority | Issue | Recommended disposition |
|---|---|---|---|
| DR-01 | P0 | Public 311 data may not contain the claimed free-text intake signal | Run a data-fitness gate and either find a suitable source, explicitly simulate narratives, or reframe the task. |
| DR-02 | P0 | Prediction inputs and published target labels are not cleanly separated | Define and enforce an inference-safe feature contract and temporal label firewall. |
| DR-03 | P0 | “Escalate all to a human” cannot be beaten on routing correctness as written | Split machine-quality evaluation from an agent-assisted-vs-unaided-human workflow study. |
| DR-04 | P0 | 311 labels cannot establish correct `split` or `escalate` outcomes | Build an adjudicated ambiguous-case gold set with an explicit label rubric. |
| DR-05 | P0 | The non-agent baseline is too weak to prove that a loop earns its place | Add a fixed retrieval-plus-one-shot baseline using the same information and model budget. |
| DR-06 | P0 | “Humans see only uncertainty” conflicts with mandatory review of every draft | Separate manual triage from submission approval and use distinct workload metrics. |
| DR-07 | P0 | Phase 3 requires a human study, but the review harness is deferred to Phase 4 | Bring a minimal blinded review/evaluation harness into Phase 3. |
| DR-08 | P0 | Retrieval can leak future outcomes or held-out labels | Enforce as-of retrieval, duplicate exclusion, and snapshot/version controls. |
| DR-09 | P1 | Full agent traces are not an appropriate default handler explanation | Show structured evidence and uncertainty; reserve sanitized tool traces for audit/debug roles. |
| DR-10 | P1 | Human edit, split, revalidation, and resubmission semantics are incomplete | Specify per-child decisions, revalidation, state transitions, hashes, and reason codes. |
| DR-11 | P1 | LLM-generated due dates are not grounded while SLA logic is deferred | Derive dates deterministically from policy or require human entry; never invent them. |
| DR-12 | P1 | Approval is treated as stronger ground truth than it is | Treat approval as weak implicit feedback; weight edits, rejects, and audited samples more highly. |
| DR-13 | P1 | Global calibration metrics can hide cascade- and gate-specific risk | Calibrate/evaluate by tier and report selective risk-versus-coverage with a declared operating point. |
| DR-14 | P1 | Automatic provider failover can invalidate calibration and eval evidence | Version validation and calibration by provider/model; fail closed when the alternate is unvalidated. |
| DR-15 | P1 | Dedup auto-suppression is too consequential for a 0.90 precision target | Use a high-precision auto-link band, a review band, confidence intervals, and evidence-preserving merges. |
| DR-16 | P1 | Required agent guardrails are not clearly scheduled before live agent runs | Move the spend breaker and minimum injection defenses into Phase 3 entry/exit criteria. |
| DR-17 | P1 | Third-party data egress is specified for LLMs but not the simulated Linear sink | Define an explicit per-destination field policy and minimize exact-location disclosure. |
| DR-18 | P2 | Repository and phase-status documentation is stale or internally inconsistent | Update current state and distinguish implementation-complete from validation-complete. |

---

## Detailed findings

### DR-01 — Validate that the source data contains the intake problem

**Priority:** P0 — decision blocker

**Observation.** The PRD centers on ambiguous natural-language reports such as “water pouring from the ceiling and the floor is buckling.” The public NYC 311 dataset does not appear to expose that raw citizen narrative. NYC Open Data defines:

- `complaint_type` as the first level of a problem hierarchy;
- `descriptor` as a problem detail associated with that problem; and
- `descriptor_2` as a third level of detail.

The official dataset description also says it represents only service requests that can be directed to specific agencies. See [NYC Open Data — 311 Service Requests from 2020 to Present](https://data.cityofnewyork.us/Social-Services/311-Service-Requests-from-2010-to-Present/erm2-nwe9/about_data) and the [Socrata API field definitions](https://dev.socrata.com/foundry/data.cityofnewyork.us/erm2-nwe9).

This means the source is primarily a **post-intake, already-taxonomized record**, not clearly the pre-routing utterance the agent is supposed to reason over. It may also systematically omit requests that could not be directed to an agency.

**Pressure test / strongest counterargument.** Controlled descriptors can still contain useful semantics, and some records may expose genuine ambiguity across the hierarchy. The project is also explicitly a portfolio simulation, so amplified examples are allowed.

**Verdict.** The issue survives. Controlled problem labels can support routing reproduction, deduplication, and work-order generation, but they do not by themselves validate a claim about reasoning over raw ambiguous intake. Synthetic amplification would be simulating the **input modality**, not merely increasing the frequency of a naturally observed tail; that distinction must be disclosed.

**Recommended fix.** Add a data-fitness gate before the agent GO/NO-GO decision:

1. inventory the exact fields and distinct-value distributions used as model inputs;
2. manually inspect a stratified sample and state whether each field is free-form, controlled vocabulary, post-routing, or outcome-derived;
3. choose one honest path:
   - find a lawful pre-routing narrative source;
   - build a clearly labeled, curated/synthetic intake-narrative set and limit agent claims to that simulation; or
   - reframe the natural-data product as structured 311 routing reproduction and cut the agent if there is no adaptive decision to make;
4. update “what is real vs. simulated” to name the input simulation explicitly if that path is chosen.

**Affected docs:** `README.md`, `PRD.md`, `ADRs.md` (ADR-006/009), `EVAL-SPEC.md`, `ROADMAP.md`, and the Phase 2 gate report.

### DR-02 — Establish a target-leakage firewall

**Priority:** P0 — decision blocker

**Observation.** The source row already contains `agency`, `complaint_type`, `descriptor`, due dates, status, and resolution fields. The architecture retains published labels in the canonical ticket while also predicting agency and complaint type. Depending on the intended task, `complaint_type` and even its dependent `descriptor` can be post-routing features. A nearest-neighbor system can also leak through future neighbors or near-duplicate records.

**Pressure test / strongest counterargument.** If the declared task is only “predict agency from an already assigned complaint type,” using complaint type is legitimate and reflects pre-filling downstream routing.

**Verdict.** The issue survives as a task-definition problem. “Agency from an assigned problem code” is a valid but much easier, more deterministic problem than “problem and agency from raw intake language.” The suite currently gestures at both.

**Recommended fix.** Write an explicit inference feature contract:

| Field class | Examples | Prediction access |
|---|---|---|
| Allowed as-of input | approved text/input representation, coarse location, creation time | Allowed |
| Evaluation-only target | agency, target problem/type, adjudicated split/escalate label | Prohibited from prediction code paths |
| Post-outcome | closed date, status changes, resolution description, due date if assigned downstream | Prohibited |

Enforce it with a dedicated typed `InferenceTicket`/feature view rather than passing the canonical record or raw JSON to classifiers and tools. Add tests that fail if target/post-outcome fields enter prompts, embeddings, retrieval features, or model inputs. Pin training/calibration/test and retrieval by time.

**Affected docs:** `ARCHITECTURE.md` data model, `AI-ARCHITECTURE.md` cascade/tool contracts, `EVAL-SPEC.md`, `REQUIREMENTS.md` FR-3/FR-8, and ADR-006.

### DR-03 — Replace the invalid human-baseline decision rule

**Priority:** P0 — decision blocker

**Observation.** Baseline B is “escalate all low-confidence to a human,” but the ship rule requires the lower confidence bound of `agent correctness − Baseline B correctness` to exceed zero.

- If escalation itself is scored, Baseline B emits no route/split prediction, so routing correctness is undefined.
- If the human’s final decision is scored, the human workflow is effectively the reference process and may approach the gold label; expecting the agent proposal to beat it on correctness is incoherent.
- If escalation is counted as automatically correct, Baseline B is 100% correct and cannot be beaten.

**Pressure test / strongest counterargument.** The intended meaning may be “the agent should resolve cases accurately enough to avoid human triage,” with cost and latency reported alongside correctness.

**Verdict.** That is a good product objective, but it needs a multi-objective workflow evaluation rather than a correctness delta against an abstaining baseline.

**Recommended fix.** Split the claim into two studies:

1. **Machine-policy study:** agent vs. classifier and vs. the strong non-agent baseline in DR-05 on adjudicated `route | split | escalate` outcomes. A superiority CI can be used here.
2. **Human-workflow study:** unaided human review vs. agent-assisted human review. Require:
   - final correctness to be non-inferior within a predeclared margin;
   - active handling time or human touches to improve with a 95% CI;
   - override, false-split, and missed-split rates to be reported.

Use randomized, counterbalanced case assignment so reviewers do not see both versions of the same case in immediate sequence. If real intake handlers are unavailable, use proxy reviewers and state that limitation rather than calling the result an operator study.

**Affected docs:** `PRD.md` G2/success metrics/R3, `AI-ARCHITECTURE.md` §5, `REQUIREMENTS.md` FR-5.6/FR-8.7/NFR-4.3/NFR-4.5, `EVAL-SPEC.md` §5, `ROADMAP.md` Phase 3, and `AGENTS.md` non-negotiables.

### DR-04 — Create agent-specific ground truth

**Priority:** P0 — decision blocker

**Observation.** A published 311 agency is useful weak ground truth for ordinary agency reproduction, but a single row does not establish whether the original intake should have been split across agencies or escalated for clarification. Baseline A also cannot be fairly scored on split outcomes if it only emits one label.

**Pressure test / strongest counterargument.** The city’s recorded agency is the best scalable real-world label available, and synthetic cases can be authored with known intended answers.

**Verdict.** Retain 311 labels for the ordinary routing study. Do not reuse them as sufficient gold for the agent study.

**Recommended fix.** Define an ambiguous-case annotation rubric with:

- allowed outcomes: `route(agency)`, `split(set[agency])`, `escalate(reason)`;
- evidence requirements and jurisdiction references;
- over-split and under-split definitions;
- whether multiple answers may be acceptable;
- two independent annotators, adjudication, and agreement reporting;
- separate reporting for natural and synthetic/curated cases.

Use set-based metrics for splits (exact match plus precision/recall or Jaccard), not only binary correctness. Score appropriate abstention separately from incorrect routing.

**Affected docs:** `EVAL-SPEC.md` §2/§5, `REQUIREMENTS.md` FR-8.9/FR-8.14, ADR-006/009, and the Phase 3 plan.

### DR-05 — Add a strong, information-matched non-agent baseline

**Priority:** P0 — decision blocker

**Observation.** A single classifier call is too weak to establish that adaptive looping is responsible for any gain. The agent receives retrieval, jurisdiction, and historical-resolution tools that Baseline A does not.

**Pressure test / strongest counterargument.** The classifier and human baselines bracket the cheapest and most accurate alternatives, and agent cost is already reported.

**Verdict.** They do not isolate the value of agency. A reviewer can reasonably conclude that retrieval or a stronger one-shot prompt—not the loop—caused the improvement.

**Recommended fix.** Add a fixed non-agent baseline:

`parallel retrieval of the same allowed context → one structured LLM decision → deterministic validation`

Match the agent on model family, available information, output schema, and—where practical—token budget. Compare:

- classifier only;
- fixed retrieval + one structured call;
- adaptive agent loop;
- appropriate escalation/human workflow.

Include tool ablations and report the fraction of cases where adaptive tool selection changed the available evidence or final outcome. The agent earns its place only if it beats the fixed workflow enough to justify incremental cost and latency.

**Affected docs:** `AI-ARCHITECTURE.md` §5, ADR-001/004, `EVAL-SPEC.md` §5, `REQUIREMENTS.md` FR-5.6, and `ROADMAP.md` Phase 3.

### DR-06 — Separate manual triage from mandatory approval

**Priority:** P0 — decision blocker

**Observation.** G1 says humans see only genuinely uncertain work, and the success metric says at least 60% is “auto-handled.” Elsewhere, every work order reaches a mandatory approve/edit/reject gate before Linear. Therefore the system avoids some **manual triage**, but it does not auto-handle or auto-submit those tickets.

**Pressure test / strongest counterargument.** The intended distinction may be obvious: easy tickets avoid investigation but still receive a quick safety approval.

**Verdict.** The architecture is reasonable; the product language and metrics are not precise enough.

**Recommended fix.** Name two workflows:

1. **Triage-resolution gate** — only unresolved/ambiguous cases; human decides route/split/escalate.
2. **Submission-approval gate** — every draft; human approves, edits, or rejects the work order.

Replace “auto-handled” with “bypasses manual triage.” Measure agent share, escalation share, active triage minutes, approval minutes, touches per ticket, edit rate, and final submission rate separately. Never use “autonomous” or “straight-through” for a flow that still requires approval.

**Affected docs:** `PRD.md` G1/use cases/success metrics, `ARCHITECTURE.md` flows/state machine, `REQUIREMENTS.md` FR-7, and `OBSERVABILITY.md` metrics.

### DR-07 — Move a minimal human-evaluation harness into Phase 3

**Priority:** P0 — decision blocker

**Observation.** Phase 3 is supposed to compare against human escalation and decide whether the agent survives, but the review UI is scheduled in Phase 4. A human-workflow claim requires an interface, task instructions, timing instrumentation, and reviewers.

**Pressure test / strongest counterargument.** An annotation notebook or simple script could support the study without building the final UI.

**Verdict.** Correct; the full production review UI can remain in Phase 4. The minimal study harness must be an explicit Phase 3 deliverable.

**Recommended fix.** Add a blinded evaluation surface that records assigned condition, active time, final route/split/escalate, edits, and confidence. Freeze the study protocol before examining results. Reuse its interaction findings when building the Phase 4 UI.

**Affected docs:** `ROADMAP.md` Phase 3/4, `EVAL-SPEC.md` §5, and the future Phase 3 plan.

### DR-08 — Make all retrieval temporally valid

**Priority:** P0 — decision blocker

**Observation.** `find_similar_tickets` and `get_historical_resolutions` can expose the held-out ticket’s future, a duplicate of itself, or records resolved after its creation. A time-based train/test split alone does not prevent leakage if the retrieval index contains later records.

**Pressure test / strongest counterargument.** Historical resolved cases are legitimate evidence at real intake time.

**Verdict.** Exactly—only cases that were already available at that time are legitimate.

**Recommended fix.** Require every agent/eval retrieval to enforce:

- `candidate.created_at < subject.created_at`;
- any required resolution was available before `subject.created_at`;
- subject, descendants, and known duplicates are excluded;
- evaluation runs pin a retrieval snapshot/version;
- retrieved fields obey the feature firewall in DR-02.

Add adversarial tests for future-neighbor, self-neighbor, and duplicate leakage.

**Affected docs:** `AI-ARCHITECTURE.md` tool contracts, `ARCHITECTURE.md`, `EVAL-SPEC.md` reproducibility, and `REQUIREMENTS.md` FR-5.1/FR-8.9.

### DR-09 — Replace default “full trace” exposure with evidence-centered explanation

**Priority:** P1 — design correction

**Observation.** The handler is promised a rationale and full agent trace, while `agent_trace` stores a free-form `reflection`. Full execution traces are useful to engineers and auditors but can slow handlers, create automation bias, expose irrelevant model prose, and make the review depend on an explanation that is not itself validated.

**Pressure test / strongest counterargument.** Transparency is a core trust mechanism, and hiding the trace can make the agent feel opaque.

**Verdict.** Transparency should be role-appropriate. Evidence and uncertainty help a handler; raw orchestration details help an engineer.

**Recommended fix.** Default handler view:

- proposed route/split/escalation;
- cited jurisdiction rule and precedent IDs/snippets;
- unresolved questions and missing evidence;
- validator results and warnings;
- original allowed input fields.

Provide a collapsible, access-controlled audit view containing sanitized tool names, arguments, results, timings, and decision codes. Store a concise structured decision summary rather than relying on private/free-form chain-of-thought-style reflection. Test whether explanations increase wrong approvals as well as whether users like them.

**Affected docs:** `PRD.md` persona/use case, `ARCHITECTURE.md` `agent_trace`, `REQUIREMENTS.md` FR-5.3/FR-7.1, and `OBSERVABILITY.md` tracing.

### DR-10 — Specify human edit and split semantics

**Priority:** P1 — design correction

**Observation.** Approve/edit/reject is named, but important state transitions are not: whether split children are reviewed individually, whether a reviewer can merge/delete a proposed child, what happens after agency edits, and whether edited drafts are revalidated and rehashed.

**Pressure test / strongest counterargument.** These are Phase 4 interaction details rather than architecture decisions.

**Verdict.** The visual design can wait. The safety and idempotency semantics belong in requirements before Phase 4 implementation.

**Recommended fix.** Specify that:

- every child in a split has an independent review state;
- reviewers may change route, add/remove a child, or escalate;
- any route/content edit reruns deterministic validation;
- a changed draft receives a new hash while preserving lineage to the previous version;
- submission is idempotent per approved version;
- reject and override reason codes are required, with optional notes;
- conflicting concurrent reviews are rejected or version-checked.

**Affected docs:** `ARCHITECTURE.md` data model/state machine, `REQUIREMENTS.md` FR-7, and `OBSERVABILITY.md` §7.

### DR-11 — Ground due dates deterministically

**Priority:** P1 — design correction

**Observation.** The drafting LLM emits a due date even though the governing principle rejects trusted LLM numbers and the SLA model/policy is deferred. NYC Open Data itself describes due dates as based on complaint type and internal SLAs, which makes the date a policy calculation rather than a prose-generation task.

**Pressure test / strongest counterargument.** The generated date is only a proposal and becomes trusted only after human approval.

**Verdict.** Human review reduces risk, but a date without a grounded policy source invites plausible-looking fabrication and unnecessary reviewer burden.

**Recommended fix.** Compute the date from a versioned agency/complaint policy table. If no policy is available, emit `due_date: null` plus `human_input_required`; do not ask the LLM to invent one. If an LLM extracts a date from retrieved policy text, validate it deterministically against that cited policy before display.

**Affected docs:** `PRD.md` drafting language, `AI-ARCHITECTURE.md` drafting DAG, ADR-008, and `REQUIREMENTS.md` FR-6.2.

### DR-12 — Treat approval as weak feedback, not gold truth

**Priority:** P1 — design correction

**Observation.** The feedback loop treats approval as confirmation of routing and drafting. Approval can also mean “good enough,” time pressure, or automation-biased rubber-stamping.

**Pressure test / strongest counterargument.** At scale, approvals are still useful and much cheaper than independent re-labeling.

**Verdict.** Keep them, but assign evidence strength explicitly.

**Recommended fix.** Use a label hierarchy:

- independently audited/adjudicated outcome — strong;
- explicit edit or reason-coded reject — strong correction signal;
- approval later confirmed by audit/outcome — medium;
- approval alone — weak implicit signal.

Do not put unverified approvals directly into a gold set or calibration refit at equal weight. Audit a random sample and measure wrong-approval rates by path and explanation condition.

**Affected docs:** `OBSERVABILITY.md` §7, `EVAL-SPEC.md` override-derived dataset, and `REQUIREMENTS.md` FR-8.13.

### DR-13 — Evaluate calibration where the cascade actually makes decisions

**Priority:** P1 — design correction

**Observation.** kNN vote fractions, Grok outputs, and OpenAI outputs are different score-generating processes observed on different conditional populations. A single aggregate ECE can look acceptable while the high-confidence early-exit tier or a rare agency remains unsafe. ECE also does not define the acceptable fast-path error rate.

**Pressure test / strongest counterargument.** The suite already calls out cheap-tier false confidence and says to sweep the gate threshold.

**Verdict.** The right concepts are present; the contract needs an explicit operating point and tier-aware protocol.

**Recommended fix.** Report:

- calibration and error by tier, provider/model version, and important class;
- calibration on the conditional population reaching each tier;
- risk-versus-coverage/selective-accuracy curves;
- fast-path error with a confidence interval;
- agent/human load at the chosen threshold;
- a predeclared maximum tolerated fast-path error and any per-class floor.

Fit separate calibrators or a tier-aware meta-calibrator as supported by data. Version the calibrator with the model, prompt, feature set, and gate.

**Affected docs:** ADR-002/007, `AI-ARCHITECTURE.md` §3, `EVAL-SPEC.md` §3, and `REQUIREMENTS.md` NFR-4.1/FR-8.11.

### DR-14 — Make provider failover calibration-safe

**Priority:** P1 — design correction

**Observation.** NFR-3.1 calls for automatic alternate-provider degradation, while the provider-swap regression harness is P2. A score calibrated for one model/prompt/provider is not automatically meaningful for another.

**Pressure test / strongest counterargument.** Provider abstraction is operationally valuable, and queuing every outage weakens availability.

**Verdict.** Keep failover, but only for combinations that have passed tier-specific evaluation and own a valid calibrator/gate version.

**Recommended fix.** Maintain a registry of approved provider/model/prompt/calibrator combinations. On failover:

- use the alternate’s validated configuration; or
- force low confidence and human/queue fallback if it is unvalidated.

Move the minimum provider-swap regression needed for automatic failover to the same priority as failover. Do not describe interface compatibility as behavioral interchangeability.

**Affected docs:** ADR-003, `ARCHITECTURE.md` failure modes, `REQUIREMENTS.md` NFR-3.1/FR-8.15, and `EVAL-SPEC.md` §10.

### DR-15 — Raise the safety bar for automatic dedup suppression

**Priority:** P1 — design correction

**Observation.** Downstream processing operates only on canonical tickets, so a false duplicate can suppress a legitimate work order. A precision threshold of 0.90 permits roughly one false link per ten predicted links at the target boundary, and a few hundred pairs can leave a wide confidence interval. A later report may also contain new severity or hazard evidence that should not disappear into a count.

**Pressure test / strongest counterargument.** Records are linked rather than deleted, and demo-scale dedup is not a life-safety dispatch system.

**Verdict.** Reversibility helps audit and recovery, but it does not prevent an incorrect short circuit in the live pipeline.

**Recommended fix.** Use three bands:

- very-high-confidence auto-link;
- gray-zone link suggestion for review or continued independent processing;
- no-link.

Set the auto-link target substantially above 0.90 based on observed trade-offs, report a lower confidence bound, and preserve all source descriptions/evidence on the canonical cluster. Detect materially different issue/severity content and avoid suppression in those cases.

**Affected docs:** `PRD.md` use case, `ARCHITECTURE.md` dedup flow, `REQUIREMENTS.md` FR-2/NFR-4.2, and `EVAL-SPEC.md` §3.

### DR-16 — Schedule agent guardrails before live agent execution

**Priority:** P1 — design correction

**Observation.** P0 requirements include the spend/concurrency breaker, but the roadmap does not clearly place it before Phase 3 agent runs. Minimum instruction/data separation is P1 even though untrusted ticket/tool text enters the P0 agent.

**Pressure test / strongest counterargument.** Read-only tools, bounded turns, and the human gate sharply limit the blast radius; broader red-team work can reasonably remain P1.

**Verdict.** Keep the full red-team study in P1. Move minimum runtime defenses into the Phase 3 definition of done.

**Recommended fix.** Phase 3 entry/exit criteria should include:

- daily budget and global concurrency enforcement;
- turn and split caps;
- structured arguments/outputs;
- instruction/data delimiting for ticket and tool text;
- malformed-output fallback;
- queue-on-breaker behavior tested under concurrency.

**Affected docs:** `ROADMAP.md` Phase 3, `REQUIREMENTS.md` FR-10.2/FR-10.4, and the future Phase 3 plan.

### DR-17 — Define data egress for every external destination

**Priority:** P1 — design correction

**Observation.** The privacy requirements are explicit for OpenAI/Grok but less explicit for Linear. The public dataset says it does not reveal customer-identifying information, yet it does include incident-location fields. Copying exact locations or raw payload fields into a third-party simulated sink remains a deliberate data-egress decision.

**Pressure test / strongest counterargument.** The data is already public and Linear is a controlled portfolio stand-in.

**Verdict.** Risk is limited, but a clear field policy strengthens the honesty and security story.

**Recommended fix.** Add a destination matrix listing fields allowed for:

- local storage;
- embeddings/classification LLMs;
- agent tools and traces;
- reviewer UI;
- Linear.

Default to data minimization. Use coarse location for semantic routing where possible; send exact operational location to Linear only if necessary for the simulated workflow and explicitly disclosed. Ensure tool results are redacted before prompts and telemetry, not only the original ticket.

**Affected docs:** `AI-ARCHITECTURE.md` guardrails, `ARCHITECTURE.md` security, `REQUIREMENTS.md` NFR-8.4, and ADR-005.

### DR-18 — Correct repository and phase-status drift

**Priority:** P2 — strengthening

**Observation.** `AGENTS.md` says the repository is in the design phase with no application code, while Phases 0 and 1 are implemented and Phase 2 is underway. The Phase 1 plan says “shipped” while also stating that the full 12-month run, live dedup validation, and actual GO/NO-GO profile remain incomplete. The Phase 2 plan status can likewise drift behind committed work.

**Pressure test / strongest counterargument.** Implementation status changes frequently, and the design suite is intentionally more stable than project tracking.

**Verdict.** The governing documents need only coarse current status, but “no code” and “shipped with unmet exit criteria” can mislead contributors and reviewers.

**Recommended fix.** Use two status dimensions:

- implementation: planned / in progress / complete;
- validation: pending / partial / complete.

Update `AGENTS.md` and the plan index at phase boundaries. Do not mark a phase shipped when its declared exit criteria are deferred; either finish them or formally revise the criteria with rationale.

**Affected docs:** `AGENTS.md`, `docs/plans/README.md`, `docs/plans/phase-1.md`, and `docs/plans/phase-2.md`.

---

## Recommended revised agent decision

Proceed to the Phase 3 agent only when all of the following are true:

1. **Data fit:** the evaluated input modality is explicitly identified as natural, curated, or synthetic, and the claims match it.
2. **No leakage:** the inference feature contract and as-of retrieval tests pass.
3. **Enough ambiguity:** a credible natural or explicitly simulated ambiguous set exists with adjudicated route/split/escalate labels.
4. **Strong baseline:** the agent beats an information-matched fixed retrieval + one-shot workflow by a meaningful amount, not merely a weak classifier.
5. **Human value:** agent assistance preserves final correctness within a declared non-inferiority margin and reduces measured human effort.
6. **Bounded operation:** spend, concurrency, turn, output, and prompt-injection controls are active before live runs.

If conditions 1–3 fail, cut or reframe the agent. If condition 4 fails, keep the fixed workflow. If condition 5 fails, the agent is an interesting model result but not a useful human-in-the-loop product feature.

## Recommended human-in-the-loop shape

```text
easy/high-confidence ticket
  -> bypass manual triage
  -> deterministic drafting
  -> short submission-approval review

ambiguous ticket
  -> agent proposal or graceful abstention
  -> triage-resolution review with evidence
  -> deterministic drafting/revalidation
  -> submission-approval review
```

The primary product outcome should be **safe reduction in active human handling time**, not elimination of human accountability.

## Suggested implementation order for these recommendations

1. Resolve DR-01 and DR-02 in the Phase 2 gate before interpreting classifier or ambiguity results.
2. Rewrite the Phase 3 eval contract around DR-03 through DR-08.
3. Add DR-13, DR-14, and DR-16 before any live/batch agent run.
4. Carry DR-09 through DR-12 and DR-17 into the Phase 4 human-review design.
5. Tighten dedup under DR-15 and clean project status under DR-18 without blocking the data-fitness decision.


---

## Maintainer disposition (2026-06-22)

Reviewed against the actual repo (docs + implemented code). Calibrated to scope: this is a **measured portfolio artifact**, not a production routing system. Legend: **Accept** (folded into source-of-truth docs / code), **Defer** (Phase 4 / later, noted), **Push back** (scope creep or already-handled; minimal or no change).

| DR | Disposition | Where it landed |
|----|-------------|-----------------|
| DR-01 | Accept (already ~80% done) | [README](README.md) + [PRD](PRD.md) input-modality disclosure; [phase-2-gate](plans/phase-2-gate.md) already is the data-fitness analysis |
| DR-02 | **Accept (P0)** | [ADR-011](ADRs.md#adr-011) feature contract; [FR-3.5](REQUIREMENTS.md#fr-3--classification--routing); Phase-3 entry criteria |
| DR-03 | **Accept** | Baseline B reframed as cost/coverage (not a correctness comparator) in [EVAL-SPEC §5](EVAL-SPEC.md#5-agent-path-eval--the-headline), AI-ARCH §5, NFR-4.3/4.5 |
| DR-04 | Accept (scoped down) | Adjudicated split/escalate gold set + set-based metrics ([FR-8.3b](REQUIREMENTS.md#fr-8--evaluation--observability)); `split` is secondary, small labeled set not a pipeline |
| DR-05 | **Accept (keystone, P0)** | Information-matched **Baseline C** ([EVAL-SPEC §5](EVAL-SPEC.md#5-agent-path-eval--the-headline), AI-ARCH §5, FR-8.3a, FR-5.6); ship gate is (agent − C) |
| DR-06 | Accept | Two named gates + "bypasses manual triage" in [PRD](PRD.md) §5/§6 |
| DR-07 | **Push back** (overblown) → minimal | Full counterbalanced operator study rejected; a *minimal blinded harness* is a Phase-3 deliverable ([FR-8.3c](REQUIREMENTS.md#fr-8--evaluation--observability), [EVAL-SPEC §5a](EVAL-SPEC.md#5a-human-workflow-study-dr-03dr-07)); thesis stays "where an agent earns its place," not "reduced handling time" |
| DR-08 | **Accept (P0)** | As-of retrieval ([FR-5.7](REQUIREMENTS.md#fr-5--intake-triage-agent), [ADR-011](ADRs.md#adr-011)); **fixed the real bug** — `eval/classify_eval.py` now uses a temporal split, not crc32 hash |
| DR-09 | Defer (Phase 4) | Evidence-centered handler view — noted for the Phase-4 review UI |
| DR-10 | Defer (Phase 4) | Edit/split/rehash semantics — to specify before Phase-4 build |
| DR-11 | Accept (already a non-negotiable) | Due dates: governing principle already bans LLM numbers; enforce in the Phase-4 drafting DAG (policy table or `null`+`human_input_required`) |
| DR-12 | Accept | Label-strength hierarchy in [OBSERVABILITY §7](OBSERVABILITY.md#7-human-in-the-loop-feedback-loop) |
| DR-13 | Accept (sentence) | Per-tier calibration + declared max fast-path error in [NFR-4.1](REQUIREMENTS.md#nfr-4--correctness--calibration) |
| DR-14 | Push back (over-scoped) → sentence | Registry machinery dropped; failover-only-if-validated + fail-closed in [ADR-003](ADRs.md#adr-003) consequence + [NFR-3.1](REQUIREMENTS.md#nfr-3--availability--reliability) |
| DR-15 | Accept (de-alarmed) | Three-band dedup + preserve sources ([FR-2.2a](REQUIREMENTS.md#fr-2--deduplication)); "life-safety" framing rejected (it's link-not-delete) |
| DR-16 | **Accept** | Guardrails moved into Phase-3 entry criteria ([ROADMAP](ROADMAP.md#phase-3)) |
| DR-17 | Accept (scoped) | Redact tool results + per-destination egress incl. Linear ([NFR-8.4/8.5](REQUIREMENTS.md#nfr-8--privacy--fairness)) |
| DR-18 | Accept | Two-axis (implementation/validation) status; "no code yet" fixed in [CLAUDE/AGENTS](../AGENTS.md); plan statuses corrected |

**Net:** the four headline-protecting findings (DR-02, DR-05, DR-08, DR-03) are accepted and now bind Phase 3. The production-ops findings (DR-07, DR-14, DR-15) are pushed back or minimized as out-of-scope for a portfolio demo. The single most overblown — DR-07's full human study — was reduced to a minimal Phase-3 harness so it informs the work without moving the thesis's goalposts.
