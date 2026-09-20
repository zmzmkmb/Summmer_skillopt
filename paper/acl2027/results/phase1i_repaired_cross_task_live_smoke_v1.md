# Phase 1I: Authorized repaired cross-task live smoke

## Decision

The repaired two-call smoke failed its task-valid gate. Exactly two Token Plan provider attempts were made in the frozen OfficeQA-then-SpreadsheetBench order, with no SDK or explicit retries. Paid permission was closed immediately after execution, and the OfficeQA 24 / SpreadsheetBench 40 batch remains closed.

## Execution audit

- Model: `qwen3.6-flash`
- Provider attempts: `2/2`
- Network calls: `2`
- Paid API calls: `2`
- Retries: `0`
- Input tokens: `1,978`
- Output tokens: `2,985`
- Total tokens: `4,963`
- Exact usage metadata: available for both calls
- Aggregate fingerprint: `33c4699b2415a5b43f18cf2f7ecd38a8d140ed776a41ea22a0084c890c3c7d09`

The config hash, runner hash, and scientific-results fingerprint all revalidated after execution.

## OfficeQA result

The response was valid JSON and supplied 12 provenance-rich monthly evidence entries. The evidence values sum to the reference answer:

```text
132 + 129 + 143 + 159 + 154 + 153 + 177 + 200 + 219 + 287 + 376 + 473 = 2602
```

However, the model reported `2561` in both the answer and calculation result. The response therefore failed answer correctness independently of any validator detail.

A residual protocol defect was also exposed: the prompt required 12 monthly operands but did not explicitly require each operand to be an object containing `period` and `value`. The model returned 12 numeric operands, while the validator counted only structured period-bearing operands. This caused the period-count check to report zero even though the evidence list contained all 12 periods. The mismatch did not change the final rejection because the arithmetic answer was independently wrong.

## SpreadsheetBench result

The provider used the full `1,800` output-token allowance and the JSON was truncated inside `explanation`, so the response failed parsing. The complete prefix nevertheless contains all 12 requested cell edits.

A diagnostic recovery of that immutable prefix found that all 12 formulas disagree with the golden workbook. The generated formulas compare against a global `B1:D3` maximum, whereas the task requires each output column to rank the three values within that same column. Thus the response would still have failed formula correctness even without truncation.

This result exposes two distinct issues:

- output-budget/schema control was insufficient to guarantee a closed JSON response;
- the model misinterpreted the per-column spreadsheet operation.

## Scientific interpretation

Phase 1I is negative base-task calibration evidence, not a test of the paper's prior-transfer or triage method. No copied-global/global-only/contextual prior comparison and no accept/reject/abstain decision was exercised. Therefore the main scientific claim is neither proved nor directly falsified.

The result does change the experimental plan. Raw `qwen3.6-flash` generation under the current contracts does not provide a reliable task-valid substrate for measuring prior or gate effects. Scaling now would confound method behavior with arithmetic, schema-completion, and spreadsheet-reasoning failures.

The defensible next step is a no-paid Phase 1J calibration:

1. Specify OfficeQA operands as `{period, value}` objects and independently recompute the answer from extracted evidence.
2. Require a short SpreadsheetBench explanation and a compact exact JSON schema so 12 edits fit safely within the output budget.
3. Make the per-column interpretation explicit on development data and test formula persistence and golden agreement locally.
4. Compare whether a stronger available model is required before any paid confirmation.
5. Establish a frozen task-valid floor before running prior-type or triage comparisons.

## Contribution consequence

The overall ACL claim remains **partially supported, not established**. The paper direction does not yet need to change, but the real-task evidence route must add capability calibration. If a repaired/stronger substrate still cannot achieve reliable task validity, OfficeQA and SpreadsheetBench should not be used as primary method evidence and the evaluation suite must be replaced or narrowed.