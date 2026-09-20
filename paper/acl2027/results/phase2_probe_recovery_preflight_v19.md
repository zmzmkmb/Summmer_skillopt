# ACL 2027 Phase 2 v19 probe recovery preflight

This was a zero-network recovery preflight. It preserves v18 provenance, excludes all 50 spent v18 requests, and freezes a 112-call replacement plan. No provider authorization was opened.

{
  "aggregate_fingerprint": "12582b59aa355f1f0e5c8e1340613edce816a24e7c6d80504087a2114a8a7e4c",
  "all_recovery_logical_ids_new": true,
  "all_recovery_request_hashes_new": true,
  "authorization_request_status": "fresh_explicit_authorization_required",
  "bindings": {
    "prior_bundles_canonical_sha256": "47a4fc15983e4e4d4faf22ad72f538ea38e5878ae031fec6e1fe1c5ba56be91e",
    "recovery_gold_canonical_sha256": "16192a489bf477711c0e6ab84815a5ae45b487507c5bafbcb557e6f0f27c2a9f",
    "recovery_schedule_canonical_sha256": "4b16ab327f0a15c0c735170cd7ba7b1b935f491233fd42bcdb1e67bd559ec3ee",
    "v17_aggregate_fingerprint": "68a173ca4e45f58879221ca4c15c9df7bc08dcccae452d496cdb22d9e6cdaa8a",
    "v17_config_sha256": "6749c2d72aa4a10f2df20b1efa6bb023c9459bf7e142eaec4f458520e0bb6794",
    "v17_gold_sha256": "e43d8226e675578e0bfa090138af0ed2e87fb646d7f37e9e0b6cba46e17bc781",
    "v17_manifest_sha256": "93b7856c3c7dda5a25b062162024cb663c73d15c9d7746cbf90e805c26293d11",
    "v17_prior_bundles_sha256": "f4de47c538fedf1d28ecba8c07d8f4605f7fff4be1e8e300634c7af273a6d63d",
    "v17_schedule_sha256": "207e5d0fd867c045169d67751926755b744bfbe13d223a929c02becfb6762856",
    "v18_closed_authorization_sha256": "4831a4da13f039b42b6944d686206b3ceb947ad9774cd969703c4e0c83463376",
    "v18_closure_sha256": "4831a4da13f039b42b6944d686206b3ceb947ad9774cd969703c4e0c83463376",
    "v18_ledger_sha256": "07f67c1109297f01888121b13f29abe2e228c9327deea254f560fc5fe59d301d",
    "v18_open_authorization_sha256": "f10c9cb4d21ae4909734be8937228492462851df6752a865bde80d1654f85ca9",
    "v18_request_start_ledger_sha256": "d1ddb24ffaf7cddb6cc8fc2f21be4bf6b5bb1e7587472499b1dcefb253e39815",
    "v18_run_audit_sha256": "74d6eebf822fefc2dc5efd4a0f8cff1d8d572c5bbe7ca3193bea10d33c62e379",
    "v4_aggregate_fingerprint": "17752bb2d26f38e253c91a5f789654dad209eb6c16a1dd68203a942fa354e8d9",
    "v4_manifest_sha256": "19108e7ed5837bbd199a1d36bfb78886b4998a8da72337a9ea5e439562ec35c7"
  },
  "combined_analysis_rows": 160,
  "combined_condition_counts": {
    "cold": 40,
    "contextual_typed_prior": 40,
    "copied_global": 40,
    "global_only": 40
  },
  "combined_task_count": 40,
  "coverage_gate_preserved": true,
  "execution": {
    "formal_scaling_allowed": false,
    "network_calls_allowed": false,
    "paid_api_allowed": false,
    "provider_calls_allowed": false,
    "qwen_authorization_open": false
  },
  "experiment": "acl2027_phase2_probe_recovery_preflight_v19",
  "formal_scaling_calls": 0,
  "held_out_calls": 0,
  "held_out_gold_used_for_priors": false,
  "later_stage_calls": 0,
  "model_calls": 0,
  "network_calls": 0,
  "paid_api_calls": 0,
  "private_gold_used_for_priors": false,
  "proposed_authorization": {
    "cumulative_cost_ceiling_cny": 7.5,
    "formal_scaling_authorized": false,
    "held_out_authorized": false,
    "later_stages_authorized": false,
    "max_provider_attempts": 112,
    "max_tokens_present": false,
    "model_id": "qwen3.7-plus",
    "requested_calls": 112,
    "response_format": {
      "type": "json_object"
    },
    "retries": 0,
    "scope": "probe_only",
    "stage_cost_ceiling_cny": 7.5,
    "status": "fresh_explicit_authorization_required",
    "temperature": 0
  },
  "provider_calls": 0,
  "recovery_calls": 112,
  "recovery_condition_counts": {
    "cold": 28,
    "contextual_typed_prior": 28,
    "copied_global": 28,
    "global_only": 28
  },
  "replacement_selection": {
    "candidate_pool_size": 2956,
    "replacement_not_in_any_prior_or_v17_probe": true,
    "replacement_payload_hash": "9744939e6c9e3db74a16bab68b2a79db68c1552a3f0ec18f80e3c87243a035bb",
    "replacement_selector_hash": "0013a1010d3099f1fd43b41028995c77836c6fe53c364e1ff5b6313749622683",
    "replacement_source_split": "dev",
    "replacement_task_id": "fac0692508c111ebbd8bac1f6bf848b6",
    "selector": "min SHA256(phase2-v19:probe-recovery-replacement:attribute_comparison:<task_id>)"
  },
  "schema_version": 19,
  "spent_v18_requests_excluded": 50,
  "status": "preflight-passed-recovery-plan",
  "v18_provenance": {
    "carry_forward_rows": 108,
    "excluded_task_ids": [
      "49960e10089111ebbd72ac1f6bf848b6"
    ],
    "orphan_completed_rows": 1,
    "reusable_completed_rows": 48,
    "reusable_task_ids": [
      "0cd00484d33645b0a58f51dfec568995",
      "21bb7f82096c11ebbdafac1f6bf848b6",
      "353217467129452597e5b903092164e5",
      "5deb6bfcdd8c486d9f5f630309968763",
      "5efc135508bb11ebbd88ac1f6bf848b6",
      "6a56c658096811ebbdafac1f6bf848b6",
      "8b1cc801ee384a50a8a2f85d0057be79",
      "8b649492cc804c6badfd043b2122ccba",
      "a50ae9e7cb6a4f1e8dad07a9bbace810",
      "b10f01cf02e04443a3de620e24f5f86c",
      "c240018708a311ebbd7cac1f6bf848b6",
      "ec656d35dc024d7197c664055e09a4cd"
    ],
    "terminal_logical_call_id": "phase2-v17:probe:attribute_comparison:49960e10089111ebbd72ac1f6bf848b6:copied_global",
    "terminal_request_hash": "f287ce0b83f83e6ddc8d97df9851ab53af7705e1ddb7febfbcb0a91a5ba3f300",
    "v18_closure_sha256": "4831a4da13f039b42b6944d686206b3ceb947ad9774cd969703c4e0c83463376",
    "v18_completed_rows": 49,
    "v18_ledger_sha256": "07f67c1109297f01888121b13f29abe2e228c9327deea254f560fc5fe59d301d",
    "v18_request_start_ledger_sha256": "d1ddb24ffaf7cddb6cc8fc2f21be4bf6b5bb1e7587472499b1dcefb253e39815",
    "v18_rows": 50,
    "v18_run_audit_sha256": "74d6eebf822fefc2dc5efd4a0f8cff1d8d572c5bbe7ca3193bea10d33c62e379",
    "v18_terminal_rows": 1,
    "v18_unattempted_rows": 110
  }
}
