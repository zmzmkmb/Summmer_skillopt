# ACL 2027 Current Work Summary

**Snapshot date:** 2026-08-10
**Repository:** `SummerSkillOpt`
**Working title:** *Safe Continual Skill Routing for LLM Agents under Budget and Non-Regression Constraints*

## Executive summary

The repository is an engineering-complete ACL 2027 pilot with a persistent, auditable experiment program. The central research question is whether an agent can retrieve and update typed skill priors from a growing rule library under a prompt-token budget while avoiding regressions on previously learned domains.

The current evidence supports the **measurement, provenance, and offline safety infrastructure** and provides a useful negative result on the first real-task route. It does **not** yet establish the paper's central method-effect claim. The real-task route is currently blocked by task-validity failures in the frozen model substrate, not by an unexamined method comparison.

## What has been completed

### 1. Repository and experiment foundation

- JoS/formal artifacts have been audited offline with per-example output fingerprints; copied and superseded artifacts remain visible as resolved provenance warnings.
- The experiment registry records immutable historical runs with unique run IDs, declared seeds, result fingerprints, and append-only provenance.
- Parsed rules now use content-addressed stable IDs, and outputs preserve both local indices and `selected_rule_ids`.
- A deterministic zero-API scaling suite exists for nested 8/16/32/64-rule libraries. It is a selector-only diagnostic and must not be presented as task accuracy.
- The ACL program has repository-backed handoff, validation, registry, artifact-audit, continual-routing, cross-task protocol, and scaling entrypoints.

### 2. Offline continual-routing evidence (Phase 0H-0N)

The offline work moved from comparator repair to rollout-aware and identity-aware non-regression guards. The strongest frozen candidate passed the held-out oracle and candidate-state immutability gates, with 1/20 adversarial accepts at the allowed safety boundary and 0/40 candidate-state mutations. However, probe-to-stream representativeness and token overhead remain important limitations.

This supports a scoped statement: the repository contains a tested safety/protocol mechanism under explicit synthetic assumptions. It does not support the stronger statement that MOAR or any selector is generally the most accurate or scalable method.

### 3. Real-task route (Phase 1A-1K)

- SearchQA preflight and live pilot plumbing are complete. The 2,448-call pilot had zero 429s and exact accounting; frozen MOAR was strongest, while selective transfer did not clearly beat the reset comparator.
- The three-way accept/reject/abstain triage protocol is frozen and audited. Development-only evidence shows it can eliminate unsafe deployments, but real cross-task evidence is still required.
- Two repaired live smoke calls in Phase 1I failed both task-valid gates: OfficeQA returned the correct 12 evidence values but the wrong calendar sum (2,561 vs. 2,602), while SpreadsheetBench returned truncated output and 12/12 formula mismatches.
- Phase 1J separated retrieval, provenance, operand schema, arithmetic, answer, completion, and formula-semantics failure channels using zero-network replay. Both negative labels were retained.
- Phase 1K froze four fair, leakage-audited requests for `qwen3.6-flash` and `qwen3.8-max`. It passed protocol readiness checks but made no paid calls and provides no model-effect evidence.

## Current state at the 2026-08-10 checkpoint

| Item | State |
|---|---|
| Completed phases | 18 persisted phases, through Phase 1K |
| Immutable run count | 837 |
| Current phase | Phase 1L, paired-model live capability confirmation |
| Paid API calls | Disabled; Phase 1L requires separate authorization for exactly four calls |
| Formal scaling | Disabled |
| OfficeQA 24 / SpreadsheetBench 40 batch | Closed |
| Main ACL claim | Partially supported, not established |
| Immediate blocker | A task-valid model-contract substrate has not yet been demonstrated |

## Scientific interpretation

The current result should be reported conservatively:

1. **Supported:** artifact provenance, deterministic validation, cross-conversation handoff, identity-aware offline guard behavior, and a repaired cross-task evaluation protocol.
2. **Negative/diagnostic:** the initial real-task route did not meet task-validity gates; the failure was localized rather than hidden by post-hoc correction.
3. **Not established:** a real-task Pareto advantage for typed priors, sparse probes, or three-way triage; superiority of MOAR; large-library scaling; or formal cross-model generalization.

The important methodological decision is to keep negative task-valid evidence visible and to stop before an underqualified model contaminates a 24/40 batch or formal scaling result.

## Next actions

1. Review the immutable Phase 1K four-request plan.
2. Obtain explicit authorization for **exactly four** paid Token Plan calls; do not add retries.
3. Execute the four frozen requests in order, with exact usage auditing and immediate permission closure.
4. Apply the predeclared model-selection gate:
   - `qwen3.6-flash` passes both tasks -> retain it;
   - only `qwen3.8-max` passes -> switch substrate;
   - neither passes -> change the task route or narrow the claim scope.
5. Only after a task-valid substrate exists should the project reconsider the OfficeQA 24 / SpreadsheetBench 40 batch and later formal scaling.

## Reproducibility entrypoints

```powershell
python scripts/acl2027_experiment_handoff.py validate
python scripts/acl2027_experiment_handoff.py status
python scripts/acl2027_experiment_handoff.py handoff
```

The detailed chronological log is in [`EXPERIMENT_LOG.md`](EXPERIMENT_LOG.md). The persistent state is [`experiment_state.json`](experiment_state.json); the cross-conversation operating rules are [`CROSS_CONVERSATION_PROTOCOL.md`](CROSS_CONVERSATION_PROTOCOL.md).

## Scope note

This document summarizes the ACL 2027 experiment program from the repository-backed state at the snapshot date. It intentionally does not stage or reinterpret unrelated local modifications outside the ACL program.
