# Phase 1E: Real Cross-Task Triage Protocol Freeze

Date: 2026-08-10

## Status

This phase freezes the protocol for the next real validation; it does not execute model calls. The execution policy remains no-paid, no-network, and formal scaling disabled.

## Frozen scope

- SearchQA is confirmatory-only. The completed Phase 1B held-out answers cannot tune thresholds, prompts, or prior labels.
- OfficeQA is the first new document/tool-oriented task family, using its validation split after authorized payload materialization.
- SpreadsheetBench is the second new tool-use task family, using its validation split after task JSON and spreadsheet files are materialized.
- Prior identity is explicit: `copied-global`, `global-only`, and `contextual`.
- Methods are paired: identity-correct reset, binary proxy gate, three-way triage gate, and frozen MOAR.
- The analysis unit is `task_id:seed:prior_type`, with identical model, prompt, task order, and budget across methods.
- `accept`, `reject`, and `abstain` are deployment actions; `discard` is never emitted by the validation gate.

## Frozen decision gate

The real pilot passes its method gate only if triage reduces harmful deployment on at least one new task family without rejecting nearly all helpful updates and without losing the frozen MOAR quality advantage. If it fails, the paper keeps prior taxonomy plus proxy-to-real mismatch as the main analysis and demotes triage to a safety limitation.

## Audit result

The protocol audit passed all structural checks: three task families, two new task families, SearchQA held-out protection, three-way actions, and no paid/network execution. `payloads_ready` is false because local OfficeQA and SpreadsheetBench files are split manifests rather than complete benchmark payloads.

## Provenance

- Config: `configs/acl2027/phase1e_real_cross_task_triage_protocol_v1.json`
- Audit script: `scripts/validate_acl2027_phase1e_protocol.py`
- Artifact: `artifacts/acl2027_phase1e_real_cross_task_triage_protocol_v1`
- Test: `tests/test_acl2027_phase1e_protocol.py`
- Network calls: 0
- Paid API calls: 0
