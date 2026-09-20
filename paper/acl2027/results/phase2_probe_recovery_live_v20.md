# ACL 2027 Phase 2 v20 probe-recovery live execution report

## Scope and authorization

The separately versioned v20 authorization executed only the exact 112-row v19 probe-recovery schedule.

- Model: `qwen3.7-plus`
- Planned calls and maximum provider attempts: `112`
- Temperature: `0`
- Retries: `0`
- `max_tokens`: absent
- Thinking: disabled
- Response format: JSON object
- Stage and cumulative cost ceilings: CNY `7.50`
- Held-out, later Phase 2 stages, and formal scaling: not authorized

The authorization bound v19 aggregate fingerprint `12582b59aa355f1f0e5c8e1340613edce816a24e7c6d80504087a2114a8a7e4c`, v19 schedule SHA-256 `a30223a0de310b972f052f9a74be7f4552fd71aa6ede66b620e00e8a21b7649a`, v20 zero-network fingerprint `f4707106f4575173095a7afd0a4fe39fcc7c361ee2481b1cd4ca2dcf2470cd6c`, and open authorization SHA-256 `867d1cc58f7ceb965e10af32b6502d0d29602cf245b92a105a98f5ec087c5343`.

## Zero-network gates

The focused v20 mock lifecycle passed `7/7`. A v18/v20 isolation regression passed `14/14`, and the complete cache-free v1-v4/v13-v20/handoff regression passed `135/135`. No network, provider, model, or paid call occurred before the credential-fingerprint-bound authorization opened.

## Execution and accounting

The run completed all `112/112` planned calls and closed automatically.

| Item | Result |
|---|---:|
| Provider attempts | 112 |
| Completed calls | 112 |
| Terminal rows | 0 |
| Unique logical requests | 112 |
| Unique request hashes | 112 |
| Unique provider request IDs | 112 |
| Retries | 0 |
| Duplicates, skipped, out-of-bounds | 0 / 0 / 0 |
| Input tokens | 249,336 |
| Output tokens | 1,137 |
| Total tokens | 250,473 |
| Exact local cost | CNY 0.507768 |
| Minimum request-start spacing | 1.005430 seconds |

All per-call usage and cost values are exact. Ledger and request-start hash chains, exact-prefix recovery, model, temperature, retry, JSON response format, and absent `max_tokens` checks passed. Network/provider/model/paid-call counters were `112/112/112/112`; held-out/later-stage/formal-scaling counters were `0/0/0`.

## Combined probe gate

The frozen analyzer combined `48` reusable completed v18 rows with the `112` completed v20 rows. The result is a unique balanced `160`-row grid with `40` tasks and four conditions per task.

| Condition | Correct | Accuracy |
|---|---:|---:|
| cold | 30/40 | 75.0% |
| copied_global | 27/40 | 67.5% |
| global_only | 27/40 | 67.5% |
| contextual_typed_prior | 28/40 | 70.0% |

The predeclared gate `contextual_typed_prior_accuracy >= global_only_accuracy` passed. The primary difference was `+0.025` (`+2.5` percentage points), with `2` typed wins, `1` typed loss, and `37` ties.

This is frozen probe eligibility evidence. It is not held-out method-effect evidence and does not authorize held-out execution, later stages, or formal scaling.

## Integrity bindings and closure

- Ledger SHA-256: `37dbeece35d7a9972d48d9168c789f0b741639313bfa40baa6b98321bf00b405`
- Request-start ledger SHA-256: `8f543c7e19405047c3bb9048c1ed3ff86771bfb9610dd3dcbd4282aabb89e778`
- Run audit SHA-256: `8a635da2c45a453ff9bb3f58b766934a0a5f028704430287c42c0ade05950f50`
- Probe audit SHA-256: `2ce0e311858bcc22ebd581915b7bb96bfb33092f51e9ff0084255a056e412a96`
- Closed authorization SHA-256: `8578dc65a3c3220ff5b7c0c92a30b577f2f4927f8636c432f67f3dafdf135873`

The v20 authorization is terminally closed. No permission carries forward. The only permissible continuation is zero-network interpretation or a separately versioned preflight followed by fresh explicit authorization. Held-out, later stages, and formal scaling remain forbidden.
