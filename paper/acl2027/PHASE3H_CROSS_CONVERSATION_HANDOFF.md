# Phase 3H Cross-Conversation Handoff

Updated: 2026-08-17

## Authoritative State

- Phase 3F v2 is complete: 240/240 paid calls, zero retries, CNY 1.543848,
  authorization closed.
- Strict Phase 3F gate: `inconclusive`; fingerprint
  `d797e795ba5d6318cbeb01ce8ff7187949a134679a621a673855b216e3a3d0cc`.
- Boolean-mapping diagnostic: selector specificity improves, but answer
  mediation remains below threshold; fingerprint
  `96e6678979361ed7b840bc0b1e80ac4ddbf1b19bb49ede377a3379b224d0b4`.
- Phase 3G zero-network audit: operation changes exceed answer changes in both
  families. Report: `paper/acl2027/results/phase3g_answer_grounding_audit_v1.md`.
- All paid, provider, model, later-stage, cross-domain, and formal-scaling
  permissions are closed. Do not retry any existing request.

## Completed Preflight

- Phase 3H v1 was materialized with fingerprint
  `9888dac8cef340a6fee5b09252ad19911d7febae5a4b7cf9dacb2b2df6dc906b`.
  It made zero calls, but its first regression suite contained a false-positive
  substring assertion. Preserve it as unaccepted provenance; do not overwrite it.
- Phase 3H v2 made zero calls and passed its design checks, but its completion
  manifest used `completed_calls=0` and omitted `rows`. Preserve it as
  unaccepted provenance; fingerprint
  `41a5e6f82c5503c09bf380f0489bcc5fef9af8343f4f46ab790c03ee7f956e64`.
- Phase 3H v3 is the accepted completion-schema-corrected preflight. It excludes
  all v1/v2 identities and freezes 40 wholly new tasks, 20 each from attribute and
  bridge-attribute comparison.
- Every v2 task has two distinct preregistered answers and two distinct source
  evidence traces: the dataset answer under the question's direction and the
  other compared entity under the inverse procedure.
- The v2 schedule contains 200 unique proposed requests across cold,
  contextual, forced incompatible-control, and reversed dual conditions.
- Task, logical-call, and request-hash overlap is zero. All network, provider,
  model, paid, later-stage, cross-domain, and formal-scaling call counts are zero.
- Its completion manifest records `completed_calls=rows=200` frozen design rows
  and `provider_calls_executed=0`.
- Accepted v3 fingerprint:
  `61d55a4c3134c0ccf349aa400d3fd2333376b7e7775c3730a7a1016fc942eafb`.

## Closed Live Preflight

- Phase 3H v4 is a separately versioned, zero-network live-execution preflight
  for the immutable v3 schedule. It binds all 200 canonical requests to the
  Token Plan Beijing endpoint and `qwen3.7-plus`, temperature 0, disabled
  thinking, zero retries, absent `max_tokens`, JSON-object responses, and
  one-second pacing.
- It freezes CNY 3.00 stage and CNY 15.00 cumulative ceilings, exact usage and
  hash-chain ledgers, first-failure terminal stop, exact-prefix resume, and
  automatic authorization closure. Its schedule audit confirms 40 tasks, 200
  unique logical IDs, 200 unique request hashes, and 40 rows per condition.
- All network, provider, model, paid, later-stage, cross-domain, and
  formal-scaling counters are zero. No receipt or open authorization exists.
- v4 aggregate fingerprint:
  `9355217fec78e792e421cc12d807ad9846e3f50f84724d6856c0f3bc19aa5e23`.

## Completed Execution

- The exact v4 authorization statement was received and consumed only by Phase
  3H v5. All 200 `qwen3.7-plus` calls completed with zero retries and valid
  one-second request-start pacing; the authorization then closed automatically.
- Exact usage was 425,725 input plus 19,204 output tokens, 444,929 total, at
  CNY 1.005082 exact stage cost and CNY 11.339420 known cumulative cost.
- The frozen answer-grounding gate is `inconclusive`: 40 primary-population
  pairs, contextual target-answer rate 0.825, incompatible-control
  counterfactual-answer rate 0.475, and paired grounding rate 0.425.
- Preserve all v5 ledgers, audit, closure, and analysis. Do not retry or resume
  any spent request. Cross-domain and formal scaling remain closed.

## Next Exact Actions

1. Preserve all Phase 3H versions unchanged; v1 and v2 are unaccepted
   provenance, v3 is the accepted zero-network design, v4 is the closed
   execution preflight, and v5 is a closed completed execution.
2. Do not retry or resume any v5 request, open a new authorization, or send
   additional payloads from a generic continuation request.
3. Continue only paper/report consolidation unless a separately designed
   zero-network phase is accepted and later receives fresh explicit
   authorization. Cross-domain and formal scaling remain closed.

## Required Verification

Use cache-free tests only:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
python -m pytest -p no:cacheprovider tests/test_acl2027_phase3h_counterfactual_answer_sensitivity_live_v5.py tests/test_acl2027_phase3h_counterfactual_answer_sensitivity_live_v5_analysis.py tests/test_acl2027_experiment_handoff.py
python scripts/acl2027_experiment_handoff.py validate
```

The v5 authorization is closed after 200 completed provider calls. The final
cache-free regression status is recorded in `experiment_state.json`.
