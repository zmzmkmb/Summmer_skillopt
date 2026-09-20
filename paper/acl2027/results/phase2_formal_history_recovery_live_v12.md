# Phase 2 Formal History Recovery Live v12

```json
{
  "aggregate_fingerprint": "8827222c7d290050969531b7ee6a7c049ac287b0e3098b0ba4f8b15c43b762fe",
  "authorization_closed": true,
  "completed_calls": 128,
  "coverage_passed": false,
  "coverage_status": "not_reached_materialization_hard_stop",
  "duplicate_response_hash_groups": [
    {
      "count": 2,
      "raw_response_sha256": "326009597e11bae22b8c642cacee531082ff17e3f2a8f188fa253f3980a53a10"
    },
    {
      "count": 2,
      "raw_response_sha256": "61cabec8da73d5a8e3755a7bbeba755312bb05f7d55641d9825915ca211a1b89"
    },
    {
      "count": 12,
      "raw_response_sha256": "95e26df6da2bf99f32d09a325499b24f90c945ac79f18adb371c23516d30a59e"
    },
    {
      "count": 2,
      "raw_response_sha256": "a73414c6d83978f8b31c645ecd3f4b4702bc39076c512c7e30d099e35b6b6faf"
    }
  ],
  "duplicates": 0,
  "exact_local_cost_cny": 0.301124,
  "exact_prefix_valid": true,
  "formal_scaling_calls": 0,
  "held_out_calls": 0,
  "independent_verified_supports": {},
  "input_tokens": 145718,
  "ledger_hash_chain_valid": true,
  "max_tokens_present": false,
  "model_calls": 128,
  "model_ids": [
    "qwen3.7-plus"
  ],
  "network_calls": 128,
  "output_tokens": 1211,
  "paid_api_calls": 128,
  "probe_calls": 0,
  "provider_attempts": 128,
  "provider_calls": 128,
  "request_start_pacing_valid": true,
  "retries": 0,
  "schema_version": 12,
  "status": "terminal_hard_stop",
  "temperature": 0,
  "terminal_reason": "duplicate response hash",
  "terminal_rows": 0,
  "total_tokens": 146929,
  "unique_logical_calls": 128
}
```

## Gate Decision

The frozen v12 candidate materializer did not reach the minimum-eight-per-family coverage gate. It terminally rejected four repeated `raw_response_sha256` groups even though the 128 provider response IDs and logical request IDs were unique. The repeated hashes correspond to distinct tasks that returned identical short JSON answers such as `{"answer":"Yes"}`. This is a post-execution materialization hard stop, not a duplicate provider call, and the v12 authorization is closed and non-resumable.

## Non-Gating Diagnostic

A read-only verifier replay that omitted only the frozen duplicate-answer rejection found 160/160 contract-valid combined rows and 121/160 verifier-confirmed successes. Supports were fact retrieval 28/32, attribute comparison 32/32, bridge attribute comparison 28/32, entity bridge 17/32, and relation inference 16/32. These counts would satisfy the numerical coverage threshold, but they are diagnostic only and do not override the frozen v12 gate.

The v12 live ledger records per-call input, output, and total tokens for all 128 calls. Aggregate v12 usage was 145,718 input plus 1,211 output equals 146,929 total tokens, with exact local cost CNY 0.301124 under the CNY 1.64 ceiling.

Probe, held-out, later stages, and formal scaling remain unauthorized.
