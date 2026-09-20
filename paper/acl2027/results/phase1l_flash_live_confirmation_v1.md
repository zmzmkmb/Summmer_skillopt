# Phase 1L: Cost-aware qwen3.6-flash live confirmation

## Decision

The staged Flash confirmation failed the frozen two-task capability floor. Exactly two authorized Token Plan calls were executed in the frozen order with zero retries. Paid permission was closed immediately afterward; `qwen3.7-plus`, `qwen3.8-max`, the OfficeQA 24 / SpreadsheetBench 40 batch, and formal scaling remain unauthorized.

- Model: `qwen3.6-flash`
- Provider attempts: `2/2`
- Network / paid calls: `2 / 2`
- Exact total usage: `4,440` tokens (`1,967` input, `2,473` output)
- Aggregate fingerprint: `b81f5084376c0493ed3defea26c71ad7e8c653c3388484c5c12d461b1bb0e6aa`
- OfficeQA task-valid: failed
- SpreadsheetBench task-valid: failed

## Failure attribution

OfficeQA consumed `2,745` tokens and reached the frozen `1,200` output-token limit. The response was truncated inside an operand string and could not be parsed. The visible prefix already reported `1580` rather than the reference `2602` and mixed annual values with monthly values, so the failure includes temporal/task grounding and answer error in addition to completion truncation.

SpreadsheetBench consumed `1,695` tokens and returned complete JSON with exact 12-cell coverage, syntactically valid formulas, and a persisted workbook. However, all `12/12` formulas mismatched the frozen golden semantics. The formulas counted the number of maxima but omitted the row-specific check that the current person actually holds the maximum, causing the same formula to be repeated for all three people in each column.

## Scientific consequence

This phase selects a model-contract substrate; it does not test copied-global/global-only/contextual priors, sparse-probe representativeness, or accept/reject/abstain deployment. Therefore it neither confirms nor falsifies the paper's main method claims.

It does strengthen a negative engineering conclusion: repaired prompting alone is insufficient to make `qwen3.6-flash` reliable on these two real-task development checks. The real-task method experiment remains blocked. The cost-aware next step is a new zero-network preflight for exactly the same task content under `qwen3.7-plus`, followed by separate authorization for exactly two Plus calls. `qwen3.8-max` remains unnecessary unless later evidence specifically requires it.

If `qwen3.7-plus` also fails the same frozen floor, the experiment should replace or narrow the OfficeQA/SpreadsheetBench route rather than continue escalating model cost. At that point the real-task scope of the ACL claim must be reconsidered, while the current synthetic evidence remains intact.