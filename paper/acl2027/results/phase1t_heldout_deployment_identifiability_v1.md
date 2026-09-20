# Phase 1T: held-out deployment identifiability redesign

## Purpose

Phase 1T replaced the Phase 1S development-only factorial with a
capability-gated, longitudinal design. The redesign admits a task substrate
only when a frozen no-skill calibration demonstrates enough verified
successes to form reusable historical experience, then separates history,
development probes, held-out deployment, and later recovery windows.

This phase freezes an identifiable protocol. It does not execute a model or
establish a real-task method effect.

## Audit result

The immutable zero-network audit passed all 21 checks:

- the 12-task eligibility gate requires at least 90% contract validity;
- baseline accuracy must be within the inclusive 25%-75% non-floor band;
- at least three successes must span at least three task types;
- no task ID may contribute more than half of the successes;
- an automatic verifier and reusable skill families are mandatory;
- SearchQA requires a fresh gate despite its historical no-skill EM of
  `0.758929`;
- SearchQA streams contain 12 calibration, 120 history, 24 development-probe,
  and 120 held-out downstream identities;
- all 360 Phase 1B spent SearchQA test IDs are excluded from downstream
  selection;
- 2WikiMultiHopQA remains explicitly unmaterialized and was not downloaded;
- accept, reject, abstain, retention, destructive discard, and recovery
  scenarios are numerically distinguishable;
- exact counterfactual accounting charges candidate and fallback branches;
- network calls, provider calls, paid calls, and formal scaling remained zero.

Decision:

```text
design_frozen_execution_closed
```

Config SHA-256:

```text
e6b0136c2e646feff74316d9eeedc9da695ebab0e663d9f5a8f5d7820d5200ef
```

Aggregate fingerprint:

```text
dd5a45d13889c53c8f313946d924987113d2306404f99e93256efa2a5b5c8e81
```

## Frozen decision semantics

The probe comparison is paired candidate exact match minus fresh fallback
exact match over at least eight tasks with at least 90% contract validity.

| Decision | Frozen rule |
|---|---|
| Accept | Mean margin at least `0.125`, at least 3 helpful pairs, and 0 harmful pairs |
| Reject | Mean margin at most `-0.125`, or at least 2 harmful pairs |
| Abstain | Every valid outcome satisfying neither accept nor reject, plus an invalid probe panel |

Under candidate-retaining triage, reject and abstain preserve inactive or
pending candidates. Two later qualifying windows recover a retained candidate
to `candidate_recovered_active`. Under destructive gating, reject and abstain
irreversibly enter `candidate_discarded`. The audit exercised both paths and
confirmed that only the retained candidate recovered.

## Scientific interpretation

Phase 1T resolves the principal identifiability failures exposed by Phase 1S:
too few reusable successes, no held-out deployment stream, metadata-only gate
labels, no numerical decisions, and no longitudinal candidate state. It also
adds an explicit antecedent to the paper claim: inherited experience must
first be verified, reusable, and supported by a capability-qualified
substrate.

No central method claim is strengthened yet. SearchQA is the proven non-floor
anchor but must pass the new frozen calibration. 2WikiMultiHopQA is the
preferred new candidate, with BFCL simple/multiple/non-live retained as the
backup. OfficeQA, SpreadsheetBench, and LiveMathematicianBench remain outside
the primary causal route unless they independently clear the same gate.

## Next step

Phase 1U should remain zero-network and provider-closed. It should materialize
the frozen 12-task SearchQA calibration payload from local data, audit its full
request/verifier contract, and freeze the 2WikiMultiHopQA acquisition and
materialization validator without downloading the dataset. No provider
calibration, `qwen3.8-max`, legacy 24/40 batch, or formal scaling is
authorized.
