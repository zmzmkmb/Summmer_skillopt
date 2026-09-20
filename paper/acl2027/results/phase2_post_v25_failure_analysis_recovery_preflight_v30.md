# ACL 2027 Phase 2 v30 second recovery preflight

This zero-network preflight preserves 1,380 completed rows from 345 complete task grids, excludes all 1,383 spent v27/v29 requests, replaces the incomplete v29 terminal task, and freezes 220 new requests. No authorization was opened.

{
  "aggregate_fingerprint": "d008dd5fc9cdd765a1dcc3c09da207e983c550a4fe77558da4cfb78f66bae23a",
  "all_recovery_logical_ids_new": true,
  "all_recovery_request_hashes_new": true,
  "analysis_gate_reached": false,
  "authorization_request_status": "fresh_explicit_user_authorization_required",
  "bindings": {
    "combined_gold_canonical_sha256": "1d5a3574b270e6b2734366275831fc03e37432e7f7b4833c8b3eb27e49aa2de2",
    "recovery_schedule_canonical_sha256": "e040721aa84756b2d47fa2ade0f30097a7a168913a85c4666585ec8429d90273",
    "v27_corrected_audit_sha256": "bbe2040baf08bbad8897f789b3105939e743b35b7b82a244387e6a463da0f738",
    "v27_ledger_sha256": "77bedbb5c09ac9fd865a9924fc82ce6cd2752a05bbf07a7962043304f02d3940",
    "v28_gold_sha256": "b8532bb1288710bb3db82fdcadc4b4994a03a5b77f059f2dfc6745c6e9caff50",
    "v28_schedule_sha256": "be7bb2888be1d291074f71f44a04aaa762f8e21a1901c5cddd58ff15c23f9425",
    "v29_closure_sha256": "2128440464a3d0e5b2de75e1f0c8f5cc6d25801f5f94710b8778e142ef39a926",
    "v29_ledger_sha256": "811169fd708a38f0a367a3d01fe35c5f3c9b56d958f7c7c089ef177760702563",
    "v29_request_start_ledger_sha256": "349b8c46093ad8d3fb0ecc8486f4059f62899fd65926d6dba0540c7a18015ef5",
    "v29_run_audit_sha256": "c68475742824ad71cb53f57f07b8bbfd71814ddfb41d4f6182131ceedabb7aaa"
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
  "experiment": "acl2027_phase2_post_v25_failure_analysis_recovery_preflight_v30",
  "formal_scaling_calls": 0,
  "later_stage_calls": 0,
  "model_calls": 0,
  "network_calls": 0,
  "paid_api_calls": 0,
  "proposed_authorization": {
    "cumulative_cost_ceiling_cny": 8.0,
    "formal_scaling_authorized": false,
    "known_cumulative_cost_lower_bound_cny": 6.13433,
    "later_stages_authorized": false,
    "max_provider_attempts": 220,
    "max_tokens_present": false,
    "model_id": "qwen3.7-plus",
    "request_interval_seconds": 1.0,
    "requested_calls": 220,
    "response_format": {
      "type": "json_object"
    },
    "retries": 0,
    "scope": "post_v25_failure_analysis_second_recovery_only",
    "stage_cost_ceiling_cny": 1.5,
    "status": "fresh_explicit_user_authorization_required",
    "temperature": 0
  },
  "provenance": {
    "excluded_terminal_logical_call_id": "phase2-v28:post_v25_failure_analysis_recovery:relation_inference:6aada36a0baf11ebab90acde48001122:copied_global",
    "excluded_terminal_task_id": "6aada36a0baf11ebab90acde48001122",
    "replacement_selector_hash": "00505f19046cc6f58cf60d23c52c780d7166b7a14eb359769cdca0803fdb4439",
    "replacement_skill_family": "relation_inference",
    "replacement_task_id": "60b1ee0c0baf11ebab90acde48001122",
    "unattempted_complete_tasks_carried": 54,
    "v27_attempted_rows": 1073,
    "v27_reusable_completed_rows": 1072,
    "v27_reusable_completed_tasks": 268,
    "v29_attempted_rows": 310,
    "v29_completed_rows": 309,
    "v29_orphan_completed_rows_excluded": 1,
    "v29_reusable_completed_rows": 308,
    "v29_reusable_completed_tasks": 77,
    "v29_terminal_rows": 1
  },
  "provider_calls": 0,
  "recovery_calls": 220,
  "recovery_tasks": 55,
  "schema_version": 30,
  "spent_v27_v29_requests_excluded": 1383,
  "status": "preflight-passed-recovery-plan-closed"
}
