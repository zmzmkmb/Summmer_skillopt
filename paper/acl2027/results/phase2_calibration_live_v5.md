# Phase 2 Calibration Live v5

The separately authorized calibration-only run was opened after the independently accepted v4 preflight and all zero-network authorization regressions passed (v5 boundary/handoff 18/18; v4 focused 26/26). The authorization bound qwen3.7-plus, exactly 60 logical calls and maximum attempts, temperature 0, zero retries, no `max_tokens`, and CNY 0.50 stage and cumulative ceilings.

Execution terminated at the first provider attempt with HTTP 401 Unauthorized. Under the zero-retry and terminal-error contract, no retry was made. The atomic ledger contains one terminal attempt, one unique logical request, unknown usage, zero known tokens, and no computable local cost. The eligibility gate therefore failed as incomplete; no history, probe, held-out, development acquisition, or formal scaling stage was authorized or run. The v5 authorization was closed immediately.

Artifacts: `configs/acl2027/phase2_calibration_live_authorization_v5.json`, `configs/acl2027/phase2_calibration_live_authorization_closed_v5.json`, `artifacts/acl2027_phase2_calibration_live_v5/`.

Aggregate fingerprint remains `17752bb2d26f38e253c91a5f789654dad209eb6c16a1dd68203a942fa354e8d9`.
