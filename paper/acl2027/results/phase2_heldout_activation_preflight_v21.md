# Phase 2 v21 Held-out Activation Preflight

This artifact is a zero-network activation preflight only. It does not contain
held-out model outputs and it does not open provider permission.

## Frozen design

- Stage 6 uses the frozen `data/searchqa_phase2_verified/held_out.json` payload:
  80 unique SearchQA tasks, 16 per skill family.
- Each task has four separately called, model-visible conditions: `cold`,
  `copied_global`, `global_only`, and `contextual_typed_prior`.
- The resulting schedule has exactly 320 new logical requests and request
  hashes, with a new `phase2-v21:held_out:*` namespace and exact indices 1..320.
- The route is fixed to `qwen3.7-plus`, temperature 0, zero retries,
  `enable_thinking=false`, JSON-object responses, and no `max_tokens` field.

## Evidence boundary

The priors are copied from the accepted v17 verifier-confirmed formal-history
bundle. No probe or held-out gold answer is used to construct a prior. History,
probe, and held-out task IDs are pairwise disjoint. The passed v20 probe gate is
bound as eligibility evidence only; it is not treated as held-out method-effect
evidence.

The held-out primary contrast is the paired `contextual_typed_prior` minus
`global_only` margin on the same task IDs. The frozen Phase 1T numerical rules
are carried forward without post-held-out tuning: positive requires margin at
least 0.125, at least three helpful pairs, and no harmful pairs; negative is
margin at most -0.125 or at least two harmful pairs; otherwise the result is
inconclusive. Coverage alone cannot change the conclusion.

## Integrity and authorization

The preflight binds v4 aggregate fingerprint
`17752bb2d26f38e253c91a5f789654dad209eb6c16a1dd68203a942fa354e8d9`, the
accepted v17/v19 artifacts, and the closed v20 probe audit and zero-network
fingerprint `f4707106f4575173095a7afd0a4fe39fcc7c361ee2481b1cd4ca2dcf2470cd6c`.
The v21 aggregate fingerprint is
`ad438265794ba44e5c401f757e01f547f0bce2dbfb52607e4b8399915834e630`.

All execution switches and counters remain false/zero. A separate authorization
request proposes 320 held-out-only calls with a CNY 3.50 stage ceiling and CNY
7.50 cumulative ceiling, but it remains `awaiting_fresh_explicit_user_authorization`.
It does not inherit v20 and does not authorize calibration, development,
formal history, probe, later stages, or formal scaling.

## Verification

`tests/test_acl2027_phase2_heldout_activation_preflight_v21.py`: 3/3 passed
with `PYTHONDONTWRITEBYTECODE=1` and `-p no:cacheprovider`.

Files:

- `configs/acl2027/phase2_heldout_activation_preflight_v21.json`
- `configs/acl2027/phase2_heldout_only_authorization_request_v21.json`
- `artifacts/acl2027_phase2_heldout_activation_preflight_v21/`
- `scripts/run_acl2027_phase2_heldout_activation_preflight_v21.py`
