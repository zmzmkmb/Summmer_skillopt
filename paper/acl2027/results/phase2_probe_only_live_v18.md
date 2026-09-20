# ACL 2027 Phase 2 v18 probe-only live execution report

## Scope and authorization

This run used the separately versioned v18 authorization and executed only the accepted v17 replacement probe schedule.

- Model: `qwen3.7-plus`
- Planned calls and maximum provider attempts: `160`
- Temperature: `0`
- Retries: `0`
- `max_tokens`: absent
- Thinking: disabled
- Response format: JSON object
- Stage and cumulative cost ceilings: CNY `7.50`
- Held-out, later Phase 2 stages, and formal scaling: not authorized

The open authorization was bound to:

- v4 aggregate fingerprint: `17752bb2d26f38e253c91a5f789654dad209eb6c16a1dd68203a942fa354e8d9`
- v17 aggregate fingerprint: `68a173ca4e45f58879221ca4c15c9df7bc08dcccae452d496cdb22d9e6cdaa8a`
- v17 manifest SHA-256: `93b7856c3c7dda5a25b062162024cb663c73d15c9d7746cbf90e805c26293d11`
- v17 schedule SHA-256: `207e5d0fd867c045169d67751926755b744bfbe13d223a929c02becfb6762856`
- v18 zero-network preflight fingerprint: `25fb5aa660c0f80cccd94a943c7c00be994a06463ec6e1d5765292de8870df8c`
- v18 open authorization SHA-256: `f10c9cb4d21ae4909734be8937228492462851df6752a865bde80d1654f85ca9`

## Zero-network gates

Before provider execution, the focused v18/v17 suite passed `11/11`, and the complete cache-free v1-v4/v13-v18/handoff suite passed `123/123`. The v4 integrity gate independently recomputed all 16 disk bindings and its aggregate fingerprint. The v17 validation recomputed the 160 unique logical/request identities, replacement-task exclusion, condition semantics, coverage supports `28/32/28/17/16`, and all source/artifact bindings.

No provider, model, network, or paid call occurred before the authorization was opened.

## Execution result

The live runner terminally hard-stopped at provider attempt `50` after the provider returned HTTP 400. Zero retries were made, and the authorization closed automatically.

| Item | Result |
|---|---:|
| Planned calls | 160 |
| Provider attempts | 50 |
| Completed calls | 49 |
| Terminal rows | 1 |
| Unique logical requests | 50 |
| Unique request hashes | 50 |
| Unique completed provider request IDs | 49 |
| Unattempted suffix | 110 |
| Duplicate requests | 0 |
| Skipped indices within attempted prefix | 0 |
| Out-of-bounds requests | 0 |

The attempted prefix was exactly staged indices `1..50`. It contained 13 cold, 13 copied-global, 12 global-only, and 12 contextual-typed-prior attempts. The completed rows contained 13 cold and 12 rows for each other condition. Attempt 50 was:

- Logical request: `phase2-v17:probe:attribute_comparison:49960e10089111ebbd72ac1f6bf848b6:copied_global`
- Task: `49960e10089111ebbd72ac1f6bf848b6`
- Condition: `copied_global`
- Terminal error: `HTTPError: HTTP Error 400: Bad Request`

The provider error body and usage were not returned through the frozen adapter, so the exact HTTP 400 cause, terminal-request tokens, and terminal-request cost are unknown. This terminal transport outcome must not be interpreted as probe method-effect evidence.

## Token and cost audit

All 49 completed rows have exact per-call input/output/total token counts and local costs in `ledger.json`. The terminal row has unknown usage and cost.

- Known input tokens: `98,597`
- Known output tokens: `378`
- Known total tokens: `98,975`
- Known local cost lower bound: CNY `0.200218`
- Exact total cost: unavailable because attempt 50 has unknown usage
- Completed-call input range: `718..2,662`
- Completed-call output range: `5..11`
- Completed-call total range: `725..2,671`
- Completed-call local cost range: CNY `0.001492..0.005396`

The known lower bound remained below both CNY 7.50 ceilings. Closure was caused by the terminal provider error, not the cost ceiling.

## Integrity and eligibility

- Request-start and response ledgers both contain 50 aligned rows.
- Ledger hash chain: valid.
- Request-start hash chain: valid.
- Exact-prefix resume audit: valid, but the terminal row makes the run non-resumable.
- Minimum request-start spacing: `1.0554322` seconds.
- Model, temperature, retries, and `max_tokens` fields: all within the authorization boundary.
- Network/provider/model/paid-call counters: `50/50/50/50`.
- Held-out/later-stage/formal-scaling counters: `0/0/0`.

The probe eligibility gate was not reached because the frozen analyzer requires a complete 160-row ledger. `probe_gate_passed=false` therefore means incomplete/terminal execution, not evidence that contextual typed priors failed against global-only priors.

## Closure and next boundary

The authorization is closed. The 49 completed logical requests and the terminal request are spent and must not be repeated. The remaining 110 requests were not attempted, but this terminal ledger cannot be resumed under v18.

The only permissible next work is a separately versioned zero-network postmortem and recovery preflight that preserves v18 provenance and freezes a non-retry schedule before requesting any new provider authorization. Held-out execution, later Phase 2 stages, formal scaling, and all additional provider calls remain forbidden.
