# Phase 1P: contribution-aligned real-task protocol freeze

## Purpose

Phase 1P froze a zero-network protocol that returns the experiment program to
the paper's three central claims:

1. inherited prior scope must distinguish `copied-global`, `global-only`, and
   `contextual`;
2. sparse validation evidence must be tested for downstream
   representativeness;
3. `accept` / `reject` / `abstain` must retain candidates and be compared with
   destructive gating.

This phase is protocol evidence only. It does not establish a real-task method
effect.

## Frozen design

- Task families: executor-backed OfficeQA and constrained executor-backed
  SpreadsheetBench Cell-Level Manipulation.
- Per family: 8 development tasks and 16 disjoint downstream tasks.
- Probe panels: four representative tasks and four deliberately shifted tasks.
- Conditions: 3 prior identities x 2 probe strata x 2 gate policies x 2 task
  families = 24 design cells.
- Fairness: identical model, prompt template, examples, task order, and call
  allocation; `max_tokens` is omitted in every future condition.
- Accounting: candidate and fallback counterfactual branches must both be
  charged in cumulative token accounting.
- Leakage: OfficeQA references and SpreadsheetBench golden workbooks are
  forbidden during construction and may be used only after persisted output.

The 24 design cells are experimental conditions, not authorization for the
previous OfficeQA 24 / SpreadsheetBench 40 paid batch.

## Audit result

The immutable preflight passed all 22 checks:

- development and held-out identities exist, are unique, and are disjoint;
- both frozen downstream orders exactly cover their 16 held-out tasks;
- all 24 SpreadsheetBench tasks are Cell-Level Manipulation and have one
  initial/golden workbook pair;
- Phase 1O executor-backed route decisions and hashes are present;
- prior identities, probe metrics, three-way retention semantics, destructive
  comparator, and fairness controls are complete;
- reference/golden access is forbidden during construction;
- provider calls: 0;
- paid calls: 0.

Decision:

```text
protocol_frozen_future_execution_closed
```

Aggregate fingerprint:

```text
8f5f87370999567c40e86ad40bac4edca12c15a60261384dd8952c7b40013968
```

## Scientific interpretation

Phase 1P removes protocol ambiguity but does not strengthen the empirical
status of the main claim. The thesis remains partially supported: prior
identity and retention have held-out synthetic evidence, while real-task prior
effects, probe-to-stream representativeness, and triage effectiveness remain
unmeasured.

No paper-direction change is triggered. A change or narrowing is required
before scaling if a future paired run finds any of the following:

- no real-task effect of prior identity;
- representative probes do not improve sign agreement or safety error over
  shifted probes;
- candidate-retaining triage has no safety/usefulness advantage over an
  identity-correct reset or destructive comparator.

## Next step

Phase 1Q should remain zero-network and materialize the exact candidate,
fallback, executor-eligibility, call-count, and worst-case cost matrix for the
24 frozen cells. It must not authorize provider calls or formal scaling.
