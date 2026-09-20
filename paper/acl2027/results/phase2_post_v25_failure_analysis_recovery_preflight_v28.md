# ACL 2027 Phase 2 v28 failure-analysis recovery preflight

This zero-network preflight preserves 1072 completed v27 rows from 268 complete task grids, excludes all 1073 spent v27 requests, replaces the incomplete terminal task, and freezes 528 new requests. No authorization was opened.

{
  "aggregate_fingerprint": "63f64eb6d3854198c03f0cfdfd0905f803a78ed10d6d4a2d150f351323006640",
  "all_recovery_logical_ids_new": true,
  "all_recovery_request_hashes_new": true,
  "analysis_gate_reached": false,
  "authorization_request_status": "fresh_explicit_user_authorization_required",
  "bindings": {
    "combined_gold_canonical_sha256": "a58d695618f31cfff67c4e1906861a7494464b524c72f5303f4de521643277c5",
    "recovery_schedule_canonical_sha256": "cadb95b6ed8f388998128540004ed179a89f3a05b7e01b48b7e4ae9f4249c0e8",
    "v26_gold_sha256": "fdc0a531772afa435d0845b4f2fade75438da3683c0f0ae83c74dd9e5247c134",
    "v26_manifest_sha256": "d300a32607ee892e3e00579cdb9acb1a3c8580af05a1dbf90a9cf240b14d5292",
    "v26_schedule_sha256": "328afd840a21bebedb0eab956af73c04375e8f124f24cd03b5eaf51dcc4afa53",
    "v27_closure_sha256": "13cc9ec45da8fdb60e893538c671e61565d6c8ae97f14c8ef7721ac0f7bb8951",
    "v27_corrected_audit_sha256": "bbe2040baf08bbad8897f789b3105939e743b35b7b82a244387e6a463da0f738",
    "v27_ledger_sha256": "77bedbb5c09ac9fd865a9924fc82ce6cd2752a05bbf07a7962043304f02d3940",
    "v27_request_start_ledger_sha256": "a2246ba427e682922d9b50acfbc433573ac62f7acc1e388e50b753cfea97785a"
  },
  "combined_analysis_rows": 1600,
  "combined_condition_counts": {
    "cold": 400,
    "contextual_typed_prior": 400,
    "copied_global": 400,
    "global_only": 400
  },
  "combined_task_count": 400,
  "execution": {
    "formal_scaling_allowed": false,
    "network_calls_allowed": false,
    "paid_api_allowed": false,
    "provider_calls_allowed": false,
    "qwen_authorization_open": false
  },
  "experiment": "acl2027_phase2_post_v25_failure_analysis_recovery_preflight_v28",
  "formal_scaling_calls": 0,
  "later_stage_calls": 0,
  "model_calls": 0,
  "network_calls": 0,
  "paid_api_calls": 0,
  "proposed_authorization": {
    "cumulative_cost_ceiling_cny": 8.0,
    "formal_scaling_authorized": false,
    "later_stages_authorized": false,
    "max_provider_attempts": 528,
    "max_tokens_present": false,
    "model_id": "qwen3.7-plus",
    "request_interval_seconds": 1.0,
    "requested_calls": 528,
    "response_format": {
      "type": "json_object"
    },
    "retries": 0,
    "scope": "post_v25_failure_analysis_recovery_only",
    "stage_cost_ceiling_cny": 3.0,
    "status": "fresh_explicit_user_authorization_required",
    "temperature": 0
  },
  "provenance": {
    "excluded_terminal_logical_call_id": "phase2-v26:post_v25_failure_analysis:entity_bridge:7284db480bdd11eba7f7acde48001122:cold",
    "excluded_terminal_task_id": "7284db480bdd11eba7f7acde48001122",
    "replacement_selector_hash": "001756a9d38873e57093059bdc4b84fc5a265e719dc1e0062bf86aea954696e1",
    "replacement_skill_family": "entity_bridge",
    "replacement_task_id": "cd0d76600bdd11eba7f7acde48001122",
    "reusable_completed_rows": 1072,
    "reusable_completed_tasks": 268,
    "unattempted_complete_tasks_carried": 131,
    "v27_attempted_rows": 1073,
    "v27_completed_rows": 1072,
    "v27_terminal_rows": 1
  },
  "provider_calls": 0,
  "recovery_calls": 528,
  "recovery_tasks": 132,
  "schema_version": 28,
  "spent_v27_requests_excluded": 1073,
  "status": "preflight-passed-recovery-plan-closed"
}
