# Phase 1N: qwen3.7-plus live confirmation without client output cap

## Decision

Phase 1N completed exactly the two authorized `qwen3.7-plus` Token Plan calls. Both requests completely omitted the client-side `max_tokens` field, the SDK used `max_retries=0`, and no third call or batch expansion occurred. Both provider responses completed with exact usage, but both strict task-valid gates failed.

- Provider attempts: `2`
- Network / paid calls: `2 / 2`
- Explicit and SDK retries: `0 / 0`
- Total usage: `1,967` input + `2,872` output = `4,839` tokens
- Frozen request-plan SHA-256: `295d239cabab1c6559e7fe1e303a1afa0699c9d415a105238e202c7873c92260`
- Aggregate scientific fingerprint: `b98d8961457e990865f2077af07c330550318b5538a53e82349f9a1c1a202d0f`
- Decision: `plus_task_valid_floor_failed_route_review_required`

Paid permission was closed immediately after the two attempts. `qwen3.8-max`, OfficeQA 24, SpreadsheetBench 40, retries, and formal scaling remain unauthorized.

## Per-task audit

### OfficeQA UID0001

The response was complete rather than truncated: it returned exactly 12 evidence items and a validator-eligible calendar trace. The 12 grounded operand values sum to the reference answer `2602`, but the model reported both `answer=2498` and `calculation.result=2498`. Thus grounding and schema passed while arithmetic and final-answer identity failed.

Usage: `1,545` input, `1,552` output, `3,097` total tokens.

### SpreadsheetBench 45635

The response returned all 12 required edits with valid formula syntax and exact cell coverage. Nevertheless, all `12/12` formulas disagreed with the golden semantics. The model compared across rows such as `$B$1:$D$1` instead of comparing the three people within each output column such as `B$1:B$3`, despite the explicit same-column instruction.

Usage: `422` input, `1,320` output, `1,742` total tokens.

## Scientific consequence

Removing the client output cap repaired the Phase 1L attribution confound: neither Phase 1N failure can be explained by client-side truncation. Plus improved completeness and OfficeQA grounding, but it still failed deterministic arithmetic and spreadsheet semantics. The current OfficeQA/SpreadsheetBench route therefore remains unsuitable as the formal substrate without additional task-system design.

This phase does not test copied-global/global-only/contextual priors, sparse-probe representativeness, or accept/reject/abstain deployment. It supplies motivating evidence that complete, plausible outputs can still require validators and abstention, but the ACL main claim remains partially supported rather than established.

The next step should be a zero-network route adjudication: assess deterministic recomputation for OfficeQA and either constrained formula synthesis or replacement/narrowing for SpreadsheetBench. Automatic escalation to `qwen3.8-max` is not justified by this result.
