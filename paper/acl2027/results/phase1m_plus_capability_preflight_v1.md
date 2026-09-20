# Phase 1M: qwen3.7-plus preflight without client output cap

## Decision

The zero-network Phase 1M preflight passed. Exactly two `qwen3.7-plus` requests were frozen for OfficeQA `UID0001` and SpreadsheetBench `45635`. Both requests preserve the Phase 1K/1L task messages while completely omitting the client-side `max_tokens` field.

- Planned live calls: `2`
- Network calls: `0`
- Paid calls: `0`
- Retries authorized: `0`
- Client output cap: omitted from both requests
- Aggregate fingerprint: `295d239cabab1c6559e7fe1e303a1afa0699c9d415a105238e202c7873c92260`
- Reference-answer leakage: none
- Golden-formula leakage: none

The old Phase 1L requests remain immutable and retain their historical `1200/1400` limits. Phase 1M does not rewrite those results; it corrects the design of the successor comparison.

## Cost and execution boundary

Omitting `max_tokens` does not remove the provider/model context boundary and does not authorize unlimited calls. Cost remains bounded operationally by exactly two logical calls, at most two provider attempts, zero retries, and no batch execution. Exact RMB cost cannot be known before the provider reports usage and billing.

## Scientific consequence

This phase repairs a capability-evaluation confound. A future Plus response can no longer fail merely because the client imposed the Phase 1L output cap. This improves attribution but does not test typed priors, sparse-probe representativeness, or accept/reject/abstain deployment.

The main ACL claim remains partially supported, not established. The next phase requires separate authorization for exactly two `qwen3.7-plus` calls. `qwen3.8-max`, OfficeQA 24, SpreadsheetBench 40, retries, and formal scaling remain closed.