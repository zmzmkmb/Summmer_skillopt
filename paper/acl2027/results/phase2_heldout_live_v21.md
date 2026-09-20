# Phase 2 v21 Held-out Live Execution

The exact v21 held-out-only authorization terminally hard-stopped at provider
attempt 234. The provider closed the connection without a response. The first
233 calls completed, the terminal request was not retried, and the authorization
closed immediately.

## Execution audit

- Planned attempts: 320
- Provider attempts / unique logical requests: 234 / 234
- Completed calls: 233
- Terminal rows: 1
- Known input/output/total tokens: 476,180 / 1,775 / 477,955
- Known local cost lower bound: CNY 0.966560
- Exact total cost: unknown because terminal usage is unknown
- Retries, duplicate logical requests, out-of-bounds requests: 0 / 0 / 0
- Model and route: qwen3.7-plus, temperature 0, JSON object, no max_tokens
- Ledger chain, request-start chain, exact-prefix, and pacing: valid
- Calibration, development, formal history, probe, later-stage, and formal
  scaling calls: all zero

## Partial held-out audit

All 233 completed responses satisfied the exact JSON response contract. The
completed prefix contains 58 complete four-condition task grids plus the cold
row of the next task. On the 58 complete grids:

- cold: 12/58
- copied-global: 10/58
- global-only: 10/58
- contextual typed prior: 10/58
- typed minus global-only: 0.0, with 0 wins, 0 losses, and 58 ties

These values are descriptive provenance only. The frozen 320-row held-out gate
was not reached, so this run cannot establish a positive, negative, or
inconclusive full held-out method-effect result. No remaining request may be
resumed under the closed v21 authorization, and the terminal request must never
be retried.

## Files

- `artifacts/acl2027_phase2_heldout_live_v21/ledger.json`
- `artifacts/acl2027_phase2_heldout_live_v21/request_start_ledger.json`
- `artifacts/acl2027_phase2_heldout_live_v21/run_audit.json`
- `artifacts/acl2027_phase2_heldout_live_v21/held_out_partial_audit.json`
- `artifacts/acl2027_phase2_heldout_live_v21/authorization_closure.json`
- `configs/acl2027/phase2_heldout_live_authorization_closed_v21.json`
