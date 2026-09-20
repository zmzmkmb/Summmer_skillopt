# Phase 1O: zero-network real-task route adjudication

## Decision

Phase 1O completed one immutable, zero-network construct-first audit over the two frozen Phase 1N task failures. Both task families can be retained only with explicit executor backing:

- OfficeQA: `keep_with_deterministic_executor_and_abstain_on_evidence_mismatch`.
- SpreadsheetBench: `redesign_as_constrained_executor_backed_task`.

The run made `0` network calls, `0` paid calls, and `0` provider attempts. It did not use `qwen3.8-max`, launch the OfficeQA 24 / SpreadsheetBench 40 batch, or enable formal scaling.

Aggregate scientific fingerprint: `19af72c409f118dfdbfb9a5a5c8e1d0fee98cb8b9fa9f6d4685afef337d614e9`.

## Construct-first isolation

The constructors and evaluators have separate interfaces and frozen input sets. The OfficeQA constructor received only the Phase 1N response artifact; it did not receive the reference CSV. The SpreadsheetBench constructor received only the initial workbook, target range `B5:E7`, source rows `1:3`, and the natural-language scoring contract; it did not receive the golden workbook. Constructor records and the generated workbook were persisted before either evaluator accessed reference outputs.

The signature leakage audit found no reference or golden parameter in either constructor. All five immutable source hashes matched the configuration.

## Results

### OfficeQA UID0001

The frozen model response contained 12 unique calendar-period operands whose values exactly agreed with the grounded evidence. The deterministic executor summed those operands to `2602`, while preserving the Phase 1N model outputs `answer=2498` and `calculation.result=2498` as failures. Only after the construction was persisted did the evaluator read `officeqa_full.csv`; the recomputed value matched the reference `2602` exactly.

This route is retained conditionally: execute when provenance, time basis, period coverage, and evidence-operand identity pass; otherwise abstain. The model's arithmetic is not trusted as the deployed answer.

### SpreadsheetBench 45635

The constrained constructor generated all 12 formulas by applying the stated per-column tie-sharing rule. For example, `B5` was generated as `=IF(B1=MAX(B$1:B$3),6/COUNTIF(B$1:B$3,MAX(B$1:B$3)),0)`. After the workbook and construction record were persisted, the independent evaluator compared them with the golden workbook and obtained `12/12` exact formula matches with `0` mismatches.

This repairs the execution substrate but narrows the interpretation: the task can measure routing into a verified spreadsheet executor, not unconstrained model formula synthesis.

## Scientific consequence

Phase 1O resolves the immediate task-substrate blockage created by Phase 1N. It also supplies concrete motivation for validation and abstention: complete, well-grounded model output may still contain an unsafe execution error.

It does not test whether `copied-global`, `global-only`, and `contextual` priors differ on real task streams; whether sparse validation predicts downstream safety; or whether non-destructive `accept` / `reject` / `abstain` improves outcomes. The ACL main claim therefore remains partially supported rather than established.

The next phase should be a zero-network contribution-aligned protocol freeze. It should combine both executor-backed task families in a matched stream, pre-register the three prior types, define representative and shifted sparse-probe strata, and compare candidate-retaining triage with destructive gating before any new paid authorization or scaling decision.
