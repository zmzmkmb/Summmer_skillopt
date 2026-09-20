# Phase 2 Formal History v11

```json
{
  "authorization_closed": true,
  "completed_calls": 32,
  "coverage_passed": false,
  "coverage_status": "not_reached",
  "duplicates": 0,
  "exact_local_cost_cny": null,
  "experiment": "acl2027_phase2_formal_history_v11",
  "formal_scaling_calls": 0,
  "held_out_calls": 0,
  "independent_verified_supports": {
    "attribute_comparison": 0,
    "bridge_attribute_comparison": 0,
    "entity_bridge": 0,
    "fact_retrieval": 0,
    "relation_inference": 0
  },
  "max_tokens_present": false,
  "probe_calls": 0,
  "provider_attempts": 33,
  "request_start_pacing_valid": true,
  "retries": 0,
  "schema_version": 11,
  "status": "terminal_hard_stop",
  "terminal_rows": 1,
  "total_tokens": null
}
```

Probe and held-out remain unauthorized.

An additive partial-prefix verifier audit found 32/32 contract-valid and 28/32 verifier-correct completed `fact_retrieval` responses before the terminal timeout. Those completed calls account for a known lower bound of 37,108 tokens and CNY 0.075602. The terminal attempt returned no usage, so exact total tokens and cost are unknown. The frozen materializer requires all 160 formal-history rows and rejected partial materialization; coverage is incomplete and no candidate, probe, or held-out stage was opened.
